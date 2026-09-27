from __future__ import annotations

import json
import re
from typing import Any

from models import FullContext, MessageStrategy, RetrievedFacts, ComposedMessage
from .client import LLMClient
from .parser import LLMOutputParser
from session.suppression import generate_suppression_key


SYSTEM_PROMPT = """You are Vera, a merchant AI assistant for Indian local businesses.

Write exactly one concise WhatsApp message for the supplied recipient.

NON-NEGOTIABLE RULES
1. Use only facts present in VERIFIED_FACTS, CATEGORY_CONTEXT, MERCHANT_CONTEXT,
   CUSTOMER_CONTEXT, and TRIGGER_CONTEXT.
2. Never invent a number, date, price, offer, competitor, study, source, slot,
   capability, or outcome.
3. Make the trigger explicit: the reader should understand why this message is being
   sent now.
4. Personalize using merchant/customer facts when available.
5. Match the category voice, terminology, and taboo vocabulary.
6. Match the recipient's language preference. Hindi-English code-mix is allowed when
   the context indicates it.
7. Prefer one strong concrete fact over several weak generic claims.
8. For research/compliance content, retain the supplied source when available.
9. Do not use generic promotional copy such as "boost sales" when a concrete fact exists.
10. Do not re-introduce yourself after conversation has started.
11. Keep one primary CTA. Do not stack unrelated requests.
12. Customer-facing messages must be written as the merchant, not as Vera.
13. Never claim an action was completed unless the input explicitly says it was completed.
14. Return JSON only with keys: body, cta, send_as, suppression_key, rationale.
"""


ACTION_VERBS = {
    "create",
    "draft",
    "update",
    "start",
    "join",
    "schedule",
    "confirm",
    "send",
    "publish",
}


def _dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _first_active_offer(merchant: Any) -> str | None:
    data = merchant if isinstance(merchant, dict) else getattr(merchant, "__dict__", {})
    for offer in _list(data.get("offers")):
        if isinstance(offer, dict) and offer.get("status") in {None, "active"} and offer.get("title"):
            return str(offer["title"])
    return None


def _all_active_offers(merchant: Any) -> list[str]:
    data = merchant if isinstance(merchant, dict) else getattr(merchant, "__dict__", {})
    out: list[str] = []
    for offer in _list(data.get("offers")):
        if isinstance(offer, dict) and offer.get("status") in {None, "active"} and offer.get("title"):
            out.append(str(offer["title"]))
    return out


def _merchant_identity(ctx: FullContext) -> tuple[str, str, str, str]:
    identity = _dict(ctx.merchant.identity)
    name = str(identity.get("name") or "your business")
    owner = str(identity.get("owner_first_name") or name)
    city = str(identity.get("city") or "")
    locality = str(identity.get("locality") or "")
    return name, owner, locality, city


def _language_is_hinglish(strategy: MessageStrategy) -> bool:
    return strategy.language == "hi-en"


def _digest_item(ctx: FullContext, item_id: str | None = None) -> dict | None:
    digest = _list(ctx.category.digest)
    if item_id:
        for item in digest:
            if isinstance(item, dict) and item.get("id") == item_id:
                return item
    return digest[0] if digest and isinstance(digest[0], dict) else None


def _find_digest(ctx: FullContext, *terms: str) -> dict | None:
    for item in _list(ctx.category.digest):
        if not isinstance(item, dict):
            continue
        blob = " ".join(str(item.get(k, "")) for k in ("id", "title", "summary", "actionable", "source")).lower()
        if any(term.lower() in blob for term in terms):
            return item
    return None


def _pct(value: Any) -> str | None:
    if isinstance(value, (int, float)):
        return f"{abs(value) * 100:.0f}%"
    return None


def _customer_name(ctx: FullContext) -> str:
    identity = _dict(ctx.customer.identity) if ctx.customer else {}
    return str(identity.get("name") or "there")


def _preferred_customer_slots(ctx: FullContext) -> str | None:
    prefs = _dict(ctx.customer.preferences) if ctx.customer else {}
    value = prefs.get("preferred_slots") or prefs.get("preferred_time")
    return str(value) if value else None


def _has_consent(ctx: FullContext, required_scope: str) -> bool:
    if not ctx.customer:
        return True
    consent = _dict(ctx.customer.consent)
    scope = consent.get("scope")
    if not isinstance(scope, list):
        return False
    return required_scope in scope


def _appointment_line(ctx: FullContext, lang: str) -> str:
    customer = _customer_name(ctx)
    merchant, _, _, _ = _merchant_identity(ctx)
    if lang == "hindi":
        return f"Namaste {customer}, {merchant} se kal aapki appointment hai. Time confirm karna ho to yahin reply karein."
    if _language_is_hinglish_strategy(lang):
        return f"Hi {customer}, {merchant} here. Kal aapki appointment hai — time confirm karna ho to yahin reply karein."
    return f"Hi {customer}, {merchant} here. You have an appointment tomorrow. Reply here to confirm the time or tell us if anything has changed."


def _language_is_hinglish_strategy(lang: str) -> bool:
    return lang == "hi-en"


def _format_medicine_list(values: list[Any]) -> str:
    cleaned = [str(v).replace("...", "").strip() for v in values if str(v).strip() and str(v).strip() != "..."]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"
    return ", ".join(cleaned[:-1]) + f", and {cleaned[-1]}"


def _safe_customer_body(ctx: FullContext, strategy: MessageStrategy) -> tuple[str, str]:
    """Customer-facing composition from verified context only."""
    t = ctx.trigger
    kind = t.kind
    payload = t.payload or {}
    merchant, owner, locality, city = _merchant_identity(ctx)
    cname = _customer_name(ctx)
    offer = _first_active_offer(ctx.merchant)
    lang = strategy.language

    if not _has_consent(ctx, "recall_reminders") and kind == "recall_due":
        return (
            f"Hi {cname}, {merchant} here. We have a follow-up reminder for you. Reply here if you want the details.",
            "open_ended",
        )

    if kind == "recall_due":
        service_due = str(payload.get("service_due") or "").lower()
        last_visit = _dict(ctx.customer.relationship).get("last_visit") if ctx.customer else None
        slots = [s.get("label") for s in _list(payload.get("available_slots")) if isinstance(s, dict) and s.get("label")]
        slot_text = " or ".join(slots[:2])
        if "6_month" in service_due or "6 month" in service_due:
            recall = "6-month cleaning recall"
        else:
            recall = "recall reminder"

        if lang == "hi-en":
            body = f"Hi {cname}, {merchant} here 🦷 {recall} due hai"
            if last_visit:
                body += f" — last visit {last_visit} tha."
            else:
                body += "."
            if slot_text:
                body += f" Aapke liye {slot_text} available hain."
            if offer:
                body += f" {offer}."
            body += " Kaunsa slot convenient rahega?"
            return body, "open_ended"

        body = f"Hi {cname}, {merchant} here. Your {recall} is due."
        if last_visit:
            body += f" Your last visit was {last_visit}."
        if slot_text:
            body += f" Available slots: {slot_text}."
        if offer:
            body += f" {offer}."
        body += " Reply with the slot that works for you."
        return body, "open_ended"

    if kind == "chronic_refill_due":
        molecules = _format_medicine_list(payload.get("molecule_list", []))
        runout = payload.get("stock_runs_out_iso")
        saved = payload.get("delivery_address_saved") is True
        pref = _preferred_customer_slots(ctx)
        hi = lang in {"hi", "hi-en"}
        prefix = "Namaste" if hi else "Hi"
        body = f"{prefix} {cname}, {merchant} here."
        if molecules:
            body += f" Your refill covers {molecules}."
        if runout:
            body += f" Current stock is due to run out on {str(runout)[:10]}"
        else:
            body += " Your refill is due"
        body += "."
        if saved:
            body += " Delivery address is already saved."
        if pref:
            body += f" Preferred timing: {pref.replace('_', ' ')}."
        if offer:
            body += f" {offer}."
        body += " Reply CONFIRM to proceed or reply here with any change."
        return body, "open_ended"

    if kind in {"customer_lapsed_hard", "customer_lapsed_soft", "winback_glamour"}:
        days = payload.get("days_since_last_visit")
        focus = payload.get("previous_focus") or _dict(ctx.customer.preferences).get("training_focus") if ctx.customer else None
        body = f"Hi {cname}, {merchant} here."
        if days is not None:
            body += f" It's been {days} days since your last visit"
        else:
            last_visit = _dict(ctx.customer.relationship).get("last_visit") if ctx.customer else None
            if last_visit:
                body += f" It's been a while since your last visit on {last_visit}"
        if kind == "customer_lapsed_hard":
            body += " — no pressure, just a quick way back in."
        else:
            body += "."
        if focus:
            body += f" I remember your focus was {str(focus).replace('_', ' ')}."
        if offer:
            body += f" {offer} is currently active."
        body += " Want me to help you pick a simple next step?"
        return body, "open_ended"

    if kind == "appointment_tomorrow":
        return _appointment_line(ctx, lang), "open_ended"

    if kind == "trial_followup":
        last = _dict(ctx.customer.relationship).get("last_visit") if ctx.customer else None
        body = f"Hi {cname}, {merchant} here."
        if last:
            body += f" Following up on your trial/visit from {last}."
        else:
            body += " Following up on your recent trial."
        if offer:
            body += f" {offer} is active."
        body += " Want me to help with the next step?"
        return body, "open_ended"

    if kind == "wedding_package_followup":
        wedding = payload.get("wedding_date")
        days = payload.get("days_to_wedding")
        window = payload.get("next_step_window_open")
        body = f"Hi {cname}, {merchant} here 💍"
        if days is not None:
            body += f" You have {days} days to the wedding."
        elif wedding:
            body += f" Your wedding date is {wedding}."
        if window:
            body += f" Your {str(window).replace('_', ' ')} window is open."
        if offer:
            body += f" {offer} is currently active."
        body += " Want me to help with the next step?"
        return body, "open_ended"

    return (
        f"Hi {cname}, {merchant} here. I have a relevant update for you from this reminder. Reply here and I'll keep it to one concrete next step.",
        "open_ended",
    )


def _merchant_message(ctx: FullContext, strategy: MessageStrategy) -> str:
    m = ctx.merchant
    t = ctx.trigger
    payload = t.payload or {}
    category_slug = ctx.category.slug
    merchant, owner, locality, city = _merchant_identity(ctx)
    owner_greeting = owner if owner else merchant
    kind = t.kind
    active_offers = _all_active_offers(m.model_dump(mode="json"))
    first_offer = active_offers[0] if active_offers else None
    perf = _dict(m.performance)
    delta = _dict(perf.get("delta_7d"))
    agg = _dict(m.customer_aggregate)

    if kind == "research_digest":
        item = _digest_item(ctx, payload.get("top_item_id"))
        if item:
            title = str(item.get("title") or "New category research")
            source = item.get("source")
            trial_n = item.get("trial_n")
            summary = str(item.get("summary") or "")
            patient_segment = str(item.get("patient_segment") or "").replace("_", " ")
            body = f"{owner_greeting}, {source or 'a new category update'} just landed. {title}."
            if trial_n:
                body += f" {trial_n:,}-participant evidence"
            if patient_segment:
                body += f" is relevant to your {patient_segment} cohort"
            if summary:
                # Keep the first complete sentence without truncating decimal numbers such as 1.0 mSv.
                parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", summary.strip())
                claim = parts[0].strip() if parts else summary.strip()
                if claim:
                    body += f" — {claim}"
            body += " Worth a look? I can turn the useful point into a customer-facing draft."
            if source:
                body += f" — {source}"
            return body

    if kind == "cde_opportunity":
        item = _digest_item(ctx, payload.get("digest_item_id"))
        body = f"{owner_greeting}, I found a relevant professional learning item."
        if item:
            body += f" {item.get('title', 'The session')}"
            if item.get("date"):
                body += f" is on {str(item['date'])[:16].replace('T', ' ')}"
        if payload.get("credits") is not None:
            body += f" — {payload['credits']} credits"
        if payload.get("fee"):
            body += f", {str(payload['fee']).replace('_', ' ')}"
        body += ". Want the link/details?"
        return body

    if kind == "regulation_change":
        item = _digest_item(ctx, payload.get("top_item_id"))
        deadline = payload.get("deadline_iso")
        body = f"{owner_greeting}, a compliance update is relevant to your practice."
        if item:
            body += f" {item.get('title', '')}."
            if item.get("summary"):
                summary = str(item["summary"]).strip()
                parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", summary)
                claim = parts[0].strip() if parts else summary
                if claim:
                    body += f" {claim}"
        if deadline:
            body += f" Deadline: {deadline}."
        body += " Want me to turn the required change into a short audit checklist?"
        return body

    if kind == "supply_alert":
        manufacturer = payload.get("manufacturer")
        molecule = payload.get("molecule")
        batches = payload.get("affected_batches") or []
        batch_text = ", ".join(map(str, batches[:3]))
        body = f"{owner_greeting}, urgent supply alert:"
        if molecule:
            body += f" {molecule}"
        if batch_text:
            body += f" — affected batches {batch_text}"
        if manufacturer:
            body += f" from {manufacturer}"
        body += ". Check your stock against those batch IDs before the next dispense. Want me to format a customer-notification draft?"
        return body

    if kind == "category_seasonal":
        trends = [str(x).replace("_", " ") for x in _list(payload.get("trends"))]
        body = f"{owner_greeting}, summer demand is shifting the shelf mix."
        if trends:
            body += " " + "; ".join(trends[:4]) + "."
        if payload.get("shelf_action_recommended"):
            body += " I’d move the rising-demand items forward and review the slower category rather than push a blanket offer."
        body += " Want me to turn that into a simple shelf/action checklist?"
        return body

    if kind == "ipl_match_today":
        match = payload.get("match") or "today's match"
        venue = payload.get("venue")
        time = payload.get("match_time_iso")
        match_digest = _find_digest(ctx, "ipl", "match-night")
        pct = None
        if match_digest:
            match_pct = re.search(r"(?:down|drop(?:ped)?|-)\s*(\d+)%", str(match_digest.get("summary", "")), flags=re.I)
            if match_pct:
                pct = match_pct.group(1)
        body = f"Quick heads-up {owner}: {match}"
        if venue:
            body += f" is at {venue}"
        if time:
            body += f" at {str(time)[11:16]}"
        body += "."
        if pct:
            body += f" The category digest says Saturday IPL matches can shift covers down around {pct}% versus the Saturday baseline."
        if first_offer:
            body += f" Your active offer is {first_offer}, so I'd avoid inventing a new discount and use the existing offer in delivery-led messaging."
        body += " Want me to draft the match-day copy?"
        return body

    if kind == "active_planning_intent":
        topic = str(payload.get("intent_topic") or "the plan").replace("_", " ")
        last_message = str(payload.get("merchant_last_message") or "")
        body = f"{owner_greeting}, yes — let’s move straight into a draft for your {topic}."
        if first_offer:
            body += f" I’ll anchor it on your existing {first_offer} rather than invent a new price."
        elif last_message:
            body += " I’ll keep the first version to a practical outline using only what we already know."
        body += " Want me to draft the first version here?"
        return body

    if kind == "curious_ask_due":
        question = "what service has been getting the most customer interest this week?"
        template = payload.get("ask_template")
        if template == "what_service_in_demand_this_week":
            question = "what service has been getting the most customer interest this week?"
        body = f"Hi {owner}! Quick one — {question}"
        if active_offers:
            body += f" I’ll use your current {active_offers[0]} as context and turn the answer into a short customer-ready draft."
        else:
            body += " I’ll turn the answer into one short customer-ready draft."
        body += " What’s the one service you’re hearing about most?"
        return body

    if kind == "gbp_unverified":
        verified = payload.get("verified")
        path = str(payload.get("verification_path") or "the verification flow").replace("_", " ")
        uplift = _pct(payload.get("estimated_uplift_pct"))
        body = f"{owner_greeting}, your Google Business Profile is still unverified."
        if verified is False:
            body += f" The supplied context points to {path}"
        if uplift:
            body += f" and estimates up to {uplift} potential uplift"
        body += ". Want me to walk through the next verification step?"
        return body

    if kind == "renewal_due":
        days = payload.get("days_remaining") or _dict(m.subscription).get("days_remaining")
        plan = payload.get("plan") or _dict(m.subscription).get("plan")
        body = f"{owner_greeting}, your {plan or 'current'} plan"
        if days is not None:
            body += f" has {days} days left"
        body += "."
        amount = payload.get("renewal_amount")
        if amount is not None:
            body += f" Renewal amount in the trigger is ₹{amount:,}."
        body += " Want me to take you through the renewal step?"
        return body

    if kind == "milestone_reached":
        metric = payload.get("metric")
        value_now = payload.get("value_now")
        milestone = payload.get("milestone_value")
        if metric and value_now is not None and milestone is not None:
            unit = "reviews" if "review" in str(metric) else str(metric).replace("_", " ")
            gap = max(int(milestone) - int(value_now), 0)
            body = f"{owner_greeting}, you’re at {value_now} {unit} now"
            if gap:
                body += f" — {gap} to the {milestone} milestone."
            else:
                body += f" — you’ve reached {milestone}."
            body += " Want me to suggest one easy way to turn the milestone into fresh profile content?"
            return body
        body = f"{owner_greeting}, you just hit a milestone on the account. Want me to turn it into a small customer-facing/profile moment?"
        return body

    if kind == "perf_dip":
        metric = payload.get("metric")
        delta_pct = payload.get("delta_pct")
        baseline = payload.get("vs_baseline")
        body = f"{owner_greeting}, the current performance alert is on"
        if metric:
            body += f" {metric}"
        if isinstance(delta_pct, (int, float)):
            body += f" — down {_pct(delta_pct)}"
        if baseline is not None:
            body += f" against a baseline of {baseline}"
        body += "."
        if not delta_pct:
            neg = [(k, v) for k, v in delta.items() if isinstance(v, (int, float)) and v < 0]
            if neg:
                key, val = min(neg, key=lambda x: x[1])
                body += f" The merchant snapshot also shows {key.replace('_pct','')} at {_pct(val)}."
        if "unverified_gbp" in [str(s) for s in _list(m.signals)]:
            body += " Your profile is also unverified, so that is one concrete thing worth checking."
        body += " Want me to break the alert into the most likely next check?"
        return body

    if kind == "seasonal_perf_dip":
        metric = payload.get("metric") or "performance"
        delta_pct = payload.get("delta_pct")
        note = str(payload.get("season_note") or "the current seasonal window").replace("_", " ")
        members = agg.get("total_active_members")
        body = f"{owner_greeting}, {metric} is down"
        if isinstance(delta_pct, (int, float)):
            body += f" {_pct(delta_pct)} this week"
        body += f", but the trigger flags this as an expected {note}."
        if members is not None:
            body += f" You still have {members} active members to focus on."
        body += " Want me to draft one retention-focused message instead of pushing acquisition spend into the dip?"
        return body

    if kind == "perf_spike":
        metric = payload.get("metric")
        delta_pct = payload.get("delta_pct")
        driver = payload.get("likely_driver")
        body = f"{owner_greeting}, {metric or 'one of your key metrics'} is moving up"
        if isinstance(delta_pct, (int, float)):
            body += f" {_pct(delta_pct)} over {payload.get('window', 'the latest window')}"
        if driver:
            body += f"; the trigger points to {str(driver).replace('_', ' ')} as the likely driver"
        elif "high_retention" in [str(s) for s in _list(m.signals)]:
            body += "; your current signals also show high retention"
        body += ". Want me to show how to turn that signal into another piece of content?"
        return body

    if kind == "competitor_opened":
        name = payload.get("competitor_name")
        distance = payload.get("distance_km")
        their_offer = payload.get("their_offer")
        body = f"{owner_greeting}, there’s a new local competitor signal"
        if name:
            body += f": {name}"
        if distance is not None:
            body += f" about {distance} km away"
        if their_offer:
            body += f", advertising {their_offer}"
        body += "."
        if first_offer:
            body += f" You already have {first_offer} active, so I’d sharpen the positioning before changing price."
        body += " Want me to suggest one response based on your current profile?"
        return body

    if kind == "dormant_with_vera":
        days = payload.get("days_since_last_merchant_message")
        last_topic = payload.get("last_topic")
        body = f"Hi {owner}!"
        if days is not None:
            body += f" It’s been {days} days since we last spoke"
        else:
            body += " We haven’t spoken recently"
        if last_topic:
            body += f"; last topic was {str(last_topic).replace('_', ' ')}"
        body += "."
        ctr = perf.get("ctr")
        peer = _dict(ctx.category.peer_stats).get("avg_ctr")
        if isinstance(ctr, (int, float)) and isinstance(peer, (int, float)) and ctr < peer:
            body += f" Your current CTR is {ctr * 100:.1f}% vs peer {peer * 100:.1f}%."
        elif first_offer:
            body += f" You still have {first_offer} active."
        body += " Want one concrete thing to work on today?"
        return body

    if kind == "winback_eligible":
        days = payload.get("days_since_expiry")
        lapsed = payload.get("lapsed_customers_added_since_expiry")
        body = f"{owner_greeting}, your win-back signal is active."
        if days is not None:
            body += f" The account has been expired for {days} days"
        if lapsed is not None:
            body += f" and {lapsed} lapsed customers have been added since then"
        body += "."
        body += " Want me to draft one win-back message using only your existing offers?"
        return body

    if kind == "festival_upcoming":
        festival = payload.get("festival") or "the upcoming festival"
        date = payload.get("date")
        days = payload.get("days_until")
        body = f"{owner_greeting}, {festival} is the next timely beat"
        if date:
            body += f" on {date}"
        if days is not None:
            body += f" ({days} days in the supplied trigger)"
        body += "."
        if first_offer:
            body += f" You already have {first_offer}, so I’d build the campaign around a concrete service/price rather than a blanket discount."
        else:
            body += " Want me to draft one category-specific campaign angle from your current context?"
        if first_offer:
            body += " Want me to draft the message around that existing offer?"
        return body

    if kind == "review_theme_emerged":
        themes = _list(m.model_dump(mode="json").get("review_themes"))
        top = themes[0] if themes and isinstance(themes[0], dict) else None
        body = f"{owner_greeting}, a review theme is emerging."
        if top and top.get("theme"):
            body += f" {top['theme'].replace('_', ' ')} appears in {top.get('occurrences_30d', 'multiple')} recent reviews."
            if top.get("common_quote"):
                body += f" One customer phrased it as: {top['common_quote']}"
        body += " Want me to turn the pattern into one practical profile/reply improvement?"
        return body

    # Safe generic fallback that still names the merchant, place, trigger, and a concrete signal.
    location = f" in {locality}, {city}" if locality and city else (f" in {city}" if city else "")
    body = f"{owner_greeting}, I’m reaching out about {kind.replace('_', ' ')}{location}."
    if first_offer:
        body += f" Your current offer is {first_offer}."
    body += " Want me to work from the specific trigger detail?"
    return body


class LocalDeterministicComposer:
    """High-quality no-API baseline. It remains fully deterministic."""

    def compose(self, ctx: FullContext, strategy: MessageStrategy, facts: RetrievedFacts) -> ComposedMessage:
        if strategy.send_as == "merchant_on_behalf" and ctx.customer:
            body, cta = _safe_customer_body(ctx, strategy)
        else:
            body = _merchant_message(ctx, strategy)
            cta = strategy.cta

        suppression = generate_suppression_key(
            ctx.trigger.suppression_key or ctx.trigger.kind,
            ctx.merchant.merchant_id,
            ctx.customer.customer_id if ctx.customer else None,
        )

        rationale = (
            f"{strategy.objective} for {ctx.trigger.kind}; "
            f"used {strategy.engagement_lever} with verified context and {strategy.language} language handling."
        )
        return ComposedMessage(
            body=body,
            cta=cta,
            send_as=strategy.send_as,
            suppression_key=suppression,
            rationale=rationale,
        )


class LLMComposer:
    def __init__(self, client: LLMClient):
        self.client = client
        self.parser = LLMOutputParser()

    def compose(self, ctx: FullContext, strategy: MessageStrategy, facts: RetrievedFacts) -> ComposedMessage:
        user_payload = {
            "TASK": "Compose one WhatsApp message.",
            "STRATEGY": strategy.model_dump(),
            "VERIFIED_FACTS": facts.facts,
            "EVIDENCE": facts.evidence,
            "TRIGGER": ctx.trigger.model_dump(mode="json"),
            "CATEGORY_VOICE": ctx.category.voice,
            "MERCHANT": ctx.merchant.model_dump(mode="json"),
            "CUSTOMER": ctx.customer.model_dump(mode="json") if ctx.customer else None,
            "ACTIVE_OFFERS": _all_active_offers(ctx.merchant.model_dump(mode="json")),
            "REQUIREMENT": "Do not invent missing values; keep the CTA as specified by STRATEGY.",
        }
        raw = self.client.generate(
            SYSTEM_PROMPT,
            json.dumps(user_payload, ensure_ascii=False, default=str),
        )
        return self.parser.parse(raw)
