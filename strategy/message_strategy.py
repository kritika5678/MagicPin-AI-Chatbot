from __future__ import annotations

from models import FullContext, MessageStrategy
from routing.trigger_router import TriggerRouter
from detection.language_detector import LanguageDetector


class MessageStrategyEngine:
    """Deterministic planner: decides what the message should accomplish before generation."""

    def __init__(self):
        self.trigger_router = TriggerRouter()
        self.language_detector = LanguageDetector()

    def build(
        self,
        ctx: FullContext,
        last_user_message: str | None,
        requires_template: bool,
    ) -> MessageStrategy:
        scope = self.trigger_router.scope(ctx.trigger.kind, ctx.trigger.scope)
        objective = self.trigger_router.objective_hint(ctx.trigger.kind)

        language_context = ctx.customer if scope == "customer" and ctx.customer else ctx.merchant
        preferred = None
        if language_context is not None:
            identity = language_context.identity if isinstance(language_context.identity, dict) else {}
            preferred = identity.get("language_pref")
            if preferred is None and isinstance(identity.get("languages"), list):
                langs = identity["languages"]
                preferred = "hi-en mix" if "hi" in langs and "en" in langs else ("english" if "en" in langs else None)

        language = self.language_detector.detect(
            last_user_message or "",
            preferred=preferred,
        )
        if language == "unknown":
            language = "english"

        voice = ctx.category.voice if isinstance(ctx.category.voice, dict) else {}
        tone = str(voice.get("tone", "peer"))
        send_as = "merchant_on_behalf" if scope == "customer" else "vera"

        lever_by_trigger = {
            "research_digest": "reciprocity",
            "cde_opportunity": "specificity",
            "regulation_change": "specificity",
            "category_seasonal": "specificity",
            "festival_upcoming": "specificity",
            "ipl_match_today": "loss_aversion",
            "perf_dip": "loss_aversion",
            "seasonal_perf_dip": "reframe",
            "perf_spike": "social_proof",
            "milestone_reached": "social_proof",
            "competitor_opened": "curiosity",
            "curious_ask_due": "direct_question",
            "active_planning_intent": "effort_externalization",
            "gbp_unverified": "effort_externalization",
            "dormant_with_vera": "reciprocity",
            "winback_eligible": "loss_aversion",
            "renewal_due": "loss_aversion",
            "customer_lapsed_hard": "barrier_removal",
            "customer_lapsed_soft": "reciprocity",
            "recall_due": "specificity",
            "chronic_refill_due": "specificity",
            "appointment_tomorrow": "specificity",
            "trial_followup": "effort_externalization",
            "wedding_package_followup": "specificity",
        }
        lever = lever_by_trigger.get(ctx.trigger.kind, "specificity")

        if objective == "EXIT":
            cta = "none"
        elif objective == "ACTION" and ctx.trigger.kind not in {"active_planning_intent", "gbp_unverified", "winback_eligible"}:
            cta = "yes_stop"
        else:
            cta = "open_ended"

        return MessageStrategy(
            objective=objective,
            engagement_lever=lever,
            tone=tone,
            language=language,
            cta=cta,
            send_as=send_as,
            urgency=ctx.trigger.urgency,
            requires_template=requires_template,
        )
