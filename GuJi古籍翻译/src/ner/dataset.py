"""
古籍NER数据集定义与处理模块
==============================

本模块实现了古籍命名实体识别的数据集类和数据处理工具，包括：
- NERDataset: PyTorch数据集类
- 标注格式转换（JSON -> BIO标签序列）
- 少样本数据增强
- 数据加载与预处理工具函数

BIO标注体系:
    B-PER: 人物实体起始
    I-PER: 人物实体内部
    B-LOC: 地点实体起始
    I-LOC: 地点实体内部
    B-OFF: 官职实体起始
    I-OFF: 官职实体内部
    B-EVT: 事件实体起始
    I-EVT: 事件实体内部
    B-ORG: 组织实体起始
    I-ORG: 组织实体内部
    B-TIME: 时间实体起始
    I-TIME: 时间实体内部
    O: 非实体

典型用法:
    >>> dataset = NERDataset.from_annotated_file("data/sample_annotated.json")
    >>> print(f"样本数: {len(dataset)}")
    >>> sample = dataset[0]
    >>> print(sample["tokens"][:5], sample["labels"][:5])
"""

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
from torch.utils.data import Dataset
from loguru import logger


# 默认实体类型列表
DEFAULT_ENTITY_TYPES = ["PER", "LOC", "OFF", "EVT", "ORG", "TIME"]

# BIO标签到ID的映射（包含默认实体类型）
def build_label2id(entity_types: Optional[List[str]] = None) -> Dict[str, int]:
    """构建BIO标签到ID的映射字典。

    Args:
        entity_types: 实体类型列表，默认使用 DEFAULT_ENTITY_TYPES

    Returns:
        标签到ID的映射字典
    """
    types = entity_types or DEFAULT_ENTITY_TYPES
    label2id = {"O": 0}
    idx = 1
    for entity_type in types:
        label2id[f"B-{entity_type}"] = idx
        label2id[f"I-{entity_type}"] = idx + 1
        idx += 2
    return label2id


def build_id2label(label2id: Dict[str, int]) -> Dict[int, str]:
    """构建ID到标签的映射字典。

    Args:
        label2id: 标签到ID的映射字典

    Returns:
        ID到标签的映射字典
    """
    return {v: k for k, v in label2id.items()}


class NERDataset(Dataset):
    """古籍命名实体识别数据集。

    将标注数据转换为模型可训练的格式，支持BIO标注体系，
    并与HuggingFace Transformers的Tokenizer配合使用。

    Attributes:
        samples: 样本列表，每个样本为包含 tokens 和 labels 的字典
        label2id: 标签到ID的映射
        id2label: ID到标签的映射
        entity_types: 实体类型列表
        max_seq_length: 最大序列长度
    """

    def __init__(
        self,
        samples: List[Dict[str, Any]],
        label2id: Optional[Dict[str, int]] = None,
        entity_types: Optional[List[str]] = None,
        max_seq_length: int = 256,
    ):
        """初始化NER数据集。

        Args:
            samples: 样本列表，每个样本需包含 'tokens'(List[str]) 和 'labels'(List[str]) 字段
            label2id: 标签到ID的映射，若为None则自动构建
            entity_types: 实体类型列表
            max_seq_length: 最大序列长度
        """
        self.samples = samples
        self.entity_types = entity_types or DEFAULT_ENTITY_TYPES
        self.label2id = label2id or build_label2id(self.entity_types)
        self.id2label = build_id2label(self.label2id)
        self.max_seq_length = max_seq_length

        logger.info(
            f"NER数据集初始化 | 样本数: {len(samples)} | "
            f"标签数: {len(self.label2id)} | 最大序列长度: {max_seq_length}"
        )

    def __len__(self) -> int:
        """返回数据集大小。"""
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        """获取单个样本。

        Args:
            idx: 样本索引

        Returns:
            包含 input_ids, attention_mask, labels 的字典
        """
        sample = self.samples[idx]
        tokens = sample["tokens"]
        labels = sample["labels"]

        # 截断到最大长度
        if len(tokens) > self.max_seq_length - 2:  # 预留[CLS]和[SEP]
            tokens = tokens[:self.max_seq_length - 2]
            labels = labels[:self.max_seq_length - 2]

        # 转换标签为ID
        label_ids = [self.label2id.get(l, 0) for l in labels]

        return {
            "tokens": tokens,
            "labels": label_ids,
        }

    def get_label_info(self) -> Dict[str, Any]:
        """获取标签信息。

        Returns:
            包含标签映射和统计信息的字典
        """
        # 统计各标签出现次数
        label_counts = {}
        for sample in self.samples:
            for label in sample["labels"]:
                label_counts[label] = label_counts.get(label, 0) + 1

        return {
            "label2id": self.label2id,
            "id2label": self.id2label,
            "num_labels": len(self.label2id),
            "label_counts": label_counts,
        }

    @classmethod
    def from_annotated_file(
        cls,
        file_path: str,
        entity_types: Optional[List[str]] = None,
        max_seq_length: int = 256,
    ) -> "NERDataset":
        """从标注JSON文件创建数据集。

        标注文件格式参见 data/sample_annotated.json。

        Args:
            file_path: 标注文件路径
            entity_types: 实体类型列表
            max_seq_length: 最大序列长度

        Returns:
            NERDataset实例
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        types = entity_types or data.get("metadata", {}).get(
            "entity_types", DEFAULT_ENTITY_TYPES
        )

        samples = []
        for doc in data.get("documents", []):
            sample = _convert_document_to_bio(doc, types)
            if sample:
                samples.append(sample)

        logger.info(f"从 {file_path} 加载 {len(samples)} 个标注样本")
        return cls(
            samples=samples,
            entity_types=types,
            max_seq_length=max_seq_length,
        )

    @classmethod
    def from_raw_text(
        cls,
        texts: List[str],
        entity_types: Optional[List[str]] = None,
        max_seq_length: int = 256,
    ) -> "NERDataset":
        """从原始文本创建数据集（所有标签为O，用于推理）。

        Args:
            texts: 文本列表
            entity_types: 实体类型列表
            max_seq_length: 最大序列长度

        Returns:
            NERDataset实例
        """
        samples = []
        for text in texts:
            # 按字符切分
            chars = list(text)
            labels = ["O"] * len(chars)
            samples.append({"tokens": chars, "labels": labels})

        return cls(
            samples=samples,
            entity_types=entity_types,
            max_seq_length=max_seq_length,
        )


def _convert_document_to_bio(
    doc: Dict[str, Any],
    entity_types: List[str],
) -> Optional[Dict[str, Any]]:
    """将标注文档转换为BIO格式。

    将包含实体位置信息的标注文档转换为字符级别的BIO标签序列。

    Args:
        doc: 标注文档，包含 text, entities 字段
        entity_types: 实体类型列表

    Returns:
        包含 tokens 和 labels 的字典，若转换失败则返回None
    """
    text = doc.get("text", "")
    if not text:
        return None

    # 初始化所有标签为O
    chars = list(text)
    labels = ["O"] * len(chars)

    # 根据实体标注设置BIO标签
    entities = doc.get("entities", [])
    for entity in entities:
        entity_type = entity.get("type", "")
        start = entity.get("start", 0)
        end = entity.get("end", 0)

        # 验证实体类型
        if entity_type not in entity_types:
            continue

        # 验证位置
        if start < 0 or end > len(chars) or start >= end:
            continue

        # 设置BIO标签
        labels[start] = f"B-{entity_type}"
        for i in range(start + 1, end):
            labels[i] = f"I-{entity_type}"

    return {"tokens": chars, "labels": labels}


class DataCollatorForNER:
    """NER数据整理器。

    将多个样本整理为一个批次，包括：
    - 使用Tokenizer进行tokenize
    - 填充（padding）到批次内最大长度
    - 生成attention_mask
    - 对齐标签与子词token

    Attributes:
        tokenizer: HuggingFace Tokenizer
        label2id: 标签到ID的映射
        max_length: 最大序列长度
    """

    def __init__(
        self,
        tokenizer,
        label2id: Dict[str, int],
        max_length: int = 256,
    ):
        """初始化数据整理器。

        Args:
            tokenizer: HuggingFace Transformers的Tokenizer
            label2id: 标签到ID的映射
            max_length: 最大序列长度
        """
        self.tokenizer = tokenizer
        self.label2id = label2id
        self.max_length = max_length

    def __call__(self, batch: List[Dict[str, Any]]) -> Dict[str, torch.Tensor]:
        """整理一个批次的数据。

        Args:
            batch: 样本列表

        Returns:
            包含 input_ids, attention_mask, labels 的张量字典
        """
        all_tokens = [item["tokens"] for item in batch]
        all_labels = [item["labels"] for item in batch]

        # 使用Tokenizer编码
        encodings = self.tokenizer(
            all_tokens,
            is_split_into_words=True,
            max_length=self.max_length,
            padding=True,
            truncation=True,
            return_tensors="pt",
        )

        # 对齐标签
        batch_labels = []
        for i, labels in enumerate(all_labels):
            word_ids = encodings.word_ids(batch_index=i)
            aligned_labels = []

            previous_word_idx = None
            for word_idx in word_ids:
                if word_idx is None:
                    # [CLS], [SEP], 或padding token
                    aligned_labels.append(-100)  # -100表示在损失计算中忽略
                elif word_idx != previous_word_idx:
                    # 新词的第一个子词token
                    if word_idx < len(labels):
                        aligned_labels.append(labels[word_idx])
                    else:
                        aligned_labels.append(0)
                else:
                    # 同一个词的后续子词token，标记为-100（忽略）
                    aligned_labels.append(-100)
                previous_word_idx = word_idx

            batch_labels.append(aligned_labels)

        encodings["labels"] = torch.tensor(batch_labels, dtype=torch.long)
        return encodings


class FewShotAugmentor:
    """少样本数据增强器。

    针对古籍NER标注数据稀缺的问题，提供多种数据增强策略：
    - 实体替换：用同类型实体替换原实体
    - 随机删除：随机删除非实体字符
    - 随机交换：交换相邻非实体字符
    - 同义词替换：替换为古籍同义表达

    Attributes:
        entity_replacement_dict: 各类型实体的替换候选列表
        augmentation_factor: 数据增强倍数
    """

    # 各类型实体的替换候选（示例）
    DEFAULT_REPLACEMENTS = {
        "PER": ["张三", "李四", "王五", "赵六", "孙七", "周八", "吴九", "郑十"],
        "LOC": ["长安", "洛阳", "建康", "临安", "汴京", "咸阳", "邯郸", "姑苏"],
        "OFF": ["丞相", "太尉", "司徒", "司空", "尚书", "侍郎", "郎中", "主簿"],
        "EVT": ["起义", "叛乱", "和议", "征伐", "巡幸", "祭祀", "册封", "禅让"],
    }

    def __init__(
        self,
        entity_replacement_dict: Optional[Dict[str, List[str]]] = None,
        augmentation_factor: int = 3,
    ):
        """初始化数据增强器。

        Args:
            entity_replacement_dict: 各类型实体的替换候选字典
            augmentation_factor: 每个原始样本生成的增强样本数
        """
        self.replacements = entity_replacement_dict or self.DEFAULT_REPLACEMENTS
        self.augmentation_factor = augmentation_factor

    def augment(self, samples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """对样本列表进行数据增强。

        Args:
            samples: 原始样本列表

        Returns:
            包含原始样本和增强样本的列表
        """
        augmented = list(samples)  # 保留原始样本

        for sample in samples:
            for _ in range(self.augmentation_factor):
                aug_sample = self._augment_one(sample)
                if aug_sample:
                    augmented.append(aug_sample)

        logger.info(
            f"数据增强完成 | 原始: {len(samples)} | "
            f"增强后: {len(augmented)} | 增强倍数: {self.augmentation_factor}"
        )
        return augmented

    def _augment_one(self, sample: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """对单个样本进行数据增强。

        随机选择一种增强策略并应用。

        Args:
            sample: 原始样本

        Returns:
            增强后的样本，若增强失败返回None
        """
        strategy = random.choice(
            ["entity_replace", "random_delete", "random_swap"]
        )

        try:
            if strategy == "entity_replace":
                return self._entity_replace(sample)
            elif strategy == "random_delete":
                return self._random_delete(sample)
            elif strategy == "random_swap":
                return self._random_swap(sample)
        except Exception as e:
            logger.debug(f"数据增强失败 ({strategy}): {e}")
            return None

        return None

    def _entity_replace(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """实体替换增强。

        随机选择一个实体，用同类型的其他实体替换。

        Args:
            sample: 原始样本

        Returns:
            增强后的样本
        """
        tokens = list(sample["tokens"])
        labels = list(sample["labels"])

        # 找到所有实体
        entities = []
        i = 0
        while i < len(labels):
            if labels[i].startswith("B-"):
                entity_type = labels[i][2:]
                start = i
                end = i + 1
                while end < len(labels) and labels[end] == f"I-{entity_type}":
                    end += 1
                entities.append((start, end, entity_type))
                i = end
            else:
                i += 1

        if not entities:
            return {"tokens": tokens, "labels": labels}

        # 随机选择一个实体进行替换
        start, end, entity_type = random.choice(entities)
        if entity_type not in self.replacements:
            return {"tokens": tokens, "labels": labels}

        replacement = random.choice(self.replacements[entity_type])
        new_tokens = list(replacement)

        # 替换tokens和labels
        tokens[start:end] = new_tokens
        new_labels = [f"B-{entity_type}"] + [f"I-{entity_type}"] * (len(new_tokens) - 1)
        labels[start:end] = new_labels

        return {"tokens": tokens, "labels": labels}

    def _random_delete(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """随机删除增强。

        以一定概率随机删除非实体字符，模拟古籍文本的残缺情况。

        Args:
            sample: 原始样本

        Returns:
            增强后的样本
        """
        tokens = list(sample["tokens"])
        labels = list(sample["labels"])

        delete_prob = 0.1  # 每个非实体字符的删除概率
        new_tokens = []
        new_labels = []

        for token, label in zip(tokens, labels):
            # 不删除实体字符
            if label != "O":
                new_tokens.append(token)
                new_labels.append(label)
            elif random.random() > delete_prob:
                new_tokens.append(token)
                new_labels.append(label)

        # 确保至少保留一个token
        if not new_tokens:
            return {"tokens": tokens, "labels": labels}

        return {"tokens": new_tokens, "labels": new_labels}

    def _random_swap(self, sample: Dict[str, Any]) -> Dict[str, Any]:
        """随机交换增强。

        交换相邻的非实体字符，增加文本的多样性。

        Args:
            sample: 原始样本

        Returns:
            增强后的样本
        """
        tokens = list(sample["tokens"])
        labels = list(sample["labels"])

        if len(tokens) < 2:
            return {"tokens": tokens, "labels": labels}

        # 找到可以交换的位置（两个相邻的非实体字符）
        swap_candidates = []
        for i in range(len(tokens) - 1):
            if labels[i] == "O" and labels[i + 1] == "O":
                swap_candidates.append(i)

        if not swap_candidates:
            return {"tokens": tokens, "labels": labels}

        # 随机交换一对
        idx = random.choice(swap_candidates)
        tokens[idx], tokens[idx + 1] = tokens[idx + 1], tokens[idx]

        return {"tokens": tokens, "labels": labels}


def load_ner_data(
    data_path: str,
    entity_types: Optional[List[str]] = None,
    max_seq_length: int = 256,
    augment: bool = False,
    augmentation_factor: int = 3,
) -> NERDataset:
    """加载NER数据的便捷函数。

    支持从标注文件加载，可选进行数据增强。

    Args:
        data_path: 标注文件路径
        entity_types: 实体类型列表
        max_seq_length: 最大序列长度
        augment: 是否进行数据增强
        augmentation_factor: 数据增强倍数

    Returns:
        NERDataset实例
    """
    dataset = NERDataset.from_annotated_file(
        file_path=data_path,
        entity_types=entity_types,
        max_seq_length=max_seq_length,
    )

    if augment:
        augmentor = FewShotAugmentor(augmentation_factor=augmentation_factor)
        dataset.samples = augmentor.augment(dataset.samples)
        logger.info(f"数据增强后样本数: {len(dataset)}")

    return dataset


def split_dataset(
    dataset: NERDataset,
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
    seed: int = 42,
) -> Tuple[NERDataset, NERDataset, NERDataset]:
    """将数据集划分为训练集、验证集和测试集。

    Args:
        dataset: 原始数据集
        train_ratio: 训练集比例
        val_ratio: 验证集比例
        test_ratio: 测试集比例
        seed: 随机种子

    Returns:
        (train_dataset, val_dataset, test_dataset) 元组
    """
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6, \
        "数据集划分比例之和必须为1.0"

    n = len(dataset)
    indices = list(range(n))
    random.seed(seed)
    random.shuffle(indices)

    train_end = int(n * train_ratio)
    val_end = train_end + int(n * val_ratio)

    train_indices = indices[:train_end]
    val_indices = indices[train_end:val_end]
    test_indices = indices[val_end:]

    train_dataset = NERDataset(
        samples=[dataset.samples[i] for i in train_indices],
        label2id=dataset.label2id,
        entity_types=dataset.entity_types,
        max_seq_length=dataset.max_seq_length,
    )
    val_dataset = NERDataset(
        samples=[dataset.samples[i] for i in val_indices],
        label2id=dataset.label2id,
        entity_types=dataset.entity_types,
        max_seq_length=dataset.max_seq_length,
    )
    test_dataset = NERDataset(
        samples=[dataset.samples[i] for i in test_indices],
        label2id=dataset.label2id,
        entity_types=dataset.entity_types,
        max_seq_length=dataset.max_seq_length,
    )

    logger.info(
        f"数据集划分完成 | 训练: {len(train_dataset)} | "
        f"验证: {len(val_dataset)} | 测试: {len(test_dataset)}"
    )
    return train_dataset, val_dataset, test_dataset
