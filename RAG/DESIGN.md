# RAG 系统设计文档

## 1. 项目概述

个人知识库 RAG（Retrieval-Augmented Generation）系统，作为后续个人 Agent 的知识库组件使用。

| 维度 | 结论 |
|---|---|
| 定位 | 实际落地型，供后续个人 Agent 集成 |
| 数据 | 个人知识库：基本信息、学业经历、项目资料（Word / PPT / PDF / Excel / 网页 / 代码 / Markdown），中小规模 |
| 技术栈 | Python + LangChain |
| Embedding | 本地模型（GPU：RTX 4050 Laptop 6GB） |
| LLM | 云端 API：DeepSeek 为主，可切换 OpenAI；API key 运行时传入（前端输入） |
| 向量数据库 | Chroma（本地持久化，零部署） |
| 召回策略 | 混合召回（向量 + BM25）+ Rerank 重排 |
| 交付形态 | 可导入的 Python 包 + 简单 CLI |

## 2. 整体架构

系统分为两大部分：

### 2.1 对话前（离线，Ingestion Pipeline）

负责**分片**与**索引**：

```
原始文档(data/)
   │
   ▼
文档加载/解析（loaders，按扩展名分发）
   │
   ▼
文本清洗（去空白、去页眉页脚噪声等）
   │
   ▼
分片 chunking（按文档类型选择策略）
   │
   ├──→ Embedding（bge-m3，本地 GPU）──→ 写入 Chroma（storage/chroma）
   │
   └──→ 分词（jieba）──→ 构建 BM25 索引 ──→ 落盘（storage/bm25.json）
```

### 2.2 对话后（在线，Query Pipeline）

负责**召回、重排、生成**：

```
用户问题
   │
   ├──→ 向量召回 top-k=20 ──┐
   │                        ├──→ RRF 合并去重 ──→ Rerank 重排（bge-reranker-base）──→ top-n=5
   └──→ BM25 召回 top-k=20 ─┘
                                                            │
                                                            ▼
                                              拼装 Prompt（上下文 + 来源标注）
                                                            │
                                                            ▼
                                                  LLM 生成答案（DeepSeek / OpenAI）
                                                            │
                                                            ▼
                                              返回答案 + 引用来源（source / chunk）
```

## 3. 目录结构

```
RAG/
├── DESIGN.md                  # 本文档
├── requirements.txt
├── cli.py                     # CLI 入口：build / query / stats
├── rag/
│   ├── __init__.py            # 对外暴露 RAGEngine
│   ├── config.py              # 集中配置（路径、模型名、top-k 等）
│   ├── engine.py              # RAGEngine：query() 主入口
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── loaders.py         # 多格式文档加载（docx/pptx/pdf/xlsx/html/md/代码/txt）
│   │   ├── chunking.py        # 分片策略（按文件类型分发）
│   │   └── pipeline.py        # 建库流水线（全量 + 增量更新）
│   ├── retrieval/
│   │   ├── __init__.py
│   │   ├── embeddings.py      # 本地 bge-m3 Embedding 封装（LangChain Embeddings 接口）
│   │   ├── vector_store.py    # Chroma 封装（PersistentClient）
│   │   ├── bm25.py            # BM25 索引（rank-bm25 + jieba，JSON 落盘）
│   │   ├── hybrid.py          # 混合召回 + RRF 融合
│   │   └── reranker.py        # bge-reranker-base 本地重排
│   └── generation/
│       ├── __init__.py
│       ├── llm.py             # LLM 封装（DeepSeek / OpenAI 可切换）
│       └── prompts.py         # Prompt 模板
├── data/                      # 原始文档（用户放入）
└── storage/                   # 索引持久化（chroma/、bm25.json、catalog.json）
```

## 4. 关键选型

| 组件 | 选型 | 理由 |
|---|---|---|
| Embedding | `BAAI/bge-m3`（HuggingFace 本地加载） | 中英双语效果好，支持长文本，约 2GB 显存，4050 6GB 可承担 |
| Reranker | `BAAI/bge-reranker-base`（本地 CPU） | v2-m3（2.27GB）超出本机显存/内存限制，改用 base（~1.1GB），实测重排区分度良好（见 HANDOFF.md 坑 7/8） |
| 向量库 | Chroma `PersistentClient` | 零部署，数据落盘 `storage/chroma`，LangChain 集成成熟 |
| BM25 | `rank-bm25` + `jieba` 分词 | 中文必须先分词；索引随建库生成并落盘 |
| 文档加载 | LangChain Community Loaders | 按扩展名分发：`.docx→Docx2txtLoader`、`.pptx→UnstructuredPowerPointLoader`、`.pdf→PyMuPDFLoader`、`.xlsx→UnstructuredExcelLoader`、`.html→BSHTMLLoader`、`.md/.txt→TextLoader`、代码→`TextLoader`+语言感知分片 |
| LLM | DeepSeek API（`deepseek-chat`，OpenAI 兼容协议） | 更换 `base_url`/`model` 即可切到 OpenAI；key 运行时传入 |

## 5. 分片策略（按文件类型）

| 类型 | 策略 | 参数 |
|---|---|---|
| Markdown / 笔记 | `MarkdownHeaderTextSplitter` 按标题层级切，再做长度二次切分 | 标题路径写入 metadata |
| PDF / Word / PPT / Excel / 网页 | `RecursiveCharacterTextSplitter` | chunk_size=500，chunk_overlap=50 |
| 代码 | `RecursiveCharacterTextSplitter.from_language()` 按语言切 | 依扩展名映射语言 |

每个分片的 metadata：

| 字段 | 说明 |
|---|---|
| `source` | 源文件相对路径 |
| `file_type` | 扩展名 |
| `chunk_id` | `{source}#{序号}`，全局唯一 |
| `title_path` | Markdown 标题路径（如有） |
| `file_mtime` | 文件修改时间（增量更新用） |

## 6. 检索与生成流程（对话后）

1. **召回**：向量 top-20 ＋ BM25 top-20，两路并行
2. **融合**：RRF（Reciprocal Rank Fusion，`k=60`）合并去重
3. **重排**：bge-reranker-base 对候选打分，取 top-5
4. **生成**：top-5 分片填入 Prompt；要求 LLM：
   - 仅基于给定上下文回答
   - 答案中标注来源（文件名）
   - 上下文不足时明确回答"知识库中没有相关信息"
5. **返回**：`{answer, sources: [{source, chunk_id, score}]}`

## 7. 增量更新

- 维护 `storage/catalog.json`：`{文件路径: {mtime, chunk_ids}}`
- `build` 时对比文件 mtime：新增/变更的文件重新分片入库，并先删除旧 chunk；未变化的跳过
- BM25 索引在文档集变化后整体重建（中小规模成本可接受）

## 8. 配置与密钥管理

- `rag/config.py` 集中管理：路径、模型名、chunk 参数、top-k/top-n、RRF k 等常量
- **API key 不落盘、不硬编码**：`RAGEngine(api_key=..., base_url=..., model=...)` 运行时传入，或读取环境变量 `LLM_API_KEY`——为后续前端传入 key 预留
- LLM 切换：DeepSeek 与 OpenAI 均为 OpenAI 兼容协议，改 `base_url` + `model` 即可

## 9. CLI 设计

```powershell
python cli.py build            # 扫描 data/ 建库（全量/增量自动判断）
python cli.py build --force    # 强制全量重建
python cli.py query "你的问题"  # 问答（召回→重排→生成，打印答案与来源）
python cli.py stats            # 查看库状态（文档数、分片数、最近建库时间）
```

## 10. 依赖（requirements.txt）

```
langchain>=1.3.0
langchain-community>=0.4.0
langchain-huggingface>=1.2.0
langchain-chroma>=1.1.0
langchain-text-splitters>=1.1.0
chromadb>=1.5.0
sentence-transformers==3.3.1
transformers==4.46.3
tokenizers==0.20.3
huggingface-hub==0.36.2
torch>=2.5.0
rank-bm25>=0.2.2
jieba>=0.42.1
openai>=2.0.0
docx2txt>=0.9
pymupdf>=1.28.0
unstructured>=0.24.0
beautifulsoup4>=4.12.0
lxml>=5.0.0
```

## 11. 后续扩展（不在本次交付）

- 前端交互界面（API key 由前端输入 → `RAGEngine(api_key=...)`）
- FastAPI 后端封装
- 多轮对话 query 改写
- 与 Agent 框架集成
