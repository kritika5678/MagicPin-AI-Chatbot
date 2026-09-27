from __future__ import annotations
from difflib import SequenceMatcher
from models.messages import ComposedMessage
from models.results import ValidationResult


class RepetitionValidator:
    def validate(self, message: ComposedMessage, previous_messages: list[str]) -> ValidationResult:
        for prev in previous_messages:
            if not prev.strip():
                continue
            ratio = SequenceMatcher(None, message.body.lower().strip(), prev.lower().strip()).ratio()
            if ratio >= 0.90:
                return ValidationResult(valid=False, errors=[f"message too similar to previous message ({ratio:.2f})"])
        return ValidationResult(valid=True)
