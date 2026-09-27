from __future__ import annotations
from typing import Any

from models import CategoryContext, MerchantContext, CustomerContext, TriggerContext, FullContext, ComposedMessage
from retrieval.fact_retriever import FactRetriever
from strategy.message_strategy import MessageStrategyEngine
from llm.client import LLMClient
from llm.composer import LLMComposer, LocalDeterministicComposer
from validators.message_validator import MessageValidator
from session.suppression import generate_suppression_key

_llm_client: LLMClient | None = None


def configure_llm(client: LLMClient | None) -> None:
    global _llm_client
    _llm_client = client


def compose(category: dict, merchant: dict, trigger: dict, customer: dict | None = None) -> dict:
    category_m = CategoryContext.model_validate(category)
    merchant_m = MerchantContext.model_validate(merchant)
    trigger_m = TriggerContext.model_validate(trigger)
    customer_m = CustomerContext.model_validate(customer) if customer is not None else None

    trigger_merchant_id = trigger_m.merchant_id or trigger_m.payload.get("merchant_id")
    if trigger_merchant_id and trigger_merchant_id != merchant_m.merchant_id:
        raise ValueError("trigger merchant_id does not match merchant.merchant_id")
    trigger_customer_id = trigger_m.customer_id or trigger_m.payload.get("customer_id")
    if customer_m is not None:
        if customer_m.merchant_id != merchant_m.merchant_id:
            raise ValueError("customer.merchant_id does not match merchant.merchant_id")
        if trigger_customer_id and customer_m.customer_id != trigger_customer_id:
            raise ValueError("customer does not match trigger.customer_id")
    if merchant_m.category_slug and merchant_m.category_slug != category_m.slug:
        raise ValueError("merchant.category_slug does not match category.slug")

    # Use conversation history only for unambiguous action intent; do not treat
    # generic historical affirmations such as "yes please" as a new turn.
    history = merchant_m.conversation_history if isinstance(merchant_m.conversation_history, list) else []
    latest_merchant = None
    for item in reversed(history):
        if isinstance(item, dict) and item.get("from") == "merchant":
            latest_merchant = str(item.get("body", ""))
            break
        if isinstance(item, dict) and item.get("role") == "merchant":
            latest_merchant = str(item.get("message") or item.get("body") or "")
            break
    if latest_merchant:
        lower = latest_merchant.lower().strip()
        strong_action = (
            any(x in lower for x in ["want to join", "join magicpin", "join karna hai", "mujhe magicpin join"])
            or "update google profile" in lower
            or "update my profile" in lower
            or "create an offer" in lower
            or "make an offer" in lower
            or lower in {"go ahead", "let's do it", "lets do it"}
        )
        if strong_action and customer_m is None:
            result = ComposedMessage(
                body="Bilkul — aapne action ke liye clear intent diya hai. Chaliye next concrete step se start karte hain.",
                cta="yes_stop",
                send_as="vera",
                suppression_key=generate_suppression_key(trigger_m.suppression_key or trigger_m.kind, merchant_m.merchant_id, None),
                rationale="Strong explicit action intent found in the supplied conversation history; routed directly to action mode.",
            )
            return result.model_dump()

    ctx = FullContext(category=category_m, merchant=merchant_m, trigger=trigger_m, customer=customer_m)
    strategy = MessageStrategyEngine().build(ctx, last_user_message=None, requires_template=False)
    facts = FactRetriever().retrieve(ctx, strategy.objective)

    if _llm_client is None:
        draft = LocalDeterministicComposer().compose(ctx, strategy, facts)
    else:
        draft = LLMComposer(_llm_client).compose(ctx, strategy, facts)

    draft = draft.model_copy(update={
        "suppression_key": generate_suppression_key(trigger_m.suppression_key or trigger_m.kind, merchant_m.merchant_id, customer_m.customer_id if customer_m else None),
        "send_as": "merchant_on_behalf" if customer_m is not None and trigger_m.scope == "customer" else draft.send_as,
    })

    validation = MessageValidator().validate(draft, ctx, strategy)
    if not validation.valid:
        raise ValueError("Message failed validation: " + " | ".join(validation.errors))
    return draft.model_dump()
