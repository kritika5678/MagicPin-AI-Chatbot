from __future__ import annotations
import re
from difflib import SequenceMatcher
from models.results import AutoReplyResult


DEFAULT_PATTERNS = [
    r"thank you for (contacting|reaching out)",
    r"thanks for (contacting|reaching out)",
    r"our team will (get back|contact|respond)",
    r"we will get back to you",
    r"for your (information|reference)",
    r"automated assistant",
    r"this is an automated",
]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w₹%+.-]+", " ", text.lower())).strip()


class AutoReplyDetector:
    def __init__(self, patterns: list[str] | None = None, duplicate_threshold: float = 0.96):
        self.patterns = patterns or DEFAULT_PATTERNS
        self.duplicate_threshold = duplicate_threshold

    def detect(self, current_message: str, conversation_history: list[str]) -> AutoReplyResult:
        cur = _norm(current_message)
        if not cur:
            return AutoReplyResult(is_auto_reply=False, confidence=0.0, reason="empty message")

        duplicate_count = sum(1 for m in conversation_history if _norm(m) == cur)
        if duplicate_count >= 2:
            return AutoReplyResult(
                is_auto_reply=True, confidence=0.99,
                reason=f"same normalized reply observed {duplicate_count + 1} times",
                should_retry_once=False,
            )

        best_similarity = 0.0
        for m in conversation_history:
            if not m:
                continue
            best_similarity = max(best_similarity, SequenceMatcher(None, cur, _norm(m)).ratio())
        if best_similarity >= self.duplicate_threshold and len(cur) > 20:
            return AutoReplyResult(
                is_auto_reply=True, confidence=0.93,
                reason=f"high similarity to prior reply ({best_similarity:.2f})",
                should_retry_once=True,
            )

        hits = [p for p in self.patterns if re.search(p, current_message, flags=re.I)]
        if hits:
            return AutoReplyResult(
                is_auto_reply=True, confidence=0.86,
                reason=f"known auto-reply pattern matched: {hits[0]}",
                should_retry_once=True,
            )

        return AutoReplyResult(is_auto_reply=False, confidence=0.08, reason="no auto-reply signal")
