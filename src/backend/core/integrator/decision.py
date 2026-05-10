"""整合决策:对每个簇决定 merge/keep/remove,生成 result_node。"""
from __future__ import annotations
import uuid
from loguru import logger

from ...models.schemas import KnowledgeNode, Decision


def _pick_best_definition(nodes: list[KnowledgeNode]) -> KnowledgeNode:
    """选最长 + 最完整的定义为代表。"""
    return max(nodes, key=lambda n: (len(n.definition), -len(n.name)))


def decide_cluster(cluster: list[KnowledgeNode]) -> tuple[Decision, KnowledgeNode]:
    """
    返回 (Decision, 整合后保留的 KnowledgeNode)。

    规则:
    - 簇大小 1 → keep
    - 簇大小 ≥2 → merge,定义最完整的那个胜出
    - remove 由上游 compressor 在压缩比超额时追加
    """
    decision_id = f"d_{uuid.uuid4().hex[:8]}"
    if len(cluster) == 1:
        n = cluster[0]
        return (
            Decision(
                decision_id=decision_id,
                action="keep",
                affected_nodes=[n.id],
                result_node=n.id,
                reason=f"《{n.source_book}》独有概念,直接保留",
                confidence=1.0,
            ),
            n,
        )

    # merge
    best = _pick_best_definition(cluster)
    sources = sorted(set(n.source_book for n in cluster))
    new_id = f"merged_{uuid.uuid4().hex[:8]}"
    merged_node = KnowledgeNode(
        id=new_id,
        name=best.name,
        definition=best.definition,
        category=best.category,
        chapter=best.chapter,
        page=best.page,
        source_book=",".join(sources),  # 多源标记
    )
    return (
        Decision(
            decision_id=decision_id,
            action="merge",
            affected_nodes=[n.id for n in cluster],
            result_node=new_id,
            reason=(
                f"{len(sources)} 本教材({','.join(sources)})均讲解了'{best.name}',"
                f"保留《{best.source_book}》版本因其定义最系统(共 {len(best.definition)} 字)"
            ),
            confidence=0.85 + min(0.10, 0.03 * len(cluster)),
        ),
        merged_node,
    )
