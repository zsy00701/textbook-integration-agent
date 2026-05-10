"""数据集分布统计 → Markdown 表(可直接贴报告)。

用法::

    python stats.py            # 打印到 stdout
    python stats.py --md stats.md   # 同时写文件
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

VALID_TEXTBOOKS = [
    "局部解剖学", "组织学与胚胎学", "生理学", "医学微生物学",
    "病理学", "传染病学", "病理生理学",
]
TYPES = ["factual", "comparative", "reasoning", "cross_book", "unanswerable"]
DIFFS = ["easy", "medium", "hard"]


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def render(items: list[dict]) -> str:
    n = len(items)
    type_cnt = Counter(o["type"] for o in items)
    diff_cnt = Counter(o["difficulty"] for o in items)
    book_cnt: Counter = Counter()
    for o in items:
        for b in o["textbooks"]:
            book_cnt[b] += 1
    cross_cnt = Counter(len(o["textbooks"]) for o in items if o["type"] != "unanswerable")
    avg_kw = sum(len(o["keywords"]) for o in items) / n
    avg_qlen = sum(len(o["question"]) for o in items) / n
    avg_alen = sum(len(o["answer_summary"]) for o in items) / n

    L: list[str] = []
    L.append(f"# Benchmark 数据集统计 ({n} 题)")
    L.append("")
    L.append(f"- 平均 keywords 数:**{avg_kw:.1f}** / 题")
    L.append(f"- 平均 question 长度:**{avg_qlen:.0f}** 字符")
    L.append(f"- 平均 answer_summary 长度:**{avg_alen:.0f}** 字符")
    L.append("")

    L.append("## 题型分布")
    L.append("")
    L.append("| Type | 数量 | 占比 |")
    L.append("| --- | ---: | ---: |")
    for t in TYPES:
        c = type_cnt.get(t, 0)
        L.append(f"| {t} | {c} | {c / n * 100:.1f}% |")
    L.append("")

    L.append("## 难度分布")
    L.append("")
    L.append("| Difficulty | 数量 | 占比 |")
    L.append("| --- | ---: | ---: |")
    for d in DIFFS:
        c = diff_cnt.get(d, 0)
        L.append(f"| {d} | {c} | {c / n * 100:.1f}% |")
    L.append("")

    L.append("## 教材覆盖(允许多教材计数)")
    L.append("")
    L.append("| 教材 | 出现次数 |")
    L.append("| --- | ---: |")
    for b in VALID_TEXTBOOKS:
        L.append(f"| {b} | {book_cnt.get(b, 0)} |")
    L.append("")

    L.append("## 跨教材深度(非 unanswerable 题)")
    L.append("")
    L.append("| 涉及教材数 | 题数 |")
    L.append("| ---: | ---: |")
    for k in sorted(cross_cnt):
        L.append(f"| {k} | {cross_cnt[k]} |")
    L.append("")

    # 题型 × 难度交叉
    L.append("## 题型 × 难度 矩阵")
    L.append("")
    L.append("| Type \\ Difficulty | " + " | ".join(DIFFS) + " | 合计 |")
    L.append("| --- |" + " ---: |" * (len(DIFFS) + 1))
    for t in TYPES:
        row = [t]
        total = 0
        for d in DIFFS:
            c = sum(1 for o in items if o["type"] == t and o["difficulty"] == d)
            row.append(str(c))
            total += c
        row.append(str(total))
        L.append("| " + " | ".join(row) + " |")
    L.append("")

    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", default=str(Path(__file__).parent / "questions.jsonl"))
    ap.add_argument("--md", default=None, help="可选:写到该路径")
    args = ap.parse_args()

    items = load(Path(args.questions))
    md = render(items)
    print(md)
    if args.md:
        Path(args.md).write_text(md, encoding="utf-8")
        print(f"\n[OK] 写入 {args.md}")


if __name__ == "__main__":
    main()
