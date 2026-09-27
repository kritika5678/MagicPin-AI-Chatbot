from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any


@dataclass
class VersionedContext:
    version: int
    payload: dict[str, Any]
    delivered_at: str | None = None


@dataclass
class Conversation:
    conversation_id: str
    merchant_id: str
    customer_id: str | None
    trigger_id: str | None = None
    turns: list[dict[str, Any]] = field(default_factory=list)
    auto_reply_count: int = 0
    retry_count: int = 0
    status: str = "NEW"
    last_outbound: str | None = None
    last_cta: str | None = None
    last_send_as: str | None = None
    last_suppression_key: str | None = None
    template_sent: bool = False
    last_inbound_at: datetime | None = None
    last_outbound_at: datetime | None = None
    next_retry_at: datetime | None = None

    @property
    def has_merchant_reply(self) -> bool:
        return any(t.get("role") == "merchant" for t in self.turns)


class ContextStore:
    """Thread-safe in-memory context store matching the challenge push semantics."""

    def __init__(self):
        self._data: dict[str, dict[str, VersionedContext]] = {
            "category": {}, "merchant": {}, "customer": {}, "trigger": {}
        }
        self._conversations: dict[str, Conversation] = {}
        self._suppressed: set[str] = set()
        self._lock = RLock()
        self.started_at = datetime.now(timezone.utc)

    def put(self, scope: str, context_id: str, version: int, payload: dict[str, Any], delivered_at: str | None = None) -> tuple[bool, str | None, int | None]:
        with self._lock:
            existing = self._data[scope].get(context_id)
            if existing is not None and version < existing.version:
                return False, "stale_version", existing.version
            if existing is not None and version == existing.version:
                # Idempotent replay: the same context version is accepted as a no-op.
                return True, None, existing.version
            self._data[scope][context_id] = VersionedContext(version, payload, delivered_at)
            return True, None, None

    def get(self, scope: str, context_id: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._data.get(scope, {}).get(context_id)
            return None if item is None else item.payload

    def version(self, scope: str, context_id: str) -> int | None:
        with self._lock:
            item = self._data.get(scope, {}).get(context_id)
            return None if item is None else item.version

    def counts(self) -> dict[str, int]:
        with self._lock:
            return {k: len(v) for k, v in self._data.items()}

    def upsert_conversation(self, conv: Conversation) -> None:
        with self._lock:
            self._conversations[conv.conversation_id] = conv

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        with self._lock:
            return self._conversations.get(conversation_id)

    def suppress(self, key: str) -> None:
        with self._lock:
            self._suppressed.add(key)

    def is_suppressed(self, key: str) -> bool:
        with self._lock:
            return key in self._suppressed

    @property
    def uptime_seconds(self) -> int:
        return max(0, int((datetime.now(timezone.utc) - self.started_at).total_seconds()))
