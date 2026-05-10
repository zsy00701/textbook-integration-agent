"""数据集自检:确保 questions.jsonl 没有低级错误。

检查项:
- 每行是合法 JSON
- id 唯一且连续(q001..qNNN)
- 必填字段齐全
- type / difficulty 在白名单
- textbooks 在 7 本教材范围内(unanswerable 例外)
- keywords 非空(unanswerable 例外)
- 同一 question 字面不重复

输出 0 / 非0 退出码,可挂 CI。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

VALID_TYPES = {"factual", "comparative", "reasoning", "cross_book", "unanswerable"}
VALID_DIFFICULTY = {"easy", "medium", "hard"}
VALID_TEXTBOOKS = {
    "局部解剖学", "组织学与胚胎学", "生理学", "医学微生物学",
    "病理学", "传染病学", "病理生理学",
}
REQUIRED_FIELDS = {"id", "type", "difficulty", "textbooks", "chapter_hint",
                   "question", "keywords", "answer_summary"}


def validate(path: Path) -> list[str]:
    errs: list[str] = []
    seen_ids: set[str] = set()
    seen_qs: dict[str, str] = {}
    items: list[dict] = []

    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            errs.append(f"L{lineno}: 非合法 JSON: {e}")
            continue
        items.append(obj)

        missing = REQUIRED_FIELDS - obj.keys()
        if missing:
            errs.append(f"L{lineno} {obj.get('id','?')}: 缺字段 {missing}")
            continue

        qid = obj["id"]
        if qid in seen_ids:
            errs.append(f"L{lineno}: id 重复 {qid}")
        seen_ids.add(qid)
        if not re.fullmatch(r"q\d{3}", qid):
            errs.append(f"L{lineno}: id 格式错 {qid},应为 qNNN")

        if obj["type"] not in VALID_TYPES:
            errs.append(f"L{lineno} {qid}: type 非法 {obj['type']}")
        if obj["difficulty"] not in VALID_DIFFICULTY:
            errs.append(f"L{lineno} {qid}: difficulty 非法 {obj['difficulty']}")

        is_un = obj["type"] == "unanswerable"
        for tb in obj["textbooks"]:
            if tb not in VALID_TEXTBOOKS:
                errs.append(f"L{lineno} {qid}: textbook 非白名单 {tb!r}")
        if is_un and obj["textbooks"]:
            errs.append(f"L{lineno} {qid}: unanswerable 题不应有 textbooks")
        if not is_un and not obj["textbooks"]:
            errs.append(f"L{lineno} {qid}: 非 unanswerable 题必须给 textbooks")

        if not obj["keywords"]:
            errs.append(f"L{lineno} {qid}: keywords 不能为空")
        if not obj["question"].strip():
            errs.append(f"L{lineno} {qid}: question 为空")

        prev = seen_qs.get(obj["question"])
        if prev:
            errs.append(f"L{lineno} {qid}: question 与 {prev} 重复")
        else:
            seen_qs[obj["question"]] = qid

    # ID 连续性
    nums = sorted(int(i[1:]) for i in seen_ids)
    if nums:
        expected = list(range(1, nums[-1] + 1))
        missing = sorted(set(expected) - set(nums))
        if missing:
            errs.append(f"id 不连续,缺号: {['q%03d' % n for n in missing]}")

    return errs


def main() -> int:
    path = Path(__file__).parent / "questions.jsonl"
    errs = validate(path)
    if errs:
        print(f"[FAIL] {len(errs)} 个问题:")
        for e in errs:
            print(f"  - {e}")
        return 1
    n = sum(1 for _ in path.read_text(encoding="utf-8").splitlines() if _.strip())
    print(f"[OK] questions.jsonl: {n} 条记录,均通过校验")
    return 0


if __name__ == "__main__":
    sys.exit(main())
