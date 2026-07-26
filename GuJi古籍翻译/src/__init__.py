"""
面向古籍文本的语义理解与知识图谱构建方法研究
============================================

本包实现了完整的古籍文本处理流水线，包括：
- 古籍OCR后处理与文本清洗
- 古籍分词、断句与词性标注
- 古籍命名实体识别（人物、地点、官职、事件）
- 实体关系抽取
- 知识图谱构建与存储
- 少样本学习
- Web API接口

模块结构:
    text_cleaner       - 文本清洗
    tokenizer          - 分词与断句
    ner                - 命名实体识别
    relation_extractor - 关系抽取
    knowledge_graph    - 知识图谱
    pipeline           - 端到端流水线
    few_shot           - 少样本学习
    web_api            - Web API接口
"""

__version__ = "1.0.0"
__author__ = "GuJi Research Team"
__description__ = "面向古籍文本的语义理解与知识图谱构建方法研究"
