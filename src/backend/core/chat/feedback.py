"""多轮对话:解析教师反馈 → 生成 patch → 修改决策 → 刷新主图谱。

设计:
- LLM 输出 patch 列表(modify/create/delete + 新 action)
- 应用 patch 时,只改 decisions.json 与 master_graph.json
- 不重新跑整合(成本太高);patch 直接增删节点/边
"""
from __future__ import annotations
import time
import uuid
from loguru import logger

from ...models.schemas import (
    ChatMessage, ChatResponse, Decision, KnowledgeNode, BookGraph,
)
from ...storage import data_store
from ..agent.llm_client import get_llm
from ..extractor.prompts import CHAT_SYSTEM, CHAT_USER_PROMPT


def _summarize_decisions(decisions: list[dict], limit: int = 30) -> str:
    """挑出最近 + 多源的若干条决策展示给 LLM。"""
    if not decisions:
        return "(尚无整合决策,请先点击'一键整合')"
    # 优先展示 merge / remove(用户更可能反馈这些)
    sorted_d = sorted(decisions, key=lambda d: ({"merge": 0, "remove": 1, "keep": 2}[d.get("action", "keep")], -float(d.get("confidence", 0))))
    lines = []
    for d in sorted_d[:limit]:
        lines.append(
            f"- [{d.get('decision_id','')}] {d.get('action','')} "
            f"(置信 {float(d.get('confidence',0))*100:.0f}%) "
            f"影响 {len(d.get('affected_nodes',[]))} 节点 | {d.get('reason','')[:80]}"
        )
    if len(decisions) > limit:
        lines.append(f"...(另 {len(decisions) - limit} 条决策未展示)")
    return "\n".join(lines)


def _format_history(history: list[ChatMessage], limit: int = 6) -> str:
    if not history:
        return "(无历史)"
    recent = history[-limit:]
    return "\n".join(
        f"{'用户' if m.role == 'user' else '助手'}:{m.content[:200]}"
        for m in recent
    )


def _apply_patches(patches: list[dict]) -> tuple[list[dict], list[str]]:
    """根据 patches 更新 decisions.json & master_graph.json,返回新决策列表 + 变更 id 列表。"""
    decisions, stats = data_store.load_decisions()
    master = data_store.load_master_graph()
    if master is None:
        return decisions, []

    by_id = {d["decision_id"]: d for d in decisions}
    changed: list[str] = []
    nodes_to_remove: set[str] = set()
    nodes_to_add: list[KnowledgeNode] = []

    for p in patches:
        op = p.get("op")
        did = p.get("decision_id", "")
        new_action = p.get("new_action")
        new_reason = p.get("new_reason", "")
        affected = p.get("affected_nodes", [])

        if op == "modify" and did in by_id:
            d = by_id[did]
            old_action = d.get("action")
            d["action"] = new_action or old_action
            if new_reason:
                d["reason"] = new_reason
            changed.append(did)

            # remove → keep:不能直接还原(节点可能已删),提示 LLM 注意
            # keep → remove:从 master 删节点
            if old_action != "remove" and d["action"] == "remove":
                for nid in d.get("affected_nodes", []):
                    nodes_to_remove.add(nid)
            # merge → keep:把 merged 节点拆开 — 简化版:保留代表节点,标记 reason
            # 复杂场景在赛后扩展

        elif op == "delete" and did in by_id:
            del by_id[did]
            changed.append(did)

        elif op == "create":
            new_id = f"d_{uuid.uuid4().hex[:8]}"
            by_id[new_id] = {
                "decision_id": new_id,
                "action": new_action or "keep",
                "affected_nodes": affected,
                "result_node": affected[0] if affected else "",
                "reason": new_reason or "用户对话新增",
                "confidence": 0.7,
            }
            changed.append(new_id)

    # 应用到 master 节点集
    if nodes_to_remove:
        master = BookGraph(
            book_id=master.book_id,
            book_title=master.book_title,
            nodes=[n for n in master.nodes if n.id not in nodes_to_remove],
            edges=[
                e for e in master.edges
                if e.source not in nodes_to_remove and e.target not in nodes_to_remove
            ],
        )

    if changed:
        new_decisions = list(by_id.values())
        # 重算 stats(节点数 + 决策计数)
        from collections import Counter
        cnt = Counter(d["action"] for d in new_decisions)
        stats = dict(stats or {})
        stats["final_node_count"] = len(master.nodes)
        stats["decisions_count"] = {
            "merge": cnt.get("merge", 0),
            "keep": cnt.get("keep", 0),
            "remove": cnt.get("remove", 0),
        }
        # 重算 final_chars 与 ratio
        final_chars = sum(len(n.definition) + len(n.name) + len(n.chapter) for n in master.nodes)
        stats["final_chars"] = final_chars
        if stats.get("orig_chars"):
            stats["ratio"] = final_chars / stats["orig_chars"]
        data_store.save_master_graph(master)
        data_store.save_decisions(new_decisions, stats)
        return new_decisions, changed
    return decisions, []


def handle_user_message(session_id: str, message: str) -> ChatResponse:
    # 加载历史
    raw_hist = data_store.load_session(session_id)
    history = [ChatMessage.model_validate(h) for h in raw_hist]
    history.append(ChatMessage(role="user", content=message, timestamp=time.time()))

    # 加载当前决策
    decisions, _ = data_store.load_decisions()
    decisions_summary = _summarize_decisions(decisions)
    history_str = _format_history(history[:-1])

    prompt = CHAT_USER_PROMPT.format(
        decisions_summary=decisions_summary,
        history=history_str,
        user_message=message,
    )

    try:
        # V4 Pro 推理模型,留足 reasoning 预算
        result = get_llm().complete_json(prompt, system=CHAT_SYSTEM, max_tokens=4000)
    except Exception as e:
        logger.exception("[chat] LLM 调用失败")
        reply = f"抱歉,处理你的反馈时出错了:{e}"
        history.append(ChatMessage(role="assistant", content=reply, timestamp=time.time()))
        data_store.save_session(session_id, [m.model_dump() for m in history])
        return ChatResponse(session_id=session_id, reply=reply, history=history)

    if not isinstance(result, dict):
        result = {"reply": "我没能理解,请换种说法。", "patches": []}

    reply = str(result.get("reply", "好的,我已记录。"))
    patches = result.get("patches", []) or []

    changed_ids: list[str] = []
    if patches:
        try:
            _, changed_ids = _apply_patches(patches)
            if changed_ids:
                reply += f"\n\n✅ 已更新 {len(changed_ids)} 项决策(图谱已实时刷新)。"
        except Exception as e:
            logger.exception("[chat] apply patches 失败")
            reply += f"\n\n⚠️ 应用决策变更时出错:{e}"

    history.append(ChatMessage(role="assistant", content=reply, timestamp=time.time()))
    data_store.save_session(session_id, [m.model_dump() for m in history])

    return ChatResponse(
        session_id=session_id,
        reply=reply,
        decisions_changed=changed_ids,
        history=history,
    )
