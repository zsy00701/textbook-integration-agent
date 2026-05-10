"""压缩控制:整合后字数 ≤ 原始 30%,超出时按 confidence 升序删冗余节点。

策略:
1. 计算"原始总字数" = sum(book.total_chars)
2. 计算"整合后总字数" = sum(node.definition 长度)(主图谱内容只剩定义)
3. 若超 30% 上限,按 confidence 从低到高删 keep 类决策对应的节点
   (merge 类不删,因为合并已是有意保留的精华)
"""
from __future__ import annotations
from loguru import logger

from ...models.schemas import KnowledgeNode, Decision


def char_count(nodes: list[KnowledgeNode]) -> int:
    return sum(len(n.definition) + len(n.name) + len(n.chapter) for n in nodes)


def enforce_compression(
    nodes: list[KnowledgeNode],
    decisions: list[Decision],
    orig_chars: int,
    ratio_limit: float = 0.30,
) -> tuple[list[KnowledgeNode], list[Decision]]:
    """超额时追加 remove 决策直到达标。"""
    target = int(orig_chars * ratio_limit)
    cur = char_count(nodes)
    if cur <= target:
        logger.info(f"[compress] 当前 {cur}/{orig_chars} = {cur/orig_chars*100:.1f}%, 达标")
        return nodes, decisions

    logger.info(f"[compress] 超额 {cur}/{orig_chars} = {cur/orig_chars*100:.1f}%,目标 ≤{ratio_limit*100:.0f}%,开始裁剪")

    # 候选可删:对应 keep 决策的节点(单源,信息冗余度大)
    keep_decisions = [d for d in decisions if d.action == "keep"]
    keep_decisions.sort(key=lambda d: (d.confidence, -len(d.affected_nodes)))  # confidence 升序

    removed_ids: set[str] = set()
    new_decisions = list(decisions)
    by_id = {n.id: n for n in nodes}

    for d in keep_decisions:
        if cur <= target:
            break
        for nid in d.affected_nodes:
            if nid in by_id and nid not in removed_ids:
                cur -= len(by_id[nid].definition) + len(by_id[nid].name)
                removed_ids.add(nid)
        # 把决策从 keep 改为 remove
        d_dump = d.model_dump()
        d_dump["action"] = "remove"
        d_dump["reason"] = f"压缩约束:为达到 ≤{ratio_limit*100:.0f}% 压缩比,删除冗余单源知识点。原因:{d.reason}"
        new_decisions = [
            Decision(**d_dump) if dd.decision_id == d.decision_id else dd
            for dd in new_decisions
        ]

    final_nodes = [n for n in nodes if n.id not in removed_ids]
    logger.info(f"[compress] 删除 {len(removed_ids)} 节点,最终 {char_count(final_nodes)}/{orig_chars} = {char_count(final_nodes)/orig_chars*100:.1f}%")
    return final_nodes, new_decisions
