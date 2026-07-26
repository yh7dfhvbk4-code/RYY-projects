"""
古籍命名实体识别（NER）模块
============================

本模块实现了面向古籍文本的命名实体识别功能，包括：
- 基于BERT-CRF的序列标注模型
- BIO/BIOES标注体系支持
- 少样本学习（数据增强 + 元学习）
- 古籍实体类型识别（人物、地点、官职、事件等）

子模块:
    dataset   - 数据集定义与处理
    model     - BERT-CRF模型定义
    predictor - 推理预测器
"""

from src.ner.dataset import NERDataset
from src.ner.model import BertCRF, BertCRFConfig
from src.ner.predictor import NERPredictor

__all__ = ["NERDataset", "BertCRF", "BertCRFConfig", "NERPredictor"]
