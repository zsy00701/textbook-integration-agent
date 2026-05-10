"""DOCX 解析:按 Heading 1/2 切章节。"""
from __future__ import annotations
from pathlib import Path
from docx import Document
from ...models.schemas import Chapter, TextbookDoc


def parse_docx(file_path: Path, textbook_id: str) -> TextbookDoc:
    doc = Document(str(file_path))
    chapters: list[dict] = []
    current = None
    para_no = 0

    def flush(end_para: int):
        nonlocal current
        if current:
            current["page_end"] = max(current["page_start"], end_para // 30 + 1)
            current["char_count"] = len(current["content"])
            chapters.append(current)
            current = None

    for p in doc.paragraphs:
        para_no += 1
        text = p.text.strip()
        if not text:
            continue
        style = (p.style.name or "").lower() if p.style else ""
        is_heading = style.startswith("heading 1") or style.startswith("heading 2") or style.startswith("title")
        if is_heading and len(text) < 60:
            flush(para_no - 1)
            current = {
                "chapter_id": f"{textbook_id}_ch{len(chapters) + 1:02d}",
                "title": text,
                "page_start": para_no // 30 + 1,
                "page_end": para_no // 30 + 1,
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
            current["content"] += text + "\n"

    flush(para_no)
    total_chars = sum(c["char_count"] for c in chapters)
    return TextbookDoc(
        textbook_id=textbook_id,
        filename=file_path.name,
        title=file_path.stem,
        total_pages=max(1, para_no // 30),
        total_chars=total_chars,
        chapters=[Chapter(**c) for c in chapters],
    )
