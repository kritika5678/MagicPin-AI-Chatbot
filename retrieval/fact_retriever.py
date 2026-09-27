from __future__ import annotations
from typing import Any
from models import FullContext
from models.results import RetrievedFacts


def _get(obj: Any, *keys: str, default=None):
    cur = obj
    for key in keys:
        if isinstance(cur, dict):
            cur = cur.get(key, default)
        else:
            cur = getattr(cur, key, default)
        if cur is None:
            return default
    return cur


def _fmt(value: Any) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{k}={v}" for k, v in value.items())
    if isinstance(value, list):
        return ", ".join(map(str, value))
    return str(value)


class FactRetriever:
    def retrieve(self, ctx: FullContext, objective: str) -> RetrievedFacts:
        facts: list[str] = []
        evidence: dict[str, str] = {}
        m, c, t, customer = ctx.merchant, ctx.category, ctx.trigger, ctx.customer

        identity_name = _get(m.identity, "name")
        for key, value in (("merchant_name", identity_name), ("city", _get(m.identity, "city")), ("locality", _get(m.identity, "locality")), ("owner_first_name", _get(m.identity, "owner_first_name"))):
            if value:
                facts.append(f"{key}={value}")
                evidence[key] = f"MerchantContext.identity.{key if key != 'merchant_name' else 'name'}"

        perf = m.performance if isinstance(m.performance, dict) else {}
        for key in ("views", "calls", "directions", "ctr", "leads"):
            if key in perf:
                facts.append(f"performance.{key}={perf[key]}")
                evidence[f"performance.{key}"] = f"MerchantContext.performance.{key}"
        delta = perf.get("delta_7d")
        if isinstance(delta, dict):
            for key, value in delta.items():
                facts.append(f"performance.delta_7d.{key}={value}")
                evidence[f"performance.delta_7d.{key}"] = f"MerchantContext.performance.delta_7d.{key}"

        sub = m.subscription if isinstance(m.subscription, dict) else {}
        for key in ("status", "plan", "days_remaining", "days_since_expiry"):
            if key in sub and sub[key] is not None:
                facts.append(f"subscription.{key}={sub[key]}")
                evidence[f"subscription.{key}"] = f"MerchantContext.subscription.{key}"

        if m.offers:
            for i, offer in enumerate(m.offers):
                if isinstance(offer, dict) and offer.get("status") not in {None, "active"}:
                    continue
                facts.append(f"offer_{i+1}={_fmt(offer)}")
                evidence[f"offer_{i+1}"] = "MerchantContext.offers"
                if i >= 4:
                    break

        peer = c.peer_stats if isinstance(c.peer_stats, dict) else {}
        for key in peer:
            if key.startswith("avg_") or "median" in key:
                facts.append(f"peer_stats.{key}={peer[key]}")
                evidence[f"peer_stats.{key}"] = f"CategoryContext.peer_stats.{key}"

        facts.append(f"trigger.kind={t.kind}")
        evidence["trigger.kind"] = "TriggerContext.kind"
        payload = t.payload or {}
        for key, value in payload.items():
            if isinstance(value, (str, int, float, bool)):
                facts.append(f"trigger.payload.{key}={value}")
                evidence[f"trigger.payload.{key}"] = f"TriggerContext.payload.{key}"

        # Resolve the canonical digest item referenced by top_item_id.
        top = payload.get("top_item") if isinstance(payload, dict) else None
        top_id = payload.get("top_item_id") if isinstance(payload, dict) else None
        if top is None and top_id:
            top = next((x for x in c.digest if isinstance(x, dict) and x.get("id") == top_id), None)
        if t.kind in {"research_digest", "research_digest_release", "category_research_digest_release", "regulation_change", "category_trend_movement"} and isinstance(top, dict):
            for key in ("id", "title", "source", "trial_n", "patient_segment", "summary", "actionable", "kind", "date"):
                if key in top:
                    facts.append(f"digest.{key}={top[key]}")
                    evidence[f"digest.{key}"] = f"CategoryContext.digest[{top.get('id', top_id)}].{key}"

        if customer is not None:
            name = _get(customer.identity, "name")
            if name:
                facts.append(f"customer_name={name}")
                evidence["customer_name"] = "CustomerContext.identity.name"
            facts.append(f"customer_state={customer.state}")
            evidence["customer_state"] = "CustomerContext.state"
            for key in ("last_visit", "first_visit", "visits_total", "services_received", "lifetime_value"):
                v = _get(customer.relationship, key)
                if v is not None:
                    facts.append(f"customer.{key}={_fmt(v)}")
                    evidence[f"customer.{key}"] = f"CustomerContext.relationship.{key}"
            for key in ("preferred_slots", "channel"):
                v = _get(customer.preferences, key)
                if v is not None:
                    facts.append(f"customer.preference.{key}={_fmt(v)}")
                    evidence[f"customer.preference.{key}"] = f"CustomerContext.preferences.{key}"
            consent_scope = _get(customer.consent, "scope")
            if consent_scope is not None:
                facts.append(f"customer.consent_scope={_fmt(consent_scope)}")
                evidence["customer.consent_scope"] = "CustomerContext.consent.scope"

        return RetrievedFacts(facts=facts, evidence=evidence)
