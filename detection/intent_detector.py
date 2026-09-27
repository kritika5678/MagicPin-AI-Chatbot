from __future__ import annotations
import re
from models.results import IntentResult

RULES: list[tuple[str, list[str], float]] = [
    ("stop", [r"\bstop\b", r"unsubscribe", r"don't message", r"do not message", r"dont message", r"stop sending"], 0.99),
    ("not_interested", [r"not interested", r"nahi chahiye", r"no thanks", r"not required", r"don't need", r"dont need", r"useless", r"bothering me"], 0.98),
    ("join", [r"want to join", r"join magicpin", r"mujhe.*join.*karna", r"join karna hai", r"join.*karna"], 0.98),
    ("update_profile", [r"update.*google profile", r"update.*profile", r"google listing", r"google business profile"], 0.96),
    ("create_offer", [r"create.*offer", r"make.*offer", r"offer.*bana", r"draft.*offer"], 0.96),
    ("approve", [r"go ahead", r"do it", r"let's do it", r"lets do it", r"what's next", r"whats next", r"chalega", r"yes please"], 0.96),
    ("request_information", [r"how much", r"what is", r"what's", r"tell me", r"details", r"kitna", r"kaise", r"how does it work"], 0.92),
    ("complaint", [r"complaint", r"issue", r"problem", r"not working", r"can't see", r"cannot see"], 0.94),
]


class IntentDetector:
    def classify(self, message: str) -> IntentResult:
        text = (message or "").lower().strip()
        if not text:
            return IntentResult(intent="unknown", confidence=0.0, reason="empty input")
        for intent, patterns, confidence in RULES:
            for pattern in patterns:
                if re.search(pattern, text, re.I):
                    return IntentResult(intent=intent, confidence=confidence, reason=f"matched rule: {pattern}")
        if text in {"yes", "haan", "yeah", "y", "okay", "ok", "sure"}:
            return IntentResult(intent="positive_interest", confidence=0.90, reason="short affirmative response")
        if text in {"no", "n", "nah", "nope"}:
            return IntentResult(intent="negative_interest", confidence=0.90, reason="short negative response")
        return IntentResult(intent="unknown", confidence=0.45, reason="no deterministic rule matched")
