"""基于检索结果生成答案,带强制引用。"""
from __future__ import annotations
from loguru import logger

from ...models.schemas import QAResponse, Citation
from ..agent.llm_client import get_llm
from ..extractor.prompts import RAG_SYSTEM, RAG_USER_PROMPT


def _build_context(hits: list[dict]) -> str:
    blocks = []
    for i, h in enumerate(hits):
        m = h.get("metadata", {}) or {}
        head = f"[{i+1}] 《{m.get('book_title', m.get('textbook_id', '?'))}》· {m.get('chapter', '?')} · 第 {m.get('page', '?')} 页"
        blocks.append(f"{head}\n{h['text']}")
    return "\n\n".join(blocks)


def generate_answer(question: str, hits: list[dict]) -> QAResponse:
    if not hits:
        return QAResponse(answer="当前知识库中未找到相关信息。", citations=[], source_chunks=[])

    context = _build_context(hits)
    prompt = RAG_USER_PROMPT.format(n=len(hits), context=context, question=question)

    try:
        # 用 deepseek-chat:答题需流畅自然回答,推理模型容易保守拒答
        answer = get_llm().complete(
            prompt, system=RAG_SYSTEM, temperature=0.2, max_tokens=1500,
            model="deepseek-chat",
        )
    except Exception as e:
        logger.exception("[rag-gen] LLM 调用失败")
        answer = f"生成回答时出错:{e}"

    citations = []
    source_chunks = []
    for h in hits:
        m = h.get("metadata", {}) or {}
        citations.append(Citation(
            textbook=m.get("book_title", m.get("textbook_id", "")),
            chapter=m.get("chapter", ""),
            page=int(m.get("page", 0) or 0),
            relevance_score=float(h.get("score", 0.0)),
        ))
        source_chunks.append(h.get("text", ""))

    return QAResponse(answer=answer.strip(), citations=citations, source_chunks=source_chunks)
