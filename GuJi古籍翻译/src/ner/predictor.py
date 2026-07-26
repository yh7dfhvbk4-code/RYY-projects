"""
古籍NER推理预测模块
======================

本模块实现了古籍命名实体识别的推理预测功能，包括：
- NERPredictor: 推理预测器
- 预测结果后处理
- 实体提取与格式化
- 模型训练函数

典型用法:
    >>> predictor = NERPredictor(model_path="models/ner")
    >>> entities = predictor.predict("屈原者，名平，楚之同姓也。")
    >>> for ent in entities:
    ...     print(f"{ent['text']} ({ent['type']})")
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

import torch
from torch.optim import AdamW
from torch.utils.data import DataLoader
from tqdm import tqdm
from transformers import AutoTokenizer, get_linear_schedule_with_warmup

from loguru import logger

from src.ner.dataset import (
    NERDataset,
    DataCollatorForNER,
    build_label2id,
    build_id2label,
    DEFAULT_ENTITY_TYPES,
)
from src.ner.model import BertCRF, BertCRFConfig


class NERPredictor:
    """古籍命名实体识别推理预测器。"""

    def __init__(
        self,
        model_path: Optional[str] = None,
        model: Optional[BertCRF] = None,
        tokenizer: Optional[Any] = None,
        label2id: Optional[Dict[str, int]] = None,
        device: Optional[str] = None,
        max_seq_length: int = 256,
    ):
        # 设备选择
        if device is None or device == "auto":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        self.max_seq_length = max_seq_length

        if model_path and os.path.exists(model_path):
            self._load_from_path(model_path)
        else:
            self.model = model
            self.tokenizer = tokenizer
            self.label2id = label2id or build_label2id()
            self.id2label = build_id2label(self.label2id)

        if self.model is not None:
            self.model.to(self.device)
            self.model.eval()

        logger.info(f"NER预测器初始化完成 | 设备: {self.device}")

    def _load_from_path(self, model_path: str):
        # ========== 修复 1：确保 config 一定存在 ==========
        config_path = os.path.join(model_path, "config.json")
        if os.path.exists(config_path):
            config = BertCRFConfig.from_pretrained(model_path)
            self.label2id = getattr(config, "label2id", None) or build_label2id()
            self.max_seq_length = getattr(config, "max_seq_length", self.max_seq_length)
        else:
            config = None
            self.label2id = build_label2id()

        self.id2label = build_id2label(self.label2id)

        label_map_path = os.path.join(model_path, "label_map.json")
        if os.path.exists(label_map_path):
            with open(label_map_path, "r", encoding="utf-8") as f:
                self.label2id = json.load(f)
                self.id2label = build_id2label(self.label2id)

        # 加载模型
        try:
            if config is not None:
                self.model = BertCRF(config)
            else:
                self.model = BertCRF(
                    BertCRFConfig(
                        bert_model_name="bert-base-chinese",
                        num_labels=len(self.label2id),
                        label2id=self.label2id,
                    )
                )
            state_dict = torch.load(
                os.path.join(model_path, "pytorch_model.bin"),
                map_location=self.device,
                weights_only=True,
            )
            self.model.load_state_dict(state_dict)
            logger.info(f"模型权重加载成功: {model_path}")
        except Exception as e:
            logger.warning(f"模型加载失败: {e}")
            self.model = None

        # 加载 tokenizer
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        except Exception:
            try:
                if config is not None:
                    bert_name = getattr(config, "bert_model_name", "bert-base-chinese")
                else:
                    bert_name = "bert-base-chinese"
                self.tokenizer = AutoTokenizer.from_pretrained(bert_name)
            except Exception as e2:
                logger.warning(f"Tokenizer加载失败: {e2}")
                self.tokenizer = None

    def predict(self, text: str) -> List[Dict[str, Any]]:
        if not text:
            return []

        if self.model is None or self.tokenizer is None:
            logger.warning("模型或Tokenizer未加载")
            return []

        chars = list(text)
        encoding = self.tokenizer(
            chars,
            is_split_into_words=True,
            max_length=self.max_seq_length,
            truncation=True,
            return_tensors="pt",
            return_offsets_mapping=True,
        )

        input_ids = encoding["input_ids"].to(self.device)
        attention_mask = encoding["attention_mask"].to(self.device)
        offsets = encoding["offset_mapping"][0].cpu().numpy()

        with torch.no_grad():
            outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)

        predictions = outputs.get("predictions")
        if predictions is None:
            return []

        pred_ids = predictions[0].cpu().tolist()
        pred_labels = [self.id2label.get(pid, "O") for pid in pred_ids]

        # ========== 修复 2：正确的标签对齐逻辑 ==========
        aligned_labels = ["O"] * len(chars)
        token_idx = 1  # skip [CLS]

        while token_idx < len(offsets) - 1:  # skip [SEP]
            start, end = offsets[token_idx]
            if start < end and token_idx - 1 < len(pred_labels):
                label = pred_labels[token_idx - 1]
                for i in range(start, end):
                    if i < len(aligned_labels):
                        aligned_labels[i] = label
            token_idx += 1

        entities = self._extract_entities(chars, aligned_labels)
        return entities

    def predict_batch(self, texts: List[str], batch_size: int = 16) -> List[List[Dict[str, Any]]]:
        results = []
        for text in texts:
            results.append(self.predict(text))
        logger.info(f"批量预测完成 | 文本数: {len(texts)}")
        return results

    def _extract_entities(self, chars: List[str], labels: List[str]) -> List[Dict[str, Any]]:
        entities = []
        current = None
        for i, (c, lab) in enumerate(zip(chars, labels)):
            if lab.startswith("B-"):
                if current:
                    entities.append(current)
                current = {"text": c, "type": lab[2:], "start": i, "end": i + 1}
            elif lab.startswith("I-") and current:
                if lab[2:] == current["type"]:
                    current["text"] += c
                    current["end"] = i + 1
                else:
                    entities.append(current)
                    current = None
            else:
                if current:
                    entities.append(current)
                    current = None
        if current:
            entities.append(current)
        return entities

    def save(self, save_path: str):
        os.makedirs(save_path, exist_ok=True)
        if self.model:
            torch.save(self.model.state_dict(), os.path.join(save_path, "pytorch_model.bin"))
            # ========== 修复 3：保存 max_seq_length ==========
            self.model.config.max_seq_length = self.max_seq_length
            self.model.config.save_pretrained(save_path)

        with open(os.path.join(save_path, "label_map.json"), "w", encoding="utf-8") as f:
            json.dump(self.label2id, f, ensure_ascii=False, indent=2)

        if self.tokenizer:
            self.tokenizer.save_pretrained(save_path)
        logger.info(f"模型已保存至: {save_path}")

def train_ner_model(
    train_dataset: NERDataset,
    val_dataset: Optional[NERDataset] = None,
    pretrained_model: str = "bert-base-chinese",
    num_labels: Optional[int] = None,
    batch_size: int = 16,
    learning_rate: float = 2e-5,
    num_epochs: int = 10,
    early_stop_patience: int = 3,
    save_dir: str = "models/ner",
    device: Optional[str] = None,
) -> BertCRF:
    """训练NER模型。

    完整的训练流程，包括：
    - 模型初始化（加载预训练BERT）
    - 优化器和学习率调度器配置
    - 训练循环与验证
    - 早停机制
    - 模型保存

    Args:
        train_dataset: 训练数据集
        val_dataset: 验证数据集
        pretrained_model: 预训练模型名称
        num_labels: 标签数量
        batch_size: 批次大小
        learning_rate: 学习率
        num_epochs: 训练轮数
        early_stop_patience: 早停耐心值
        save_dir: 模型保存目录
        device: 计算设备

    Returns:
        训练完成的模型
    """
    # 设备选择
    if device is None or device == "auto":
        dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        dev = torch.device(device)

    logger.info(f"训练设备: {dev}")

    # 标签信息
    label_info = train_dataset.get_label_info()
    n_labels = num_labels or label_info["num_labels"]
    label2id = label_info["label2id"]

    # 加载Tokenizer
    tokenizer = AutoTokenizer.from_pretrained(pretrained_model)

    # 创建数据整理器
    data_collator = DataCollatorForNER(
        tokenizer=tokenizer,
        label2id=label2id,
        max_length=train_dataset.max_seq_length,
    )

    # 创建数据加载器
    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        collate_fn=data_collator,
    )

    val_loader = None
    if val_dataset is not None:
        val_loader = DataLoader(
            val_dataset,
            batch_size=batch_size,
            shuffle=False,
            collate_fn=data_collator,
        )

    # 创建模型
    model = BertCRF.from_pretrained_bert(
        bert_model_name=pretrained_model,
        num_labels=n_labels,
    )
    model.to(dev)

    # 优化器
    optimizer = AdamW(model.parameters(), lr=learning_rate)

    # 学习率调度器
    total_steps = len(train_loader) * num_epochs
    scheduler = get_linear_schedule_with_warmup(
        optimizer,
        num_warmup_steps=int(0.1 * total_steps),
        num_training_steps=total_steps,
    )

    # 训练循环
    best_val_loss = float("inf")
    patience_counter = 0

    for epoch in range(num_epochs):
        model.train()
        total_loss = 0.0

        progress_bar = tqdm(train_loader, desc=f"Epoch {epoch + 1}/{num_epochs}")
        for batch in progress_bar:
            # 数据移到设备
            input_ids = batch["input_ids"].to(dev)
            attention_mask = batch["attention_mask"].to(dev)
            labels = batch["labels"].to(dev)

            # 前向传播
            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels,
            )
            loss = outputs["loss"]

            # 反向传播
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()

            total_loss += loss.item()
            progress_bar.set_postfix({"loss": f"{loss.item():.4f}"})

        avg_train_loss = total_loss / len(train_loader)
        logger.info(f"Epoch {epoch + 1} | 训练损失: {avg_train_loss:.4f}")

        # 验证
        if val_loader is not None:
            val_loss = _evaluate(model, val_loader, dev)
            logger.info(f"Epoch {epoch + 1} | 验证损失: {val_loss:.4f}")

            # 早停检查
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                # 保存最佳模型
                predictor = NERPredictor(
                    model=model,
                    tokenizer=tokenizer,
                    label2id=label2id,
                    device=str(dev),
                )
                predictor.save(save_dir)
                logger.info(f"最佳模型已保存 (val_loss: {val_loss:.4f})")
            else:
                patience_counter += 1
                if patience_counter >= early_stop_patience:
                    logger.info(f"早停触发 (patience: {early_stop_patience})")
                    break

        # 训练完成后，直接返回初始化好的预测器（修复核心）
    logger.info("训练完成")
    return model 


def _evaluate(
    model: BertCRF,
    val_loader: DataLoader,
    device: torch.device,
) -> float:
    """评估模型。

    Args:
        model: BERT-CRF模型
        val_loader: 验证数据加载器
        device: 计算设备

    Returns:
        平均验证损失
    """
    model.eval()
    total_loss = 0.0

    with torch.no_grad():
        for batch in val_loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["labels"].to(device)

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                labels=labels,
            )
            total_loss += outputs["loss"].item()

    return total_loss / len(val_loader) if len(val_loader) > 0 else 0.0


def evaluate_ner(
    model: BertCRF,
    dataset: NERDataset,
    tokenizer,
    batch_size: int = 16,
    device: Optional[str] = None,
) -> Dict[str, float]:
    """评估NER模型性能，计算精确率、召回率和F1值。

    Args:
        model: BERT-CRF模型
        dataset: 评估数据集
        tokenizer: Tokenizer
        batch_size: 批次大小
        device: 计算设备

    Returns:
        包含 precision, recall, f1 的评估指标字典
    """
    if device is None or device == "auto":
        dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        dev = torch.device(device)

    model.to(dev)
    model.eval()

    label2id = dataset.label2id
    id2label = build_id2label(label2id)

    data_collator = DataCollatorForNER(
        tokenizer=tokenizer,
        label2id=label2id,
        max_length=dataset.max_seq_length,
    )
    data_loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=False,
        collate_fn=data_collator,
    )

    # 收集所有预测和真实标签
    all_preds = []
    all_golds = []

    with torch.no_grad():
        for batch in data_loader:
            input_ids = batch["input_ids"].to(dev)
            attention_mask = batch["attention_mask"].to(dev)
            labels = batch["labels"].to(dev)

            outputs = model(
                input_ids=input_ids,
                attention_mask=attention_mask,
            )

            predictions = outputs.get("predictions", [])
            if isinstance(predictions, torch.Tensor):
                predictions = predictions.cpu().tolist()

            # 收集有效位置的预测和真实标签
            for i in range(len(predictions)):
                if isinstance(predictions, list) and i < len(predictions):
                    pred_seq = predictions[i]
                else:
                    pred_seq = []

                gold_seq = labels[i].cpu().tolist()

                for j in range(min(len(pred_seq), len(gold_seq))):
                    if gold_seq[j] != -100:  # 忽略特殊token
                        pred_label = id2label.get(pred_seq[j], "O") if j < len(pred_seq) else "O"
                        gold_label = id2label.get(gold_seq[j], "O")
                        all_preds.append(pred_label)
                        all_golds.append(gold_label)

    # 计算实体级别的指标
    metrics = _compute_entity_metrics(all_preds, all_golds)
    logger.info(
        f"NER评估 | P: {metrics['precision']:.4f} | "
        f"R: {metrics['recall']:.4f} | F1: {metrics['f1']:.4f}"
    )
    return metrics


def _compute_entity_metrics(
    preds: List[str],
    golds: List[str],
) -> Dict[str, float]:
    """计算实体级别的评估指标。

    使用MUC评测方法，基于BIO标签序列计算实体级别的
    精确率(Precision)、召回率(Recall)和F1值。

    Args:
        preds: 预测标签列表
        golds: 真实标签列表

    Returns:
        包含 precision, recall, f1 的字典
    """
    # 提取实体span
    pred_entities = set()
    gold_entities = set()

    current_pred = None
    current_gold = None

    for i, (pred, gold) in enumerate(zip(preds, golds)):
        # 预测实体
        if pred.startswith("B-"):
            if current_pred is not None:
                pred_entities.add(current_pred)
            current_pred = (pred[2:], i, i + 1)
        elif pred.startswith("I-") and current_pred is not None and pred[2:] == current_pred[0]:
            current_pred = (current_pred[0], current_pred[1], i + 1)
        else:
            if current_pred is not None:
                pred_entities.add(current_pred)
            current_pred = None

        # 真实实体
        if gold.startswith("B-"):
            if current_gold is not None:
                gold_entities.add(current_gold)
            current_gold = (gold[2:], i, i + 1)
        elif gold.startswith("I-") and current_gold is not None and gold[2:] == current_gold[0]:
            current_gold = (current_gold[0], current_gold[1], i + 1)
        else:
            if current_gold is not None:
                gold_entities.add(current_gold)
            current_gold = None

    # 处理最后一个实体
    if current_pred is not None:
        pred_entities.add(current_pred)
    if current_gold is not None:
        gold_entities.add(current_gold)

    # 计算指标
    correct = len(pred_entities & gold_entities)
    precision = correct / len(pred_entities) if pred_entities else 0.0
    recall = correct / len(gold_entities) if gold_entities else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }
