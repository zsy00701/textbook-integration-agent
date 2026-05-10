"""检索器:向量召回 + 可选 BM25 混合 + 简单 RRF 重排序。

P1 加分:混合检索(向量 + BM25)+ Reciprocal Rank Fusion 重排序。
"""
from __future__ import annotations
from functools import lru_cache
from rank_bm25 import BM25Okapi
from loguru import logger
import numpy as np

from . import vectorstore
from ..integrator.embedder_singleton import get_embedder


def _tokenize_zh(text: str) -> list[str]:
    """简单的中文/英文混合 tokenize:按字 + 按英文词。"""
    out: list[str] = []
    buf = ""
    for ch in text:
        if ch.isalnum() and ord(ch) < 128:
            buf += ch
        else:
            if buf:
                out.append(buf.lower())
                buf = ""
            if ch.strip() and "一" <= ch <= "鿿":
                out.append(ch)
    if buf:
        out.append(buf.lower())
    return out


_bm25_cache: dict[str, tuple[BM25Okapi, list[dict]]] = {}


def _get_bm25() -> tuple[BM25Okapi, list[dict]]:
    """构建 BM25 索引(基于 chroma 中的全部 chunks)。第一次调用较慢,之后 cache。"""
    if "v1" in _bm25_cache:
        return _bm25_cache["v1"]
    docs = vectorstore.get_all_documents()
    if not docs:
        bm25 = BM25Okapi([[""]])
        _bm25_cache["v1"] = (bm25, [])
        return _bm25_cache["v1"]
    corpus = [_tokenize_zh(d["text"]) for d in docs]
    logger.info(f"[bm25] 构建索引,{len(corpus)} 文档")
    bm25 = BM25Okapi(corpus)
    _bm25_cache["v1"] = (bm25, docs)
    return _bm25_cache["v1"]


def invalidate_bm25_cache() -> None:
    _bm25_cache.clear()


def retrieve(question: str, top_k: int = 5, hybrid: bool = True) -> list[dict]:
    """返回 top_k 个 chunk dict:{id, text, metadata, score}。

    hybrid=True:向量 top-k*2 + BM25 top-k*2 → RRF 取 top-k
    """
    embedder = get_embedder()
    q_emb = embedder.encode([question], normalize_embeddings=True)[0].tolist()
    vec_hits = vectorstore.query_topk(q_emb, top_k=top_k * 2 if hybrid else top_k)

    if not hybrid:
        return vec_hits[:top_k]

    try:
        bm25, docs = _get_bm25()
        if not docs:
            return vec_hits[:top_k]
        q_tokens = _tokenize_zh(question)
        scores = bm25.get_scores(q_tokens)
        # 取 BM25 top-k*2
        idx_sorted = np.argsort(-scores)[: top_k * 2]
        bm25_hits = [
            {
                "id": docs[i]["id"],
                "text": docs[i]["text"],
                "metadata": docs[i]["metadata"],
                "score": float(scores[i]),
            }
            for i in idx_sorted
            if scores[i] > 0
        ]
    except Exception as e:
        logger.warning(f"[retrieve] BM25 失败,只用向量: {e}")
        return vec_hits[:top_k]

    # RRF 融合
    K_RRF = 60
    rank_score: dict[str, float] = {}
    item_by_id: dict[str, dict] = {}
    vec_score_by_id: dict[str, float] = {h["id"]: float(h.get("score", 0.0)) for h in vec_hits}
    for r, h in enumerate(vec_hits):
        rank_score[h["id"]] = rank_score.get(h["id"], 0.0) + 1.0 / (K_RRF + r + 1)
        item_by_id[h["id"]] = h
    for r, h in enumerate(bm25_hits):
        rank_score[h["id"]] = rank_score.get(h["id"], 0.0) + 1.0 / (K_RRF + r + 1)
        item_by_id.setdefault(h["id"], h)

    fused = sorted(rank_score.items(), key=lambda x: -x[1])[:top_k]
    out = []
    for cid, _s in fused:
        item = dict(item_by_id[cid])
        # score 用向量余弦(0-1),BM25-only 命中的 chunk 用 0.5 占位(不展示原始 BM25 raw score)
        item["score"] = vec_score_by_id.get(cid, 0.5)
        out.append(item)
    return out
