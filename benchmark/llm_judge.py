"""LLM-as-Judge:用 DeepSeek 给候选答案打分,缓解关键词法对同义改写不敏感的问题。

输出三个 0~1 的子分:
- correctness: 答案在事实上是否正确(对照参考摘要)
- completeness: 是否覆盖参考要点
- faithfulness: 是否只基于教材引用、未编造(对应 RAG 的核心约束)

带本地磁盘缓存(`.judge_cache/`),同样的 (question_id, answer_hash) 不重复花 token。
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from urllib import request as urlreq
from urllib.error import HTTPError, URLError

CACHE_DIR = Path(__file__).parent / ".judge_cache"

SYSTEM_PROMPT = """你是医学教材RAG系统的严格评分员。给定题目、参考答案要点、候选回答和引用列表,请输出JSON:

{
  "correctness": 0~1的浮点数,候选回答在事实上是否正确(对照参考要点),
  "completeness": 0~1的浮点数,候选回答是否覆盖参考要点的核心内容,
  "faithfulness": 0~1的浮点数,候选回答是否仅基于引用内容,无编造,
  "reason": "一句话评语"
}

评分准则:
- 完全正确且全面: 1.0;部分正确: 0.4~0.7;明显错误或答非所问: 0~0.3
- 拒答("当前知识库中未找到相关信息"等):若题目应当能答,三项均 0;若题目本就在教材外,三项均 1.0
- 同义改写不扣分,只看医学含义是否对应"""


def _env(key: str, default: str = "") -> str:
    val = os.environ.get(key)
    if val:
        return val
    # 简易 .env 读取(避免引入 dotenv 依赖)
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key}=") and not line.lstrip().startswith("#"):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return default


def _cache_key(qid: str, answer: str, citations: list[dict]) -> str:
    h = hashlib.sha1()
    h.update(qid.encode())
    h.update(b"\x00")
    h.update(answer.encode("utf-8"))
    h.update(b"\x00")
    h.update(json.dumps(citations, ensure_ascii=False, sort_keys=True).encode("utf-8"))
    return h.hexdigest()[:16]


def _call_deepseek(user_content: str, model: str, base_url: str, api_key: str, timeout: float = 60.0) -> dict:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.0,
    }
    req = urlreq.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    with urlreq.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    parsed = json.loads(content)
    return {
        "correctness": float(parsed.get("correctness", 0.0)),
        "completeness": float(parsed.get("completeness", 0.0)),
        "faithfulness": float(parsed.get("faithfulness", 0.0)),
        "reason": parsed.get("reason", ""),
        "usage": usage,
    }


def judge_one(question: dict, response: dict, *, use_cache: bool = True) -> dict:
    """对单题打 LLM 分,带磁盘缓存。出错时 raise,由调用方决定是否吞掉。"""
    answer = response.get("answer", "") or ""
    citations = response.get("citations", []) or []

    if use_cache:
        CACHE_DIR.mkdir(exist_ok=True)
        ck = CACHE_DIR / f"{_cache_key(question['id'], answer, citations)}.json"
        if ck.exists():
            cached = json.loads(ck.read_text(encoding="utf-8"))
            cached["cached"] = True
            return cached

    api_key = _env("DEEPSEEK_API_KEY")
    base_url = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    model = _env("DEEPSEEK_MODEL", "deepseek-chat")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY 未设置")

    user_content = json.dumps(
        {
            "question": question["question"],
            "type": question["type"],
            "expected_textbooks": question.get("textbooks", []),
            "answer_summary": question.get("answer_summary", ""),
            "candidate_answer": answer,
            "candidate_citations": citations,
        },
        ensure_ascii=False,
    )

    t0 = time.perf_counter()
    result = _call_deepseek(user_content, model, base_url, api_key)
    result["judge_ms"] = int((time.perf_counter() - t0) * 1000)
    result["cached"] = False

    if use_cache:
        ck.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result


def judge_safe(question: dict, response: dict) -> dict:
    """容错包装:网络/Key 错误时返回全 0 分 + error,不打断评测流程。"""
    try:
        return judge_one(question, response)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, RuntimeError) as e:
        return {
            "correctness": 0.0,
            "completeness": 0.0,
            "faithfulness": 0.0,
            "reason": "",
            "error": str(e),
            "cached": False,
        }
