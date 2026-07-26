"""
古籍实体关系抽取模块
======================

本模块实现了面向古籍文本的实体关系抽取功能，包括：
- RelationExtractor: 基于BERT的关系分类器
- 关系类型定义与映射
- 实体对生成与特征构建
- 远程监督关系抽取

支持的关系类型:
    - 任职: 人物-官职关系
    - 籍贯: 人物-地点关系
    - 事件参与: 人物-事件关系
    - 地点位于: 地点-地点关系
    - 亲属: 人物-人物关系
    - 师承: 人物-人物关系
    - 任职于: 人物-组织关系
    - 发生于: 事件-地点关系
    - 发生于时: 事件-时间关系

典型用法:
    >>> extractor = RelationExtractor()
    >>> entities = [{"text": "屈原", "type": "PER", "start": 0, "end": 2}, ...]
    >>> relations = extractor.extract("屈原者，名平，楚之同姓也。", entities)
"""

import json
import os
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from transformers import AutoModel, AutoTokenizer, BertPreTrainedModel, BertModel
from transformers import get_linear_schedule_with_warmup
from loguru import logger


# 默认关系类型列表
DEFAULT_RELATION_TYPES = [
    "任职", "籍贯", "事件参与", "地点位于",
    "亲属", "师承", "任职于", "发生于", "发生于时",
]

# 关系类型到ID的映射
def build_relation2id(relation_types: Optional[List[str]] = None) -> Dict[str, int]:
    """构建关系类型到ID的映射。

    Args:
        relation_types: 关系类型列表

    Returns:
        关系类型到ID的映射字典，包含"NA"（无关系）类别
    """
    types = relation_types or DEFAULT_RELATION_TYPES
    relation2id = {"NA": 0}
    for i, rel_type in enumerate(types, 1):
        relation2id[rel_type] = i
    return relation2id


@dataclass
class EntityMention:
    """实体提及数据结构。

    Attributes:
        text: 实体文本
        type: 实体类型
        start: 起始位置
        end: 结束位置
        id: 实体唯一标识
    """
    text: str
    type: str
    start: int
    end: int
    id: str = ""

    def to_dict(self) -> Dict:
        return {"text": self.text, "type": self.type,
                "start": self.start, "end": self.end, "id": self.id}


@dataclass
class Relation:
    """关系数据结构。

    Attributes:
        head: 头实体
        tail: 尾实体
        type: 关系类型
        confidence: 置信度
    """
    head: EntityMention
    tail: EntityMention
    type: str
    confidence: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "head": self.head.to_dict(),
            "tail": self.tail.to_dict(),
            "type": self.type,
            "confidence": self.confidence,
        }


@dataclass
class RelationInstance:
    """关系分类实例，用于模型训练和推理。

    Attributes:
        text: 原始文本
        head: 头实体
        tail: 尾实体
        relation: 关系类型（NA表示无关系）
    """
    text: str
    head: EntityMention
    tail: EntityMention
    relation: str = "NA"


class RelationDataset(Dataset):
    """关系抽取数据集。

    将实体对和文本转换为关系分类模型的输入格式。

    Attributes:
        instances: 关系实例列表
        relation2id: 关系类型到ID的映射
        max_seq_length: 最大序列长度
    """

    def __init__(
        self,
        instances: List[RelationInstance],
        relation2id: Optional[Dict[str, int]] = None,
        max_seq_length: int = 256,
    ):
        """初始化关系抽取数据集。

        Args:
            instances: 关系实例列表
            relation2id: 关系类型映射
            max_seq_length: 最大序列长度
        """
        self.instances = instances
        self.relation2id = relation2id or build_relation2id()
        self.max_seq_length = max_seq_length

    def __len__(self) -> int:
        return len(self.instances)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        instance = self.instances[idx]
        label = self.relation2id.get(instance.relation, 0)
        return {
            "text": instance.text,
            "head_text": instance.head.text,
            "head_type": instance.head.type,
            "tail_text": instance.tail.text,
            "tail_type": instance.tail.type,
            "label": label,
        }


class RelationClassificationModel(nn.Module):
    """基于BERT的关系分类模型。

    模型结构:
        1. 使用特殊标记标注实体位置: [E1]...[/E1] [E2]...[/E2]
        2. BERT编码标注后的文本
        3. 提取[CLS]和实体标记的表示
        4. 全连接层进行关系分类

    Attributes:
        bert: BERT模型
        dropout: Dropout层
        classifier: 分类全连接层
    """

    # 实体标记
    HEAD_START = "[E1]"
    HEAD_END = "[/E1]"
    TAIL_START = "[E2]"
    TAIL_END = "[/E2]"

    def __init__(
        self,
        pretrained_model: str = "bert-base-chinese",
        num_relations: int = 10,
        dropout: float = 0.1,
    ):
        """初始化关系分类模型。

        Args:
            pretrained_model: 预训练模型名称
            num_relations: 关系类别数量（含NA）
            dropout: Dropout概率
        """
        super().__init__()

        self.bert = AutoModel.from_pretrained(pretrained_model)
        hidden_size = self.bert.config.hidden_size

        self.dropout = nn.Dropout(dropout)
        # 输入: [CLS] + [E1] + [E2] 的拼接表示
        self.classifier = nn.Sequential(
            nn.Linear(hidden_size * 3, hidden_size),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, num_relations),
        )

        logger.info(
            f"关系分类模型初始化 | 预训练: {pretrained_model} | "
            f"关系数: {num_relations}"
        )

    def _mark_entities(
        self,
        text: str,
        head: EntityMention,
        tail: EntityMention,
    ) -> str:
        """在文本中用特殊标记标注实体位置。

        Args:
            text: 原始文本
            head: 头实体
            tail: 尾实体

        Returns:
            标注后的文本
        """
        # 确保head在tail之前
        if head.start > tail.start:
            head, tail = tail, head

        # 插入实体标记
        marked_text = (
            text[:head.start]
            + self.HEAD_START + text[head.start:head.end] + self.HEAD_END
            + text[head.end:tail.start]
            + self.TAIL_START + text[tail.start:tail.end] + self.TAIL_END
            + text[tail.end:]
        )
        return marked_text

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        e1_mask: Optional[torch.Tensor] = None,
        e2_mask: Optional[torch.Tensor] = None,
        labels: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """模型前向传播。

        Args:
            input_ids: 输入token ID (batch_size, seq_len)
            attention_mask: 注意力掩码 (batch_size, seq_len)
            e1_mask: 头实体标记掩码 (batch_size, seq_len)
            e2_mask: 尾实体标记掩码 (batch_size, seq_len)
            labels: 关系标签 (batch_size,)

        Returns:
            包含loss和logits的字典
        """
        # BERT编码
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        hidden_states = outputs.last_hidden_state

        # 提取[CLS]表示
        cls_output = hidden_states[:, 0, :]

        # 提取实体表示
        if e1_mask is not None and e2_mask is not None:
            # 使用实体标记的平均池化
            e1_output = self._entity_pool(hidden_states, e1_mask)
            e2_output = self._entity_pool(hidden_states, e2_mask)
        else:
            # 回退: 使用位置2和位置3（假设[E1]和[E2]紧跟[CLS]）
            e1_output = hidden_states[:, 1, :]
            e2_output = hidden_states[:, 2, :]

        # 拼接表示
        combined = torch.cat([cls_output, e1_output, e2_output], dim=-1)

        # 分类
        combined = self.dropout(combined)
        logits = self.classifier(combined)

        result = {"logits": logits}

        if labels is not None:
            loss_fct = nn.CrossEntropyLoss()
            loss = loss_fct(logits, labels)
            result["loss"] = loss

        return result

    def _entity_pool(
        self,
        hidden_states: torch.Tensor,
        entity_mask: torch.Tensor,
    ) -> torch.Tensor:
        """实体标记的池化操作。

        对实体标记位置的隐藏状态进行平均池化。

        Args:
            hidden_states: BERT输出 (batch_size, seq_len, hidden_size)
            entity_mask: 实体标记掩码 (batch_size, seq_len)

        Returns:
            池化后的实体表示 (batch_size, hidden_size)
        """
        mask_expanded = entity_mask.unsqueeze(-1).float()
        masked_hidden = hidden_states * mask_expanded
        entity_len = entity_mask.sum(dim=1, keepdim=True).float().clamp(min=1)
        pooled = masked_hidden.sum(dim=1) / entity_len
        return pooled


class RelationExtractor:
    """古籍实体关系抽取器。

    整合实体对生成、关系分类和结果后处理的完整流程。

    Attributes:
        model: 关系分类模型
        tokenizer: Tokenizer
        relation2id: 关系类型映射
        id2relation: ID到关系类型的映射
        device: 计算设备
        threshold: 关系分类阈值
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        pretrained_model: str = "bert-base-chinese",
        relation_types: Optional[List[str]] = None,
        threshold: float = 0.5,
        device: Optional[str] = None,
    ):
        """初始化关系抽取器。

        Args:
            model_path: 模型保存路径
            pretrained_model: 预训练模型名称
            relation_types: 关系类型列表
            threshold: 关系分类阈值
            device: 计算设备
        """
        self.relation_types = relation_types or DEFAULT_RELATION_TYPES
        self.relation2id = build_relation2id(self.relation_types)
        self.id2relation = {v: k for k, v in self.relation2id.items()}
        self.threshold = threshold

        # 设备
        if device is None or device == "auto":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        # 加载Tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(pretrained_model)
        # 添加实体标记
        special_tokens = ["[E1]", "[/E1]", "[E2]", "[/E2]"]
        self.tokenizer.add_special_tokens({"additional_special_tokens": special_tokens})

        # 加载或创建模型
        if model_path and os.path.exists(model_path):
            self._load_model(model_path)
        else:
            self.model = RelationClassificationModel(
                pretrained_model=pretrained_model,
                num_relations=len(self.relation2id),
            )
            self.model.bert.resize_token_embeddings(len(self.tokenizer))

        self.model.to(self.device)
        self.model.eval()

        logger.info(f"关系抽取器初始化完成 | 关系数: {len(self.relation2id)}")

    def _load_model(self, model_path: str):
        """加载已保存的模型。"""
        try:
            state_dict = torch.load(
                os.path.join(model_path, "pytorch_model.bin"),
                map_location=self.device,
                weights_only=True,
            )
            self.model = RelationClassificationModel(
                num_relations=len(self.relation2id),
            )
            self.model.load_state_dict(state_dict, strict=False)
            logger.info(f"关系分类模型加载成功: {model_path}")
        except Exception as e:
            logger.warning(f"模型加载失败: {e}，使用新模型")

    def generate_entity_pairs(
        self,
        entities: List[Dict[str, Any]],
    ) -> List[Tuple[EntityMention, EntityMention]]:
        """生成候选实体对。

        基于实体类型约束，生成可能存在关系的实体对。
        例如：人物-官职、人物-地点等。

        Args:
            entities: 实体列表

        Returns:
            候选实体对列表
        """
        # 关系类型约束：头实体类型 -> 尾实体类型
        type_constraints = {
            "任职": ("PER", "OFF"),
            "籍贯": ("PER", "LOC"),
            "事件参与": ("PER", "EVT"),
            "地点位于": ("LOC", "LOC"),
            "亲属": ("PER", "PER"),
            "师承": ("PER", "PER"),
            "任职于": ("PER", "ORG"),
            "发生于": ("EVT", "LOC"),
            "发生于时": ("EVT", "TIME"),
        }

        # 转换为EntityMention
        mentions = []
        for i, ent in enumerate(entities):
            mention = EntityMention(
                text=ent["text"],
                type=ent["type"],
                start=ent["start"],
                end=ent["end"],
                id=ent.get("id", f"e{i}"),
            )
            mentions.append(mention)

        # 生成候选对
        pairs = []
        valid_tail_types = set()
        for head_type, tail_type in type_constraints.values():
            valid_tail_types.add((head_type, tail_type))

        for i, m1 in enumerate(mentions):
            for j, m2 in enumerate(mentions):
                if i == j:
                    continue
                if (m1.type, m2.type) in valid_tail_types:
                    pairs.append((m1, m2))

        return pairs

    def extract(
        self,
        text: str,
        entities: List[Dict[str, Any]],
    ) -> List[Relation]:
        """从文本中抽取实体间的关系。

        Args:
            text: 输入文本
            entities: 已识别的实体列表

        Returns:
            抽取到的关系列表

        Example:
            >>> extractor = RelationExtractor()
            >>> entities = [
            ...     {"text": "屈原", "type": "PER", "start": 0, "end": 2},
            ...     {"text": "左徒", "type": "OFF", "start": 14, "end": 16},
            ... ]
            >>> relations = extractor.extract("屈原者，名平，楚之同姓也。为楚怀王左徒。", entities)
        """
        if not entities or len(entities) < 2:
            return []

        # 生成候选实体对
        pairs = self.generate_entity_pairs(entities)
        if not pairs:
            return []

        # 对每个实体对进行关系分类
        relations = []
        for head, tail in pairs:
            relation_type, confidence = self._classify_relation(text, head, tail)

            if relation_type != "NA" and confidence >= self.threshold:
                rel = Relation(
                    head=head,
                    tail=tail,
                    type=relation_type,
                    confidence=confidence,
                )
                relations.append(rel)

        logger.debug(f"抽取到 {len(relations)} 个关系")
        return relations

    def _classify_relation(
        self,
        text: str,
        head: EntityMention,
        tail: EntityMention,
    ) -> Tuple[str, float]:
        """对单个实体对进行关系分类。

        Args:
            text: 原始文本
            head: 头实体
            tail: 尾实体

        Returns:
            (关系类型, 置信度) 元组
        """
        # 标注实体位置
        marked_text = self.model._mark_entities(text, head, tail)

        # Tokenizer编码
        encoding = self.tokenizer(
            marked_text,
            max_length=256,
            truncation=True,
            return_tensors="pt",
        )

        input_ids = encoding["input_ids"].to(self.device)
        attention_mask = encoding["attention_mask"].to(self.device)

        # 创建实体标记掩码
        tokens = self.tokenizer.convert_ids_to_tokens(input_ids[0])
        e1_mask = torch.zeros_like(input_ids, dtype=torch.bool)
        e2_mask = torch.zeros_like(input_ids, dtype=torch.bool)

        in_e1 = False
        in_e2 = False
        for idx, token in enumerate(tokens):
            if token == "[E1]":
                in_e1 = True
            elif token == "[/E1]":
                in_e1 = False
            elif token == "[E2]":
                in_e2 = True
            elif token == "[/E2]":
                in_e2 = False
            elif in_e1:
                e1_mask[0, idx] = True
            elif in_e2:
                e2_mask[0, idx] = True

        e1_mask = e1_mask.to(self.device)
        e2_mask = e2_mask.to(self.device)

        # 推理
        with torch.no_grad():
            outputs = self.model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                e1_mask=e1_mask,
                e2_mask=e2_mask,
            )

        logits = outputs["logits"]
        probs = torch.softmax(logits, dim=-1)
        pred_id = logits.argmax(dim=-1).item()
        confidence = probs[0, pred_id].item()
        relation_type = self.id2relation.get(pred_id, "NA")

        return relation_type, confidence

    def extract_from_annotated_file(self, file_path: str) -> List[Relation]:
        """从标注文件中抽取关系。

        Args:
            file_path: 标注文件路径

        Returns:
            抽取到的关系列表
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        all_relations = []
        for doc in data.get("documents", []):
            text = doc["text"]
            entities = doc.get("entities", [])
            relations = self.extract(text, entities)
            all_relations.extend(relations)

        logger.info(f"从 {file_path} 抽取到 {len(all_relations)} 个关系")
        return all_relations

    def save(self, save_path: str):
        """保存模型和配置。

        Args:
            save_path: 保存路径
        """
        os.makedirs(save_path, exist_ok=True)
        torch.save(self.model.state_dict(), os.path.join(save_path, "pytorch_model.bin"))
        self.tokenizer.save_pretrained(save_path)

        config = {
            "relation_types": self.relation_types,
            "relation2id": self.relation2id,
            "threshold": self.threshold,
        }
        with open(os.path.join(save_path, "re_config.json"), "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)

        logger.info(f"关系抽取模型已保存至: {save_path}")


def train_relation_model(
    train_dataset: RelationDataset,
    val_dataset: Optional[RelationDataset] = None,
    pretrained_model: str = "bert-base-chinese",
    batch_size: int = 16,
    learning_rate: float = 2e-5,
    num_epochs: int = 10,
    early_stop_patience: int = 3,
    save_dir: str = "models/re",
    device: Optional[str] = None,
) -> RelationClassificationModel:
    """训练关系分类模型。

    Args:
        train_dataset: 训练数据集
        val_dataset: 验证数据集
        pretrained_model: 预训练模型名称
        batch_size: 批次大小
        learning_rate: 学习率
        num_epochs: 训练轮数
        early_stop_patience: 早停耐心值
        save_dir: 模型保存目录
        device: 计算设备

    Returns:
        训练完成的模型
    """
    if device is None or device == "auto":
        dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        dev = torch.device(device)

    logger.info(f"关系分类训练设备: {dev}")

    # 创建Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(pretrained_model)
    special_tokens = ["[E1]", "[/E1]", "[E2]", "[/E2]"]
    tokenizer.add_special_tokens({"additional_special_tokens": special_tokens})

    # 创建模型
    model = RelationClassificationModel(
        pretrained_model=pretrained_model,
        num_relations=len(train_dataset.relation2id),
    )
    model.bert.resize_token_embeddings(len(tokenizer))
    model.to(dev)

    # 优化器与调度器
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    total_steps = len(train_dataset) * num_epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(0.1 * total_steps),
        num_training_steps=total_steps,
    )

    # 损失函数
    loss_fct = nn.CrossEntropyLoss()

    # 训练循环
    best_val_loss = float("inf")
    patience_counter = 0

    for epoch in range(num_epochs):
        model.train()
        total_loss = 0.0
        num_batches = 0

        # 构建批次
        indices = list(range(len(train_dataset)))
        random.shuffle(indices)

        for batch_start in range(0, len(indices), batch_size):
            batch_indices = indices[batch_start:batch_start + batch_size]
            batch_input_ids = []
            batch_attention_masks = []
            batch_e1_masks = []
            batch_e2_masks = []
            batch_labels = []

            for idx in batch_indices:
                instance = train_dataset.instances[idx]
                head = instance.head
                tail = instance.tail
                label = train_dataset.relation2id.get(instance.relation, 0)

                # 标注实体位置
                marked_text = model._mark_entities(instance.text, head, tail)

                # Tokenizer编码
                encoding = tokenizer(
                    marked_text,
                    max_length=256,
                    truncation=True,
                    padding="max_length",
                    return_tensors="pt",
                )

                batch_input_ids.append(encoding["input_ids"])
                batch_attention_masks.append(encoding["attention_mask"])

                # 创建实体标记掩码
                tokens = tokenizer.convert_ids_to_tokens(encoding["input_ids"][0])
                e1_mask = torch.zeros_like(encoding["input_ids"], dtype=torch.bool)
                e2_mask = torch.zeros_like(encoding["input_ids"], dtype=torch.bool)

                in_e1 = False
                in_e2 = False
                for t_idx, token in enumerate(tokens):
                    if token == "[E1]":
                        in_e1 = True
                    elif token == "[/E1]":
                        in_e1 = False
                    elif token == "[E2]":
                        in_e2 = True
                    elif token == "[/E2]":
                        in_e2 = False
                    elif in_e1:
                        e1_mask[0, t_idx] = True
                    elif in_e2:
                        e2_mask[0, t_idx] = True

                batch_e1_masks.append(e1_mask)
                batch_e2_masks.append(e2_mask)
                batch_labels.append(label)

            # 合并批次
            input_ids = torch.cat(batch_input_ids).to(dev)
            attention_mask = torch.cat(batch_attention_masks).to(dev)
            e1_mask = torch.cat(batch_e1_masks).to(dev)
            e2_mask = torch.cat(batch_e2_masks).to(dev)
            labels = torch.tensor(batch_labels, dtype=torch.long).to(dev)

            # 前向传播
            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                e1_mask=e1_mask,
                e2_mask=e2_mask,
                labels=labels,
            )

            loss = outputs["loss"]
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()

            total_loss += loss.item()
            num_batches += 1

        avg_loss = total_loss / max(num_batches, 1)
        logger.info(f"Epoch {epoch + 1}/{num_epochs} | 训练损失: {avg_loss:.4f}")

        # 验证
        if val_dataset is not None:
            val_loss = _evaluate_relation_model(
                model, val_dataset, tokenizer, dev, batch_size, loss_fct
            )
            logger.info(f"Epoch {epoch + 1}/{num_epochs} | 验证损失: {val_loss:.4f}")

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                # 保存最佳模型
                os.makedirs(save_dir, exist_ok=True)
                torch.save(model.state_dict(), os.path.join(save_dir, "pytorch_model.bin"))
                tokenizer.save_pretrained(save_dir)
                logger.info(f"最佳模型已保存 (val_loss: {val_loss:.4f})")
            else:
                patience_counter += 1
                if patience_counter >= early_stop_patience:
                    logger.info(f"早停触发 (patience: {early_stop_patience})")
                    break
        else:
            # 无验证集时每个epoch都保存
            os.makedirs(save_dir, exist_ok=True)
            torch.save(model.state_dict(), os.path.join(save_dir, "pytorch_model.bin"))

    # 保存配置
    config = {
        "relation_types": list(train_dataset.relation2id.keys()),
        "relation2id": train_dataset.relation2id,
        "pretrained_model": pretrained_model,
    }
    with open(os.path.join(save_dir, "re_config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    logger.info(f"关系分类模型训练完成，已保存至: {save_dir}")

    return model


def _evaluate_relation_model(
    model: RelationClassificationModel,
    val_dataset: RelationDataset,
    tokenizer,
    device: torch.device,
    batch_size: int = 16,
    loss_fct: Optional[nn.Module] = None,
) -> float:
    """评估关系分类模型。

    Args:
        model: 关系分类模型
        val_dataset: 验证数据集
        tokenizer: Tokenizer
        device: 计算设备
        batch_size: 批次大小
        loss_fct: 损失函数

    Returns:
        平均验证损失
    """
    model.eval()
    total_loss = 0.0
    num_batches = 0

    if loss_fct is None:
        loss_fct = nn.CrossEntropyLoss()

    with torch.no_grad():
        for batch_start in range(0, len(val_dataset), batch_size):
            batch_instances = val_dataset.instances[batch_start:batch_start + batch_size]
            if not batch_instances:
                continue

            batch_input_ids = []
            batch_attention_masks = []
            batch_e1_masks = []
            batch_e2_masks = []
            batch_labels = []

            for instance in batch_instances:
                head = instance.head
                tail = instance.tail
                label = val_dataset.relation2id.get(instance.relation, 0)

                marked_text = model._mark_entities(instance.text, head, tail)
                encoding = tokenizer(
                    marked_text,
                    max_length=256,
                    truncation=True,
                    padding="max_length",
                    return_tensors="pt",
                )

                batch_input_ids.append(encoding["input_ids"])
                batch_attention_masks.append(encoding["attention_mask"])

                tokens = tokenizer.convert_ids_to_tokens(encoding["input_ids"][0])
                e1_mask = torch.zeros_like(encoding["input_ids"], dtype=torch.bool)
                e2_mask = torch.zeros_like(encoding["input_ids"], dtype=torch.bool)

                in_e1 = False
                in_e2 = False
                for t_idx, token in enumerate(tokens):
                    if token == "[E1]":
                        in_e1 = True
                    elif token == "[/E1]":
                        in_e1 = False
                    elif token == "[E2]":
                        in_e2 = True
                    elif token == "[/E2]":
                        in_e2 = False
                    elif in_e1:
                        e1_mask[0, t_idx] = True
                    elif in_e2:
                        e2_mask[0, t_idx] = True

                batch_e1_masks.append(e1_mask)
                batch_e2_masks.append(e2_mask)
                batch_labels.append(label)

            if not batch_input_ids:
                continue

            input_ids = torch.cat(batch_input_ids).to(device)
            attention_mask = torch.cat(batch_attention_masks).to(device)
            e1_mask = torch.cat(batch_e1_masks).to(device)
            e2_mask = torch.cat(batch_e2_masks).to(device)
            labels = torch.tensor(batch_labels, dtype=torch.long).to(device)

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                e1_mask=e1_mask,
                e2_mask=e2_mask,
            )

            logits = outputs["logits"]
            loss = loss_fct(logits, labels)
            total_loss += loss.item()
            num_batches += 1

    return total_loss / max(num_batches, 1)
