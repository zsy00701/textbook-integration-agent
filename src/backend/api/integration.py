"""跨教材整合 API。"""
from __future__ import annotations
import threading
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from loguru import logger

from ..storage import data_store
from ..core.integrator.pipeline import run_integration

router = APIRouter()

_lock = threading.Lock()
_running: dict = {"flag": False, "book_ids": []}


class IntegrationRequest(BaseModel):
    """整合请求。空 book_ids = 整合所有可用图谱。"""
    book_ids: list[str] = Field(default_factory=list)


def _do_run(book_ids: list[str]) -> None:
    try:
        all_graphs = data_store.list_graphs()
        if book_ids:
            wanted = set(book_ids)
            graphs = [g for g in all_graphs if g.book_id in wanted]
            missing = wanted - {g.book_id for g in graphs}
            if missing:
                logger.warning(f"[integration] 以下教材没有图谱,跳过:{missing}")
        else:
            graphs = all_graphs

        if len(graphs) < 1:
            logger.warning("[integration] 无可用图谱")
            return
        if len(graphs) < 2:
            logger.info(f"[integration] 仅 1 本图谱({graphs[0].book_id}),将直接产出 master 而不做对齐")

        logger.info(f"[integration] 开始整合 {len(graphs)} 本: {[g.book_id for g in graphs]}")
        result = run_integration(graphs)
        data_store.save_master_graph(result.master_graph)
        data_store.save_decisions(
            [d.model_dump() for d in result.decisions],
            result.stats.model_dump(),
        )
        logger.info(f"[integration] 完成,压缩比 {result.stats.ratio*100:.1f}%")
    except Exception:
        logger.exception("[integration] 失败")
    finally:
        _running["flag"] = False
        _running["book_ids"] = []


@router.post("/integration/run")
def run(req: IntegrationRequest | None = None) -> dict:
    book_ids = req.book_ids if req else []
    with _lock:
        if _running["flag"]:
            raise HTTPException(409, "整合任务已在运行")
        _running["flag"] = True
        _running["book_ids"] = list(book_ids)
    threading.Thread(target=_do_run, args=(list(book_ids),), daemon=True).start()
    return {"status": "started", "book_ids": book_ids}


@router.get("/integration/status")
def status() -> dict:
    return {"running": _running["flag"], "book_ids": _running.get("book_ids", [])}


@router.get("/integration/decisions")
def get_decisions() -> dict:
    decs, stats = data_store.load_decisions()
    return {"decisions": decs, "stats": stats}


@router.get("/integration/available")
def available_books() -> dict:
    """前端选择教材时用:列出所有有图谱的教材。"""
    graphs = data_store.list_graphs()
    return {
        "books": [
            {"book_id": g.book_id, "book_title": g.book_title, "node_count": len(g.nodes)}
            for g in graphs
        ]
    }
