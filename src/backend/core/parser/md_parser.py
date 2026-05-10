"""Markdown 解析:按 # / ## / ### 切章节。"""
from __future__ import annotations
import re
from pathlib import Path
from ...models.schemas import Chapter, TextbookDoc

HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")


def parse_md(file_path: Path, textbook_id: str) -> TextbookDoc:
    text = file_path.read_text(encoding="utf-8", errors="ignore")
    lines = text.splitlines()

    chapters: list[dict] = []
    current = None
    line_no = 0  # 用 line 序号近似页码

    def flush(end_line: int):
        nonlocal current
        if current:
            current["page_end"] = max(current["page_start"], end_line // 40 + 1)
            current["char_count"] = len(current["content"])
            chapters.append(current)
            current = None

    for raw in lines:
        line_no += 1
        m = HEADING_RE.match(raw)
        if m and len(m.group(1)) <= 2:  # 只把 # / ## 当章节
            flush(line_no - 1)
            current = {
                "chapter_id": f"{textbook_id}_ch{len(chapters) + 1:02d}",
                "title": m.group(2).strip(),
                "page_start": line_no // 40 + 1,
                "page_end": line_no // 40 + 1,
                "content": "",
                "char_count": 0,
            }
        else:
            if current is None:
                # 文档开头无标题:建一个隐式章节
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
