"""Chroma 向量库封装（PersistentClient，本地落盘）。"""
from functools import lru_cache

from langchain_chroma import Chroma
from langchain_core.documents import Document

from rag import config
from rag.retrieval.embeddings import get_embeddings


@lru_cache(maxsize=1)
def get_vector_store() -> Chroma:
    """获取（或创建）持久化 Chroma 集合（单例缓存，避免重复建立连接）。"""
    config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name=config.COLLECTION_NAME,
        embedding_function=get_embeddings(),
        persist_directory=str(config.CHROMA_DIR),
    )


def add_chunks(chunks: list[Document]) -> None:
    """写入分片，以 chunk_id 作为文档 ID（重复写入会报错，调用方需先删除旧分片）。"""
    if not chunks:
        return
    store = get_vector_store()
    ids = [c.metadata["chunk_id"] for c in chunks]
    store.add_documents(chunks, ids=ids)


def delete_by_source(source: str) -> None:
    """删除某源文件的所有分片。"""
    store = get_vector_store()
    existing = store.get(where={"source": source})
    if not existing["ids"]:
        return
    store.delete(ids=existing["ids"])


def vector_search(query: str, top_k: int | None = None) -> list[tuple[Document, float]]:
    """向量召回，返回 (Document, distance) 列表。

    distance 为 Chroma L2 距离，越小越相似（非相似度分数）。
    """
    store = get_vector_store()
    return store.similarity_search_with_score(query, k=top_k or config.VECTOR_TOP_K)


def get_all_documents() -> list[Document]:
    """取出库中全部文档（用于重建 BM25 索引）。"""
    store = get_vector_store()
    data = store.get(include=["documents", "metadatas"])
    return [
        Document(page_content=text, metadata=meta or {})
        for text, meta in zip(data["documents"], data["metadatas"])
    ]


def count() -> int:
    """库中分片总数。"""
    store = get_vector_store()
    return len(store.get(include=[])["ids"])


def clear() -> None:
    """清空集合（强制全量重建用）。"""
    store = get_vector_store()
    data = store.get(include=[])
    if data["ids"]:
        store.delete(ids=data["ids"])
