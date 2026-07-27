"""多格式文档加载：按扩展名分发到对应 LangChain Loader。

统一返回 List[Document]，metadata 中含 source（相对路径）与 file_type。
"""
from pathlib import Path

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    BSHTMLLoader,
    Docx2txtLoader,
    PyMuPDFLoader,
    TextLoader,
    UnstructuredExcelLoader,
    UnstructuredPowerPointLoader,
)

# 代码文件扩展名（用纯文本加载，分片阶段按语言处理）
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".hpp",
    ".go", ".rs", ".cs", ".php", ".rb", ".swift", ".kt", ".sql",
    ".sh", ".bat", ".ps1", ".json", ".yaml", ".yml", ".xml", ".css",
}

SUPPORTED_EXTENSIONS = {
    ".md", ".txt", ".docx", ".pptx", ".pdf", ".xlsx", ".html", ".htm",
} | CODE_EXTENSIONS


def load_document(file_path: Path) -> list[Document]:
    """加载单个文件，返回 Document 列表。"""
    ext = file_path.suffix.lower()
    path_str = str(file_path)

    if ext in (".md", ".txt") or ext in CODE_EXTENSIONS:
        loader = TextLoader(path_str, encoding="utf-8", autodetect_encoding=True)
    elif ext == ".docx":
        loader = Docx2txtLoader(path_str)
    elif ext == ".pptx":
        loader = UnstructuredPowerPointLoader(path_str)
    elif ext == ".pdf":
        loader = PyMuPDFLoader(path_str)
    elif ext == ".xlsx":
        loader = UnstructuredExcelLoader(path_str)
    elif ext in (".html", ".htm"):
        loader = BSHTMLLoader(path_str, open_encoding="utf-8")
    else:
        raise ValueError(f"不支持的文件类型: {ext}")

    docs = loader.load()

    # 清洗：去除首尾空白，过滤空文档
    cleaned = []
    for doc in docs:
        text = doc.page_content.strip()
        if text:
            doc.page_content = text
            doc.metadata["file_type"] = ext
            cleaned.append(doc)
    return cleaned


def scan_data_dir(data_dir: Path) -> list[Path]:
    """扫描数据目录，返回所有受支持的文件路径（相对 data_dir 排序）。"""
    files = [
        p for p in data_dir.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]
    return sorted(files)
