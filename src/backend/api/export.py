"""精华版导出 API:Markdown / PDF。"""
from __future__ import annotations
from datetime import datetime
from urllib.parse import quote
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from loguru import logger

from ..models.schemas import IntegrationStats, Decision
from ..storage import data_store
from ..core.export.exporter import render_markdown, render_pdf_bytes

router = APIRouter()


def _gather() -> tuple[list[Decision], dict, object]:
    master = data_store.load_master_graph()
    if master is None:
        raise HTTPException(404, "尚未运行整合,无法导出。请先点击「一键整合」。")
    raw_decs, raw_stats = data_store.load_decisions()
    decisions = [Decision.model_validate(d) for d in raw_decs]
    return decisions, raw_stats, master


def _attachment_headers(filename_zh: str, fallback_ascii: str) -> dict:
    """RFC 5987 兼容(中文文件名需 URL 编码;additionally 提供 ASCII 兜底)。"""
    encoded = quote(filename_zh, safe="")
    return {
        "Content-Disposition": (
            f'attachment; filename="{fallback_ascii}"; '
            f"filename*=UTF-8''{encoded}"
        ),
    }


@router.get("/export/markdown")
def export_markdown() -> Response:
    decisions, stats, master = _gather()
    md = render_markdown(master, decisions, stats)
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    headers = _attachment_headers(
        filename_zh=f"知识整合精华_{ts}.md",
        fallback_ascii=f"knowledge_integration_{ts}.md",
    )
    return Response(content=md.encode("utf-8"), media_type="text/markdown; charset=utf-8", headers=headers)


@router.get("/export/markdown/preview")
def export_markdown_preview() -> dict:
    """前端预览用:返回 markdown 文本(JSON),不下载。"""
    decisions, stats, master = _gather()
    md = render_markdown(master, decisions, stats)
    return {"markdown": md, "char_count": len(md)}


@router.get("/export/pdf")
def export_pdf() -> Response:
    decisions, stats, master = _gather()
    md = render_markdown(master, decisions, stats)
    try:
        pdf_bytes = render_pdf_bytes(md)
    except Exception as e:
        logger.exception("[export] PDF 渲染失败")
        raise HTTPException(500, f"PDF 生成失败: {e}")
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    headers = _attachment_headers(
        filename_zh=f"知识整合精华_{ts}.pdf",
        fallback_ascii=f"knowledge_integration_{ts}.pdf",
    )
    return Response(content=pdf_bytes, media_type="application/pdf", headers=headers)
