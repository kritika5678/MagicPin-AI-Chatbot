from __future__ import annotations
import re
from models import FullContext, MessageStrategy
from models.messages import ComposedMessage
from models.results import ValidationResult


class CTAValidator:
    def validate(self, message: ComposedMessage, strategy: MessageStrategy, ctx: FullContext) -> ValidationResult:
        errors = []
        yes = len(re.findall(r"\bYES\b", message.body, flags=re.I))
        stop = len(re.findall(r"\bSTOP\b", message.body, flags=re.I))
        question_marks = message.body.count("?")
        if strategy.cta == "yes_stop":
            if not (yes or stop):
                errors.append("expected YES/STOP CTA but none found")
            if yes + stop > 2:
                errors.append("more than one YES/STOP CTA token pair detected")
        if strategy.cta == "none" and (yes or stop or question_marks):
            errors.append("CTA-like text present while CTA is configured as none")
        return ValidationResult(valid=not errors, errors=errors)
