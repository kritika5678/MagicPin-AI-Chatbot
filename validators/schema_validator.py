from __future__ import annotations
from pydantic import ValidationError
from models.messages import ComposedMessage
from models.results import ValidationResult


class SchemaValidator:
    def validate(self, message: ComposedMessage) -> ValidationResult:
        try:
            ComposedMessage.model_validate(message.model_dump())
            return ValidationResult(valid=True)
        except ValidationError as e:
            return ValidationResult(valid=False, errors=[str(e)])
