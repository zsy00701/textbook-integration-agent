"""文件上传 + 教材列表 API。

注意:PDF 解析(PyMuPDF/MuPDF C 库)在并发场景偶尔触发 SIGSEGV(已实测确认),
因此用全局信号量把解析串行化。教材最多 7 本,串行总耗时 1-2 分钟可接受。
"""
from __future__ import annotations
import re
import shutil
import threading
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from loguru import logger

from ..config import TEXTBOOKS_DIR
from ..core.parser.unified import parse_file, SUPPORTED_EXTS
from ..storage import data_store
from ..models.schemas import TextbookMeta

router = APIRouter()

# 全局解析串行化(MuPDF 非线程安全)
_PARSE_LOCK = threading.Lock()


def _safe_book_id(filename: str) -> str:
    """从文件名生成稳定 id。"""
    stem = Path(filename).stem
    # 去掉空白、保留中英文数字
    sid = re.sub(r"\s+", "_", stem)
    sid = re.sub(r"[^\w一-鿿_-]", "", sid)
    return sid or "book"


def _do_parse(book_id: str, saved_path: Path) -> None:
    """后台解析任务,通过 _PARSE_LOCK 串行化。"""
    with _PARSE_LOCK:
        try:
            data_store.update_meta_status(book_id, "parsing")
            doc = parse_file(saved_path, book_id)
            data_store.save_textbook(doc)
            logger.info(f"[upload] {book_id} 解析完成: {len(doc.chapters)} 章")
        except Exception as e:
            logger.exception(f"[upload] {book_id} 解析失败")
            data_store.update_meta_status(book_id, "failed", error=str(e))


@router.post("/upload")
async def upload(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
) -> dict:
    """支持批量上传。立刻返回,后台解析。"""
    accepted = []
    skipped = []
    for f in files:
        ext = Path(f.filename or "").suffix.lower()
        if ext not in SUPPORTED_EXTS:
            skipped.append({"filename": f.filename, "reason": f"不支持的格式 {ext}"})
            continue
        book_id = _safe_book_id(f.filename or "book")
        # 防重名:已存在时加后缀
        existing = list(TEXTBOOKS_DIR.glob(f"{book_id}.*"))
        if existing:
            i = 2
            while list(TEXTBOOKS_DIR.glob(f"{book_id}_{i}.*")):
                i += 1
            book_id = f"{book_id}_{i}"
        saved = TEXTBOOKS_DIR / f"{book_id}{ext}"
        with saved.open("wb") as out:
            shutil.copyfileobj(f.file, out)

        # 写初始 meta
        meta = TextbookMeta(
            textbook_id=book_id,
            filename=f.filename or saved.name,
            title=Path(f.filename or saved.name).stem,
            total_pages=0,
            total_chars=0,
            chapter_count=0,
            status="parsing",
        )
        data_store.upsert_meta(meta)
        background_tasks.add_task(_do_parse, book_id, saved)
        accepted.append({"book_id": book_id, "filename": f.filename})

    return {"accepted": accepted, "skipped": skipped}


@router.get("/textbooks")
def list_textbooks() -> list[dict]:
    return [m.model_dump() for m in data_store.list_metas()]


@router.post("/scan")
def scan_existing() -> dict:
    """开发便捷:扫描 data/textbooks/ 下的现有文件,触发解析(含赛方提供的 7 本)。"""
    from ..config import PARSED_DIR
    import threading
    found = 0
    for path in sorted(TEXTBOOKS_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTS:
            continue
        book_id = _safe_book_id(path.name)
        # 已解析则跳过
        if (PARSED_DIR / f"{book_id}.json").exists():
            continue
        meta = TextbookMeta(
            textbook_id=book_id,
            filename=path.name,
            title=path.stem,
            total_pages=0, total_chars=0, chapter_count=0,
            status="parsing",
        )
        data_store.upsert_meta(meta)
        threading.Thread(target=_do_parse, args=(book_id, path), daemon=True).start()
        found += 1
    return {"scanned": found}


@router.delete("/textbooks/{book_id}")
def delete_textbook(book_id: str) -> dict:
    from ..config import PARSED_DIR, GRAPHS_DIR
    removed = []
    for p in [
        PARSED_DIR / f"{book_id}.json",
        PARSED_DIR / f"{book_id}.meta.json",
        GRAPHS_DIR / f"{book_id}.json",
    ]:
        if p.exists():
            p.unlink()
            removed.append(str(p.name))
    for p in TEXTBOOKS_DIR.iterdir():
        if p.stem == book_id:
            p.unlink()
            removed.append(p.name)
    if not removed:
        raise HTTPException(404, "教材不存在")
    return {"removed": removed}
