from __future__ import annotations
from models import FullContext, MessageStrategy
from models.messages import ComposedMessage
from models.results import ValidationResult
from .schema_validator import SchemaValidator
from .fact_validator import FactValidator
from .cta_validator import CTAValidator
from .voice_validator import VoiceValidator
from .language_validator import LanguageValidator
from .repetition_validator import RepetitionValidator


class MessageValidator:
    def __init__(self):
        self.schema = SchemaValidator()
        self.fact = FactValidator()
        self.cta = CTAValidator()
        self.voice = VoiceValidator()
        self.language = LanguageValidator()
        self.repetition = RepetitionValidator()

    def validate(self, message: ComposedMessage, ctx: FullContext, strategy: MessageStrategy) -> ValidationResult:
        results = [
            self.schema.validate(message),
            self.fact.validate(message, ctx),
            self.cta.validate(message, strategy, ctx),
            self.voice.validate(message, ctx),
            self.language.validate(message, strategy),
        ]
        previous = []
        hist = ctx.merchant.conversation_history
        if isinstance(hist, list):
            for item in hist:
                if isinstance(item, str):
                    previous.append(item)
                elif isinstance(item, dict) and "message" in item:
                    previous.append(str(item["message"]))
        results.append(self.repetition.validate(message, previous))

        errors = [e for r in results for e in r.errors]
        warnings = [w for r in results for w in r.warnings]
        return ValidationResult(valid=not errors, errors=errors, warnings=warnings)
