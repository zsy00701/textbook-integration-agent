"""RAG 主流程:索引 + 查询。"""
from __future__ import annotations
import time
from typing import Callable
from loguru import logger

from ...models.schemas import QAResponse, RagStatus
from ...storage import data_store
from ..integrator.embedder_singleton import get_embedder
from .chunker import chunk_textbook, Chunk
from . import vectorstore
from .retriever import retrieve, invalidate_bm25_cache
from .generator import generate_answer


def build_index(on_progress: Callable[[str], None] | None = None) -> dict:
    """全量重建索引(rebuild from data/parsed)。"""
    metas = data_store.list_metas()
    logger.info(f"[rag-index] 候选 {len(metas)} 本教材")
    if on_progress:
        on_progress(f"重置向量库…")
    vectorstore.reset_collection()
    invalidate_bm25_cache()

    embedder = get_embedder()
    total_chunks = 0
    for m in metas:
        if m.status == "failed":
            continue
        doc = data_store.load_textbook(m.textbook_id)
        if not doc:
            continue
        chunks: list[Chunk] = chunk_textbook(doc)
        if not chunks:
            continue
        if on_progress:
            on_progress(f"嵌入《{doc.title}》{len(chunks)} 块…")
        # batch 嵌入
        texts = [c.text for c in chunks]
        embs = embedder.encode(
            texts, batch_size=64, show_progress_bar=False, normalize_embeddings=True
        )
        # chroma add 一次最大 ~5000,分批
        BATCH = 200
        for i in range(0, len(chunks), BATCH):
            batch = chunks[i : i + BATCH]
            batch_embs = [e.tolist() for e in embs[i : i + BATCH]]
            vectorstore.add_chunks(batch, batch_embs)
        total_chunks += len(chunks)
        logger.info(f"[rag-index] {doc.title} → {len(chunks)} 块, 累计 {total_chunks}")

    if on_progress:
        on_progress(f"完成,共 {total_chunks} 块")
    return {"total_chunks": total_chunks}


def query(question: str, top_k: int = 5) -> QAResponse:
    t0 = time.perf_counter()
    hits = retrieve(question, top_k=top_k, hybrid=True)
    t_retrieve = time.perf_counter()
    resp = generate_answer(question, hits)
    t_done = time.perf_counter()
    resp.latency_ms = {
        "retrieval": int((t_retrieve - t0) * 1000),
        "generation": int((t_done - t_retrieve) * 1000),
        "total": int((t_done - t0) * 1000),
    }
    return resp


def get_status() -> dict:
    return vectorstore.stats()
