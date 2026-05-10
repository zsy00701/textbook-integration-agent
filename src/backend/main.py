"""FastAPI 入口:挂 API 路由 + 前端静态产物。"""
import os
# 防止 sentence-transformers 在多线程场景 fork 后死锁
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from loguru import logger

from .config import settings, FRONTEND_DIST
from .api import health, upload, graph, integration, rag, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting backend; model={settings.deepseek_model}")
    # 预加载 embedder(下载 BGE 模型,~100MB),避免业务请求时卡死
    import threading
    def _preload():
        try:
            from .core.integrator.embedder_singleton import get_embedder
            get_embedder()
            logger.info("[startup] embedder 预加载完成")
        except Exception as e:
            logger.exception(f"[startup] embedder 预加载失败: {e}")
    threading.Thread(target=_preload, daemon=True).start()
    yield
    logger.info("Shutting down backend")


app = FastAPI(
    title="学科知识整合智能体",
    description="多本教材知识图谱整合 + RAG 精准问答",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(graph.router, prefix="/api", tags=["graph"])
app.include_router(integration.router, prefix="/api", tags=["integration"])
app.include_router(rag.router, prefix="/api", tags=["rag"])
app.include_router(chat.router, prefix="/api", tags=["chat"])

# 前端静态托管(只在构建产物存在时挂载)
if FRONTEND_DIST.exists() and (FRONTEND_DIST / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
    logger.info(f"Mounted frontend at / from {FRONTEND_DIST}")
else:
    logger.warning(f"Frontend dist not found at {FRONTEND_DIST}; run `npm run build` first")

    @app.get("/")
    def root() -> dict:
        return {
            "message": "Backend running. Frontend not built yet.",
            "build_hint": "cd src/frontend && npm install && npm run build",
            "api_docs": "/docs",
        }
