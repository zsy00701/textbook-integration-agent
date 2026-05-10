"""DeepSeek LLM 客户端封装。

设计要点:
- 使用 OpenAI SDK 兼容接口(DeepSeek 完全兼容)
- 支持 JSON 模式(知识点抽取/整合决策必须用)
- 失败重试(指数退避)
- Token 统计累计
- 全局单例,避免重复 init
"""
from __future__ import annotations
import json
import time
from threading import Lock
from typing import Any
from loguru import logger
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ...config import settings


class TokenStats:
    """全局 token 统计,用于 P1 加分项展示。"""

    def __init__(self):
        self.lock = Lock()
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.requests = 0
        self.total_latency = 0.0

    def add(self, prompt: int, completion: int, latency: float) -> None:
        with self.lock:
            self.prompt_tokens += prompt
            self.completion_tokens += completion
            self.total_latency += latency
            self.requests += 1

    def snapshot(self) -> dict:
        with self.lock:
            avg = self.total_latency / self.requests if self.requests else 0
            return {
                "requests": self.requests,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "total_tokens": self.prompt_tokens + self.completion_tokens,
                "avg_latency_s": round(avg, 2),
            }


token_stats = TokenStats()


class LLMClient:
    def __init__(self):
        if not settings.deepseek_api_key:
            logger.warning("DEEPSEEK_API_KEY 未配置,LLM 调用会失败")
        self.client = OpenAI(
            api_key=settings.deepseek_api_key or "missing",
            base_url=settings.deepseek_base_url,
            timeout=120.0,
            max_retries=0,  # 自己用 tenacity 控
        )
        self.model = settings.deepseek_model

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def complete(
        self,
        prompt: str,
        system: str | None = None,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> str:
        """同步调用,返回 content 字符串。

        model 参数允许 per-call override(例如对齐验证用 deepseek-chat 而非推理模型,JSON 更稳)。
        """
        msgs: list[dict] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        kwargs: dict[str, Any] = {
            "model": model or self.model,
            "messages": msgs,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        t0 = time.time()
        resp = self.client.chat.completions.create(**kwargs)
        dt = time.time() - t0

        if resp.usage:
            token_stats.add(
                resp.usage.prompt_tokens,
                resp.usage.completion_tokens,
                dt,
            )
        return resp.choices[0].message.content or ""

    def complete_json(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        model: str | None = None,
    ) -> dict | list:
        """JSON 模式:尝试解析返回的 JSON,解析失败则抛 ValueError。"""
        raw = self.complete(prompt, system=system, json_mode=True,
                            temperature=temperature, max_tokens=max_tokens, model=model)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            # 兜底:截取首个 { 到末尾的 }
            i, j = raw.find("{"), raw.rfind("}")
            if i != -1 and j > i:
                try:
                    return json.loads(raw[i : j + 1])
                except json.JSONDecodeError:
                    pass
            i, j = raw.find("["), raw.rfind("]")
            if i != -1 and j > i:
                try:
                    return json.loads(raw[i : j + 1])
                except json.JSONDecodeError:
                    pass
            logger.error(f"JSON parse failed: {raw[:300]}...")
            raise ValueError(f"LLM did not return valid JSON: {e}") from e


# 单例
_client: LLMClient | None = None


def get_llm() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
