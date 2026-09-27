from __future__ import annotations
from pydantic import BaseModel, Field


class IntentResult(BaseModel):
    intent: str
    confidence: float = Field(ge=0, le=1)
    reason: str = ""


class AutoReplyResult(BaseModel):
    is_auto_reply: bool
    confidence: float = Field(ge=0, le=1)
    reason: str = ""
    should_retry_once: bool = False


class RetrievedFacts(BaseModel):
    facts: list[str] = Field(default_factory=list)
    evidence: dict[str, str] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
