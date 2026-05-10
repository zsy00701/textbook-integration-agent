"""一次性清洗章节标题。

问题:PDF 解析器把孤立数字(如 "10")或长正文片段误认成章节标题,导致
data/parsed 和 data/graphs 中存了形如 "10(自动切分 4/19)" 或
"第六章),周期为数秒至数分钟。平滑肌细胞..." 这种垃圾章节名。

策略:
- 标题只含数字 → 用 "第 N 部分(book_title)"
- "(自动切分 X/N)" 后缀仍保留(信息量),但前面如果是数字/垃圾,替换前缀
- 标题超过 25 字 → 截到首个标点或前 18 字
- 把 "(自动切分" 之前的真实章节标题保留

用法:
    python scripts/clean_chapter_titles.py
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PARSED_DIR = ROOT / "data" / "parsed"
GRAPHS_DIR = ROOT / "data" / "graphs"

# "第二章 细胞的基本功能" 这种
GOOD_HEAD = re.compile(r"^(第\s*[一二三四五六七八九十百千〇零0-9]+\s*[章篇部分]\s*[一-龥]{1,30})")
# 纯数字
PURE_NUM = re.compile(r"^\d+$")
SPLIT_SUFFIX = re.compile(r"\(自动切分\s*(\d+)\s*/\s*(\d+)\)\s*$")


def clean_title(raw: str, fallback_idx: int, book_title: str) -> str:
    raw = raw.strip()
    # 提取自动切分尾巴
    suffix = ""
    m = SPLIT_SUFFIX.search(raw)
    base = raw
    if m:
        base = raw[: m.start()].strip()
        suffix = f"(第 {m.group(1)}/{m.group(2)} 部分)"

    # 优质章节头匹配
    g = GOOD_HEAD.match(base)
    if g:
        head = g.group(1).strip()
        # 如果匹配后还有内容(碎片),全删
        cleaned = head
    else:
        # 纯数字 / 垃圾长串
        if PURE_NUM.match(base) or len(base) > 28:
            cleaned = f"第 {fallback_idx} 部分"
        elif not base:
            cleaned = f"第 {fallback_idx} 部分"
        else:
            cleaned = base[:24]

    return f"{cleaned}{suffix}".strip()


def clean_parsed():
    n_files = 0
    n_chapters = 0
    for jf in sorted(PARSED_DIR.glob("*.json")):
        if jf.name.endswith(".meta.json"):
            continue
        data = json.loads(jf.read_text(encoding="utf-8"))
        title = data.get("title", "")
        for i, ch in enumerate(data.get("chapters", []), 1):
            old = ch.get("title", "")
            new = clean_title(old, i, title)
            if old != new:
                ch["title"] = new
                n_chapters += 1
        jf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        n_files += 1
    print(f"[parsed] 清洗 {n_files} 文件, 改动 {n_chapters} 章节标题")


def clean_graphs():
    n_files = 0
    n_nodes = 0
    for jf in sorted(GRAPHS_DIR.glob("*.json")):
        data = json.loads(jf.read_text(encoding="utf-8"))
        # graph 里 nodes 的 chapter 字段
        title = data.get("book_title", "")
        # 章节序号建立索引(从 chapter_id 推 idx)
        for n in data.get("nodes", []):
            old = n.get("chapter", "")
            # 从 id 中抽 ch 数字
            cid = n.get("id", "")
            m = re.search(r"_ch(\d+)", cid)
            idx = int(m.group(1)) if m else 1
            new = clean_title(old, idx, title)
            if old != new:
                n["chapter"] = new
                n_nodes += 1
        jf.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        n_files += 1
    print(f"[graphs] 清洗 {n_files} 文件, 改动 {n_nodes} 节点章节字段")


if __name__ == "__main__":
    clean_parsed()
    clean_graphs()
    print("\n下一步:触发 /api/integration/run 重出 master,然后 /api/rag/index 重建索引")
