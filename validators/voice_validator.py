from __future__ import annotations
import re
from models import FullContext
from models.messages import ComposedMessage
from models.results import ValidationResult


class VoiceValidator:
    def validate(self, message: ComposedMessage, ctx: FullContext) -> ValidationResult:
        errors = []
        category = ctx.category.slug.lower()
        body = message.body.lower()
        if category in {"dentists", "doctors", "lawyers"}:
            banned = ["guaranteed", "cure", "amazing deal", "best ever"]
            hits = [x for x in banned if re.search(rf"\b{re.escape(x)}\b", body)]
            if hits:
                errors.append(f"category voice/taboo violation: {hits[0]}")
        return ValidationResult(valid=not errors, errors=errors)
