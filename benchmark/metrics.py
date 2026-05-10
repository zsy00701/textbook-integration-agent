"""Benchmark scoring functions.

每道题打三个分:
- answer_score: 关键词召回率(预期关键词在 answer 中命中的比例)
- citation_score: 引用命中(textbook 命中 0.5,chapter 也命中 1.0,无命中 0)
- refusal_correct: unanswerable 题专用,answer 是否包含拒答短语
"""
from __future__ import annotations

REFUSAL_PHRASES = ("未找到相关信息", "未找到", "知识库中未", "没有找到", "无法回答")


def normalize(text: str) -> str:
    return text.replace(" ", "").replace("\t", "").replace("\n", "").lower()


def answer_keyword_recall(answer: str, keywords: list[str]) -> float:
    """关键词召回率:命中数 / 总数。空 keywords 返回 1.0。"""
    if not keywords:
        return 1.0
    norm = normalize(answer)
    hits = sum(1 for kw in keywords if normalize(kw) in norm)
    return hits / len(keywords)


def citation_score(citations: list[dict], expected_textbooks: list[str], chapter_hint: str) -> float:
    """引用打分。

    - 若 expected_textbooks 为空(unanswerable),返回 1.0 当 citations 为空,否则 0.0。
    - 若任一引用 textbook 命中预期,且其 chapter 包含 chapter_hint,得 1.0。
    - 仅 textbook 命中得 0.5。
    - 否则 0.0。
    """
    if not expected_textbooks:
        return 1.0 if not citations else 0.0
    if not citations:
        return 0.0

    norm_hint = normalize(chapter_hint or "")
    expected_norm = [normalize(t) for t in expected_textbooks]
    book_hit = False
    chapter_hit = False
    for c in citations:
        tb = normalize(str(c.get("textbook", "")))
        ch = normalize(str(c.get("chapter", "")))
        if any(et in tb or tb in et for et in expected_norm):
            book_hit = True
            if norm_hint and norm_hint in ch:
                chapter_hit = True
                break
    if chapter_hit:
        return 1.0
    if book_hit:
        return 0.5
    return 0.0


def is_refusal(answer: str) -> bool:
    norm = normalize(answer)
    return any(normalize(p) in norm for p in REFUSAL_PHRASES)


def score_one(question: dict, response: dict) -> dict:
    """对单个 (question, RAG response) 计算所有分数。"""
    answer = response.get("answer", "") or ""
    citations = response.get("citations", []) or []
    is_unanswerable = question["type"] == "unanswerable"

    refusal = is_refusal(answer)
    if is_unanswerable:
        ans_score = 1.0 if refusal else 0.0
        cite_score = citation_score(citations, [], "")
    else:
        # 正常题:若错误地拒答,answer 分扣到 0
        ans_score = 0.0 if refusal else answer_keyword_recall(answer, question.get("keywords", []))
        cite_score = citation_score(
            citations,
            question.get("textbooks", []),
            question.get("chapter_hint", ""),
        )

    return {
        "id": question["id"],
        "type": question["type"],
        "difficulty": question["difficulty"],
        "answer_score": round(ans_score, 4),
        "citation_score": round(cite_score, 4),
        "refusal": refusal,
        "refusal_correct": refusal == is_unanswerable,
        "answer_len": len(answer),
        "n_citations": len(citations),
    }


_LLM_KEYS = ("llm_correctness", "llm_completeness", "llm_faithfulness")


def aggregate(scored: list[dict]) -> dict:
    """聚合分数:按 type / difficulty / 总体 输出均值。"""
    def mean(xs: list[float]) -> float:
        return round(sum(xs) / len(xs), 4) if xs else 0.0

    def bucket(items: list[dict]) -> dict:
        b = {
            "n": len(items),
            "answer_score": mean([s["answer_score"] for s in items]),
            "citation_score": mean([s["citation_score"] for s in items]),
            "refusal_acc": mean([1.0 if s["refusal_correct"] else 0.0 for s in items]),
        }
        # 仅当至少一项有 LLM 分时才聚合
        if items and any(k in items[0] for k in _LLM_KEYS):
            for k in _LLM_KEYS:
                b[k] = mean([s.get(k, 0.0) for s in items if k in s])
        return b

    by_type: dict[str, list[dict]] = {}
    by_diff: dict[str, list[dict]] = {}
    for s in scored:
        by_type.setdefault(s["type"], []).append(s)
        by_diff.setdefault(s["difficulty"], []).append(s)

    return {
        "overall": bucket(scored),
        "by_type": {k: bucket(v) for k, v in by_type.items()},
        "by_difficulty": {k: bucket(v) for k, v in by_diff.items()},
    }
