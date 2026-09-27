from __future__ import annotations
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


class ContextPush(BaseModel):
    scope: Literal["category", "merchant", "customer", "trigger"]
    context_id: str
    version: int = Field(ge=1)
    delivered_at: str | None = None
    payload: dict[str, Any]


class TickRequest(BaseModel):
    now: str
    available_triggers: list[str] = Field(default_factory=list)


class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: str | None = None
    customer_id: str | None = None
    from_role: Literal["merchant", "customer"] = "merchant"
    message: str
    received_at: str | None = None
    turn_number: int = Field(default=2, ge=1)


class ContextAck(BaseModel):
    accepted: bool
    ack_id: str | None = None
    stored_at: str | None = None
    reason: str | None = None
    current_version: int | None = None


class TickAction(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: str | None = None
    send_as: Literal["vera", "merchant_on_behalf"]
    trigger_id: str
    template_name: str | None = None
    template_params: list[str] = Field(default_factory=list)
    body: str
    cta: str
    suppression_key: str
    rationale: str


class TickResponse(BaseModel):
    actions: list[TickAction] = Field(default_factory=list)


class ReplyResponse(BaseModel):
    action: Literal["send", "wait", "end"]
    body: str | None = None
    cta: str | None = None
    wait_seconds: int | None = None
    rationale: str


class MetadataResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    team_name: str
    team_members: list[str]
    model: str
    approach: str
    contact_email: str
    version: str
    submitted_at: str
