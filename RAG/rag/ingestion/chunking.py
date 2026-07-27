"""分片策略：按文件类型选择切分方式。

- Markdown：按标题层级切分（保留标题路径），超长再按长度二次切分
- 代码：语言感知分片（按函数/类边界）
- 其他：递归字符分片
"""
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import (
    Language,
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from rag import config
from rag.ingestion.loaders import CODE_EXTENSIONS

# 代码扩展名 → LangChain Language 映射（枚举无对应成员的扩展名走默认递归分片）
_EXT_TO_LANGUAGE = {
    ".py": Language.PYTHON, ".js": Language.JS, ".ts": Language.TS,
    ".java": Language.JAVA, ".c": Language.C, ".cpp": Language.CPP,
    ".h": Language.C, ".hpp": Language.CPP, ".go": Language.GO,
    ".rs": Language.RUST, ".cs": Language.CSHARP, ".php": Language.PHP,
    ".rb": Language.RUBY, ".swift": Language.SWIFT, ".kt": Language.KOTLIN,
    ".ps1": Language.POWERSHELL,
}

_MD_HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3"), ("####", "h4"), ("#####", "h5"), ("######", "h6")]


def _length_splitter() -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )


def _split_markdown(text: str, metadata: dict) -> list[Document]:
    """按标题层级切分，标题路径写入 metadata.title_path，超长二次切分。"""
    header_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=_MD_HEADERS)
    header_docs = header_splitter.split_text(text)

    results = []
    for doc in header_docs:
        # 合并标题层级为路径，如 "第一章/背景"
        title_path = "/".join(
            doc.metadata[h] for h in ("h1", "h2", "h3", "h4", "h5", "h6") if h in doc.metadata
        )
        merged_meta = {**metadata}
        if title_path:
            merged_meta["title_path"] = title_path
        for piece in _length_splitter().split_text(doc.page_content):
            if piece.strip():
                results.append(Document(page_content=piece, metadata=dict(merged_meta)))
    return results


def _split_code(text: str, metadata: dict, ext: str) -> list[Document]:
    language = _EXT_TO_LANGUAGE.get(ext)
    if language is None:
        return _split_plain(text, metadata)
    splitter = RecursiveCharacterTextSplitter.from_language(
        language=language,
        chunk_size=config.CHUNK_SIZE,
        chunk_overlap=config.CHUNK_OVERLAP,
    )
    return [
        Document(page_content=piece, metadata=dict(metadata))
        for piece in splitter.split_text(text) if piece.strip()
    ]


def _split_plain(text: str, metadata: dict) -> list[Document]:
    return [
        Document(page_content=piece, metadata=dict(metadata))
        for piece in _length_splitter().split_text(text) if piece.strip()
    ]


def chunk_documents(docs: list[Document], source: str, file_mtime: float) -> list[Document]:
    """对单个文件加载出的 Document 列表进行分片，并写入统一 metadata。"""
    ext = Path(source).suffix.lower()
    chunks: list[Document] = []

    for doc in docs:
        base_meta = {"source": source, "file_type": ext, "file_mtime": file_mtime}
        if ext == ".md":
            chunks.extend(_split_markdown(doc.page_content, base_meta))
        elif ext in CODE_EXTENSIONS:
            chunks.extend(_split_code(doc.page_content, base_meta, ext))
        else:
            chunks.extend(_split_plain(doc.page_content, base_meta))

    # 写入全局唯一 chunk_id
    for idx, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = f"{source}#{idx}"
    return chunks
