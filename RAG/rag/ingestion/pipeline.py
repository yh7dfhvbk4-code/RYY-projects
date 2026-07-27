"""建库流水线：扫描 data/ → 分片 → 写入 Chroma → 重建 BM25 → 更新 catalog。

支持增量更新：以文件 mtime 判断新增/变更，只重建受影响文件的索引。
"""
import json
import sys
import time
from pathlib import Path

from rag import config
from rag.ingestion.chunking import chunk_documents
from rag.ingestion.loaders import load_document, scan_data_dir
from rag.retrieval import vector_store
from rag.retrieval.bm25 import BM25Index


def load_catalog() -> dict:
    if config.CATALOG_PATH.exists():
        return json.loads(config.CATALOG_PATH.read_text(encoding="utf-8"))
    return {}


def _save_catalog(catalog: dict) -> None:
    config.CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = config.CATALOG_PATH.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    tmp.replace(config.CATALOG_PATH)  # 原子替换


def build_index(force: bool = False, verbose: bool = True) -> dict:
    """构建/更新索引。返回统计信息。"""
    started = time.time()
    data_dir = config.DATA_DIR
    if not data_dir.exists():
        raise FileNotFoundError(f"数据目录不存在: {data_dir}，请将文档放入该目录")

    if force:
        _save_catalog({})    # 先清 catalog，崩溃后下次增量可自愈重索引
        vector_store.clear()

    catalog = load_catalog()
    files = scan_data_dir(data_dir)

    # 相对路径（统一用正斜杠，跨平台稳定）
    current = {str(p.relative_to(data_dir)).replace("\\", "/"): p for p in files}

    changed = [
        src for src, path in current.items()
        if src not in catalog or catalog[src]["mtime"] != path.stat().st_mtime
    ]
    deleted = [src for src in catalog if src not in current]

    if verbose:
        print(f"扫描到 {len(current)} 个文件：新增/变更 {len(changed)} 个，删除 {len(deleted)} 个")

    # 处理删除的文件
    for src in deleted:
        vector_store.delete_by_source(src)
        catalog.pop(src)
        if verbose:
            print(f"  [删除] {src}")

    # 处理新增/变更的文件
    total_chunks = 0
    failed = []
    for src in changed:
        path = current[src]
        try:
            docs = load_document(path)
            if not docs:
                if verbose:
                    print(f"  [跳过] {src}（无有效文本内容）")
                continue
            mtime = path.stat().st_mtime
            vector_store.delete_by_source(src)  # 先删旧分片，避免重复
            chunks = chunk_documents(docs, source=src, file_mtime=mtime)
            vector_store.add_chunks(chunks)
            catalog[src] = {"mtime": mtime, "chunk_count": len(chunks)}
            total_chunks += len(chunks)
            if verbose:
                print(f"  [入库] {src} → {len(chunks)} 个分片")
        except Exception as e:
            # 单个文件失败不中断整体建库，始终报告错误
            print(f"  [失败] {src}：{e}", file=sys.stderr)
            failed.append(src)

    # 文档集有变化时整体重建 BM25（中小规模成本可接受）
    if changed or deleted:
        bm25 = BM25Index()
        bm25.build(vector_store.get_all_documents())
        bm25.save()
        if verbose:
            print(f"BM25 索引已重建（{bm25.size} 个分片）")

    _save_catalog(catalog)
    stats = {
        "files_total": len(current),
        "files_changed": len(changed),
        "files_deleted": len(deleted),
        "chunks_added": total_chunks,
        "chunks_total": vector_store.count(),
        "files_failed": failed,
        "elapsed_sec": round(time.time() - started, 2),
    }
    if verbose:
        print(f"完成：{stats}")
    return stats
