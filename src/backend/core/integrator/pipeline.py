"""跨教材整合主流程:对齐 → 决策 → 压缩 → 输出 master_graph。"""
from __future__ import annotations
from collections import Counter
from loguru import logger

from ...config import settings
from ...models.schemas import (
    BookGraph, KnowledgeNode, Relation, Decision,
    IntegrationResult, IntegrationStats,
)
from ...storage import data_store
from .aligner import align_clusters
from .decision import decide_cluster
from .compressor import enforce_compression


def run_integration(graphs: list[BookGraph]) -> IntegrationResult:
    """整合多本图谱,产出 master_graph + decisions + stats。"""
    if not graphs:
        raise ValueError("没有可用的图谱")

    # 1. 收集所有节点 + 边
    all_nodes: list[KnowledgeNode] = []
    all_edges: list[Relation] = []
    for g in graphs:
        all_nodes.extend(g.nodes)
        all_edges.extend(g.edges)

    orig_node_count = len(all_nodes)
    logger.info(f"[integration] 原始 {len(graphs)} 本, {orig_node_count} 节点, {len(all_edges)} 关系")

    # 2. 对齐成簇
    clusters = align_clusters(all_nodes, threshold=settings.align_threshold)
    logger.info(f"[integration] 对齐后 {len(clusters)} 簇")

    # 3. 每簇决策
    decisions: list[Decision] = []
    final_nodes: list[KnowledgeNode] = []
    old_id_to_new: dict[str, str] = {}
    for cluster in clusters:
        d, kept = decide_cluster(cluster)
        decisions.append(d)
        final_nodes.append(kept)
        for n in cluster:
            old_id_to_new[n.id] = kept.id

    # 4. 压缩约束
    orig_chars = 0
    for g in graphs:
        meta = data_store.list_metas()
        for m in meta:
            if m.textbook_id == g.book_id:
                orig_chars += m.total_chars
                break
    if orig_chars == 0:
        orig_chars = sum(len(n.definition) for n in all_nodes) * 5  # 兜底估算
    final_nodes, decisions = enforce_compression(
        final_nodes, decisions, orig_chars, settings.compression_ratio_limit
    )

    # 5. 边重映射 + 去重
    valid_ids = {n.id for n in final_nodes}
    seen_edges: set[tuple[str, str, str]] = set()
    final_edges: list[Relation] = []
    for e in all_edges:
        ns = old_id_to_new.get(e.source)
        nt = old_id_to_new.get(e.target)
        if not ns or not nt or ns == nt or ns not in valid_ids or nt not in valid_ids:
            continue
        key = (ns, nt, e.relation_type)
        if key in seen_edges:
            continue
        seen_edges.add(key)
        final_edges.append(Relation(
            source=ns, target=nt, relation_type=e.relation_type, description=e.description,
        ))

    # 6. 统计
    final_chars = sum(len(n.definition) + len(n.name) + len(n.chapter) for n in final_nodes)
    counts = Counter(d.action for d in decisions)
    stats = IntegrationStats(
        orig_books=len(graphs),
        orig_chars=orig_chars,
        final_chars=final_chars,
        ratio=final_chars / orig_chars if orig_chars else 0.0,
        orig_node_count=orig_node_count,
        final_node_count=len(final_nodes),
        decisions_count={
            "merge": counts.get("merge", 0),
            "keep": counts.get("keep", 0),
            "remove": counts.get("remove", 0),
        },
    )

    master = BookGraph(
        book_id="master",
        book_title=f"整合图谱 ({len(graphs)} 本教材)",
        nodes=final_nodes,
        edges=final_edges,
    )
    return IntegrationResult(master_graph=master, decisions=decisions, stats=stats)
