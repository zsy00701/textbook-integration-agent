"""把整合后的知识图谱导出为 Markdown / PDF。

设计:
- 输入:master_graph (BookGraph) + decisions (list[Decision]) + stats (IntegrationStats)
- MD 结构:
    # 学科知识整合精华版
    ## 整合概览(数字摘要)
    ## 多教材融合知识点(merged 节点单独成章,展示跨教材精华)
    ## 各教材知识点(按 source_book 分组)
        ### 《教材名》
            #### 章节
                - 知识点 名称
                  定义
                  来源 第 X 页
- PDF 用 weasyprint 把 MD 转 HTML 渲染。
"""
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from io import BytesIO
from pathlib import Path

import markdown as md_lib

from ...models.schemas import BookGraph, KnowledgeNode, Decision, IntegrationStats


CATEGORY_ORDER = ["核心概念", "定理", "方法", "现象", "结构", "过程"]


def _node_key(n: KnowledgeNode) -> tuple:
    """章节 + 页码排序,保持教材原顺序。"""
    return (n.chapter, n.page, n.name)


def _is_merged(node: KnowledgeNode) -> bool:
    return "," in (node.source_book or "")


def render_markdown(
    master: BookGraph,
    decisions: list[Decision],
    stats: IntegrationStats | dict | None = None,
) -> str:
    """生成精华 Markdown。"""
    if isinstance(stats, IntegrationStats):
        s = stats.model_dump()
    elif isinstance(stats, dict):
        s = stats
    else:
        s = {}

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    nodes = master.nodes
    edges = master.edges

    merged_nodes = sorted([n for n in nodes if _is_merged(n)], key=_node_key)
    single_nodes = [n for n in nodes if not _is_merged(n)]

    # 单源:按教材分组 → 章节子组
    by_book: dict[str, list[KnowledgeNode]] = defaultdict(list)
    for n in single_nodes:
        by_book[n.source_book].append(n)
    for b in by_book:
        by_book[b].sort(key=_node_key)

    out: list[str] = []
    out.append("# 学科知识整合精华版")
    out.append("")
    out.append(f"> 自动生成于 {now} · 来自整合后的 master 图谱")
    out.append("")

    # 概览
    out.append("## 整合概览")
    out.append("")
    out.append("| 指标 | 数值 |")
    out.append("| --- | ---: |")
    out.append(f"| 原始教材数量 | {s.get('orig_books', '—')} |")
    out.append(f"| 原始字数 | {s.get('orig_chars', 0):,} |")
    out.append(f"| 精华字数(节点定义合计) | {s.get('final_chars', 0):,} |")
    ratio = s.get('ratio', 0) or 0
    out.append(f"| 压缩比 | **{ratio*100:.2f}%**(目标 ≤ 30%) |")
    out.append(f"| 原始知识点 | {s.get('orig_node_count', '—')} |")
    out.append(f"| 整合后知识点 | {s.get('final_node_count', len(nodes))} |")
    out.append(f"| 关系总数 | {len(edges)} |")
    dc = s.get("decisions_count", {}) or {}
    out.append(f"| 决策分布 | merge {dc.get('merge', 0)} · keep {dc.get('keep', 0)} · remove {dc.get('remove', 0)} |")
    out.append("")

    # merged 部分:跨教材精华
    if merged_nodes:
        out.append("---")
        out.append("")
        out.append(f"## 🔗 多教材融合知识点(共 {len(merged_nodes)} 项)")
        out.append("")
        out.append("以下知识点在多本教材中被识别为同一概念,系统择优合并保留:")
        out.append("")
        for n in merged_nodes:
            out.append(f"### {n.name}")
            out.append(f"- **类别**:{n.category} · **章节**:{n.chapter} · **页码**:第 {n.page} 页")
            out.append(f"- **来源教材**:{n.source_book}")
            out.append("")
            out.append(n.definition)
            out.append("")
        out.append("")

    # 单源部分:按教材分组
    out.append("---")
    out.append("")
    out.append("## 各教材知识点")
    out.append("")

    for book in sorted(by_book.keys()):
        ns = by_book[book]
        out.append(f"### 《{book}》({len(ns)} 个知识点)")
        out.append("")
        # 章节子分组
        by_chapter: dict[str, list[KnowledgeNode]] = defaultdict(list)
        for n in ns:
            by_chapter[n.chapter].append(n)
        for ch in sorted(by_chapter.keys(), key=lambda c: (by_chapter[c][0].page, c)):
            cn = by_chapter[ch]
            out.append(f"#### {ch}")
            out.append("")
            for n in cn:
                out.append(f"- **{n.name}** ({n.category},第 {n.page} 页)")
                out.append(f"  {n.definition}")
            out.append("")
        out.append("")

    # 决策摘要(取前 10 条 merge 展示)
    merge_decisions = [d for d in decisions if d.action == "merge"]
    if merge_decisions:
        out.append("---")
        out.append("")
        out.append("## 整合决策摘要(前 20 条 merge)")
        out.append("")
        out.append("| 置信 | 影响节点 | 理由 |")
        out.append("| ---: | ---: | --- |")
        for d in sorted(merge_decisions, key=lambda x: -x.confidence)[:20]:
            reason = (d.reason or "").replace("\n", " ").replace("|", "\\|")[:90]
            out.append(f"| {d.confidence*100:.0f}% | {len(d.affected_nodes)} | {reason} |")
        out.append("")

    out.append("")
    out.append("---")
    out.append("")
    out.append("*本文档由学科知识整合智能体自动生成。点击知识点名称可在前端查看其定义、关系与原文出处引用。*")
    out.append("")

    return "\n".join(out)


# CSS 让 PDF 看着像样,中文字体,清淡风格
PDF_CSS = """
@page { size: A4; margin: 18mm 16mm; }
body {
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Source Han Sans CN", sans-serif;
  color: #2a2a2a;
  font-size: 10.5pt;
  line-height: 1.65;
}
h1 { color: #1f4e3d; font-size: 22pt; margin: 0 0 6pt 0; border-bottom: 2px solid #1f4e3d; padding-bottom: 6pt; }
h2 { color: #1f4e3d; font-size: 15pt; margin: 20pt 0 8pt 0; padding-bottom: 4pt; border-bottom: 1px solid #d8d5cf; page-break-after: avoid; }
h3 { color: #2a2a2a; font-size: 12pt; margin: 14pt 0 6pt 0; page-break-after: avoid; }
h4 { color: #4a4a4a; font-size: 11pt; margin: 10pt 0 4pt 0; page-break-after: avoid; }
p, li { font-size: 10.5pt; }
strong { color: #1f4e3d; font-weight: 600; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0; }
th, td { border: 1px solid #e7e5e0; padding: 4pt 8pt; text-align: left; font-size: 10pt; }
th { background: #f4f1ec; color: #2a2a2a; }
ul { margin: 4pt 0 4pt 18pt; }
li { margin-bottom: 3pt; }
hr { border: none; border-top: 1px solid #d8d5cf; margin: 14pt 0; }
blockquote { color: #6b6b6b; font-size: 9.5pt; margin: 4pt 0; padding-left: 10pt; border-left: 3px solid #1f4e3d; }
em { color: #6b6b6b; font-style: italic; font-size: 9.5pt; }
"""


def render_pdf_bytes(markdown_text: str) -> bytes:
    """MD → HTML → PDF。"""
    from weasyprint import HTML, CSS

    html = md_lib.markdown(
        markdown_text,
        extensions=["tables", "fenced_code", "toc"],
    )
    full_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>学科知识整合精华版</title></head>
<body>{html}</body></html>"""

    pdf_io = BytesIO()
    HTML(string=full_html).write_pdf(pdf_io, stylesheets=[CSS(string=PDF_CSS)])
    return pdf_io.getvalue()
