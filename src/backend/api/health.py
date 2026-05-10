"""健康检查与系统信息。"""
from fastapi import APIRouter
from ..config import settings, TEXTBOOKS_DIR, PARSED_DIR, GRAPHS_DIR

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model": settings.deepseek_model,
        "embedding": settings.embedding_model,
        "textbooks": len([p for p in TEXTBOOKS_DIR.glob("*") if p.is_file()]),
        "parsed": len([p for p in PARSED_DIR.glob("*.json") if not p.name.endswith(".meta.json")]),
        "graphs": len(list(GRAPHS_DIR.glob("*.json"))),
    }
