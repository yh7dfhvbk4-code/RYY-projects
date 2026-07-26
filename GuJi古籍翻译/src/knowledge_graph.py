"""
古籍知识图谱构建与存储模块
============================

本模块实现了基于Neo4j的知识图谱构建、存储和查询功能，包括：
- Neo4jClient: Neo4j数据库客户端
- KnowledgeGraphBuilder: 知识图谱构建器
- 实体去重与合并
- 批量节点/关系插入
- Cypher查询接口
- 图谱统计与可视化导出

典型用法:
    >>> builder = KnowledgeGraphBuilder()
    >>> entities = [{"text": "屈原", "type": "PER"}, ...]
    >>> relations = [{"head": "屈原", "tail": "左徒", "type": "任职"}, ...]
    >>> builder.build(entities, relations)
    >>> stats = builder.get_statistics()
"""

import json
import os
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from loguru import logger


class Neo4jClient:
    """Neo4j数据库客户端。

    封装Neo4j Python Driver，提供连接管理、查询执行等基础功能。

    Attributes:
        uri: Neo4j连接URI
        username: 用户名
        password: 密码
        database: 数据库名称
        driver: Neo4j Driver实例
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "password",
        database: str = "guji",
        max_connection_pool_size: int = 50,
        connection_timeout: int = 30,
    ):
        """初始化Neo4j客户端。

        Args:
            uri: Neo4j连接URI
            username: 用户名
            password: 密码
            database: 数据库名称
            max_connection_pool_size: 连接池大小
            connection_timeout: 连接超时（秒）
        """
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.driver = None

        try:
            from neo4j import GraphDatabase

            self.driver = GraphDatabase.driver(
                uri,
                auth=(username, password),
                max_connection_pool_size=max_connection_pool_size,
                connection_timeout=connection_timeout,
            )
            # 验证连接
            self.driver.verify_connectivity()
            logger.info(f"Neo4j连接成功: {uri} | 数据库: {database}")
        except ImportError:
            logger.warning(
                "neo4j驱动未安装，知识图谱功能不可用。"
                "可通过 pip install neo4j 安装。"
            )
        except Exception as e:
            logger.warning(f"Neo4j连接失败: {e}，知识图谱功能不可用")

    def is_available(self) -> bool:
        """检查Neo4j连接是否可用。

        Returns:
            连接是否可用
        """
        return self.driver is not None

    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """执行Cypher查询。

        Args:
            query: Cypher查询语句
            parameters: 查询参数

        Returns:
            查询结果列表
        """
        if not self.is_available():
            logger.warning("Neo4j不可用，无法执行查询")
            return []

        parameters = parameters or {}
        try:
            from neo4j import RoutingControl

            records, _, _ = self.driver.execute_query(
                query,
                parameters_=parameters,
                database_=self.database,
                routing_=RoutingControl.READ,
            )
            return [dict(record) for record in records]
        except Exception as e:
            logger.error(f"查询执行失败: {e}")
            return []

    def execute_write(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """执行Cypher写操作。

        Args:
            query: Cypher写语句
            parameters: 写参数

        Returns:
            是否执行成功
        """
        if not self.is_available():
            logger.warning("Neo4j不可用，无法执行写操作")
            return False

        parameters = parameters or {}
        try:
            self.driver.execute_query(
                query,
                parameters_=parameters,
                database_=self.database,
            )
            return True
        except Exception as e:
            logger.error(f"写操作失败: {e}")
            return False

    def close(self):
        """关闭Neo4j连接。"""
        if self.driver is not None:
            self.driver.close()
            logger.info("Neo4j连接已关闭")

    def __del__(self):
        """析构时关闭连接。"""
        self.close()


class KnowledgeGraphBuilder:
    """古籍知识图谱构建器。

    将NER识别的实体和关系抽取的结果整合为知识图谱，
    并存储到Neo4j数据库中。支持实体去重、批量插入和增量更新。

    Attributes:
        neo4j_client: Neo4j客户端
        entity_types: 实体类型列表
        relation_types: 关系类型列表
        dedup_strategy: 去重策略
        batch_size: 批量插入大小
    """

    # 实体类型到Neo4j节点标签的映射
    ENTITY_LABEL_MAP = {
        "PER": "Person",       # 人物
        "LOC": "Location",     # 地点
        "OFF": "Office",       # 官职
        "EVT": "Event",        # 事件
        "ORG": "Organization", # 组织
        "TIME": "Time",        # 时间
    }

    # 关系类型到Neo4j关系类型的映射
    RELATION_LABEL_MAP = {
        "任职": "APPOINTED_AS",
        "籍贯": "BORN_IN",
        "事件参与": "PARTICIPATED_IN",
        "地点位于": "LOCATED_IN",
        "亲属": "RELATED_TO",
        "师承": "TAUGHT_BY",
        "任职于": "WORKS_FOR",
        "发生于": "OCCURRED_AT",
        "发生于时": "OCCURRED_ON",
    }

    def __init__(
        self,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_username: str = "neo4j",
        neo4j_password: str = "password",
        neo4j_database: str = "guji",
        entity_types: Optional[List[str]] = None,
        relation_types: Optional[List[str]] = None,
        dedup_strategy: str = "exact",
        batch_size: int = 500,
        clear_before_build: bool = False,
    ):
        """初始化知识图谱构建器。

        Args:
            neo4j_uri: Neo4j连接URI
            neo4j_username: Neo4j用户名
            neo4j_password: Neo4j密码
            neo4j_database: 数据库名称
            entity_types: 实体类型列表
            relation_types: 关系类型列表
            dedup_strategy: 去重策略 ("exact" 或 "fuzzy")
            batch_size: 批量插入大小
            clear_before_build: 构建前是否清空已有图谱
        """
        self.neo4j_client = Neo4jClient(
            uri=neo4j_uri,
            username=neo4j_username,
            password=neo4j_password,
            database=neo4j_database,
        )
        self.entity_types = entity_types or list(self.ENTITY_LABEL_MAP.keys())
        self.relation_types = relation_types or list(self.RELATION_LABEL_MAP.keys())
        self.dedup_strategy = dedup_strategy
        self.batch_size = batch_size
        self.clear_before_build = clear_before_build

        # 实体缓存（用于去重）
        self._entity_cache: Dict[str, Set[str]] = defaultdict(set)

        logger.info(
            f"知识图谱构建器初始化 | 去重策略: {dedup_strategy} | "
            f"批量大小: {batch_size} | 清空重建: {clear_before_build}"
        )

    def _create_constraints(self):
        """创建Neo4j唯一性约束。

        为每种实体类型创建唯一性约束，确保实体名称唯一，
        这是实体去重的基础。
        """
        if not self.neo4j_client.is_available():
            return

        for entity_type, label in self.ENTITY_LABEL_MAP.items():
            if entity_type in self.entity_types:
                query = (
                    f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) "
                    f"REQUIRE n.name IS UNIQUE"
                )
                self.neo4j_client.execute_write(query)
                logger.debug(f"创建唯一约束: {label}.name")

        logger.info("Neo4j约束创建完成")

    def _clear_graph(self):
        """清空知识图谱中的所有节点和关系。"""
        if not self.neo4j_client.is_available():
            return

        self.neo4j_client.execute_write("MATCH (n) DETACH DELETE n")
        logger.info("知识图谱已清空")

    def _deduplicate_entity(self, entity: Dict[str, Any]) -> str:
        """实体去重。

        根据去重策略判断实体是否已存在，返回唯一标识。

        Args:
            entity: 实体字典，包含 text, type 等字段

        Returns:
            实体的唯一标识
        """
        entity_key = f"{entity['type']}:{entity['text']}"

        if self.dedup_strategy == "exact":
            # 精确匹配：类型+名称完全相同视为同一实体
            if entity_key in self._entity_cache[entity["type"]]:
                return entity_key
            self._entity_cache[entity["type"]].add(entity_key)
            return entity_key
        else:
            # 模糊匹配：暂不实现，回退到精确匹配
            return entity_key

    def add_entities(self, entities: List[Dict[str, Any]]) -> int:
        """向知识图谱添加实体节点。

        支持批量插入，自动去重。

        Args:
            entities: 实体列表，每个实体包含 text, type 字段

        Returns:
            新增实体数量
        """
        if not entities:
            return 0

        # 去重
        unique_entities = []
        for entity in entities:
            entity_key = self._deduplicate_entity(entity)
            if entity_key and entity not in unique_entities:
                unique_entities.append(entity)

        if not unique_entities:
            return 0

        # 批量插入到Neo4j
        added_count = 0
        if self.neo4j_client.is_available():
            for i in range(0, len(unique_entities), self.batch_size):
                batch = unique_entities[i:i + self.batch_size]
                for entity in batch:
                    label = self.ENTITY_LABEL_MAP.get(
                        entity["type"], entity["type"]
                    )
                    query = (
                        f"MERGE (n:{label} {{name: $name}}) "
                        f"SET n.type = $type, n.updated_at = datetime()"
                    )
                    params = {
                        "name": entity["text"],
                        "type": entity["type"],
                    }
                    # 添加额外属性
                    for key, value in entity.items():
                        if key not in ("text", "type", "start", "end", "id"):
                            query += f", n.{key} = ${key}"
                            params[key] = value

                    if self.neo4j_client.execute_write(query, params):
                        added_count += 1

        logger.info(f"添加实体: {added_count} 个（去重前: {len(entities)}）")
        return added_count

    def add_relations(self, relations: List[Dict[str, Any]]) -> int:
        """向知识图谱添加关系边。

        Args:
            relations: 关系列表，每个关系包含 head, tail, type 字段

        Returns:
            新增关系数量
        """
        if not relations:
            return 0

        added_count = 0
        if self.neo4j_client.is_available():
            for relation in relations:
                head = relation["head"]
                tail = relation["tail"]
                rel_type = relation["type"]

                head_label = self.ENTITY_LABEL_MAP.get(
                    head.get("type", ""), head.get("type", "Entity")
                )
                tail_label = self.ENTITY_LABEL_MAP.get(
                    tail.get("type", ""), tail.get("type", "Entity")
                )
                rel_label = self.RELATION_LABEL_MAP.get(rel_type, rel_type)

                # 使用MERGE避免重复关系
                query = (
                    f"MATCH (h:{head_label} {{name: $head_name}}) "
                    f"MATCH (t:{tail_label} {{name: $tail_name}}) "
                    f"MERGE (h)-[r:{rel_label}]->(t) "
                    f"SET r.type = $rel_type, r.updated_at = datetime()"
                )
                params = {
                    "head_name": head.get("text", ""),
                    "tail_name": tail.get("text", ""),
                    "rel_type": rel_type,
                }

                # 添加置信度
                if "confidence" in relation:
                    query += ", r.confidence = $confidence"
                    params["confidence"] = relation["confidence"]

                if self.neo4j_client.execute_write(query, params):
                    added_count += 1

        logger.info(f"添加关系: {added_count} 个")
        return added_count

    def build(
        self,
        entities: List[Dict[str, Any]],
        relations: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        """构建知识图谱。

        完整的图谱构建流程：创建约束 -> (可选)清空 -> 添加实体 -> 添加关系。

        Args:
            entities: 实体列表
            relations: 关系列表

        Returns:
            构建统计信息，包含 entity_count 和 relation_count
        """
        logger.info(f"开始构建知识图谱 | 实体数: {len(entities)} | 关系数: {len(relations)}")

        # 创建约束
        self._create_constraints()

        # 可选：清空已有图谱
        if self.clear_before_build:
            self._clear_graph()

        # 添加实体
        entity_count = self.add_entities(entities)

        # 添加关系
        relation_count = self.add_relations(relations)

        stats = {"entity_count": entity_count, "relation_count": relation_count}
        logger.info(f"知识图谱构建完成: {stats}")
        return stats

    def build_from_annotated_file(self, file_path: str) -> Dict[str, int]:
        """从标注文件构建知识图谱。

        Args:
            file_path: 标注文件路径

        Returns:
            构建统计信息
        """
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        all_entities = []
        all_relations = []

        for doc in data.get("documents", []):
            # 收集实体
            for entity in doc.get("entities", []):
                all_entities.append({
                    "text": entity["text"],
                    "type": entity["type"],
                    "id": entity.get("id", ""),
                })

            # 收集关系
            entity_map = {e.get("id", f"e{i}"): e
                          for i, e in enumerate(doc.get("entities", []))}
            for relation in doc.get("relations", []):
                head_entity = entity_map.get(relation.get("head", ""), {})
                tail_entity = entity_map.get(relation.get("tail", ""), {})
                if head_entity and tail_entity:
                    all_relations.append({
                        "head": head_entity,
                        "tail": tail_entity,
                        "type": relation["type"],
                    })

        return self.build(all_entities, all_relations)

    def query_entity(
        self,
        entity_name: str,
        entity_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """查询实体及其关联信息。

        Args:
            entity_name: 实体名称
            entity_type: 实体类型（可选）

        Returns:
            查询结果列表
        """
        if entity_type:
            label = self.ENTITY_LABEL_MAP.get(entity_type, entity_type)
            query = f"MATCH (n:{label})-[]-(m) WHERE n.name = $name RETURN n, m"
        else:
            query = "MATCH (n)-[]-(m) WHERE n.name = $name RETURN n, m"

        return self.neo4j_client.execute_query(query, {"name": entity_name})

    def query_relations(
        self,
        head_name: Optional[str] = None,
        tail_name: Optional[str] = None,
        relation_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """查询关系。

        Args:
            head_name: 头实体名称（可选）
            tail_name: 尾实体名称（可选）
            relation_type: 关系类型（可选）
            limit: 返回结果上限

        Returns:
            关系查询结果列表
        """
        conditions = []
        params = {}

        if head_name:
            conditions.append("h.name = $head_name")
            params["head_name"] = head_name
        if tail_name:
            conditions.append("t.name = $tail_name")
            params["tail_name"] = tail_name

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

        rel_match = f":{self.RELATION_LABEL_MAP.get(relation_type, relation_type)}" if relation_type else ""

        query = (
            f"MATCH (h)-[r{rel_match}]->(t) "
            f"{where_clause} "
            f"RETURN h.name AS head, type(r) AS relation, t.name AS tail "
            f"LIMIT {limit}"
        )

        return self.neo4j_client.execute_query(query, params)

    def get_statistics(self) -> Dict[str, Any]:
        """获取知识图谱统计信息。

        Returns:
            统计信息字典，包含节点数、关系数、各类型分布等
        """
        stats = {
            "total_nodes": 0,
            "total_relations": 0,
            "node_by_type": {},
            "relation_by_type": {},
        }

        if not self.neo4j_client.is_available():
            return stats

        # 总节点数
        result = self.neo4j_client.execute_query(
            "MATCH (n) RETURN count(n) AS count"
        )
        if result:
            stats["total_nodes"] = result[0].get("count", 0)

        # 总关系数
        result = self.neo4j_client.execute_query(
            "MATCH ()-[r]->() RETURN count(r) AS count"
        )
        if result:
            stats["total_relations"] = result[0].get("count", 0)

        # 各类型节点数
        for entity_type, label in self.ENTITY_LABEL_MAP.items():
            result = self.neo4j_client.execute_query(
                f"MATCH (n:{label}) RETURN count(n) AS count"
            )
            if result:
                stats["node_by_type"][entity_type] = result[0].get("count", 0)

        # 各类型关系数
        for rel_type, label in self.RELATION_LABEL_MAP.items():
            result = self.neo4j_client.execute_query(
                f"MATCH ()-[r:{label}]->() RETURN count(r) AS count"
            )
            if result:
                stats["relation_by_type"][rel_type] = result[0].get("count", 0)

        logger.info(f"知识图谱统计: {stats}")
        return stats

    def export_to_json(self, output_path: str) -> str:
        """将知识图谱导出为JSON格式。

        Args:
            output_path: 输出文件路径

        Returns:
            输出文件路径
        """
        if not self.neo4j_client.is_available():
            logger.warning("Neo4j不可用，无法导出")
            return ""

        # 导出所有节点
        nodes = self.neo4j_client.execute_query(
            "MATCH (n) RETURN n.name AS name, labels(n) AS labels, properties(n) AS props"
        )

        # 导出所有关系
        edges = self.neo4j_client.execute_query(
            "MATCH (h)-[r]->(t) RETURN h.name AS head, type(r) AS relation, t.name AS tail, properties(r) AS props"
        )

        export_data = {
            "nodes": [
                {"name": n["name"], "labels": n["labels"], "properties": n["props"]}
                for n in nodes
            ],
            "edges": [
                {"head": e["head"], "relation": e["relation"],
                 "tail": e["tail"], "properties": e["props"]}
                for e in edges
            ],
        }

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        logger.info(f"知识图谱已导出至: {output_path}")
        return output_path

    def close(self):
        """关闭连接。"""
        self.neo4j_client.close()

    def __del__(self):
        """析构时关闭连接。"""
        self.close()


def build_knowledge_graph_from_results(
    entities: List[Dict[str, Any]],
    relations: List[Dict[str, Any]],
    neo4j_config: Optional[Dict[str, Any]] = None,
    output_json: Optional[str] = None,
) -> KnowledgeGraphBuilder:
    """从NER和关系抽取结果构建知识图谱的便捷函数。

    Args:
        entities: 实体列表
        relations: 关系列表
        neo4j_config: Neo4j连接配置
        output_json: JSON导出路径（可选）

    Returns:
        知识图谱构建器实例
    """
    config = neo4j_config or {}
    builder = KnowledgeGraphBuilder(**config)
    builder.build(entities, relations)

    if output_json:
        builder.export_to_json(output_json)

    return builder
