"""PDF 解析:逐页流式 + 章节标题识别(字号 + 正则双判)。

设计要点:
- 用 PyMuPDF 的 page-by-page API,绝不一次性 load
- 章节判定:
  1. 强匹配:行首 "第X章/篇/部分"(中文数字或阿拉伯数字)
  2. 弱匹配:字号 ≥ body_font*1.4 + bold + 短行(<25 字)
- 过滤页眉页脚(每页固定位置 < 50pt 或 > height-50pt 的孤立短文本)
- 大文件(437MB)实测有效:每页处理后释放
"""
from __future__ import annotations
import re
from pathlib import Path
from typing import Iterator
import fitz  # PyMuPDF
from loguru import logger

from ...models.schemas import Chapter, TextbookDoc

# 章节标题正则(强匹配,优先级最高)
CHAPTER_PATTERNS = [
    re.compile(r"^\s*第\s*[一二三四五六七八九十百千〇零0-9]+\s*章\s*[^\d]"),
    re.compile(r"^\s*第\s*[一二三四五六七八九十百千〇零0-9]+\s*篇\s*[^\d]"),
    re.compile(r"^\s*第\s*[一二三四五六七八九十百千〇零0-9]+\s*部分\s*"),
    re.compile(r"^\s*Chapter\s+\d+", re.IGNORECASE),
]

# 排除明显非章节的(目录、参考文献等)
EXCLUDE_PATTERNS = [
    re.compile(r"^\s*目\s*录\s*$"),
    re.compile(r"^\s*参考文献\s*$"),
    re.compile(r"^\s*索\s*引\s*$"),
    re.compile(r"^\s*\d+\s*$"),  # 纯页码
]


def _is_chapter_title(text: str) -> bool:
    text = text.strip()
    if len(text) < 4 or len(text) > 60:
        return False
    if any(p.match(text) for p in EXCLUDE_PATTERNS):
        return False
    return any(p.search(text) for p in CHAPTER_PATTERNS)


def _clean_page_text(blocks: list, page_height: float) -> str:
    """从 dict blocks 提取正文,过滤页眉页脚。"""
    lines = []
    for blk in blocks:
        if blk.get("type") != 0:  # 0=text
            continue
        for line in blk.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            text = "".join(s.get("text", "") for s in spans).strip()
            if not text:
                continue
            y = line.get("bbox", [0, 0, 0, 0])[1]
            # 过滤页眉(顶部 50pt)和页脚(底部 50pt)且文本短
            if (y < 45 or y > page_height - 45) and len(text) < 30:
                continue
            lines.append(text)
    return "\n".join(lines)


def _detect_chapter_in_page(blocks: list, page_height: float) -> tuple[str | None, float | None]:
    """从 page blocks 中找最可能的章节标题及其 y 坐标。

    策略:
    1. 真章节标题在医学教材中通常 fs ≥ 19,且短(<30 字)
    2. "第 X 章" 经常拆成两行渲染:["第二章", "细胞的基本功能"],需要拼接
    3. 排除孤立大字号数字(页码/装饰)、英文译名、纯标点
    """
    big_lines: list[tuple[float, float, str]] = []  # (font_size, y, text)
    for blk in blocks:
        if blk.get("type") != 0:
            continue
        for line in blk.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            text = "".join(s.get("text", "") for s in spans).strip()
            if not text:
                continue
            y = line.get("bbox", [0, 0, 0, 0])[1]
            if y < 45 or y > page_height - 45:
                continue
            font_size = max((s.get("size", 0) for s in spans), default=0)
            if font_size >= 18 and len(text) < 30:
                big_lines.append((font_size, y, text))

    big_lines.sort(key=lambda x: x[1])  # 按 y 排序

    # 1) 强匹配:大字号 + "第X章/篇" 命中
    for i, (fs, y, t) in enumerate(big_lines):
        # 排除纯数字/纯英文/单字
        if PURE_NUM_RE.match(t) or _is_western_only(t) or len(t) <= 1:
            continue
        if "第" in t and any(k in t for k in ("章", "篇", "部分")):
            # 拼接同字号紧邻短行(章名)
            head = t.strip()
            pattern_only = re.match(r"^第\s*[一二三四五六七八九十百千〇零0-9]+\s*[章篇]\s*$", head)
            if pattern_only:
                # 向后找紧邻的同字号(±1)实词
                for j in range(i + 1, min(i + 3, len(big_lines))):
                    fs2, y2, t2 = big_lines[j]
                    if y2 - y > 80:  # 距离太远不算
                        break
                    if PURE_NUM_RE.match(t2) or _is_western_only(t2):
                        continue
                    if fs2 < fs - 2 or fs2 > fs + 2:
                        continue
                    if not (0 < len(t2) < 25):
                        continue
                    head = head + " " + t2.strip()
                    break
            return head, y

    # 2) 弱匹配:正则识别(原有逻辑)
    for fs, y, t in big_lines:
        if PURE_NUM_RE.match(t) or _is_western_only(t):
            continue
        if _is_chapter_title(t):
            return t.strip(), y

    return None, None


PURE_NUM_RE = re.compile(r"^[\d\s]+$")
WESTERN_RE = re.compile(r"^[A-Za-z\s,.\-\d]+$")


def _is_western_only(s: str) -> bool:
    return bool(WESTERN_RE.match(s))


def parse_pdf(file_path: Path, textbook_id: str) -> TextbookDoc:
    """主入口:逐页解析,聚合章节。"""
    logger.info(f"[PDF] 开始解析 {file_path.name}")
    doc = fitz.open(str(file_path))
    chapters: list[dict] = []
    current = None  # 当前章节累积器
    total_chars = 0

    try:
        for page_no in range(len(doc)):
            page = doc[page_no]
            page_dict = page.get_text("dict")
            blocks = page_dict.get("blocks", [])
            ph = page.rect.height

            # 检测本页是否包含新章节
            chap_title, chap_y = _detect_chapter_in_page(blocks, ph)

            page_text = _clean_page_text(blocks, ph)

            if chap_title:
                # 落幕上一章
                if current:
                    current["page_end"] = page_no  # 1-based: page_no = (page_no-1)+1 = 上一页
                    current["char_count"] = len(current["content"])
                    chapters.append(current)
                current = {
                    "chapter_id": f"{textbook_id}_ch{len(chapters) + 1:02d}",
                    "title": chap_title,
                    "page_start": page_no + 1,
                    "page_end": page_no + 1,
                    "content": "",
                    "char_count": 0,
                }

            if current is None:
                # 还没遇到第一章(前言/封面),跳过累积
                continue

            current["content"] += page_text + "\n"

            # 进度日志(每 50 页一次)
            if (page_no + 1) % 50 == 0:
                logger.info(f"[PDF] {file_path.name} {page_no+1}/{len(doc)} 页, 已识别 {len(chapters)+(1 if current else 0)} 章")

        # 收尾
        if current:
            current["page_end"] = len(doc)
            current["char_count"] = len(current["content"])
            chapters.append(current)

        # 极端兜底:全本都没识别到章节,按每 30 页切一段
        if not chapters:
            logger.warning(f"[PDF] {file_path.name} 未识别到章节,按页切片")
            chunk_size = 30
            for i in range(0, len(doc), chunk_size):
                content = ""
                for p in range(i, min(i + chunk_size, len(doc))):
                    page = doc[p]
                    pd = page.get_text("dict")
                    content += _clean_page_text(pd.get("blocks", []), page.rect.height) + "\n"
                chapters.append({
                    "chapter_id": f"{textbook_id}_ch{len(chapters) + 1:02d}",
                    "title": f"第 {len(chapters) + 1} 部分(自动切分,页 {i+1}-{min(i+chunk_size, len(doc))})",
                    "page_start": i + 1,
                    "page_end": min(i + chunk_size, len(doc)),
                    "content": content,
                    "char_count": len(content),
                })

        total_chars = sum(c["char_count"] for c in chapters)
        title_guess = file_path.stem
        logger.info(f"[PDF] {file_path.name} 解析完成:{len(doc)} 页, {len(chapters)} 章, {total_chars/1000:.1f}k 字")

        return TextbookDoc(
            textbook_id=textbook_id,
            filename=file_path.name,
            title=title_guess,
            total_pages=len(doc),
            total_chars=total_chars,
            chapters=[Chapter(**c) for c in chapters],
        )
    finally:
        doc.close()
