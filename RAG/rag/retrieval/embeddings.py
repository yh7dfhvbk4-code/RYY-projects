"""本地 Embedding 模型封装（bge-m3，懒加载单例）。"""
from functools import lru_cache

from langchain_huggingface import HuggingFaceEmbeddings

from rag import config


@lru_cache(maxsize=1)
def get_embeddings() -> HuggingFaceEmbeddings:
    """加载本地 bge-m3 模型（首次调用时加载，之后复用）。"""
    return HuggingFaceEmbeddings(
        model_name=config.EMBEDDING_MODEL,
        model_kwargs={"device": config.EMBEDDING_DEVICE},
        encode_kwargs={"normalize_embeddings": True},
    )
