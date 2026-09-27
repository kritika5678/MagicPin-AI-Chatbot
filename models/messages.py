from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class ComposedMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1)
    cta: Literal["yes_stop", "open_ended", "none"]
    send_as: Literal["vera", "merchant_on_behalf"]
    suppression_key: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
