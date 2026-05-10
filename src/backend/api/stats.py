"""系统统计:Token 累计 + 数据规模。供前端 topbar 显示。"""
from __future__ import annotations
import time
from fastapi import APIRouter

from ..config import TEXTBOOKS_DIR, PARSED_DIR, GRAPHS_DIR
from ..core.agent.llm_client import token_stats
from ..core.rag import vectorstore
from ..storage import data_store

router = APIRouter()
_BOOT_TIME = time.time()


@router.get("/stats")
def stats() -> dict:
    metas = data_store.list_metas()
    master = data_store.load_master_graph()

    # 单本图谱节点数累计
    total_nodes = 0
    for jf in GRAPHS_DIR.glob("*.json"):
        try:
            g = data_store.load_graph(jf.stem)
            if g:
                total_nodes += len(g.nodes)
        except Exception:
            pass

    try:
        rag = vectorstore.stats()
    except Exception:
        rag = {"total_chunks": 0, "indexed_books": 0}

    return {
        "token_stats": token_stats.snapshot(),
        "totals": {
            "textbooks_uploaded": len([p for p in TEXTBOOKS_DIR.glob("*") if p.is_file()]),
            "parsed": len([p for p in PARSED_DIR.glob("*.json") if not p.name.endswith(".meta.json")]),
            "graphs": len(list(GRAPHS_DIR.glob("*.json"))),
            "total_nodes": total_nodes,
            "master_nodes": len(master.nodes) if master else 0,
            "master_edges": len(master.edges) if master else 0,
            "total_chunks": rag.get("total_chunks", 0),
            "indexed_books": rag.get("indexed_books", 0),
        },
        "uptime_s": int(time.time() - _BOOT_TIME),
    }
