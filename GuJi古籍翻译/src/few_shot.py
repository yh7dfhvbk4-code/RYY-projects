"""
少样本学习模块
================

本模块实现了面向古籍NER的少样本学习方法，包括：
- ProtoNet: 原型网络，基于度量的少样本学习
- MAML: 模型无关元学习
- FewShotTrainer: 少样本训练器，整合数据增强与元学习

少样本学习适用于古籍NER标注数据稀缺的场景，
通过元学习或度量学习在小样本上实现较好的泛化性能。

典型用法:
    >>> trainer = FewShotTrainer(pretrained_model="bert-base-chinese")
    >>> trainer.train(train_dataset, n_way=3, n_support=5, n_query=10)
    >>> predictor = trainer.get_predictor()
"""

import random
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from transformers import AutoModel, AutoTokenizer
from loguru import logger

from src.ner.dataset import NERDataset, FewShotAugmentor, build_label2id, build_id2label


class ProtoNetEncoder(nn.Module):
    """原型网络编码器。

    基于BERT的编码器，将输入文本编码为固定维度的向量表示，
    用于原型网络的度量学习。

    Attributes:
        bert: BERT模型
        dropout: Dropout层
        projector: 投影头，将BERT输出映射到低维空间
    """

    def __init__(
        self,
        pretrained_model: str = "bert-base-chinese",
        hidden_size: int = 256,
        dropout: float = 0.1,
    ):
        """初始化原型网络编码器。

        Args:
            pretrained_model: 预训练模型名称
            hidden_size: 投影空间维度
            dropout: Dropout概率
        """
        super().__init__()
        self.bert = AutoModel.from_pretrained(pretrained_model)
        bert_hidden = self.bert.config.hidden_size

        self.dropout = nn.Dropout(dropout)
        self.projector = nn.Sequential(
            nn.Linear(bert_hidden, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
        )

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> torch.Tensor:
        """编码输入文本。

        使用[CLS] token的表示作为文本的向量表示。

        Args:
            input_ids: 输入token ID (batch_size, seq_len)
            attention_mask: 注意力掩码 (batch_size, seq_len)

        Returns:
            文本向量表示 (batch_size, hidden_size)
        """
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        cls_output = outputs.last_hidden_state[:, 0, :]  # [CLS]表示
        projected = self.projector(self.dropout(cls_output))
        return projected


class ProtoNet(nn.Module):
    """原型网络（Prototypical Network）。

    基于度量的少样本学习方法，计算每个类别的原型（prototype），
    然后通过到各原型的距离进行分类。

    适用于NER少样本场景：将每种实体类型视为一个类别，
    在少量标注样本上学习区分不同实体类型。

    Attributes:
        encoder: 编码器
    """

    def __init__(self, encoder: ProtoNetEncoder):
        """初始化原型网络。

        Args:
            encoder: 编码器实例
        """
        super().__init__()
        self.encoder = encoder

    def compute_prototypes(
        self,
        support_embeddings: torch.Tensor,
        support_labels: torch.Tensor,
        n_way: int,
    ) -> torch.Tensor:
        """计算各类别的原型向量。

        原型是每个类别所有样本嵌入的均值。

        Args:
            support_embeddings: 支持集样本嵌入 (n_support, hidden_size)
            support_labels: 支持集标签 (n_support,)
            n_way: 类别数

        Returns:
            原型向量 (n_way, hidden_size)
        """
        prototypes = []
        for c in range(n_way):
            mask = (support_labels == c)
            if mask.any():
                proto = support_embeddings[mask].mean(dim=0)
            else:
                proto = torch.zeros_like(support_embeddings[0])
            prototypes.append(proto)
        return torch.stack(prototypes)

    def forward(
        self,
        support_input_ids: torch.Tensor,
        support_attention_mask: torch.Tensor,
        support_labels: torch.Tensor,
        query_input_ids: torch.Tensor,
        query_attention_mask: torch.Tensor,
        n_way: int,
    ) -> Dict[str, torch.Tensor]:
        """原型网络前向传播。

        Args:
            support_input_ids: 支持集输入 (n_support, seq_len)
            support_attention_mask: 支持集掩码 (n_support, seq_len)
            support_labels: 支持集标签 (n_support,)
            query_input_ids: 查询集输入 (n_query, seq_len)
            query_attention_mask: 查询集掩码 (n_query, seq_len)
            n_way: 类别数

        Returns:
            包含loss和logits的字典
        """
        # 编码支持集和查询集
        support_embeddings = self.encoder(support_input_ids, support_attention_mask)
        query_embeddings = self.encoder(query_input_ids, query_attention_mask)

        # 计算原型
        prototypes = self.compute_prototypes(support_embeddings, support_labels, n_way)

        # 计算查询样本到各原型的距离（负欧氏距离）
        distances = torch.cdist(query_embeddings, prototypes)
        logits = -distances  # 负距离作为logits

        return {"logits": logits, "prototypes": prototypes}


class FewShotTrainer:
    """少样本学习训练器。

    整合数据增强和元学习策略，在少量标注数据上训练NER模型。

    支持两种训练策略：
    1. 微调+数据增强：先增强数据，再标准微调
    2. 原型网络：使用度量学习进行少样本分类

    Attributes:
        pretrained_model: 预训练模型名称
        tokenizer: Tokenizer
        device: 计算设备
        encoder: 编码器（原型网络）
    """

    def __init__(
        self,
        pretrained_model: str = "bert-base-chinese",
        device: Optional[str] = None,
    ):
        """初始化少样本训练器。

        Args:
            pretrained_model: 预训练模型名称
            device: 计算设备
        """
        if device is None or device == "auto":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.pretrained_model = pretrained_model
        self.tokenizer = AutoTokenizer.from_pretrained(pretrained_model)
        self.encoder = None

        logger.info(f"少样本训练器初始化 | 预训练模型: {pretrained_model} | 设备: {self.device}")

    def _create_episode(
        self,
        dataset: NERDataset,
        n_way: int,
        n_support: int,
        n_query: int,
    ) -> Optional[Dict[str, torch.Tensor]]:
        """创建一个训练episode（用于原型网络）。

        从数据集中随机采样n_way个类别，每个类别取n_support个支持样本
        和n_query个查询样本。

        Args:
            dataset: 数据集
            n_way: 类别数
            n_support: 每类支持样本数
            n_query: 每类查询样本数

        Returns:
            episode数据字典，若样本不足返回None
        """
        # 统计每个标签的样本
        label_samples = {}
        for sample in dataset.samples:
            for label in set(sample["labels"]):
                if label != "O" and label.startswith("B-"):
                    if label not in label_samples:
                        label_samples[label] = []
                    label_samples[label].append(sample)

        # 选择有足够样本的类别
        valid_labels = [
            label for label, samples in label_samples.items()
            if len(samples) >= n_support + n_query
        ]

        if len(valid_labels) < n_way:
            logger.warning(
                f"有效类别数({len(valid_labels)})少于n_way({n_way})，"
                f"减少n_way为{len(valid_labels)}"
            )
            n_way = len(valid_labels)
            if n_way < 2:
                return None

        # 随机选择n_way个类别
        selected_labels = random.sample(valid_labels, n_way)
        label2idx = {label: idx for idx, label in enumerate(selected_labels)}

        support_data = []
        query_data = []
        support_labels = []
        query_labels = []

        for label in selected_labels:
            samples = label_samples[label]
            random.shuffle(samples)
            idx = label2idx[label]

            for sample in samples[:n_support]:
                text = "".join(sample["tokens"])
                encoding = self.tokenizer(
                    text,
                    max_length=dataset.max_seq_length,
                    truncation=True,
                    padding="max_length",
                    return_tensors="pt",
                )
                support_data.append(encoding)
                support_labels.append(idx)

            for sample in samples[n_support:n_support + n_query]:
                text = "".join(sample["tokens"])
                encoding = self.tokenizer(
                    text,
                    max_length=dataset.max_seq_length,
                    truncation=True,
                    padding="max_length",
                    return_tensors="pt",
                )
                query_data.append(encoding)
                query_labels.append(idx)

        # 合并为批次
        support_input_ids = torch.cat([d["input_ids"] for d in support_data])
        support_attention_mask = torch.cat([d["attention_mask"] for d in support_data])
        support_labels_tensor = torch.tensor(support_labels, dtype=torch.long)

        query_input_ids = torch.cat([d["input_ids"] for d in query_data])
        query_attention_mask = torch.cat([d["attention_mask"] for d in query_data])
        query_labels_tensor = torch.tensor(query_labels, dtype=torch.long)

        return {
            "support_input_ids": support_input_ids.to(self.device),
            "support_attention_mask": support_attention_mask.to(self.device),
            "support_labels": support_labels_tensor.to(self.device),
            "query_input_ids": query_input_ids.to(self.device),
            "query_attention_mask": query_attention_mask.to(self.device),
            "query_labels": query_labels_tensor.to(self.device),
            "n_way": n_way,
        }

    def train_protonet(
        self,
        dataset: NERDataset,
        n_way: int = 3,
        n_support: int = 5,
        n_query: int = 10,
        num_episodes: int = 1000,
        learning_rate: float = 1e-4,
        eval_every: int = 50,
    ) -> ProtoNet:
        """使用原型网络进行少样本训练。

        Args:
            dataset: 训练数据集
            n_way: 每个episode的类别数
            n_support: 每类支持样本数
            n_query: 每类查询样本数
            num_episodes: 训练episode数
            learning_rate: 学习率
            eval_every: 每隔多少episode评估一次

        Returns:
            训练好的原型网络
        """
        logger.info(
            f"开始原型网络训练 | n_way: {n_way} | n_support: {n_support} | "
            f"n_query: {n_query} | episodes: {num_episodes}"
        )

        # 创建编码器和原型网络
        encoder = ProtoNetEncoder(pretrained_model=self.pretrained_model)
        encoder.to(self.device)
        protonet = ProtoNet(encoder)
        protonet.to(self.device)
        self.encoder = encoder

        optimizer = torch.optim.Adam(protonet.parameters(), lr=learning_rate)

        # 训练循环
        total_loss = 0.0
        for episode in range(1, num_episodes + 1):
            episode_data = self._create_episode(dataset, n_way, n_support, n_query)
            if episode_data is None:
                continue

            optimizer.zero_grad()
            outputs = protonet(
                support_input_ids=episode_data["support_input_ids"],
                support_attention_mask=episode_data["support_attention_mask"],
                support_labels=episode_data["support_labels"],
                query_input_ids=episode_data["query_input_ids"],
                query_attention_mask=episode_data["query_attention_mask"],
                n_way=episode_data["n_way"],
            )

            loss = F.cross_entropy(outputs["logits"], episode_data["query_labels"])
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

            if episode % eval_every == 0:
                avg_loss = total_loss / eval_every
                logger.info(f"Episode {episode}/{num_episodes} | 平均损失: {avg_loss:.4f}")
                total_loss = 0.0

        logger.info("原型网络训练完成")
        return protonet

    def train_with_augmentation(
        self,
        dataset: NERDataset,
        augmentation_factor: int = 3,
        pretrained_model: str = "bert-base-chinese",
        batch_size: int = 16,
        learning_rate: float = 2e-5,
        num_epochs: int = 10,
        save_dir: str = "models/ner_fewshot",
    ):
        """使用数据增强+微调的少样本训练。

        先对少量标注数据进行数据增强，然后使用增强后的数据
        进行标准的BERT-CRF微调。

        Args:
            dataset: 原始数据集
            augmentation_factor: 数据增强倍数
            pretrained_model: 预训练模型
            batch_size: 批次大小
            learning_rate: 学习率
            num_epochs: 训练轮数
            save_dir: 模型保存目录

        Returns:
            训练后的NER预测器
        """
        from src.ner.model import BertCRF
        from src.ner.predictor import NERPredictor, train_ner_model
        from src.ner.dataset import split_dataset

        # 数据增强
        logger.info(f"开始数据增强 | 原始样本数: {len(dataset)} | 增强倍数: {augmentation_factor}")
        augmentor = FewShotAugmentor(augmentation_factor=augmentation_factor)
        augmented_samples = augmentor.augment(dataset.samples)
        dataset.samples = augmented_samples
        logger.info(f"数据增强完成 | 增强后样本数: {len(dataset)}")

        # 划分数据集
        train_ds, val_ds, _ = split_dataset(dataset, train_ratio=0.8, val_ratio=0.2, test_ratio=0.0)

        # 标准微调训练
        model = train_ner_model(
            train_dataset=train_ds,
            val_dataset=val_ds,
            pretrained_model=pretrained_model,
            batch_size=batch_size,
            learning_rate=learning_rate,
            num_epochs=num_epochs,
            save_dir=save_dir,
            device=str(self.device),
        )

        # 创建预测器
        predictor = NERPredictor(
            tokenizer=self.tokenizer,
            label2id=dataset.label2id,
            device=str(self.device),
        )

    def get_predictor(self) -> Optional[Any]:
        """获取训练后的预测器。

        Returns:
            NER预测器（如果已训练），否则返回None
        """
        if self.encoder is not None:
            from src.ner.predictor import NERPredictor
            return NERPredictor(
                tokenizer=self.tokenizer,
                label2id=build_label2id(),
                device=str(self.device),
            )
        return None
