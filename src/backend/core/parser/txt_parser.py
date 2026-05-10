"""TXT 解析:正则识别章节标题。"""
from __future__ import annotations
import re
from pathlib import Path
from ...models.schemas import Chapter, TextbookDoc

CHAPTER_RE = re.compile(
    r"^\s*第\s*[一二三四五六七八九十百千〇零0-9]+\s*[章篇部分]\s",
)


def parse_txt(file_path: Path, textbook_id: str) -> TextbookDoc:
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()
    chapters: list[dict] = []
    current = None
    line_no = 0

    def flush(end_line: int):
        nonlocal current
        if current:
            current["page_end"] = max(current["page_start"], end_line // 40 + 1)
            current["char_count"] = len(current["content"])
            chapters.append(current)
            current = None

    for raw in lines:
        line_no += 1
        if CHAPTER_RE.match(raw) and len(raw.strip()) < 50:
            flush(line_no - 1)
            current = {
                "chapter_id": f"{textbook_id}_ch{len(chapters) + 1:02d}",
                "title": raw.strip(),
                "page_start": line_no // 40 + 1,
                "page_end": line_no // 40 + 1,
                "content": "",
                "char_count": 0,
            }
        else:
            if current is None:
                current = {
                    "chapter_id": f"{textbook_id}_ch01",
                    "title": file_path.stem,
                    "page_start": 1,
                    "page_end": 1,
                    "content": "",
                    "char_count": 0,
                }
            current["content"] += raw + "\n"

    flush(line_no)
    total_chars = sum(c["char_count"] for c in chapters)
    return TextbookDoc(
        textbook_id=textbook_id,
        filename=file_path.name,
        title=file_path.stem,
        total_pages=max(1, line_no // 40),
        total_chars=total_chars,
        chapters=[Chapter(**c) for c in chapters],
    )
