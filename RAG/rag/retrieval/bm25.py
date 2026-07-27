"""BM25 关键词召回（rank_bm25 + jieba 中文分词，JSON 落盘）。"""
import json
from pathlib import Path

import jieba
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from rag import config


def _tokenize(text: str) -> list[str]:
    """jieba 分词，过滤空白与单字符标点。"""
    return [w for w in jieba.lcut(text.lower()) if w.strip()]


class BM25Index:
    """BM25 索引：内存中保存文档与索引，支持落盘/加载。"""

    def __init__(self) -> None:
        self._docs: list[Document] = []
        self._index: BM25Okapi | None = None

    def build(self, docs: list[Document]) -> None:
        """从文档列表构建索引。"""
        self._docs = docs
        tokenized = [_tokenize(d.page_content) for d in docs]
        self._index = BM25Okapi(tokenized) if tokenized else None

    def search(self, query: str, top_k: int | None = None) -> list[Document]:
        """关键词召回，按 BM25 得分降序返回。"""
        if self._index is None:
            return []
        k = top_k or config.BM25_TOP_K
        scores = self._index.get_scores(_tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        return [self._docs[i] for i in ranked[:k] if scores[i] > 0]

    def save(self, path: Path | None = None) -> None:
        """落盘文档与分词结果（JSON，避免 pickle 反序列化风险）。"""
        path = path or config.BM25_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        tokenized = [_tokenize(d.page_content) for d in self._docs]
        payload = {
            "docs": [
                {"page_content": d.page_content, "metadata": d.metadata}
                for d in self._docs
            ],
            "tokenized": tokenized,
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)  # 原子替换

    @classmethod
    def load(cls, path: Path | None = None) -> "BM25Index":
        """从磁盘加载；不存在时返回空索引。"""
        path = path or config.BM25_PATH
        instance = cls()
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            instance._docs = [
                Document(page_content=d["page_content"], metadata=d["metadata"])
                for d in payload["docs"]
            ]
            tokenized = payload["tokenized"]
            instance._index = BM25Okapi(tokenized) if tokenized else None
        return instance

    @property
    def size(self) -> int:
        return len(self._docs)
