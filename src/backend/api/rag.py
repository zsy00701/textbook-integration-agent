"""RAG 索引/查询 API。"""
from __future__ import annotations
import threading
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from loguru import logger

from ..core.rag.pipeline import build_index, query, get_status

router = APIRouter()

_lock = threading.Lock()
_indexing = {"flag": False, "progress": ""}


class QueryReq(BaseModel):
    question: str
    top_k: int = 5


def _do_index() -> None:
    try:
        def progress(text: str):
            _indexing["progress"] = text
            logger.info(f"[rag-index] {text}")
        build_index(on_progress=progress)
    except Exception:
        logger.exception("[rag-index] 失败")
    finally:
        _indexing["flag"] = False
        _indexing["progress"] = ""


@router.post("/rag/index")
def index() -> dict:
    with _lock:
        if _indexing["flag"]:
            raise HTTPException(409, "正在索引中")
        _indexing["flag"] = True
    threading.Thread(target=_do_index, daemon=True).start()
    return {"status": "started"}


@router.get("/rag/status")
def status() -> dict:
    base = get_status()
    base.update({"indexing": _indexing["flag"], "progress": _indexing["progress"]})
    return base


@router.post("/rag/query")
def ask(req: QueryReq) -> dict:
    if not req.question.strip():
        raise HTTPException(400, "问题不能为空")
    return query(req.question, top_k=req.top_k).model_dump()
