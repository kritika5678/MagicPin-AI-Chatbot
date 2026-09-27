from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class MessageStrategy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: Literal[
        "INFORM", "ENGAGE", "CONVERT", "ACTION", "RETENTION", "RECALL", "CLARIFY", "EXIT"
    ]
    primary_fact: str | None = None
    supporting_facts: list[str] = Field(default_factory=list)
    engagement_lever: str | None = None
    tone: str = "peer"
    language: Literal["english", "hindi", "hi-en", "unknown"] = "unknown"
    cta: Literal["yes_stop", "open_ended", "none"] = "none"
    send_as: Literal["vera", "merchant_on_behalf"] = "vera"
    urgency: int = 1
    requires_template: bool = False
