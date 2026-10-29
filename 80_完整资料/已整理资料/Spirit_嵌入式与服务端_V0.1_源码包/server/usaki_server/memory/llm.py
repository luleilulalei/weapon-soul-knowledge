from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
import logging
import time

from usaki_server.llm.providers import LanguageModelProvider
from usaki_server.memory.store import AgentMemoryStore

logger = logging.getLogger(__name__)


class MemoryAugmentedLanguageModelProvider(LanguageModelProvider):
    def __init__(
        self,
        inner: LanguageModelProvider,
        memory_store: AgentMemoryStore,
        *,
        share_context_with_llm: bool,
    ) -> None:
        self._inner = inner
        self._memory_store = memory_store
        self._share_context_with_llm = share_context_with_llm

    async def stream_complete(
        self,
        text: str,
        device_id: str,
        memory_context: str | None = None,
    ) -> AsyncIterator[str]:
        turn_started_at = time.perf_counter()
        logger.warning(
            "[USAKI MEMORY] build_context_start device_id=%s query_chars=%d share_with_llm=%s",
            device_id,
            len(text),
            self._share_context_with_llm,
        )
        retrieved_context = await asyncio.to_thread(
            self._memory_store.build_context,
            device_id,
            text,
        )
        context_built_at = time.perf_counter()
        logger.warning(
            "[USAKI MEMORY] build_context_done device_id=%s ms=%.0f retrieved_chars=%d",
            device_id,
            (context_built_at - turn_started_at) * 1000,
            len(retrieved_context),
        )
        combined_context = memory_context
        if self._share_context_with_llm:
            combined_context = _combine_contexts(memory_context, retrieved_context)
        logger.warning(
            "[USAKI MEMORY] call_inner_llm device_id=%s combined_context_chars=%d",
            device_id,
            len(combined_context or ""),
        )
        full_parts: list[str] = []
        first_delta_logged = False

        async for delta in self._inner.stream_complete(
            text,
            device_id,
            memory_context=combined_context,
        ):
            if delta and not first_delta_logged:
                first_delta_logged = True
                logger.warning(
                    "[USAKI MEMORY] inner_first_delta device_id=%s ms_since_memory_start=%.0f",
                    device_id,
                    (time.perf_counter() - turn_started_at) * 1000,
                )
            full_parts.append(delta)
            yield delta

        assistant_text = "".join(full_parts).strip()
        remember_started_at = time.perf_counter()
        await asyncio.to_thread(
            self._memory_store.remember_turn,
            device_id,
            text,
            assistant_text,
        )
        logger.warning(
            "[USAKI MEMORY] turn processed device_id=%s remembered_text_len=%d assistant_len=%d "
            "remember_ms=%.0f total_ms=%.0f",
            device_id,
            len(text),
            len(assistant_text),
            (time.perf_counter() - remember_started_at) * 1000,
            (time.perf_counter() - turn_started_at) * 1000,
        )


def _combine_contexts(*contexts: str | None) -> str:
    return "\n\n".join(context.strip() for context in contexts if context and context.strip())
