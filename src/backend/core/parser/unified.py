"""统一解析入口:按扩展名分发,并对超长章节做后处理切分。"""
from __future__ import annotations
from pathlib import Path
from loguru import logger
from ...models.schemas import TextbookDoc, Chapter


# 章节识别失败时常见超长(整本被认成 1 章),切到此值
MAX_CHAPTER_CHARS = 30_000


def _split_oversized_chapters(doc: TextbookDoc) -> TextbookDoc:
    """把过长章节切成 30k 字的子章节,提升 KG 抽取覆盖率。"""
    new_chapters: list[Chapter] = []
    for ch in doc.chapters:
        if ch.char_count <= MAX_CHAPTER_CHARS:
            new_chapters.append(ch)
            continue
        # 切分:按 30k 一段,优先在段落处切
        n_subs = (ch.char_count + MAX_CHAPTER_CHARS - 1) // MAX_CHAPTER_CHARS
        sub_size = ch.char_count // n_subs + 1
        content = ch.content
        page_span = max(1, ch.page_end - ch.page_start)
        pos = 0
        sub_idx = 1
        while pos < len(content):
            end = min(pos + sub_size, len(content))
            # 在 [end-200, end] 找段落断点
            if end < len(content):
                window = content[max(end - 200, pos):end]
                last_para = window.rfind("\n\n")
                if last_para > 0:
                    end = max(end - 200, pos) + last_para
            sub_content = content[pos:end].strip()
            if sub_content:
                # 估算子章节页码区间
                ratio_start = pos / len(content)
                ratio_end = end / len(content)
                sub_page_start = int(ch.page_start + page_span * ratio_start)
                sub_page_end = int(ch.page_start + page_span * ratio_end)
                new_chapters.append(Chapter(
                    chapter_id=f"{ch.chapter_id}_sub{sub_idx:02d}",
                    title=f"{ch.title}(自动切分 {sub_idx}/{n_subs})",
                    page_start=sub_page_start,
                    page_end=sub_page_end,
                    content=sub_content,
                    char_count=len(sub_content),
                ))
                sub_idx += 1
            pos = end
        logger.info(f"[parser] 章节《{ch.title[:30]}》过长 ({ch.char_count}字),切为 {sub_idx-1} 子章节")

    if len(new_chapters) != len(doc.chapters):
        logger.info(f"[parser] {doc.textbook_id}: 章节数 {len(doc.chapters)} → {len(new_chapters)}")
    return TextbookDoc(
        textbook_id=doc.textbook_id,
        filename=doc.filename,
        title=doc.title,
        total_pages=doc.total_pages,
        total_chars=doc.total_chars,
        chapters=new_chapters,
    )


def parse_file(file_path: Path, textbook_id: str) -> TextbookDoc:
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        from .pdf_parser import parse_pdf
        doc = parse_pdf(file_path, textbook_id)
    elif ext in (".md", ".markdown"):
        from .md_parser import parse_md
        doc = parse_md(file_path, textbook_id)
    elif ext == ".txt":
        from .txt_parser import parse_txt
        doc = parse_txt(file_path, textbook_id)
    elif ext == ".docx":
        from .docx_parser import parse_docx
        doc = parse_docx(file_path, textbook_id)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")
    return _split_oversized_chapters(doc)


SUPPORTED_EXTS = {".pdf", ".md", ".markdown", ".txt", ".docx"}
