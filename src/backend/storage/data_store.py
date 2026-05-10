"""轻量 JSON 持久化封装。

约定:
- parsed/{book_id}.json   完整解析结果(TextbookDoc)
- parsed/{book_id}.meta.json   轻元数据(TextbookMeta,前端列表用,避免读大文件)
- graphs/{book_id}.json   单本图谱(BookGraph)
- integrated/master_graph.json
- integrated/decisions.json
- integrated/stats.json
- sessions/{sid}.json
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from threading import Lock

from ..config import PARSED_DIR, GRAPHS_DIR, INTEGRATED_DIR, SESSIONS_DIR
from ..models.schemas import TextbookDoc, TextbookMeta, BookGraph

_lock = Lock()


def _atomic_write(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


# ============ Textbook ============
def save_textbook(doc: TextbookDoc) -> None:
    with _lock:
        _atomic_write(PARSED_DIR / f"{doc.textbook_id}.json", doc.model_dump())
        meta = TextbookMeta(
            textbook_id=doc.textbook_id,
            filename=doc.filename,
            title=doc.title,
            total_pages=doc.total_pages,
            total_chars=doc.total_chars,
            chapter_count=len(doc.chapters),
            status="parsed",
        )
        _atomic_write(PARSED_DIR / f"{doc.textbook_id}.meta.json", meta.model_dump())


def load_textbook(book_id: str) -> TextbookDoc | None:
    raw = _read_json(PARSED_DIR / f"{book_id}.json")
    return TextbookDoc.model_validate(raw) if raw else None


def update_meta_status(book_id: str, status: str, error: str | None = None) -> None:
    with _lock:
        meta_path = PARSED_DIR / f"{book_id}.meta.json"
        raw = _read_json(meta_path) or {
            "textbook_id": book_id, "filename": book_id, "title": book_id,
            "total_pages": 0, "total_chars": 0, "chapter_count": 0,
        }
        raw["status"] = status
        if error:
            raw["error"] = error
        _atomic_write(meta_path, raw)


def upsert_meta(meta: TextbookMeta) -> None:
    with _lock:
        _atomic_write(PARSED_DIR / f"{meta.textbook_id}.meta.json", meta.model_dump())


def list_metas() -> list[TextbookMeta]:
    metas = []
    for p in sorted(PARSED_DIR.glob("*.meta.json")):
        raw = _read_json(p)
        if raw:
            try:
                metas.append(TextbookMeta.model_validate(raw))
            except Exception:
                pass
    return metas


# ============ Graph ============
def save_graph(graph: BookGraph) -> None:
    with _lock:
        _atomic_write(GRAPHS_DIR / f"{graph.book_id}.json", graph.model_dump())


def load_graph(book_id: str) -> BookGraph | None:
    raw = _read_json(GRAPHS_DIR / f"{book_id}.json")
    return BookGraph.model_validate(raw) if raw else None


def list_graphs() -> list[BookGraph]:
    out = []
    for p in sorted(GRAPHS_DIR.glob("*.json")):
        raw = _read_json(p)
        if raw:
            try:
                out.append(BookGraph.model_validate(raw))
            except Exception:
                pass
    return out


# ============ Integration ============
def save_master_graph(graph: BookGraph) -> None:
    with _lock:
        _atomic_write(INTEGRATED_DIR / "master_graph.json", graph.model_dump())


def load_master_graph() -> BookGraph | None:
    raw = _read_json(INTEGRATED_DIR / "master_graph.json")
    return BookGraph.model_validate(raw) if raw else None


def save_decisions(decisions: list[dict], stats: dict) -> None:
    with _lock:
        _atomic_write(INTEGRATED_DIR / "decisions.json", decisions)
        _atomic_write(INTEGRATED_DIR / "stats.json", stats)


def load_decisions() -> tuple[list[dict], dict]:
    decs = _read_json(INTEGRATED_DIR / "decisions.json") or []
    stats = _read_json(INTEGRATED_DIR / "stats.json") or {}
    return decs, stats


# ============ Session ============
def save_session(sid: str, history: list[dict]) -> None:
    with _lock:
        _atomic_write(SESSIONS_DIR / f"{sid}.json", history)


def load_session(sid: str) -> list[dict]:
    return _read_json(SESSIONS_DIR / f"{sid}.json") or []
