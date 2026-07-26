"""
古籍文本处理端到端流水线模块
================================

本模块实现了完整的古籍文本处理流水线，串联所有子模块：
文本清洗 -> 分词断句 -> 命名实体识别 -> 关系抽取 -> 知识图谱构建

支持单步执行和全流程运行，提供中间结果缓存和断点续跑。

典型用法:
    >>> pipeline = GuJiPipeline()
    >>> result = pipeline.run("data/sample_raw.txt", mode="full")
    >>> print(result.summary())
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from loguru import logger

from src.text_cleaner import AncientTextCleaner
from src.tokenizer import AncientTokenizer
from src.ner.predictor import NERPredictor
from src.relation_extractor import RelationExtractor
from src.knowledge_graph import KnowledgeGraphBuilder
from src.ner.predictor import NERPredictor


@dataclass
class PipelineResult:
    """流水线处理结果。

    Attributes:
        raw_text: 原始文本
        cleaned_text: 清洗后文本
        tokenization_result: 分词结果（字典）
        entities: 识别到的实体列表
        relations: 抽取到的关系列表
        kg_stats: 知识图谱统计信息
        elapsed_time: 各步骤耗时
    """
    raw_text: str = ""
    cleaned_text: str = ""
    tokenization_result: Optional[Dict] = None
    entities: List[Dict[str, Any]] = field(default_factory=list)
    relations: List[Dict[str, Any]] = field(default_factory=list)
    kg_stats: Optional[Dict[str, Any]] = None
    elapsed_time: Dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        """生成处理结果摘要。

        Returns:
            摘要字符串
        """
        lines = [
            "=" * 60,
            "古籍文本处理流水线 - 结果摘要",
            "=" * 60,
            f"原始文本长度: {len(self.raw_text)} 字符",
            f"清洗后文本长度: {len(self.cleaned_text)} 字符",
            f"识别实体数: {len(self.entities)}",
            f"抽取关系数: {len(self.relations)}",
        ]

        # 实体类型统计
        if self.entities:
            type_counts = {}
            for ent in self.entities:
                t = ent.get("type", "UNK")
                type_counts[t] = type_counts.get(t, 0) + 1
            lines.append("  实体类型分布:")
            for t, c in sorted(type_counts.items(), key=lambda x: -x[1]):
                lines.append(f"    {t}: {c}")

        # 关系类型统计
        if self.relations:
            rel_counts = {}
            for rel in self.relations:
                t = rel.get("type", "UNK")
                rel_counts[t] = rel_counts.get(t, 0) + 1
            lines.append("  关系类型分布:")
            for t, c in sorted(rel_counts.items(), key=lambda x: -x[1]):
                lines.append(f"    {t}: {c}")

        # 知识图谱统计
        if self.kg_stats:
            lines.append(f"  知识图谱节点数: {self.kg_stats.get('total_nodes', 0)}")
            lines.append(f"  知识图谱关系数: {self.kg_stats.get('total_relations', 0)}")

        # 耗时统计
        if self.elapsed_time:
            lines.append("  各步骤耗时:")
            total = sum(self.elapsed_time.values())
            for step, t in self.elapsed_time.items():
                lines.append(f"    {step}: {t:.2f}s")
            lines.append(f"    总计: {total:.2f}s")

        lines.append("=" * 60)
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式。"""
        return {
            "raw_text_length": len(self.raw_text),
            "cleaned_text_length": len(self.cleaned_text),
            "entities": self.entities,
            "relations": self.relations,
            "kg_stats": self.kg_stats,
            "elapsed_time": self.elapsed_time,
        }

    def save(self, output_path: str):
        """保存结果到JSON文件。

        Args:
            output_path: 输出文件路径
        """
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info(f"结果已保存至: {output_path}")


class GuJiPipeline:
    """古籍文本处理端到端流水线。

    串联文本清洗、分词断句、命名实体识别、关系抽取和知识图谱构建
    五个核心模块，支持灵活的执行模式配置。

    Attributes:
        cleaner: 文本清洗器
        tokenizer: 分词器
        ner_predictor: NER预测器
        relation_extractor: 关系抽取器
        kg_builder: 知识图谱构建器
        config: 流水线配置
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """初始化流水线。

        Args:
            config: 流水线配置字典，支持以下键:
                - text_cleaner: 文本清洗器配置
                - tokenizer: 分词器配置
                - ner: NER配置
                - relation_extractor: 关系抽取配置
                - knowledge_graph: 知识图谱配置
                - device: 计算设备
        """
        self.config = config or {}
        self._init_modules()

    def _init_modules(self):
        """初始化各子模块。"""
        device = self.config.get("device", "auto")

        # 文本清洗器
        cleaner_config = self.config.get("text_cleaner", {})
        self.cleaner = AncientTextCleaner(
            conversion_mode=cleaner_config.get("conversion_mode", "t2s"),
            merge_whitespace=cleaner_config.get("merge_whitespace", True),
            strip_lines=cleaner_config.get("strip_lines", True),
            min_line_length=cleaner_config.get("min_line_length", 2),
        )

        # 分词器
        tokenizer_config = self.config.get("tokenizer", {})
        self.tokenizer = AncientTokenizer(
            max_sentence_length=tokenizer_config.get("max_sentence_length", 128),
            keep_punctuation=tokenizer_config.get("keep_punctuation", True),
        )

        # NER预测器（优化健壮版）
        ner_config = self.config.get("ner", {})
        ner_model_path = ner_config.get("model_path", None)
        try:
    # 核心：路径存在则加载模型，否则初始化空预测器
            self.ner_predictor = NERPredictor(
                model_path=ner_model_path if (ner_model_path and os.path.exists(ner_model_path)) else None,
                device=device,
            )
            logger.info(f"NER预测器初始化成功 | 模型路径: {ner_model_path}")
        except Exception as e:
            logger.warning(f"NER预测器初始化失败: {e}，将使用规则方法")
            self.ner_predictor = None

        # 关系抽取器
        re_config = self.config.get("relation_extractor", {})
        re_model_path = re_config.get("model_path", None)
        try:
            self.relation_extractor = RelationExtractor(
                model_path=re_model_path,
                pretrained_model=re_config.get("pretrained_model", pretrained),
                threshold=re_config.get("classification_threshold", 0.5),
                device=device,
            )
        except Exception as e:
            logger.warning(f"关系抽取器初始化失败: {e}，将使用规则方法")
            self.relation_extractor = None

        # 知识图谱构建器
        kg_config = self.config.get("knowledge_graph", {})
        neo4j_config = kg_config.get("neo4j", {})
        self.kg_builder = KnowledgeGraphBuilder(
            neo4j_uri=neo4j_config.get("uri", "bolt://localhost:7687"),
            neo4j_username=neo4j_config.get("username", "neo4j"),
            neo4j_password=neo4j_config.get("password", "password"),
            neo4j_database=neo4j_config.get("database", "guji"),
            clear_before_build=kg_config.get("clear_before_build", False),
            batch_size=kg_config.get("batch_insert_size", 500),
        )

        logger.info("流水线所有模块初始化完成")

    def step_clean(self, text: str) -> str:
        """执行文本清洗步骤。

        Args:
            text: 原始文本

        Returns:
            清洗后的文本
        """
        logger.info("步骤 1/5: 文本清洗")
        return self.cleaner.clean(text)

    def step_tokenize(self, text: str) -> Dict:
        """执行分词断句步骤。

        Args:
            text: 清洗后的文本

        Returns:
            分词结果字典
        """
        logger.info("步骤 2/5: 分词断句")
        result = self.tokenizer.process(text)
        return result.to_dict()

    def step_ner(self, text: str) -> List[Dict[str, Any]]:
        """执行命名实体识别步骤。

        Args:
            text: 清洗后的文本

        Returns:
            实体列表
        """
        logger.info("步骤 3/5: 命名实体识别")
        if self.ner_predictor is not None:
            try:
                entities = self.ner_predictor.predict(text)
                return entities
            except Exception as e:
                logger.warning(f"NER预测失败: {e}，使用规则方法")

        # 回退：基于规则的实体识别
        return self._rule_based_ner(text)

    def step_relation_extraction(
        self,
        text: str,
        entities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """执行关系抽取步骤。

        Args:
            text: 清洗后的文本
            entities: 识别到的实体列表

        Returns:
            关系列表
        """
        logger.info("步骤 4/5: 关系抽取")
        if self.relation_extractor is not None:
            try:
                relations = self.relation_extractor.extract(text, entities)
                return [r.to_dict() for r in relations]
            except Exception as e:
                logger.warning(f"关系抽取失败: {e}，使用规则方法")

        # 回退：基于规则的关系抽取
        return self._rule_based_relation_extraction(text, entities)

    def step_build_kg(
        self,
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """执行知识图谱构建步骤。

        Args:
            entities: 实体列表
            relations: 关系列表

        Returns:
            知识图谱统计信息
        """
        logger.info("步骤 5/5: 知识图谱构建")
        stats = self.kg_builder.build(entities, relations)
        return stats

    def run(
        self,
        input_path: str,
        mode: str = "full",
        output_path: Optional[str] = None,
    ) -> PipelineResult:
        """运行流水线。

        Args:
            input_path: 输入文件路径
            mode: 运行模式，可选:
                - "full": 完整流水线
                - "clean": 仅文本清洗
                - "ner": 清洗 + NER
                - "re": 清洗 + NER + 关系抽取
                - "build_kg": 仅构建知识图谱（从标注文件）
            output_path: 结果输出路径

        Returns:
            流水线处理结果
        """
        result = PipelineResult()
        logger.info(f"流水线启动 | 模式: {mode} | 输入: {input_path}")

        # 读取输入
        if os.path.isfile(input_path):
            with open(input_path, "r", encoding="utf-8") as f:
                result.raw_text = f.read()
        else:
            result.raw_text = input_path

        # Step 1: 文本清洗
        if mode in ("full", "clean", "ner", "re"):
            t0 = time.time()
            result.cleaned_text = self.step_clean(result.raw_text)
            result.elapsed_time["文本清洗"] = time.time() - t0

        if mode == "clean":
            self._finalize(result, output_path)
            return result

        # Step 2: 分词断句
        if mode in ("full", "ner", "re"):
            t0 = time.time()
            result.tokenization_result = self.step_tokenize(result.cleaned_text)
            result.elapsed_time["分词断句"] = time.time() - t0

        # Step 3: NER
        if mode in ("full", "ner", "re"):
            t0 = time.time()
            result.entities = self.step_ner(result.cleaned_text)
            result.elapsed_time["命名实体识别"] = time.time() - t0

        if mode == "ner":
            self._finalize(result, output_path)
            return result

        # Step 4: 关系抽取
        if mode in ("full", "re"):
            t0 = time.time()
            result.relations = self.step_relation_extraction(
                result.cleaned_text, result.entities
            )
            result.elapsed_time["关系抽取"] = time.time() - t0

        if mode == "re":
            self._finalize(result, output_path)
            return result

        # Step 5: 知识图谱构建
        if mode in ("full", "build_kg"):
            t0 = time.time()
            if mode == "build_kg":
                # 从标注文件构建
                result.kg_stats = self.kg_builder.build_from_annotated_file(input_path)
            else:
                result.kg_stats = self.step_build_kg(
                    result.entities, result.relations
                )
            result.elapsed_time["知识图谱构建"] = time.time() - t0

        self._finalize(result, output_path)
        return result

    def _finalize(
        self,
        result: PipelineResult,
        output_path: Optional[str] = None,
    ):
        """流水线收尾：输出摘要和保存结果。

        Args:
            result: 处理结果
            output_path: 输出路径
        """
        # 输出摘要
        print(result.summary())

        # 保存结果
        if output_path:
            result.save(output_path)

        logger.info("流水线执行完成")

    def _rule_based_ner(self, text: str) -> List[Dict[str, Any]]:
        """基于规则的命名实体识别（回退方案）。

        使用正则表达式和词典匹配进行简单的实体识别。

        Args:
            text: 输入文本

        Returns:
            识别到的实体列表
        """
        import re

        entities = []

        # 古籍常见官职模式
        office_patterns = [
            r"[\u4e00-\u9fff]{1,4}(?:大夫|尚书|侍郎|郎中|主簿|令尹|丞相|太尉|司徒|司空|左徒|太傅)",
        ]
        for pattern in office_patterns:
            for match in re.finditer(pattern, text):
                entities.append({
                    "text": match.group(),
                    "type": "OFF",
                    "start": match.start(),
                    "end": match.end(),
                })

        # 古籍常见地名模式
        location_patterns = [
            r"(?:长安|洛阳|建康|临安|汴京|咸阳|邯郸|姑苏|楚|秦|赵|魏|韩|齐|燕)",
        ]
        for pattern in location_patterns:
            for match in re.finditer(pattern, text):
                entities.append({
                    "text": match.group(),
                    "type": "LOC",
                    "start": match.start(),
                    "end": match.end(),
                })

        # 古籍常见人名模式（简单规则：X王/X公/X子）
        person_patterns = [
            r"[\u4e00-\u9fff]{1,2}(?:王|公|侯|子|帝)",
            r"(?:屈原|贾生|贾谊|怀王|顷襄王|楚怀王|秦昭王|孝文帝|上官大夫)",
        ]
        for pattern in person_patterns:
            for match in re.finditer(pattern, text):
                # 避免与官职重复
                start, end = match.start(), match.end()
                overlap = any(
                    e["start"] <= start < e["end"] or e["start"] < end <= e["end"]
                    for e in entities
                )
                if not overlap:
                    entities.append({
                        "text": match.group(),
                        "type": "PER",
                        "start": start,
                        "end": end,
                    })

        # 按位置排序
        entities.sort(key=lambda x: x["start"])
        logger.info(f"规则NER识别到 {len(entities)} 个实体")
        return entities

    def _rule_based_relation_extraction(
        self,
        text: str,
        entities: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """基于规则的关系抽取（回退方案）。

        基于实体类型约束和文本模式进行简单的关系判断。

        Args:
            text: 输入文本
            entities: 实体列表

        Returns:
            抽取到的关系列表
        """
        relations = []

        # 类型约束
        type_pairs = {
            ("PER", "OFF"): "任职",
            ("PER", "LOC"): "籍贯",
            ("PER", "EVT"): "事件参与",
            ("PER", "PER"): "亲属",
            ("EVT", "LOC"): "发生于",
        }

        # 为每对满足类型约束的实体创建关系
        for i, e1 in enumerate(entities):
            for j, e2 in enumerate(entities):
                if i >= j:
                    continue
                pair = (e1["type"], e2["type"])
                if pair in type_pairs:
                    # 检查实体距离（距离太远不太可能有关系）
                    distance = abs(e2["start"] - e1["end"])
                    if distance < 50:
                        relations.append({
                            "head": {"text": e1["text"], "type": e1["type"]},
                            "tail": {"text": e2["text"], "type": e2["type"]},
                            "type": type_pairs[pair],
                            "confidence": max(0.3, 1.0 - distance * 0.02),
                        })

                # 反向检查
                reverse_pair = (e2["type"], e1["type"])
                if reverse_pair in type_pairs and reverse_pair != pair:
                    distance = abs(e2["start"] - e1["end"])
                    if distance < 50:
                        relations.append({
                            "head": {"text": e2["text"], "type": e2["type"]},
                            "tail": {"text": e1["text"], "type": e1["type"]},
                            "type": type_pairs[reverse_pair],
                            "confidence": max(0.3, 1.0 - distance * 0.02),
                        })

        logger.info(f"规则关系抽取识别到 {len(relations)} 个关系")
        return relations


def create_pipeline_from_config(config_path: str) -> GuJiPipeline:
    """从配置文件创建流水线。

    Args:
        config_path: 配置文件路径（YAML格式）

    Returns:
        流水线实例
    """
    import yaml

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return GuJiPipeline(config=config)
