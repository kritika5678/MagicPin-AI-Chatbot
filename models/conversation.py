from __future__ import annotations
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field


class ConversationTurn(BaseModel):
    role: str
    message: str
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    intent: str | None = None


class ConversationState(BaseModel):
    conversation_id: str = ""
    merchant_id: str
    customer_id: str | None = None
    trigger_id: str | None = None
    status: str = "NEW"
    turns: list[ConversationTurn] = Field(default_factory=list)
    retry_count: int = 0
    followups_sent: int = 0
    last_intent: str | None = None
    current_goal: str | None = None
    last_outbound_at: datetime | None = None
    last_inbound_at: datetime | None = None

    def within_24h(self, now: datetime | None = None) -> bool:
        if self.last_inbound_at is None:
            return False
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now - self.last_inbound_at <= timedelta(hours=24)

# Backward-compatible alias retained for the original scaffold.
SessionState = ConversationState
