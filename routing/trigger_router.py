from __future__ import annotations

CUSTOMER_TRIGGERS = {
    "customer_lapsed_soft",
    "customer_lapsed_hard",
    "recall_due",
    "appointment_tomorrow",
    "chronic_refill_due",
    "trial_followup",
    "wedding_package_followup",
    "winback_glamour",
}


class TriggerRouter:
    def scope(self, trigger_kind: str, trigger_scope: str) -> str:
        if trigger_scope in {"merchant", "customer"}:
            return trigger_scope
        return "customer" if trigger_kind in CUSTOMER_TRIGGERS else "merchant"

    def objective_hint(self, trigger_kind: str) -> str:
        k = trigger_kind.lower()
        if k in {
            "research_digest",
            "research_digest_release",
            "category_research_digest_release",
            "regulation_change",
            "cde_opportunity",
            "supply_alert",
        }:
            return "INFORM"
        if k in {
            "customer_lapsed_soft",
            "customer_lapsed_hard",
            "recall_due",
            "appointment_tomorrow",
            "chronic_refill_due",
            "trial_followup",
            "wedding_package_followup",
            "winback_glamour",
        }:
            return "RECALL"
        if k in {"active_planning_intent", "gbp_unverified", "winback_eligible"}:
            return "ACTION"
        if k == "seasonal_perf_dip":
            return "ENGAGE"
        return "ENGAGE"
