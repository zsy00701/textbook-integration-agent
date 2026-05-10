"""KG 抽取器:遍历章节调 LLM,聚合成单本图谱。

性能策略:
- 章节内容截断到 ~6000 字(避免 prompt 过长)
- 章节级并发(asyncio,最多 5 并发,避免触发 rate limit)
- 单章失败不阻塞整本,记录到日志
"""
from __future__ import annotations
import asyncio
from concurrent.futures import ThreadPoolExecutor, as_completed
from loguru import logger

from ...models.schemas import (
    Chapter, TextbookDoc, KnowledgeNode, Relation, BookGraph
)
from ..agent.llm_client import get_llm
from .prompts import KG_SYSTEM, KG_EXTRACT_PROMPT


CHAPTER_CONTENT_LIMIT = 6000  # 字符
MAX_NODES_PER_CHAPTER = 25
PARALLEL_CHAPTERS = 4


def _truncate_chapter(content: str, limit: int = CHAPTER_CONTENT_LIMIT) -> str:
    """超长章节截断:保留前 60% + 后 30%(中间往往是细节展开)。"""
    if len(content) <= limit:
        return content
    head_len = int(limit * 0.6)
    tail_len = limit - head_len
    return content[:head_len] + "\n…(中间省略)…\n" + content[-tail_len:]


def _extract_one_chapter(chapter: Chapter, book_title: str, book_id: str) -> tuple[list[KnowledgeNode], list[Relation]]:
    """单章抽取,返回该章节的 nodes 和 edges。"""
    if chapter.char_count < 200:
        # 太短,跳过
        return [], []

    content = _truncate_chapter(chapter.content)
    prompt = KG_EXTRACT_PROMPT.format(
        book_title=book_title,
        chapter_title=chapter.title,
        page_start=chapter.page_start,
        page_end=chapter.page_end,
        chapter_content=content,
    )
    try:
        # V4 Pro 推理模型需要更大 max_tokens(reasoning + JSON 输出)
        result = get_llm().complete_json(prompt, system=KG_SYSTEM, max_tokens=8000)
    except Exception as e:
        logger.warning(f"[KG] 章节 {chapter.title} 抽取失败: {e}")
        return [], []

    if not isinstance(result, dict):
        return [], []

    raw_nodes = result.get("nodes", [])[:MAX_NODES_PER_CHAPTER]
    raw_edges = result.get("edges", [])

    # 章内 id → 全局 id 映射(避免不同章 id 冲突)
    id_map: dict[str, str] = {}
    nodes: list[KnowledgeNode] = []
    for n in raw_nodes:
        local_id = str(n.get("id", "")).strip()
        if not local_id or "name" not in n:
            continue
        global_id = f"{chapter.chapter_id}_{local_id}"
        id_map[local_id] = global_id
        try:
            nodes.append(KnowledgeNode(
                id=global_id,
                name=str(n["name"])[:80],
                definition=str(n.get("definition", ""))[:500],
                category=str(n.get("category", "核心概念"))[:30],
                chapter=chapter.title,
                page=int(n.get("page", chapter.page_start) or chapter.page_start),
                source_book=book_id,
            ))
        except Exception as e:
            logger.debug(f"node skip: {e}, raw={n}")
            continue

    edges: list[Relation] = []
    valid_types = {"prerequisite", "parallel", "contains", "applies_to"}
    for e in raw_edges:
        s_local = str(e.get("source", ""))
        t_local = str(e.get("target", ""))
        rt = str(e.get("relation_type", "")).lower()
        if s_local not in id_map or t_local not in id_map or rt not in valid_types:
            continue
        if id_map[s_local] == id_map[t_local]:
            continue
        edges.append(Relation(
            source=id_map[s_local],
            target=id_map[t_local],
            relation_type=rt,  # type: ignore
            description=str(e.get("description", ""))[:200],
        ))

    return nodes, edges


def extract_book_graph(doc: TextbookDoc, on_progress=None) -> BookGraph:
    """对整本书并发抽取(线程池;DeepSeek 同步 SDK)。"""
    all_nodes: list[KnowledgeNode] = []
    all_edges: list[Relation] = []

    # 过滤太短的章节
    chapters = [c for c in doc.chapters if c.char_count >= 200]
    total = len(chapters)
    done = 0
    logger.info(f"[KG] 开始抽取《{doc.title}》,共 {total} 章")

    with ThreadPoolExecutor(max_workers=PARALLEL_CHAPTERS) as ex:
        futures = {
            ex.submit(_extract_one_chapter, ch, doc.title, doc.textbook_id): ch
            for ch in chapters
        }
        for fut in as_completed(futures):
            ch = futures[fut]
            try:
                ns, es = fut.result()
                all_nodes.extend(ns)
                all_edges.extend(es)
            except Exception as e:
                logger.warning(f"[KG] 章节 {ch.title} 处理异常: {e}")
            done += 1
            if on_progress:
                on_progress(done, total)
            if done % 5 == 0 or done == total:
                logger.info(f"[KG] {doc.title} 进度 {done}/{total},累计 {len(all_nodes)} 节点")

    # 跨章节去重:同名 + 来源相同 → 保留首次出现的
    seen: dict[tuple[str, str], KnowledgeNode] = {}
    for n in all_nodes:
        key = (n.source_book, n.name)
        if key not in seen:
            seen[key] = n
    deduped_nodes = list(seen.values())

    # 边的端点必须都还在节点集
    valid_ids = {n.id for n in deduped_nodes}
    deduped_edges = [e for e in all_edges if e.source in valid_ids and e.target in valid_ids]

    logger.info(f"[KG] 《{doc.title}》抽取完成: {len(deduped_nodes)} 节点 / {len(deduped_edges)} 关系")
    return BookGraph(
        book_id=doc.textbook_id,
        book_title=doc.title,
        nodes=deduped_nodes,
        edges=deduped_edges,
    )
