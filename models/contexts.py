from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class FlexibleModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class CategoryContext(FlexibleModel):
    slug: str
    offer_catalog: list[Any] = Field(default_factory=list)
    voice: Any = Field(default_factory=dict)
    peer_stats: Any = Field(default_factory=dict)
    digest: list[Any] = Field(default_factory=list)
    patient_content_library: list[Any] = Field(default_factory=list)
    seasonal_beats: list[Any] = Field(default_factory=list)
    trend_signals: list[Any] = Field(default_factory=list)


class MerchantContext(FlexibleModel):
    merchant_id: str
    category_slug: str | None = None
    identity: Any = Field(default_factory=dict)
    subscription: Any = Field(default_factory=dict)
    performance: Any = Field(default_factory=dict)
    offers: list[Any] = Field(default_factory=list)
    conversation_history: Any = Field(default_factory=list)
    customer_aggregate: Any = Field(default_factory=dict)
    signals: list[Any] = Field(default_factory=list)


class TriggerContext(FlexibleModel):
    id: str
    merchant_id: str | None = None
    customer_id: str | None = None
    scope: Literal["merchant", "customer"]
    kind: str
    source: Literal["external", "internal"]
    payload: dict[str, Any] = Field(default_factory=dict)
    urgency: int = 1
    suppression_key: str
    expires_at: Optional[datetime] = None


class CustomerContext(FlexibleModel):
    customer_id: str
    merchant_id: str
    identity: Any = Field(default_factory=dict)
    relationship: Any = Field(default_factory=dict)
    state: str = "new"
    preferences: Any = Field(default_factory=dict)
    consent: Any = Field(default_factory=dict)


class FullContext(FlexibleModel):
    category: CategoryContext
    merchant: MerchantContext
    trigger: TriggerContext
    customer: Optional[CustomerContext] = None
