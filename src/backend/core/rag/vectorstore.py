"""ChromaDB 持久化封装。"""
from __future__ import annotations
from threading import Lock
from loguru import logger
import chromadb
from chromadb.config import Settings as ChromaSettings

from ...config import CHROMA_DIR
from .chunker import Chunk

_client = None
_collection = None
_lock = Lock()  # 非可重入锁,所有 helper 必须在外部上锁,内部不再 with _lock
COLLECTION_NAME = "textbook_chunks"


def _ensure_client_locked():
    """假设调用方已持锁。"""
    global _client, _collection
    if _client is None:
        _client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=ChromaSettings(anonymized_telemetry=False, allow_reset=True),
        )
    if _collection is None:
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"[chroma] 集合就绪,当前 {_collection.count()} 条")


def _ensure_client():
    global _collection
    if _collection is not None:
        return
    with _lock:
        _ensure_client_locked()


def reset_collection() -> None:
    global _collection
    with _lock:
        _ensure_client_locked()
        try:
            _client.delete_collection(COLLECTION_NAME)  # type: ignore
        except Exception:
            pass
        _collection = _client.get_or_create_collection(  # type: ignore
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"[chroma] 集合已重置")


def add_chunks(chunks: list[Chunk], embeddings: list[list[float]]) -> None:
    _ensure_client()
    if not chunks:
        return
    metas = [
        {
            "textbook_id": c.textbook_id,
            "book_title": c.book_title,
            "chapter": c.chapter,
            "page": c.page,
            "char_offset": c.char_offset,
        }
        for c in chunks
    ]
    _collection.add(  # type: ignore
        ids=[c.chunk_id for c in chunks],
        embeddings=embeddings,
        documents=[c.text for c in chunks],
        metadatas=metas,
    )


def query_topk(query_emb: list[float], top_k: int = 5) -> list[dict]:
    _ensure_client()
    res = _collection.query(  # type: ignore
        query_embeddings=[query_emb],
        n_results=top_k,
    )
    out = []
    if not res.get("ids") or not res["ids"][0]:
        return out
    for i, cid in enumerate(res["ids"][0]):
        meta = res["metadatas"][0][i] if res.get("metadatas") else {}
        # chroma 返回 distance(余弦距离),转为相似度
        dist = res["distances"][0][i] if res.get("distances") else 0.0
        score = max(0.0, 1.0 - float(dist))
        out.append({
            "id": cid,
            "text": res["documents"][0][i],
            "metadata": meta,
            "score": score,
        })
    return out


def get_all_documents() -> list[dict]:
    """供 BM25 混合检索使用。"""
    _ensure_client()
    res = _collection.get(include=["documents", "metadatas"])  # type: ignore
    out = []
    for i, cid in enumerate(res.get("ids") or []):
        out.append({
            "id": cid,
            "text": res["documents"][i],
            "metadata": res["metadatas"][i],
        })
    return out


def stats() -> dict:
    _ensure_client()
    cnt = _collection.count()  # type: ignore
    # 统计去重的 textbook 数量
    if cnt == 0:
        return {"total_chunks": 0, "indexed_books": 0, "books": []}
    res = _collection.get(include=["metadatas"], limit=min(cnt, 50000))  # type: ignore
    books = sorted({m.get("textbook_id") for m in (res.get("metadatas") or []) if m})
    return {"total_chunks": cnt, "indexed_books": len(books), "books": list(books)}
