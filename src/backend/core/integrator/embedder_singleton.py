"""复用一个全局 SentenceTransformer 实例(初始化耗时 5-10s)。"""
from __future__ import annotations
from threading import Lock
from loguru import logger

from ...config import settings

_model = None
_lock = Lock()


def get_embedder():
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"[embedder] 加载模型 {settings.embedding_model}…")
            _model = SentenceTransformer(settings.embedding_model)
            logger.info("[embedder] 加载完成")
    return _model
