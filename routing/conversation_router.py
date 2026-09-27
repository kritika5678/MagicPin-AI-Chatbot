from __future__ import annotations
from models.results import IntentResult, AutoReplyResult


class ConversationRouter:
    def decide(self, intent: IntentResult, auto_reply: AutoReplyResult, retry_count: int, followups_sent: int) -> str:
        if auto_reply.is_auto_reply and retry_count >= 1:
            return "EXIT"
        if intent.intent in {"stop", "not_interested", "negative_interest"}:
            return "EXIT"
        if intent.intent in {"join", "start_action", "update_profile", "create_offer", "approve"}:
            return "ACTION"
        if intent.intent in {"question", "request_information", "complaint", "clarification"}:
            return "CLARIFY"
        if followups_sent >= 3:
            return "EXIT"
        return "ENGAGE"
