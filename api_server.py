from __future__ import annotations
import os
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from bot import compose
from models.api import ContextPush, TickRequest, TickResponse, TickAction, ReplyRequest, ReplyResponse, MetadataResponse
from models.conversation import ConversationState
from session.store import ContextStore, Conversation
from conversation_handlers import respond as respond_conversation

load_dotenv()

app = FastAPI(title="Vera Merchant AI Assistant", version=os.getenv("VERA_VERSION", "1.0.0"))
store = ContextStore()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_dt(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def ack_id(scope: str, context_id: str, version: int) -> str:
    return f"ack_{scope}_{context_id[:32]}_v{version}"


def conversation_id_for(merchant_id: str, trigger_id: str, customer_id: str | None) -> str:
    raw = f"{merchant_id}|{customer_id or ''}|{trigger_id}"
    digest = sha256(raw.encode()).hexdigest()[:12]
    prefix = "conv_" + (customer_id or merchant_id).replace("_", "-")
    return f"{prefix}_{digest}"


def template_name_for(kind: str, customer: bool) -> str:
    prefix = "merchant" if customer else "vera"
    safe = kind.replace("-", "_")
    return f"{prefix}_{safe}_v1"


def template_params_for(result: dict, category: dict, merchant: dict, trigger: dict, customer: dict | None) -> list[str]:
    body = result["body"]
    if customer is not None:
        c_name = (customer.get("identity") or {}).get("name", "there")
        m_name = (merchant.get("identity") or {}).get("name", "the business")
        return [c_name, m_name, body]
    owner = (merchant.get("identity") or {}).get("owner_first_name") or (merchant.get("identity") or {}).get("name") or "there"
    return [str(owner), body, result.get("rationale", "")]


@app.get("/v1/healthz")
def healthz():
    return {
        "status": "ok",
        "uptime_seconds": store.uptime_seconds,
        "contexts_loaded": store.counts(),
    }


@app.get("/v1/metadata", response_model=MetadataResponse)
def metadata():
    return MetadataResponse(
        team_name=os.getenv("VERA_TEAM_NAME", "Team Vera"),
        team_members=[x.strip() for x in os.getenv("VERA_TEAM_MEMBERS", "").split(",") if x.strip()],
        model=os.getenv("VERA_MODEL", "deterministic-local"),
        approach="deterministic context router + retrieval + validated composer + stateful reply handlers",
        contact_email=os.getenv("VERA_CONTACT_EMAIL", "team@example.com"),
        version=os.getenv("VERA_VERSION", "1.0.0"),
        submitted_at=os.getenv("VERA_SUBMITTED_AT", now_iso()),
    )


@app.post("/v1/context")
def push_context(req: ContextPush):
    accepted, reason, current_version = store.put(req.scope, req.context_id, req.version, req.payload, req.delivered_at)
    if not accepted:
        return JSONResponse(status_code=409, content={"accepted": False, "reason": reason, "current_version": current_version})
    return {"accepted": True, "ack_id": ack_id(req.scope, req.context_id, req.version), "stored_at": now_iso()}


@app.post("/v1/tick", response_model=TickResponse)
def tick(req: TickRequest):
    actions: list[TickAction] = []
    for trigger_id in req.available_triggers:
        trigger_raw = store.get("trigger", trigger_id)
        if trigger_raw is None:
            continue
        trigger = trigger_raw
        merchant_id = trigger.get("merchant_id")
        customer_id = trigger.get("customer_id")
        if not merchant_id:
            continue
        merchant = store.get("merchant", merchant_id)
        if merchant is None:
            continue
        category_slug = merchant.get("category_slug") or trigger.get("payload", {}).get("category")
        category = store.get("category", category_slug) if category_slug else None
        customer = store.get("customer", customer_id) if customer_id else None
        if category is None or (customer_id and customer is None):
            continue

        conv_id = conversation_id_for(merchant_id, trigger_id, customer_id)
        conv = store.get_conversation(conv_id)
        if conv is None:
            conv = Conversation(conversation_id=conv_id, merchant_id=merchant_id, customer_id=customer_id, trigger_id=trigger_id)
            store.upsert_conversation(conv)

        # Suppress terminal conversations and ordinary duplicate ticks.
        # AUTO_REPLY_DETECTED is intentionally allowed to re-enter after its wait window.
        suppression = trigger.get("suppression_key") or trigger_id
        scoped_key = f"{suppression}:{merchant_id}:{customer_id or ''}"
        if conv.status in {"EXITED", "NOT_INTERESTED"} or store.is_suppressed(f"conversation:{conv_id}"):
            continue
        if conv.status == "CONTACTED" and conv.last_outbound_at is not None:
            continue
        if conv.status == "AUTO_REPLY_DETECTED" and conv.next_retry_at is not None:
            if parse_dt(req.now) < conv.next_retry_at:
                continue

        result = compose(category, merchant, trigger, customer)
        conv.last_outbound = result["body"]
        conv.last_cta = result["cta"]
        conv.last_send_as = result["send_as"]
        conv.last_suppression_key = result["suppression_key"]
        conv.last_outbound_at = parse_dt(req.now)
        conv.next_retry_at = None
        conv.template_sent = True
        conv.status = "CONTACTED"
        conv.turns.append({"role": "vera" if customer_id is None else "merchant_on_behalf", "message": result["body"]})
        store.upsert_conversation(conv)
        actions.append(TickAction(
            conversation_id=conv_id,
            merchant_id=merchant_id,
            customer_id=customer_id,
            send_as=result["send_as"],
            trigger_id=trigger_id,
            template_name=template_name_for(trigger.get("kind", "message"), customer_id is not None),
            template_params=template_params_for(result, category, merchant, trigger, customer),
            body=result["body"],
            cta=result["cta"],
            suppression_key=result["suppression_key"],
            rationale=result["rationale"],
        ))
    return TickResponse(actions=actions)


@app.post("/v1/reply", response_model=ReplyResponse)
def reply(req: ReplyRequest):
    conv = store.get_conversation(req.conversation_id)
    if conv is None:
        conv = Conversation(conversation_id=req.conversation_id, merchant_id=req.merchant_id or "", customer_id=req.customer_id)
        store.upsert_conversation(conv)

    state = ConversationState(
        conversation_id=conv.conversation_id,
        merchant_id=conv.merchant_id or req.merchant_id or "",
        customer_id=conv.customer_id or req.customer_id,
        trigger_id=conv.trigger_id,
        status=conv.status,
        retry_count=conv.retry_count,
        turns=[],
        last_outbound_at=conv.last_outbound_at,
        last_inbound_at=conv.last_inbound_at,
    )
    for turn in conv.turns:
        role = "merchant" if turn.get("role") == "merchant" else "vera"
        from models.conversation import ConversationTurn
        state.turns.append(ConversationTurn(role=role, message=str(turn.get("message", ""))))

    result = respond_conversation(state, req.message)
    if req.received_at:
        # Use the judge-supplied timestamp for deterministic retry scheduling.
        state.last_inbound_at = parse_dt(req.received_at)

    # Copy state back into store.
    conv.status = state.status
    conv.retry_count = state.retry_count
    conv.turns = [{"role": t.role, "message": t.message} for t in state.turns]
    conv.last_inbound_at = state.last_inbound_at
    conv.last_outbound_at = state.last_outbound_at
    if result["action"] == "wait":
        seconds = int(result.get("wait_seconds") or 0)
        conv.next_retry_at = (state.last_inbound_at or datetime.now(timezone.utc)) + __import__("datetime").timedelta(seconds=seconds)
    else:
        conv.next_retry_at = None
    store.upsert_conversation(conv)

    if result["action"] == "end":
        store.suppress(f"conversation:{req.conversation_id}")
    return ReplyResponse(action=result["action"], body=result.get("body"), cta=result.get("cta"), wait_seconds=result.get("wait_seconds"), rationale=result.get("rationale", ""))
