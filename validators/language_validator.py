from __future__ import annotations
from models.messages import ComposedMessage
from models.strategy import MessageStrategy
from models.results import ValidationResult


class LanguageValidator:
    def validate(self, message: ComposedMessage, strategy: MessageStrategy) -> ValidationResult:
        warnings = []
        if strategy.language == "hi-en":
            hindi_markers = {"aap", "hai", "mujhe", "karna", "chalega", "mein", "ka", "ki", "ke"}
            tokens = set(message.body.lower().split())
            if not any(m in tokens for m in hindi_markers):
                warnings.append("strategy requests hi-en but generated body looks English-only")
        return ValidationResult(valid=True, warnings=warnings)
