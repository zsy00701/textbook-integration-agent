"""全局配置:从 .env 加载,提供路径常量。"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # LLM
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # Embedding
    embedding_model: str = "BAAI/bge-small-zh-v1.5"

    # Vector store
    chroma_persist_dir: str = "data/chroma"

    # Integration
    align_threshold: float = 0.85
    compression_ratio_limit: float = 0.30

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"


settings = Settings()

# 路径(相对仓库根)
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
TEXTBOOKS_DIR = DATA_DIR / "textbooks"
PARSED_DIR = DATA_DIR / "parsed"
GRAPHS_DIR = DATA_DIR / "graphs"
INTEGRATED_DIR = DATA_DIR / "integrated"
CHROMA_DIR = DATA_DIR / "chroma"
SESSIONS_DIR = DATA_DIR / "sessions"
FRONTEND_DIST = ROOT / "src" / "frontend" / "dist"

for d in [TEXTBOOKS_DIR, PARSED_DIR, GRAPHS_DIR, INTEGRATED_DIR, CHROMA_DIR, SESSIONS_DIR]:
    d.mkdir(parents=True, exist_ok=True)
