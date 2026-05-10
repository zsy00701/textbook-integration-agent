"""跨教材整合 API。"""
from __future__ import annotations
import threading
from fastapi import APIRouter, HTTPException
from loguru import logger

from ..storage import data_store
from ..core.integrator.pipeline import run_integration

router = APIRouter()

_lock = threading.Lock()
_running = {"flag": False}


def _do_run() -> None:
    try:
        graphs = data_store.list_graphs()
        if len(graphs) < 1:
            logger.warning("[integration] 无可用图谱")
            return
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


@router.post("/integration/run")
def run() -> dict:
    with _lock:
        if _running["flag"]:
            raise HTTPException(409, "整合任务已在运行")
        _running["flag"] = True
    threading.Thread(target=_do_run, daemon=True).start()
    return {"status": "started"}


@router.get("/integration/status")
def status() -> dict:
    return {"running": _running["flag"]}


@router.get("/integration/decisions")
def get_decisions() -> dict:
    decs, stats = data_store.load_decisions()
    return {"decisions": decs, "stats": stats}
