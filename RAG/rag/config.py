"""RAG 系统集中配置。

所有可调参数集中在此，API key 不在此处配置（运行时传入或环境变量）。
"""
from pathlib import Path

# ---------- 路径 ----------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"                  # 原始文档目录
STORAGE_DIR = BASE_DIR / "storage"            # 索引持久化目录
CHROMA_DIR = STORAGE_DIR / "chroma"           # Chroma 持久化目录
BM25_PATH = STORAGE_DIR / "bm25.json"      # BM25 索引落盘路径
CATALOG_PATH = STORAGE_DIR / "catalog.json"   # 文件目录（增量更新用）

# ---------- 模型 ----------
EMBEDDING_MODEL = "BAAI/bge-m3"               # 本地 Embedding 模型
RERANKER_MODEL = "BAAI/bge-reranker-base"     # 本地重排模型（v2-m3 体积过大，见 HANDOFF.md 坑 8）
EMBEDDING_DEVICE = "cuda"                     # 无 GPU 时改为 "cpu"
RERANKER_DEVICE = "cpu"                       # 6GB 显存下与 embedding 共存易 OOM/崩溃，候选量小 CPU 足够

# ---------- 分片 ----------
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
assert CHUNK_OVERLAP < CHUNK_SIZE, "CHUNK_OVERLAP 必须小于 CHUNK_SIZE"

# ---------- 检索 ----------
VECTOR_TOP_K = 20      # 向量召回数量
BM25_TOP_K = 20        # BM25 召回数量
RRF_K = 60             # RRF 融合常数
RERANK_TOP_N = 5       # 重排后送入生成的分片数

# ---------- LLM ----------
# DeepSeek 与 OpenAI 均为 OpenAI 兼容协议，改 base_url + model 即可切换
LLM_BASE_URL = "https://api.deepseek.com"
LLM_MODEL = "deepseek-chat"
LLM_TEMPERATURE = 0.3
LLM_MAX_TOKENS = 2048

# ---------- Chroma ----------
COLLECTION_NAME = "personal_kb"
