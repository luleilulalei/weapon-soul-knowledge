from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
import json
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LlmProviderPreset:
    """Default OpenAI-compatible endpoint and model for one LLM vendor."""

    base_url: str
    model: str


# Most mainstream China/Singapore-accessible LLM vendors expose an OpenAI-compatible
# /chat/completions API. These presets keep vendor switching as an env-only change.
LLM_PROVIDER_PRESETS: dict[str, LlmProviderPreset] = {
    "qwen": LlmProviderPreset(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-plus",
    ),
    "dashscope": LlmProviderPreset(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-plus",
    ),
    "aliyun": LlmProviderPreset(
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-plus",
    ),
    "doubao": LlmProviderPreset(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        model="doubao-seed-1-6-flash-250615",
    ),
    "volcengine": LlmProviderPreset(
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        model="doubao-seed-1-6-flash-250615",
    ),
    "deepseek": LlmProviderPreset(
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
    ),
    "kimi": LlmProviderPreset(
        base_url="https://api.moonshot.cn/v1",
        model="kimi-k2-0711-preview",
    ),
    "moonshot": LlmProviderPreset(
        base_url="https://api.moonshot.cn/v1",
        model="kimi-k2-0711-preview",
    ),
    "zhipu": LlmProviderPreset(
        base_url="https://open.bigmodel.cn/api/paas/v4",
        model="glm-4.5-flash",
    ),
    "glm": LlmProviderPreset(
        base_url="https://open.bigmodel.cn/api/paas/v4",
        model="glm-4.5-flash",
    ),
    "hunyuan": LlmProviderPreset(
        base_url="https://api.hunyuan.cloud.tencent.com/v1",
        model="hunyuan-turbos-latest",
    ),
    "tencent": LlmProviderPreset(
        base_url="https://api.hunyuan.cloud.tencent.com/v1",
        model="hunyuan-turbos-latest",
    ),
    "minimax": LlmProviderPreset(
        base_url="https://api.minimax.io/v1",
        model="MiniMax-M1",
    ),
    "stepfun": LlmProviderPreset(
        base_url="https://api.stepfun.com/v1",
        model="step-2-mini",
    ),
    "step": LlmProviderPreset(
        base_url="https://api.stepfun.com/v1",
        model="step-2-mini",
    ),
}


class LanguageModelProvider:
    async def stream_complete(
        self,
        text: str,
        device_id: str,
        memory_context: str | None = None,
    ) -> AsyncIterator[str]:
        raise NotImplementedError


class OpenAICompatibleLanguageModelProvider(LanguageModelProvider):
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 512,
        timeout_seconds: float = 30,
        thinking_type: str | None = None,
        reasoning_effort: str | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._system_prompt = system_prompt
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout_seconds = timeout_seconds
        self._thinking_type = thinking_type
        self._reasoning_effort = reasoning_effort

    async def stream_complete(
        self,
        text: str,
        device_id: str,
        memory_context: str | None = None,
    ) -> AsyncIterator[str]:
        messages: list[dict[str, str]] = [
            {"role": "system", "content": self._system_prompt},
        ]
        if memory_context:
            messages.append({"role": "system", "content": memory_context})
        messages.append({"role": "user", "content": _build_user_message(text, device_id)})
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "stream": True,
        }
        if self._thinking_type:
            payload["thinking"] = {"type": self._thinking_type}
        if self._reasoning_effort:
            payload["reasoning_effort"] = self._reasoning_effort
        message_chars = [len(message["content"]) for message in messages]
        prompt_chars = sum(message_chars)
        logger.warning(
            "[USAKI LLM] request_start provider=openai_compatible base_url=%s model=%s "
            "device_id=%s messages=%d chars=%s total_chars=%d user_chars=%d "
            "memory_chars=%d max_tokens=%d timeout_s=%.1f thinking=%s reasoning_effort=%s",
            self._base_url,
            self._model,
            device_id,
            len(messages),
            message_chars,
            prompt_chars,
            len(text),
            len(memory_context or ""),
            self._max_tokens,
            self._timeout_seconds,
            self._thinking_type or "",
            self._reasoning_effort or "",
        )
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        request_started_at = time.perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
            ) as response:
                headers_at = time.perf_counter()
                logger.warning(
                    "[USAKI LLM] response_headers status=%d model=%s headers_ms=%.0f",
                    response.status_code,
                    self._model,
                    (headers_at - request_started_at) * 1000,
                )
                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError:
                    body = await response.aread()
                    logger.warning(
                        "[USAKI LLM] chat/completions failed status=%d model=%s body=%s",
                        response.status_code,
                        self._model,
                        body.decode("utf-8", errors="replace")[:1000],
                    )
                    raise

                line_iter = response.aiter_lines().__aiter__()
                pending_line: asyncio.Task[str] | None = None
                first_line_logged = False
                first_delta_logged = False
                line_count = 0
                delta_count = 0
                reasoning_count = 0
                last_wait_log_at = time.perf_counter()
                try:
                    while True:
                        if pending_line is None:
                            pending_line = asyncio.create_task(line_iter.__anext__())
                        done, _ = await asyncio.wait({pending_line}, timeout=5.0)
                        if not done:
                            now = time.perf_counter()
                            logger.warning(
                                "[USAKI LLM] waiting_stream_line model=%s elapsed_ms=%.0f "
                                "since_headers_ms=%.0f lines=%d deltas=%d reasoning=%d",
                                self._model,
                                (now - request_started_at) * 1000,
                                (now - headers_at) * 1000,
                                line_count,
                                delta_count,
                                reasoning_count,
                            )
                            last_wait_log_at = now
                            continue
                        try:
                            line = pending_line.result()
                        except StopAsyncIteration:
                            break
                        finally:
                            pending_line = None

                        line_count += 1
                        if line.strip() and not first_line_logged:
                            first_line_logged = True
                            logger.warning(
                                "[USAKI LLM] first_stream_line model=%s since_headers_ms=%.0f "
                                "line_len=%d",
                                self._model,
                                (time.perf_counter() - headers_at) * 1000,
                                len(line),
                            )
                        if time.perf_counter() - last_wait_log_at >= 10:
                            last_wait_log_at = time.perf_counter()
                            logger.warning(
                                "[USAKI LLM] streaming_progress model=%s elapsed_ms=%.0f "
                                "lines=%d deltas=%d reasoning=%d",
                                self._model,
                                (last_wait_log_at - request_started_at) * 1000,
                                line_count,
                                delta_count,
                                reasoning_count,
                            )

                        reasoning = _extract_openai_compatible_stream_reasoning(line)
                        if reasoning:
                            reasoning_count += 1
                            if reasoning_count == 1:
                                logger.warning(
                                    "[USAKI LLM] first_reasoning_delta model=%s "
                                    "since_headers_ms=%.0f chars=%d",
                                    self._model,
                                    (time.perf_counter() - headers_at) * 1000,
                                    len(reasoning),
                                )

                        delta = _extract_openai_compatible_stream_delta(line)
                        if delta:
                            delta_count += 1
                            if not first_delta_logged:
                                first_delta_logged = True
                                logger.warning(
                                    "[USAKI LLM] first_delta model=%s elapsed_ms=%.0f "
                                    "since_headers_ms=%.0f delta_chars=%d",
                                    self._model,
                                    (time.perf_counter() - request_started_at) * 1000,
                                    (time.perf_counter() - headers_at) * 1000,
                                    len(delta),
                                )
                            yield delta
                finally:
                    if pending_line is not None and not pending_line.done():
                        pending_line.cancel()

                logger.warning(
                    "[USAKI LLM] stream_done model=%s total_ms=%.0f lines=%d deltas=%d reasoning=%d",
                    self._model,
                    (time.perf_counter() - request_started_at) * 1000,
                    line_count,
                    delta_count,
                    reasoning_count,
                )


def _build_user_message(text: str, device_id: str) -> str:
    return f"device_id: {device_id}\nuser: {text.strip()}"


def _extract_openai_compatible_stream_reasoning(line: str) -> str:
    line = line.strip()
    if not line:
        return ""
    if line.startswith("data:"):
        line = line[5:].strip()
    if not line or line == "[DONE]":
        return ""
    try:
        data = json.loads(line)
    except Exception:
        return ""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return ""
    delta = first_choice.get("delta")
    if not isinstance(delta, dict):
        return ""
    reasoning = delta.get("reasoning_content") or delta.get("reasoning") or delta.get("reason")
    return reasoning if isinstance(reasoning, str) else ""


def _extract_openai_compatible_stream_delta(line: str) -> str:
    line = line.strip()
    if not line:
        return ""
    if line.startswith("data:"):
        line = line[5:].strip()
    if not line or line == "[DONE]":
        return ""
    try:
        data = json.loads(line)
    except Exception:
        return ""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return ""
    delta = first_choice.get("delta")
    if isinstance(delta, dict):
        content = delta.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)
    text = first_choice.get("text")
    return text if isinstance(text, str) else ""
