"""跨教材节点对齐:embedding 召回 + LLM 二次裁决。

策略:
1. 用 BGE 嵌入所有节点(name + 定义前 80 字)
2. 跨教材两两计算余弦,> ALIGN_THRESHOLD 进入候选
3. 候选数量大时,只对边界值(0.85-0.92)做 LLM 复查
4. 用并查集聚合成簇
"""
from __future__ import annotations
import numpy as np
from loguru import logger

from ...config import settings
from ...models.schemas import KnowledgeNode
from ..agent.llm_client import get_llm
from ..extractor.prompts import ALIGN_VERIFY_SYSTEM, ALIGN_VERIFY_PROMPT
from .embedder_singleton import get_embedder


def _node_text(n: KnowledgeNode) -> str:
    return f"{n.name}。{n.definition[:120]}"


class UnionFind:
    def __init__(self):
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def _llm_verify_pair(a: KnowledgeNode, b: KnowledgeNode) -> tuple[bool, float]:
    """二元判定 A=B,用 deepseek-chat(快+JSON 稳),不用推理模型。"""
    try:
        prompt = ALIGN_VERIFY_PROMPT.format(
            name_a=a.name, def_a=a.definition[:200], book_a=a.source_book,
            name_b=b.name, def_b=b.definition[:200], book_b=b.source_book,
        )
        result = get_llm().complete_json(
            prompt, system=ALIGN_VERIFY_SYSTEM, max_tokens=200,
            model="deepseek-chat",  # 显式覆盖:推理模型对二元判定无收益且 JSON 不稳
        )
        if not isinstance(result, dict):
            return False, 0.0
        return bool(result.get("same", False)), float(result.get("confidence", 0.5))
    except Exception as e:
        logger.warning(f"[align] LLM 验证失败,回退用 embedding 分数: {e}")
        return False, 0.0


def align_clusters(
    nodes: list[KnowledgeNode],
    threshold: float | None = None,
    llm_verify_band: tuple[float, float] = (0.85, 0.93),
    max_llm_calls: int = 80,
) -> list[list[KnowledgeNode]]:
    """返回节点簇列表(每簇内节点判定为同一概念)。

    单元素簇也返回(便于上游统一处理)。
    """
    if not nodes:
        return []
    threshold = threshold if threshold is not None else settings.align_threshold

    embedder = get_embedder()
    texts = [_node_text(n) for n in nodes]
    logger.info(f"[align] 嵌入 {len(nodes)} 节点…")
    embs = embedder.encode(texts, batch_size=64, show_progress_bar=False, normalize_embeddings=True)
    embs = np.asarray(embs, dtype=np.float32)

    uf = UnionFind()
    for n in nodes:
        uf.find(n.id)

    # 跨教材两两:embedding 高于阈值的对
    sims = embs @ embs.T
    n = len(nodes)
    pairs: list[tuple[int, int, float]] = []
    for i in range(n):
        for j in range(i + 1, n):
            if nodes[i].source_book == nodes[j].source_book:
                continue  # 同教材不对齐(章节内 dedup 已做)
            s = float(sims[i, j])
            if s >= threshold:
                pairs.append((i, j, s))

    pairs.sort(key=lambda x: -x[2])
    logger.info(f"[align] 候选对 {len(pairs)} 个(threshold={threshold})")

    llm_low, llm_high = llm_verify_band
    llm_used = 0
    for i, j, s in pairs:
        if s >= llm_high:
            uf.union(nodes[i].id, nodes[j].id)
            continue
        if s < llm_low:
            continue
        # 边界:LLM 二次裁决
        if llm_used >= max_llm_calls:
            # 预算用尽,沿用 embedding 判定
            uf.union(nodes[i].id, nodes[j].id)
            continue
        same, conf = _llm_verify_pair(nodes[i], nodes[j])
        llm_used += 1
        if same and conf >= 0.6:
            uf.union(nodes[i].id, nodes[j].id)

    logger.info(f"[align] LLM 验证调用 {llm_used} 次")

    clusters: dict[str, list[KnowledgeNode]] = {}
    for n_ in nodes:
        clusters.setdefault(uf.find(n_.id), []).append(n_)
    return list(clusters.values())
