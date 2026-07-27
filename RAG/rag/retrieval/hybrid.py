"""混合召回：向量召回 + BM25 召回，RRF 融合排序。"""
import hashlib

from langchain_core.documents import Document

from rag import config
from rag.retrieval import vector_store
from rag.retrieval.bm25 import BM25Index


def _doc_key(doc: Document) -> str:
    """以 chunk_id 去重；缺失时退化为内容哈希（md5，跨进程稳定）。"""
    return doc.metadata.get("chunk_id") or hashlib.md5(
        doc.page_content.encode()
    ).hexdigest()


def rrf_fuse(
    result_lists: list[list[Document]], k: int | None = None
) -> list[Document]:
    """Reciprocal Rank Fusion：score = Σ 1/(k + rank)，按得分降序返回去重后的文档。"""
    k = k or config.RRF_K
    scores: dict[str, float] = {}
    docs: dict[str, Document] = {}
    for results in result_lists:
        for rank, doc in enumerate(results):
            key = _doc_key(doc)
            docs.setdefault(key, doc)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
    ranked = sorted(scores, key=lambda key: scores[key], reverse=True)
    return [docs[key] for key in ranked]


def hybrid_retrieve(
    query: str,
    bm25_index: BM25Index,
    vector_top_k: int | None = None,
    bm25_top_k: int | None = None,
) -> list[Document]:
    """两路召回 + RRF 融合，返回融合排序后的候选分片。"""
    vector_hits = vector_store.vector_search(query, top_k=vector_top_k)
    vector_docs = [doc for doc, _ in vector_hits]
    bm25_docs = bm25_index.search(query, top_k=bm25_top_k)
    return rrf_fuse([vector_docs, bm25_docs])
