"""RAGEngine：对外主入口，串起 召回 → 重排 → 生成 全流程。"""
from rag import config
from rag.generation.llm import LLMClient
from rag.generation.prompts import USER_PROMPT_TEMPLATE, build_context
from rag.ingestion.pipeline import build_index
from rag.retrieval.bm25 import BM25Index
from rag.retrieval.hybrid import hybrid_retrieve
from rag.retrieval.reranker import rerank


class RAGEngine:
    """个人知识库 RAG 引擎。

    用法：
        engine = RAGEngine(api_key="sk-...")   # 或环境变量 LLM_API_KEY
        engine.build()                          # 建库（增量）
        result = engine.query("我的毕业院校是？")
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self._llm_args = {"api_key": api_key, "base_url": base_url, "model": model}
        self._llm: LLMClient | None = None
        self._bm25: BM25Index | None = None

    # ---------- 对话前：分片与索引 ----------

    def build(self, force: bool = False, verbose: bool = True) -> dict:
        """构建/更新索引（分片 + Embedding 入库 + BM25）。force=True 强制全量重建。"""
        stats = build_index(force=force, verbose=verbose)
        self._bm25 = None  # 索引已更新，下次检索时重新加载
        return stats

    # ---------- 对话后：召回、重排、生成 ----------

    def retrieve(self, question: str, top_n: int | None = None) -> list:
        """混合召回 + 重排，返回 (Document, rerank_score) 列表。"""
        if not question or not question.strip():
            return []
        if self._bm25 is None:
            self._bm25 = BM25Index.load()
        candidates = hybrid_retrieve(question, self._bm25)
        return rerank(question, candidates, top_n=top_n)

    def query(self, question: str, top_n: int | None = None) -> dict:
        """完整 RAG：召回 -> 重排 -> 生成。返回 {answer, sources}。"""
        ranked = self.retrieve(question, top_n=top_n)
        if not ranked:
            return {
                "answer": "未检索到相关内容（问题为空或知识库为空），请确认问题非空或先运行 build 建库。",
                "sources": [],
            }

        context = build_context(ranked)
        answer = self._get_llm().generate(
            USER_PROMPT_TEMPLATE.format(context=context, question=question)
        )
        sources = [
            {
                "source": doc.metadata.get("source", ""),
                "chunk_id": doc.metadata.get("chunk_id", ""),
                "score": round(score, 4),
            }
            for doc, score in ranked
        ]
        return {"answer": answer, "sources": sources}

    def stats(self) -> dict:
        """库状态概览。"""
        from rag.ingestion.pipeline import load_catalog
        from rag.retrieval import vector_store

        catalog = load_catalog()
        return {
            "files_indexed": len(catalog),
            "chunks_total": vector_store.count(),
            "storage_dir": str(config.STORAGE_DIR),
        }

    # ---------- 内部 ----------

    def _get_llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = LLMClient(**self._llm_args)
        return self._llm
