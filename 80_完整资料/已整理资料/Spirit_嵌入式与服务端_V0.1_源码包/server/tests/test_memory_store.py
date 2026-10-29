from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from usaki_server.llm.providers import LanguageModelProvider
from usaki_server.memory.llm import MemoryAugmentedLanguageModelProvider
from usaki_server.memory.store import AgentMemoryStore


def _store(tmp_path) -> AgentMemoryStore:
    return AgentMemoryStore(
        agent_id="usaki",
        agent_root=tmp_path / "agent" / "usaki",
        db_path=tmp_path / "agent" / "usaki" / "runtime" / "memory.sqlite3",
        recent_window_minutes=10,
        max_context_items=6,
        query_pool_size=50,
    )


def test_memory_store_remembers_explicit_preference(tmp_path) -> None:
    store = _store(tmp_path)

    store.remember_turn("device-a", "记住，我喜欢爵士乐。", "好呀，我记住了。")

    context = store.build_context("device-a", "今天放什么音乐")

    assert "<long_term_memory>" in context
    assert "爵士乐" in context
    assert "<recent_conversation_10min>" in context


def test_memory_wrapper_can_share_retrieved_context_when_enabled(tmp_path) -> None:
    asyncio.run(_assert_memory_wrapper_can_share_retrieved_context_when_enabled(tmp_path))


async def _assert_memory_wrapper_can_share_retrieved_context_when_enabled(tmp_path) -> None:
    store = _store(tmp_path)
    store.remember_turn("device-a", "记住，我喜欢爵士乐。", "好呀，我记住了。")
    provider = CapturingProvider()
    wrapped = MemoryAugmentedLanguageModelProvider(
        provider,
        store,
        share_context_with_llm=True,
    )

    chunks = [chunk async for chunk in wrapped.stream_complete("今天适合听什么？", "device-a")]

    assert "".join(chunks) == "ok"
    assert provider.memory_context is not None
    assert "爵士乐" in provider.memory_context


def test_memory_wrapper_does_not_share_context_by_default(tmp_path) -> None:
    asyncio.run(_assert_memory_wrapper_does_not_share_context_by_default(tmp_path))


async def _assert_memory_wrapper_does_not_share_context_by_default(tmp_path) -> None:
    store = _store(tmp_path)
    store.remember_turn("device-a", "记住，我喜欢爵士乐。", "好呀，我记住了。")
    provider = CapturingProvider()
    wrapped = MemoryAugmentedLanguageModelProvider(
        provider,
        store,
        share_context_with_llm=False,
    )

    chunks = [chunk async for chunk in wrapped.stream_complete("今天适合听什么？", "device-a")]

    assert "".join(chunks) == "ok"
    assert provider.memory_context is None


class CapturingProvider(LanguageModelProvider):
    def __init__(self) -> None:
        self.memory_context: str | None = None

    async def stream_complete(
        self,
        text: str,
        device_id: str,
        memory_context: str | None = None,
    ) -> AsyncIterator[str]:
        del text, device_id
        self.memory_context = memory_context
        yield "ok"
