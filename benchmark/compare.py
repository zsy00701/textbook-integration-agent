"""把多个 evaluate.py 的输出聚合成一张 Markdown 对比表。

用法::

    python compare.py results/baseline.json results/chunk500.json results/rerank.json \
        --out results/comparison.md

可直接把表粘到 docs/Agent架构说明.md 或 P2 技术报告中。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fmt_pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def render_markdown(runs: list[dict]) -> str:
    lines: list[str] = []
    lines.append("# RAG Benchmark 对比")
    lines.append("")
    lines.append(f"题目总数: {runs[0]['n_questions']}  |  共 {len(runs)} 个配置")
    lines.append("")

    has_llm = any("llm_correctness" in r["aggregate"]["overall"] for r in runs)

    lines.append("## 总体指标")
    lines.append("")
    if has_llm:
        lines.append("| Tag | 配置 | Answer | Citation | Refusal | LLM-Correct | LLM-Complete | LLM-Faithful | Avg | P95 |")
        lines.append("| --- |" + " --- |" * 9)
    else:
        lines.append("| Tag | 配置 | Answer | Citation | Refusal | Avg Latency | P95 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for r in runs:
        o = r["aggregate"]["overall"]
        lat = r["aggregate"].get("latency", {})
        cfg = json.dumps(r.get("config", {}), ensure_ascii=False)
        if has_llm:
            lines.append(
                f"| {r['tag']} | `{cfg}` | {fmt_pct(o['answer_score'])} | "
                f"{fmt_pct(o['citation_score'])} | {fmt_pct(o['refusal_acc'])} | "
                f"{fmt_pct(o.get('llm_correctness', 0))} | "
                f"{fmt_pct(o.get('llm_completeness', 0))} | "
                f"{fmt_pct(o.get('llm_faithfulness', 0))} | "
                f"{lat.get('avg_ms', '-')}ms | {lat.get('p95_ms', '-')}ms |"
            )
        else:
            lines.append(
                f"| {r['tag']} | `{cfg}` | {fmt_pct(o['answer_score'])} | "
                f"{fmt_pct(o['citation_score'])} | {fmt_pct(o['refusal_acc'])} | "
                f"{lat.get('avg_ms', '-')}ms | {lat.get('p95_ms', '-')}ms |"
            )
    lines.append("")

    lines.append("## 按题型分解 (Answer Score)")
    lines.append("")
    types = sorted({t for r in runs for t in r["aggregate"]["by_type"].keys()})
    header = "| Tag | " + " | ".join(types) + " |"
    sep = "| --- |" + " --- |" * len(types)
    lines.append(header)
    lines.append(sep)
    for r in runs:
        bt = r["aggregate"]["by_type"]
        cells = [fmt_pct(bt[t]["answer_score"]) if t in bt else "-" for t in types]
        lines.append(f"| {r['tag']} | " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## 按难度分解 (Answer Score)")
    lines.append("")
    diffs = ["easy", "medium", "hard"]
    lines.append("| Tag | " + " | ".join(diffs) + " |")
    lines.append("| --- |" + " --- |" * len(diffs))
    for r in runs:
        bd = r["aggregate"]["by_difficulty"]
        cells = [fmt_pct(bd[d]["answer_score"]) if d in bd else "-" for d in diffs]
        lines.append(f"| {r['tag']} | " + " | ".join(cells) + " |")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+", help="evaluate.py 输出的 JSON 文件")
    ap.add_argument("--out", default="results/comparison.md")
    args = ap.parse_args()

    runs = [load(Path(p)) for p in args.inputs]
    md = render_markdown(runs)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"[OK] 写入 {out}")
    print(md)


if __name__ == "__main__":
    main()
