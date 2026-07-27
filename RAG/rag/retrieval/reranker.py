"""本地重排模型封装（bge-reranker-base，懒加载单例）。"""
from functools import lru_cache

from langchain_core.documents import Document
from sentence_transformers import CrossEncoder

from rag import config


@lru_cache(maxsize=1)
def _get_reranker() -> CrossEncoder:
    return CrossEncoder(config.RERANKER_MODEL, device=config.RERANKER_DEVICE)


def rerank(
    query: str, docs: list[Document], top_n: int | None = None
) -> list[tuple[Document, float]]:
    """对候选分片重排，返回 (Document, score) 列表，按相关性降序取 top_n。"""
    if not docs:
        return []
    n = top_n or config.RERANK_TOP_N
    model = _get_reranker()
    pairs = [(query, doc.page_content) for doc in docs]
    scores = model.predict(pairs)
    ranked = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
    return [(doc, float(score)) for doc, score in ranked[:n]]
