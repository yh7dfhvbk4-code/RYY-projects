"""个人知识库 RAG 系统。

对外主入口：RAGEngine
    from rag import RAGEngine
    engine = RAGEngine(api_key="sk-...")
    result = engine.query("我的毕业院校是？")
"""
from rag.engine import RAGEngine

__all__ = ["RAGEngine"]
