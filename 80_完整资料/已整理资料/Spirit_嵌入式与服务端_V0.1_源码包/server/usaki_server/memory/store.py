from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import threading
from typing import Any

from usaki_server.config import Settings
from usaki_server.paths import resolve_project_path


GLOBAL_DEVICE_ID = "global"
RECENT_TURN_LIMIT = 8


@dataclass(frozen=True)
class MemoryCandidate:
    category: str
    content: str
    subject: str = "user"
    source: str = "conversation"
    confidence: float = 0.72
    importance: float = 0.55
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentMemoryStore:
    def __init__(
        self,
        *,
        agent_id: str,
        agent_root: str | Path,
        db_path: str | Path,
        recent_window_minutes: int,
        max_context_items: int,
        query_pool_size: int,
    ) -> None:
        self.agent_id = agent_id
        self.agent_root = resolve_project_path(agent_root)
        self.db_path = resolve_project_path(db_path)
        self.recent_window = timedelta(minutes=recent_window_minutes)
        self.max_context_items = max_context_items
        self.query_pool_size = query_pool_size
        self._lock = threading.Lock()
        self._ensure_directories()
        self._init_db()

    def build_context(self, device_id: str, query: str) -> str:
        memories = self.search_memories(device_id, query, limit=self.max_context_items)
        recent_turns = self.load_recent_turns(device_id)
        if not memories and not recent_turns:
            return ""

        parts: list[str] = []
        if memories:
            parts.append("<long_term_memory>")
            parts.append(
                "These are persistent memories retrieved for this turn. Use them only "
                "when relevant, and do not reveal internal memory mechanics."
            )
            for memory in memories:
                updated_at = str(memory["updated_at"]).split("T", 1)[0]
                parts.append(
                    f"- [{memory['category']} | importance {memory['importance']:.2f} | "
                    f"{updated_at}] {memory['content']}"
                )
            parts.append("</long_term_memory>")

        if recent_turns:
            parts.append("<recent_conversation_10min>")
            for turn in recent_turns[-RECENT_TURN_LIMIT:]:
                user = turn.get("user", "")
                assistant = turn.get("assistant", "")
                parts.append(f"- user: {user}")
                if assistant:
                    parts.append(f"  assistant: {assistant}")
            parts.append("</recent_conversation_10min>")

        return "\n".join(parts)

    def remember_turn(self, device_id: str, user_text: str, assistant_text: str) -> None:
        user_text = user_text.strip()
        assistant_text = assistant_text.strip()
        if not user_text:
            return

        with self._lock:
            self._append_turn(device_id, user_text, assistant_text)
            for candidate in extract_long_term_memory_candidates(user_text, assistant_text):
                self.upsert_memory(device_id, candidate)

    def upsert_memory(self, device_id: str, candidate: MemoryCandidate) -> None:
        now = _now_iso()
        normalized_device_id = device_id or GLOBAL_DEVICE_ID
        fingerprint = _fingerprint(
            self.agent_id,
            normalized_device_id,
            candidate.category,
            candidate.subject,
            candidate.content,
        )
        memory_id = f"mem_{fingerprint[:16]}"
        metadata = {
            **candidate.metadata,
            "raw_category": candidate.category,
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memories (
                    id, agent_id, device_id, fingerprint, category, subject, content,
                    source, confidence, importance, metadata, created_at, updated_at,
                    access_count, archived
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0)
                ON CONFLICT(agent_id, device_id, fingerprint) DO UPDATE SET
                    confidence = max(confidence, excluded.confidence),
                    importance = max(importance, excluded.importance),
                    metadata = excluded.metadata,
                    updated_at = excluded.updated_at,
                    archived = 0
                """,
                (
                    memory_id,
                    self.agent_id,
                    normalized_device_id,
                    fingerprint,
                    candidate.category,
                    candidate.subject,
                    candidate.content,
                    candidate.source,
                    candidate.confidence,
                    candidate.importance,
                    json.dumps(metadata, ensure_ascii=False),
                    now,
                    now,
                ),
            )

    def search_memories(self, device_id: str, query: str, *, limit: int) -> list[dict[str, Any]]:
        now = _now_iso()
        normalized_device_id = device_id or GLOBAL_DEVICE_ID
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM memories
                WHERE agent_id = ?
                  AND device_id IN (?, ?)
                  AND archived = 0
                  AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY importance DESC, updated_at DESC
                LIMIT ?
                """,
                (
                    self.agent_id,
                    normalized_device_id,
                    GLOBAL_DEVICE_ID,
                    now,
                    self.query_pool_size,
                ),
            ).fetchall()

        keywords = _keywords(query)
        scored: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            score = _memory_score(row, query, keywords)
            if score > 0:
                scored.append((score, row))

        scored.sort(key=lambda item: (item[0], item[1]["updated_at"]), reverse=True)
        selected = [dict(row) for _, row in scored[:limit]]
        if selected:
            self._mark_accessed([memory["id"] for memory in selected])
        return selected

    def load_recent_turns(self, device_id: str) -> list[dict[str, Any]]:
        path = self._recent_path()
        if not path.exists():
            return []
        cutoff = datetime.now().astimezone() - self.recent_window
        turns: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
                timestamp = datetime.fromisoformat(item["ts"])
            except Exception:
                continue
            if timestamp < cutoff:
                continue
            if item.get("device_id") not in {device_id, GLOBAL_DEVICE_ID}:
                continue
            turns.append(item)
        return turns

    def _append_turn(self, device_id: str, user_text: str, assistant_text: str) -> None:
        now = datetime.now().astimezone()
        record = {
            "ts": now.isoformat(timespec="seconds"),
            "device_id": device_id or GLOBAL_DEVICE_ID,
            "user": user_text,
            "assistant": assistant_text,
        }
        encoded = json.dumps(record, ensure_ascii=False)

        daily_path = (
            self.agent_root
            / "memory"
            / "episodic"
            / "conversations"
            / f"{now.date().isoformat()}.jsonl"
        )
        daily_path.parent.mkdir(parents=True, exist_ok=True)
        with daily_path.open("a", encoding="utf-8") as file:
            file.write(encoded + "\n")

        recent_records = self.load_recent_turns(device_id)
        recent_records.append(record)
        recent_path = self._recent_path()
        recent_path.parent.mkdir(parents=True, exist_ok=True)
        recent_path.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in recent_records) + "\n",
            encoding="utf-8",
        )

    def _mark_accessed(self, ids: list[str]) -> None:
        now = _now_iso()
        with self._connect() as conn:
            conn.executemany(
                """
                UPDATE memories
                SET last_accessed_at = ?, access_count = access_count + 1
                WHERE id = ?
                """,
                [(now, memory_id) for memory_id in ids],
            )

    def _ensure_directories(self) -> None:
        for relative_path in (
            "memory/long_term",
            "memory/short_term",
            "memory/episodic/conversations",
            "memory/episodic/summaries",
            "runtime",
        ):
            (self.agent_root / relative_path).mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    category TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.7,
                    importance REAL NOT NULL DEFAULT 0.5,
                    metadata TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_accessed_at TEXT,
                    access_count INTEGER NOT NULL DEFAULT 0,
                    expires_at TEXT,
                    archived INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(agent_id, device_id, fingerprint)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_lookup
                ON memories(agent_id, device_id, archived, importance, updated_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memories_category
                ON memories(agent_id, device_id, category)
                """
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _recent_path(self) -> Path:
        return self.agent_root / "memory" / "short_term" / "recent_10min.jsonl"


def create_agent_memory_store(settings: Settings) -> AgentMemoryStore:
    return AgentMemoryStore(
        agent_id=settings.agent_id,
        agent_root=settings.agent_root,
        db_path=settings.memory_db_path,
        recent_window_minutes=settings.memory_recent_window_minutes,
        max_context_items=settings.memory_max_context_items,
        query_pool_size=settings.memory_query_pool_size,
    )


def extract_long_term_memory_candidates(
    user_text: str,
    assistant_text: str,
) -> list[MemoryCandidate]:
    del assistant_text
    text = user_text.strip()
    if not text:
        return []

    candidates: list[MemoryCandidate] = []
    explicit = _has_any(text, ("记住", "记得", "帮我记", "以后", "下次"))
    if explicit:
        candidates.append(
            MemoryCandidate(
                category=_classify(text),
                content=f"用户明确要求记住：{_clean_text(text)}",
                confidence=0.86,
                importance=0.78,
                metadata={"extractor": "explicit_cue"},
            )
        )

    name_match = re.search(
        r"(?:我叫|我的名字叫|以后叫我|叫我)(?P<value>[\w\u4e00-\u9fff]{1,20})",
        text,
    )
    if name_match:
        value = name_match.group("value").strip("，。！？,.!? ")
        candidates.append(
            MemoryCandidate(
                category="people",
                content=f"用户希望 Usaki 称呼自己为：{value}。",
                confidence=0.9,
                importance=0.82,
                metadata={"extractor": "name_pattern"},
            )
        )

    for pattern, label, polarity in (
        (r"我(?:很|特别|比较)?喜欢(?P<value>[^。！？,.，!?\n]{1,50})", "喜欢", "positive"),
        (r"我(?:很|特别|比较)?不喜欢(?P<value>[^。！？,.，!?\n]{1,50})", "不喜欢", "negative"),
        (r"我(?:很|特别|比较)?讨厌(?P<value>[^。！？,.，!?\n]{1,50})", "讨厌", "negative"),
        (r"我(?:习惯|偏好)(?P<value>[^。！？,.，!?\n]{1,50})", "偏好", "positive"),
    ):
        match = re.search(pattern, text)
        if not match:
            continue
        value = match.group("value").strip()
        candidates.append(
            MemoryCandidate(
                category="preferences",
                content=f"用户{label}{value}。",
                confidence=0.82,
                importance=0.68,
                metadata={"extractor": "preference_pattern", "polarity": polarity},
            )
        )

    if _has_any(text, ("提醒我", "待办", "任务", "todo", "计划")):
        candidates.append(
            MemoryCandidate(
                category="tasks",
                content=f"用户提到一个需要跟进的任务或提醒：{_clean_text(text)}",
                confidence=0.78,
                importance=0.76,
                metadata={"extractor": "task_cue"},
            )
        )

    if _has_any(text, ("生日", "纪念日", "日程", "几点", "明天", "后天", "下周", "周末")):
        candidates.append(
            MemoryCandidate(
                category="events",
                content=f"用户提到一个重要时间或事件：{_clean_text(text)}",
                confidence=0.72,
                importance=0.7,
                metadata={"extractor": "event_cue"},
            )
        )

    if _has_any(text, ("纠正", "记错", "不是", "不对")) and _has_any(
        text,
        ("而是", "应该", "其实"),
    ):
        candidates.append(
            MemoryCandidate(
                category="corrections",
                content=f"用户纠正了 Usaki 的理解：{_clean_text(text)}",
                confidence=0.86,
                importance=0.9,
                metadata={"extractor": "correction_cue"},
            )
        )

    return _dedupe_candidates(candidates)


def _memory_score(row: sqlite3.Row, query: str, keywords: list[str]) -> float:
    category_priority = {
        "corrections": 3.0,
        "tasks": 2.4,
        "people": 2.1,
        "events": 1.8,
        "preferences": 1.6,
        "self_growth": 1.2,
    }
    content = str(row["content"])
    score = float(row["importance"]) * 3.0 + float(row["confidence"])
    score += category_priority.get(str(row["category"]), 1.0)

    stripped_query = query.strip()
    if stripped_query and stripped_query in content:
        score += 4.0
    for keyword in keywords:
        if keyword and keyword in content:
            score += 1.2

    if not keywords and row["category"] in {"corrections", "tasks", "people"}:
        score += 1.0
    return score


def _keywords(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9_]{2,}|[\u4e00-\u9fff]{2,}", text)
    keywords: list[str] = []
    for word in words:
        if re.fullmatch(r"[\u4e00-\u9fff]{2,}", word):
            keywords.append(word)
            keywords.extend(word[index : index + 2] for index in range(min(len(word) - 1, 6)))
        else:
            keywords.append(word.lower())
    seen: set[str] = set()
    result: list[str] = []
    for keyword in keywords:
        if keyword in seen:
            continue
        seen.add(keyword)
        result.append(keyword)
    return result[:16]


def _classify(text: str) -> str:
    if _has_any(text, ("纠正", "记错", "不是", "不对")):
        return "corrections"
    if _has_any(text, ("提醒", "待办", "任务", "todo", "计划")):
        return "tasks"
    if _has_any(text, ("生日", "纪念日", "日程", "明天", "后天", "下周")):
        return "events"
    if _has_any(text, ("我叫", "我的名字", "叫我")):
        return "people"
    if _has_any(text, ("喜欢", "不喜欢", "讨厌", "偏好", "习惯", "称呼")):
        return "preferences"
    return "self_growth" if _has_any(text, ("你以后", "以后你")) else "preferences"


def _dedupe_candidates(candidates: list[MemoryCandidate]) -> list[MemoryCandidate]:
    seen: set[tuple[str, str]] = set()
    deduped: list[MemoryCandidate] = []
    for candidate in candidates:
        key = (candidate.category, candidate.content)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in needles)


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _fingerprint(*parts: str) -> str:
    normalized = "|".join(_clean_text(part).lower() for part in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
