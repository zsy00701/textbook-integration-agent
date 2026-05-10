"""自动化评测脚本。

调用方式::

    python evaluate.py --api http://localhost:8000/api/rag/query \
        --questions questions.jsonl --out results/baseline.json --tag baseline

输出 JSON 含每题分数 + 聚合指标 + 配置元信息(用于后续 compare.py)。
脚本对 src/ 零依赖,只通过 HTTP 与后端交互;后端未起也可用 --dry 模式跑通流程。
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Callable
from urllib import request as urlreq
from urllib.error import URLError

from metrics import aggregate, score_one
from llm_judge import judge_safe


def load_questions(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def http_query(api_url: str, timeout: float = 60.0) -> Callable[[str], dict]:
    """构造一个调 RAG 接口的函数,POST {"question": ...},返回 JSON dict。"""

    def _call(question: str) -> dict:
        body = json.dumps({"question": question}).encode("utf-8")
        req = urlreq.Request(api_url, data=body, headers={"Content-Type": "application/json"})
        with urlreq.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return _call


def dry_query(question: str) -> dict:
    """无后端时占位:返回空答案,所有分都会是 0,但能验证脚本流程。"""
    return {"answer": "", "citations": [], "source_chunks": []}


def run(
    questions: list[dict],
    query_fn: Callable[[str], dict],
    on_error: str = "skip",
    use_llm_judge: bool = False,
) -> tuple[list[dict], list[dict]]:
    """对每题打分,返回 (scored, raw_responses)。on_error: skip|raise。"""
    scored: list[dict] = []
    raws: list[dict] = []
    for q in questions:
        t0 = time.perf_counter()
        try:
            resp = query_fn(q["question"])
            err = None
        except (URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            if on_error == "raise":
                raise
            resp = {"answer": "", "citations": [], "source_chunks": []}
            err = str(e)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        s = score_one(q, resp)
        s["latency_ms"] = elapsed_ms
        if err:
            s["error"] = err

        if use_llm_judge:
            j = judge_safe(q, resp)
            s["llm_correctness"] = round(j["correctness"], 4)
            s["llm_completeness"] = round(j["completeness"], 4)
            s["llm_faithfulness"] = round(j["faithfulness"], 4)
            s["llm_reason"] = j.get("reason", "")
            if j.get("error"):
                s["llm_error"] = j["error"]

        scored.append(s)
        raws.append({"id": q["id"], "question": q["question"], "response": resp, "elapsed_ms": elapsed_ms, "error": err})
    return scored, raws


def latency_stats(scored: list[dict]) -> dict:
    lats = sorted(s["latency_ms"] for s in scored)
    if not lats:
        return {}
    n = len(lats)
    return {
        "avg_ms": round(sum(lats) / n, 1),
        "p50_ms": lats[n // 2],
        "p95_ms": lats[min(n - 1, int(n * 0.95))],
        "max_ms": lats[-1],
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="RAG benchmark evaluator")
    p.add_argument("--api", default="http://localhost:8000/api/rag/query", help="RAG query 接口 URL")
    p.add_argument("--questions", default=str(Path(__file__).parent / "questions.jsonl"))
    p.add_argument("--out", required=True, help="输出 JSON 路径")
    p.add_argument("--tag", default="run", help="本次实验 tag(写进结果元信息,供 compare.py 用)")
    p.add_argument("--config", default="{}", help="实验配置的 JSON 串,例如 '{\"chunk_size\":500,\"rerank\":false}'")
    p.add_argument("--dry", action="store_true", help="不调后端,跑通流程")
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--judge", choices=["keyword", "llm", "both"], default="keyword",
                   help="打分方式:keyword(关键词,默认免费快)/llm(DeepSeek-as-Judge)/both(两个都打,便于对比)")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    questions = load_questions(Path(args.questions))
    query_fn = dry_query if args.dry else http_query(args.api, timeout=args.timeout)

    use_llm = args.judge in ("llm", "both")
    scored, raws = run(questions, query_fn, use_llm_judge=use_llm)
    agg = aggregate(scored)
    agg["latency"] = latency_stats(scored)

    out = {
        "tag": args.tag,
        "config": json.loads(args.config),
        "judge": args.judge,
        "api": args.api if not args.dry else "DRY",
        "n_questions": len(questions),
        "aggregate": agg,
        "per_question": scored,
        "raw": raws,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] tag={args.tag} judge={args.judge} -> {out_path}")
    o = agg["overall"]
    print(f"  overall: ans={o['answer_score']:.3f}  cite={o['citation_score']:.3f}  refusal_acc={o['refusal_acc']:.3f}  n={o['n']}")
    if "llm_correctness" in o:
        print(f"  LLM:     correct={o['llm_correctness']:.3f}  complete={o['llm_completeness']:.3f}  faithful={o['llm_faithfulness']:.3f}")
    if agg.get("latency"):
        L = agg["latency"]
        print(f"  latency: avg={L['avg_ms']}ms  p50={L['p50_ms']}ms  p95={L['p95_ms']}ms")


if __name__ == "__main__":
    main()
