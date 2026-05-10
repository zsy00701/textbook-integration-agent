"""图谱获取 + 知识点抽取触发 API。"""
from __future__ import annotations
import threading
from fastapi import APIRouter, HTTPException
from loguru import logger

from ..storage import data_store
from ..core.extractor.kg_extractor import extract_book_graph
from ..models.schemas import BookGraph

router = APIRouter()


def _do_extract(book_id: str) -> None:
    try:
        data_store.update_meta_status(book_id, "extracting")
        doc = data_store.load_textbook(book_id)
        if not doc:
            data_store.update_meta_status(book_id, "failed", error="未找到解析结果")
            return
        graph = extract_book_graph(doc)
        data_store.save_graph(graph)
        data_store.update_meta_status(book_id, "ready")
        logger.info(f"[graph] {book_id} 抽取入库完成,{len(graph.nodes)} 节点")
    except Exception as e:
        logger.exception(f"[graph] {book_id} 抽取失败")
        data_store.update_meta_status(book_id, "failed", error=str(e))


@router.post("/graph/{book_id}/extract")
def trigger_extract(book_id: str) -> dict:
    """触发后台抽取。"""
    if not data_store.load_textbook(book_id):
        raise HTTPException(404, "教材未解析")
    threading.Thread(target=_do_extract, args=(book_id,), daemon=True).start()
    return {"status": "started", "book_id": book_id}


@router.post("/graph/extract_all")
def trigger_extract_all() -> dict:
    """对所有已解析未抽取的教材批量触发。"""
    started = []
    for m in data_store.list_metas():
        if m.status in ("parsed", "failed"):
            doc = data_store.load_textbook(m.textbook_id)
            if doc:
                threading.Thread(target=_do_extract, args=(m.textbook_id,), daemon=True).start()
                started.append(m.textbook_id)
    return {"started": started}


@router.get("/graph/{book_id}")
def get_graph(book_id: str) -> dict:
    if book_id == "master":
        g = data_store.load_master_graph()
    else:
        g = data_store.load_graph(book_id)
    if not g:
        raise HTTPException(404, f"图谱 {book_id} 不存在(可能尚未抽取/整合)")
    return g.model_dump()
