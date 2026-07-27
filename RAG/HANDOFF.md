# RAG 系统交接文档

> 个人知识库 RAG（Retrieval-Augmented Generation）系统。项目已端到端验证通过（build / retrieve / query / stats 全部跑通），并经过多轮代码审查修复。

---

## 1. 我们在做什么

### 1.1 项目定位

构建一个**个人知识库 RAG 系统**，作为后续个人 Agent 的知识库组件。支持多格式文档（Markdown / 代码 / PDF / Word / PPT / Excel / HTML）的增量索引，采用「混合检索 + 重排 + LLM 生成」的完整流程。

- **交付形态**：可导入的 Python 包（`from rag import RAGEngine`）+ CLI 工具
- **数据规模**：个人知识库（基本信息、学业经历、项目资料），中小规模
- **硬件环境**：RTX 4050 Laptop 6GB 显存 / 16GB 内存 / Windows

### 1.2 系统架构

系统按"对话前 / 对话后"分为两条流水线，解耦离线索引与在线问答。

**对话前（离线，Ingestion Pipeline）-- 分片与索引：**

```
原始文档(data/)
   │
   ▼
文档加载/解析（loaders.py，按扩展名分发到对应 LangChain Loader）
   │
   ▼
文本清洗（去首尾空白、过滤空文档）
   │
   ▼
分片 chunking（chunking.py，按文件类型选择策略）
   │
   ├──-> Embedding（bge-m3，本地 GPU）──-> 写入 Chroma（storage/chroma）
   │
   └──-> jieba 分词 ──-> 构建 BM25 索引 ──-> 落盘（storage/bm25.json）
```

- 增量更新：`storage/catalog.json` 记录每个文件的 mtime 与 chunk_count；`build` 时只处理新增/变更/删除的文件。
- BM25 在文档集变化后整体重建（中小规模成本可接受）。

**对话后（在线，Query Pipeline）-- 召回、重排、生成：**

```
用户问题
   │
   ├──-> 向量召回 top-20 ──┐
   │                        ├──-> RRF 合并去重 ──-> Rerank 重排 ──-> top-5
   └──-> BM25 召回 top-20 ─┘
                                                        │
                                                        ▼
                                          拼装 Prompt（上下文 + 来源标注）
                                                        │
                                                        ▼
                                              LLM 生成答案（DeepSeek / OpenAI）
                                                        │
                                                        ▼
                                          返回 {answer, sources:[{source,chunk_id,score}]}
```

- 两路召回互补：向量召回擅长语义相似，BM25 擅长人名/项目名/专有名词精确匹配。
- RRF（Reciprocal Rank Fusion，k=60）合并去重后送重排模型，取 top-5 填入 Prompt。

### 1.3 技术栈与模型选型

| 组件 | 选型 | 版本约束 | 理由 |
|---|---|---|---|
| 语言 | Python | 3.12 | 生态成熟 |
| 编排框架 | LangChain | >=1.3.0 | 文档加载器/分片器/检索器现成 |
| 向量库 | Chroma（`PersistentClient`） | >=1.5.0 | 零部署，本地落盘 |
| BM25 | `rank-bm25` + `jieba` | >=0.2.2 / >=0.42.1 | 中文必须先分词 |
| Embedding | `BAAI/bge-m3` | 本地 GPU（cuda） | 中英双语强，1024 维，约 2GB 显存 |
| Reranker | `BAAI/bge-reranker-base` | 本地 CPU | ~1.1GB，6GB 显存下与 embedding 共存易 OOM，CPU 足够 |
| LLM | DeepSeek API（`deepseek-chat`） | 云端 | OpenAI 兼容协议，改 `base_url`+`model` 即切 OpenAI |

**关键库版本锁定（重要，不要随意升级，详见第 2 节坑 3/5）：**

```
sentence-transformers==3.3.1   # 5.x 与 transformers 5.x 同进程双模型必段错误
transformers==4.46.3           # 5.x 加载 .bin 权重要求 torch>=2.6，陷阱多
tokenizers==0.20.3             # 配合 transformers 4.46
huggingface-hub==0.36.2        # 配合上述版本
torch>=2.5.0,<2.6.0            # cu121 稳定可用；需从 PyTorch 官方索引安装
```

### 1.4 目录结构

```
RAG/
├── DESIGN.md                  # 完整设计文档
├── HANDOFF.md                 # 本文档
├── requirements.txt
├── .gitignore                 # 忽略 .venv/、__pycache__/、storage/
├── cli.py                     # CLI 入口：build / query / retrieve / stats
├── rag/
│   ├── config.py              # 集中配置（路径/模型名/top-k 等，API key 不在此）
│   ├── engine.py              # RAGEngine：build() / retrieve() / query() / stats()
│   ├── ingestion/
│   │   ├── loaders.py         # 多格式文档加载（按扩展名分发）
│   │   ├── chunking.py        # 分片策略（按文件类型分发，Markdown 按标题 h1-h6）
│   │   └── pipeline.py        # 建库流水线（全量 + 增量更新，原子写 catalog）
│   ├── retrieval/
│   │   ├── embeddings.py      # bge-m3 本地 Embedding（懒加载单例）
│   │   ├── vector_store.py    # Chroma 封装（PersistentClient，单例缓存）
│   │   ├── bm25.py            # BM25 索引（rank-bm25 + jieba，JSON 原子落盘）
│   │   ├── hybrid.py          # 混合召回 + RRF 融合（md5 内容去重）
│   │   └── reranker.py        # bge-reranker-base 本地重排（懒加载单例）
│   └── generation/
│       ├── llm.py             # LLM 封装（OpenAI 兼容，max_retries=3，错误上下文包装）
│       └── prompts.py         # Prompt 模板
├── data/                      # 原始文档（用户放入）
├── storage/                   # 索引持久化（chroma/、bm25.json、catalog.json）
└── .venv/                     # 项目虚拟环境
```

### 1.5 环境配置与运行

**标准运行环境（所有 python 命令都要带）：**

```powershell
# 运行（模型已在本地缓存）
$env:PYTHONDONTWRITEBYTECODE='1'; $env:HF_HUB_OFFLINE='1'; $env:TRANSFORMERS_OFFLINE='1'
.\.venv\Scripts\python.exe cli.py <build|retrieve|query|stats>

# 下载模型时改为（去掉 OFFLINE，加镜像和禁 xet）
$env:PYTHONDONTWRITEBYTECODE='1'; $env:HF_ENDPOINT='https://hf-mirror.com'; $env:HF_HUB_DISABLE_XET='1'
```

**CLI 用法：**

```powershell
.\.venv\Scripts\python.exe cli.py build              # 扫描 data/ 建库（增量）
.\.venv\Scripts\python.exe cli.py build --force      # 强制全量重建
.\.venv\Scripts\python.exe cli.py retrieve "问题"     # 仅召回+重排（不调 LLM，调试检索效果）
.\.venv\Scripts\python.exe cli.py retrieve "问题" --top-n 3   # 自定义返回数量
.\.venv\Scripts\python.exe cli.py query "问题" --api-key "sk-..."  # 完整问答
.\.venv\Scripts\python.exe cli.py query "问题" --api-key "sk-..." --top-n 3  # 自定义送入生成分片数
.\.venv\Scripts\python.exe cli.py stats              # 库状态
```

**配置与密钥管理：**

- `rag/config.py` 集中管理路径、模型名、chunk 参数、top-k/top-n、RRF k 等。
- **API key 不落盘、不硬编码**：`RAGEngine(api_key=..., base_url=..., model=...)` 运行时传入，或读环境变量 `LLM_API_KEY`。

### 1.6 当前状态

- 全部代码完成并通过语法检查 + 功能验证
- 环境：`.venv`（Python 3.12 + torch 2.5.1+cu121 + ST 3.3.1 + transformers 4.46.3）
- 模型：bge-m3（GPU）+ bge-reranker-base（CPU）已下载并验证
- 端到端验证：build（6 分片）-> retrieve -> query 全部跑通
- 经过多轮代码审查，已知问题均已修复（详见第 3 节）

---

## 2. 踩过的坑绝对不要再踩

### 2.1 环境与沙箱

**坑 1：沙箱禁止写系统 Python 目录的 `.pyc`**

- **现象**：进程被直接 kill（exit 1），日志末尾出现 `TRAE Sandbox Error: hit restricted ... .pyc`。
- **避免**：运行任何 venv python 命令前**必须**设 `$env:PYTHONDONTWRITEBYTECODE='1'`。

**坑 2：沙箱禁止 pip 写入用户/系统 site-packages**

- **现象**：`pip install` 报 `WinError 5 拒绝访问`。
- **避免**：系统 Python 不可装包；用项目内 `.venv`（`python -m venv .venv`），已建好不要重建。

### 2.2 模型版本（最关键，升一次崩一次）

**坑 3：transformers 5.x 加载 .bin 权重要求 torch>=2.6**

- **现象**：`ValueError: ... require users to upgrade torch to at least v2.6 ... CVE-2025-32434`。
- **根因**：transformers 5.x 出于安全限制，`torch.load` 加载 `.bin` 时强制要求 torch>=2.6；而 Windows 上 cu124 的 torch 2.6+ 下载极慢（2.5GB）且会停滞。
- **避免**：**锁定 `transformers==4.46.3`**，优先使用 safetensors 格式权重。不要为了"用最新版"升到 5.x。requirements.txt 中已锁定，不要改。

**坑 4：BAAI/bge-m3 的 main 分支只有 pytorch_model.bin，没有 safetensors**

- **现象**：离线加载报 `does not appear to have a file named pytorch_model.bin or model.safetensors`，即使磁盘上明明有 safetensors。
- **根因**：safetensors 在另一个 revision（9a0624b），不在 main（5617a9f）；且 hub 会缓存 `.no_exist` 标记，即使手工复制了文件，标记仍在，transformers 仍认为"不存在"。
- **避免**：手工组装后，**必须删除** `~\.cache\huggingface\hub\models--BAAI--bge-m3\.no_exist\5617a9f...\model.safetensors*`。下载模型时用 `snapshot_download` 并确认实际文件清单。

**坑 5：sentence-transformers 5.x + transformers 5.x 同进程双模型必段错误**

- **现象**：`exit code -1073741819`（0xC0000005 访问冲突），第二个模型加载即崩，换加载顺序、换 CPU 都没用。
- **避免**：**锁定 `sentence-transformers==3.3.1` + `transformers==4.46.3`**，不要升回 5.x/6.x。新版本在本场景（同进程加载 embedding + reranker）有底层冲突。

**坑 6：hf-mirror 与 xet 协议不兼容**

- **现象**：下载报 `401 Unauthorized`（cas-server.xethub.hf.co）或反复 `Read timed out`。
- **避免**：下载必须设 `$env:HF_HUB_DISABLE_XET='1'`；网络不稳重跑即可（支持断点续传）。

### 2.3 硬件资源

**坑 7：6GB 显存放不下两个 fp32 模型**

- **现象**：embedding(cuda) + reranker(cuda) 双模型上 GPU 时 OOM（`CUDA out of memory`）或驱动级段错误；fp16 改造也不稳定（段错误）。
- **避免**：**embedding 留 GPU(fp32)，reranker 放 CPU**。reranker 只对召回后的少量候选（几十条）打分，CPU 延迟可接受。配置见 `config.py`：`EMBEDDING_DEVICE="cuda"`、`RERANKER_DEVICE="cpu"`。

**坑 8：16GB 内存 + 小页面文件加载不了大模型**

- **现象**：`OSError: 页面文件太小，无法完成操作 (os error 1455)`。
- **根因**：2.27GB 的 bge-reranker-v2-m3 safetensors 内存映射放不下（空闲内存仅 ~3.4GB，虚拟内存空闲 ~4.1GB）。
- **避免**：reranker 改用 ~1.1GB 的 `bge-reranker-base`；如必须用大模型，先调大 Windows 页面文件。

**坑 10：Windows 不支持 expandable_segments**

- **现象**：设 `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True` 只打印警告，不解决 OOM。
- **避免**：Windows 下不要依赖这个环境变量解决显存问题，直接调模型放置策略（见坑 7）。

### 2.4 开发陷阱

**坑 9：langchain_text_splitters.Language 新版枚举成员缺失**

- **现象**：`AttributeError: type object 'Language' has no attribute 'SQL'`。
- **根因**：新版枚举无 SQL/JSON/YAML/XML/CSS/BASH 成员。
- **避免**：映射表里不要引用这些成员，让这些类型走默认 `RecursiveCharacterTextSplitter` 即可。

**坑 11：argparse 全局参数必须放在子命令前**

- **现象**：`cli.py query "问题" --api-key sk-...` 报 `unrecognized arguments: --api-key`。
- **根因**：`--api-key` 定义在主 parser 上，子命令的 parser 不识别。
- **避免**：用 `parents=[common]` 把公共参数传给每个子命令，子命令前后均可使用。

---

## 3. 常见存在的问题及解决方法

### 3.1 运行时问题速查

| 现象 | 可能原因 | 解决 |
|---|---|---|
| `does not appear to have a file named ... safetensors` | hub 缓存了 `.no_exist` 标记，或 main 分支确实没有 safetensors | 删除对应 `.no_exist` 标记；或手工从其他 revision 复制 safetensors 进 main snapshot（坑 4） |
| `require users to upgrade torch to at least v2.6` | transformers 5.x 加载 .bin | 降级到 `transformers==4.46.3`（坑 3） |
| 进程崩溃 exit -1073741819 | ST/transformers 5.x 双模型冲突，或显存不足 | 降级到 3.3.1+4.46.3；reranker 改 CPU（坑 5/7） |
| `CUDA out of memory` | 两个 fp32 模型同上 GPU | reranker 改 CPU（坑 7） |
| `页面文件太小 (os error 1455)` | 内存+虚拟内存不足，大模型 mmap 放不下 | 换轻量模型（bge-reranker-base）；或调大 Windows 页面文件（坑 8） |
| `WinError 5 拒绝访问`（pip） | 沙箱禁止写系统 site-packages | 用项目 `.venv`（坑 2） |
| 进程被 kill exit 1，日志含 `.pyc` | 沙箱禁止写系统 Python 目录的 pyc | 设 `PYTHONDONTWRITEBYTECODE=1`（坑 1） |
| `401 Unauthorized`（下载） | hf-mirror 与 xet 不兼容 | 设 `HF_HUB_DISABLE_XET=1`（坑 6） |
| `Read timed out`（下载） | 网络不稳 | 重跑命令，支持断点续传（坑 6） |
| `AttributeError: 'Language' has no attribute 'SQL'` | 新版枚举成员缺失 | 去掉不存在的成员，走默认分片（坑 9） |
| `unrecognized arguments: --api-key` | argparse 全局参数位置 | 用 `parents=[common]` 传给子命令（坑 11） |
| 建库后检索不到内容 | Chroma 写入失败 / BM25 索引未重建 | 跑 `cli.py stats` 看分片数；检查 `storage/bm25.json` 是否存在 |
| 召回结果不准 | chunk 太大/太小，或只用单路召回 | 调 `CHUNK_SIZE/OVERLAP`；确认混合召回两路都生效（看候选数量） |
| LLM 回答不引用来源 | Prompt 约束不够 | 检查 `prompts.py` 的 SYSTEM_PROMPT 是否要求标注来源 |
| LLM 生成失败 | 网络/限流/鉴权错误 | 检查 API key 和 base_url；SDK 已内置 max_retries=3 重试 |

### 3.2 代码审查发现的问题及修复（已全部修复）

项目经过多轮代码审查，以下为已发现并修复的问题汇总，**后续维护时不要再引入同类问题**：

**版本与依赖管理：**

| 问题 | 修复 | 文件 |
|------|------|------|
| requirements.txt 无版本约束 | 添加 `>=` 下限约束，ST/transformers/tokenizers/huggingface-hub 精确锁定 `==` | requirements.txt |
| torch 无上限锁，可能装到 2.6+ 与 transformers 4.46.3 不兼容 | 锁定 `torch>=2.5.0,<2.6.0` | requirements.txt |
| 缺 .gitignore，.venv/storage 等可能入库 | 新建 .gitignore | .gitignore |

**数据持久化安全：**

| 问题 | 修复 | 文件 |
|------|------|------|
| catalog.json 非原子写，崩溃致半截文件 | 改为先写 .tmp 再 replace 原子替换 | pipeline.py `_save_catalog` |
| BM25 索引非原子写，同样风险 | 同步采用 .tmp -> replace 原子写 | bm25.py `save()` |
| BM25 用 pickle 序列化有安全风险 | 改用 JSON 序列化文档+分词结果，加载时重建 BM25Okapi | bm25.py |
| force 模式先清 vector store 再清 catalog，崩溃后 catalog 仍指向已删数据 | 反转顺序：先清 catalog 再清 vector store，崩溃后下次增量自愈 | pipeline.py `build_index` |

**API 使用与性能：**

| 问题 | 修复 | 文件 |
|------|------|------|
| Chroma `store._collection.count()` 访问私有 API | 改用 `store.get(include=[])["ids"]` 公开 API | vector_store.py |
| `count()` 和 `clear()` 全量加载文档仅为取 IDs | 统一用 `include=[]` 仅取 IDs | vector_store.py |
| Chroma 实例每次调用新建，重复建立连接 | `get_vector_store()` 加 `@lru_cache` 单例缓存 | vector_store.py |

**错误处理与健壮性：**

| 问题 | 修复 | 文件 |
|------|------|------|
| LLM API 调用无错误上下文，原始异常直接抛出 | try/except 包装为带 model/base_url 的 RuntimeError | llm.py |
| LLM 无显式重试配置 | OpenAI 客户端显式配置 `max_retries=3` | llm.py |
| pipeline 单文件失败时 verbose=False 异常被静默吞掉 | 移除 verbose 条件，错误始终输出到 stderr | pipeline.py |
| 失败文件不记入 stats 返回值，调用方无法感知 | 新增 `files_failed` 列表记入返回值 | pipeline.py |

**输入校验与代码质量：**

| 问题 | 修复 | 文件 |
|------|------|------|
| chunk_overlap 未校验合法性（>= chunk_size 会导致分片异常） | 添加 `assert CHUNK_OVERLAP < CHUNK_SIZE` | config.py |
| 空查询无 guard，传空串仍走全流程 | retrieve() 返回 []，query() 返回提示消息 | engine.py |
| _doc_key 用 Python hash() 跨进程不稳定 | 改用 hashlib.md5 生成稳定内容哈希 | hybrid.py |
| _load_catalog 私有函数被跨模块导入 | 重命名为公开接口 load_catalog | pipeline.py / engine.py |
| pipeline.py mtime 三次重复调用，可能不一致 | 缓存为局部变量 mtime 复用 | pipeline.py |

**文档一致性：**

| 问题 | 修复 | 文件 |
|------|------|------|
| DESIGN.md / HANDOFF.md 引用 bm25.pkl（已改为 bm25.json） | 全部更新为 bm25.json | DESIGN.md / HANDOFF.md |
| 文档引用 bge-reranker-v2-m3（已改为 base） | 更新为 bge-reranker-base | DESIGN.md / HANDOFF.md |
| 文档引用 rank_bm25（规范名为 rank-bm25） | 更新为 rank-bm25 | DESIGN.md / HANDOFF.md |
| reranker.py docstring 模型名与 config 不符 | 更正为 bge-reranker-base | reranker.py |
| DESIGN.md 依赖列表含 python-docx（项目未使用） | 移除，补全实际依赖 | DESIGN.md |

**已知设计取舍（非缺陷，无需修改）：**

| 项 | 说明 |
|----|------|
| get_all_documents() 全量内存加载 | 仅在建库时调用一次重建 BM25，个人 KB 规模下成本可接受（注释已说明） |
| `[片段{i}]` 编号 | 供 LLM 在回答中引用溯源，与内部 chunk_id 用途不同，非冗余 |
| 全项目用 print 而非 logging | CLI 工具场景下 print(stdout)/stderr 分工明确，功能完备 |

### 3.3 模型缓存排查清单

当离线加载模型报错时，依次检查：

1. `~\.cache\huggingface\hub\models--<org>--<model>\refs\main` 指向哪个 revision？
2. 该 revision 的 snapshot 目录下，是否有 `model.safetensors`（或 `pytorch_model.bin`）+ `config.json` + `tokenizer.json` + `sentencepiece.bpe.model`？
3. `.no_exist\<revision>\` 下是否误标了 `model.safetensors`？有则删。
4. 如 main 缺 safetensors，去其他 revision 找，复制进来。

### 3.4 性能调优方向

- **建库慢**：bge-m3 在 GPU 上批量编码，单文件分片数多时耗时主要在 embedding；可调大批量大小。
- **检索慢**：reranker 在 CPU 上对候选打分是瓶颈；候选量小（几十条）时延迟可接受，如需加速可尝试更小的 reranker 或调大 `RERANK_TOP_N` 减少进 LLM 的分片数。
- **LLM 慢**：调 `LLM_MAX_TOKENS` 或换更快的模型/API。

### 3.5 排查通用思路

1. **先看 exit code**：
   - `0` 正常
   - `1` 一般是 Python 异常，看 Traceback
   - `-1073741819`（0xC0000005）段错误，多半是模型库底层冲突（坑 5/7）
   - `5999` 通常是网络下载异常退出
2. **看日志最后几行**：Traceback 的最后一帧往往直接指向问题。
3. **分模块隔离测试**：按 `embeddings -> build -> retrieve -> query` 逐层验证，定位是哪一层出问题。
4. **查模型缓存状态**：`~\.cache\huggingface\hub\models--*` 下看 snapshot 文件是否齐全、`.no_exist` 标记是否误伤目标文件。

---

## 附：后续扩展方向（不在本次交付）

- 前端交互界面（API key 由前端输入 -> `RAGEngine(api_key=...)`）
- FastAPI 后端封装
- 多轮对话 query 改写
- 与 Agent 框架集成
- 如转为 Agent 组件，需将 print 替换为 logging 框架避免 stdout 污染
