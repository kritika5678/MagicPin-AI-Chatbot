from __future__ import annotations
from datetime import datetime, timezone
from models.conversation import ConversationState


class SessionManager:
    def is_within_24h(self, state: ConversationState, now: datetime | None = None) -> bool:
        return state.within_24h(now=now)

    def requires_template(self, state: ConversationState, now: datetime | None = None) -> bool:
        return not self.is_within_24h(state, now=now)
