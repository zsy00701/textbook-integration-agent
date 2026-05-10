"""文档分块。

分块策略说明(写入 docs/需求分析.md):
- 600 字一块,80 字 sliding window 重叠
- 优先按句末标点切分,避免切断知识点
- 每块保留元数据:textbook_id, book_title, chapter, page
- 600 字理由:与 BGE-small-zh 上下文(512 tokens ≈ 400-700 字)匹配,
  既能容纳完整概念解释,又不会让相关度被无关内容稀释
"""
from __future__ import annotations
import re
from dataclasses import dataclass, asdict

from ...models.schemas import TextbookDoc

CHUNK_SIZE = 600
OVERLAP = 80

# 句末断点(优先级降序)
SPLIT_CHARS = "。！？!?；;.\n"


@dataclass
class Chunk:
    chunk_id: str
    text: str
    textbook_id: str
    book_title: str
    chapter: str
    page: int
    char_offset: int

    def to_dict(self) -> dict:
        return asdict(self)


def _split_chapter(content: str, max_size: int, overlap: int) -> list[tuple[int, str]]:
    """对一个章节正文做 sliding-window 切分,返回 (offset, text) 列表。"""
    if not content:
        return []
    out: list[tuple[int, str]] = []
    pos = 0
    n = len(content)
    while pos < n:
        end = min(pos + max_size, n)
        if end < n:
            # 在 [end-100, end] 区间往左找断点
            window_start = max(end - 100, pos)
            best = -1
            for ch in SPLIT_CHARS:
                idx = content.rfind(ch, window_start, end)
                if idx > best:
                    best = idx
            if best > pos:
                end = best + 1  # 包含断点字符
        chunk = content[pos:end].strip()
        if chunk:
            out.append((pos, chunk))
        if end >= n:
            break
        pos = max(end - overlap, pos + 1)  # 防死循环
    return out


def chunk_textbook(doc: TextbookDoc) -> list[Chunk]:
    chunks: list[Chunk] = []
    for ch in doc.chapters:
        for offset, text in _split_chapter(ch.content, CHUNK_SIZE, OVERLAP):
            cid = f"{doc.textbook_id}:{ch.chapter_id}:{offset}"
            # 估算页码:如果章跨多页,按比例估
            char_ratio = offset / max(1, ch.char_count)
            est_page = int(ch.page_start + (ch.page_end - ch.page_start) * char_ratio)
            chunks.append(Chunk(
                chunk_id=cid,
                text=text,
                textbook_id=doc.textbook_id,
                book_title=doc.title,
                chapter=ch.title,
                page=est_page,
                char_offset=offset,
            ))
    return chunks
