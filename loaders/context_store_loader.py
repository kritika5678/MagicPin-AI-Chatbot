from __future__ import annotations
from models import CategoryContext, MerchantContext, CustomerContext, TriggerContext
from session.store import ContextStore


def build_models(store: ContextStore, trigger_id: str):
    trigger_raw = store.get("trigger", trigger_id)
    if trigger_raw is None:
        raise KeyError(f"Unknown trigger: {trigger_id}")
    trigger = TriggerContext.model_validate(trigger_raw)

    merchant_raw = store.get("merchant", trigger.merchant_id)
    if merchant_raw is None:
        raise KeyError(f"Merchant context missing: {trigger.merchant_id}")
    merchant = MerchantContext.model_validate(merchant_raw)

    category_slug = merchant_raw.get("category_slug") or trigger.payload.get("category")
    if not category_slug:
        category_slug = trigger.payload.get("category_slug")
    if not category_slug:
        raise KeyError(f"Cannot resolve category for merchant {trigger.merchant_id}")
    category_raw = store.get("category", category_slug)
    if category_raw is None:
        raise KeyError(f"Category context missing: {category_slug}")
    category = CategoryContext.model_validate(category_raw)

    customer = None
    customer_id = trigger.customer_id
    if customer_id:
        customer_raw = store.get("customer", customer_id)
        if customer_raw is None:
            raise KeyError(f"Customer context missing: {customer_id}")
        customer = CustomerContext.model_validate(customer_raw)

    return category, merchant, trigger, customer
