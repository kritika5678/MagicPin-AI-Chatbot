from bot import compose
from detection.auto_reply_detector import AutoReplyDetector
from detection.intent_detector import IntentDetector
from models.conversation import ConversationState
from conversation_handlers import respond


def base_contexts():
    category = {
        "slug": "dentists",
        "offer_catalog": ["Dental Cleaning @ ₹299"],
        "voice": {"tone": "peer/clinical"},
        "peer_stats": {"avg_ctr": 0.03},
        "digest": [], "patient_content_library": [], "seasonal_beats": [], "trend_signals": []
    }
    merchant = {
        "merchant_id": "m_001",
        "identity": {"name": "Dr. Meera's Dental Clinic", "city": "Delhi", "locality": "Lajpat Nagar", "language_pref": "hi-en"},
        "subscription": {"status": "active"},
        "performance": {"ctr": 0.021},
        "offers": ["Dental Cleaning @ ₹299"],
        "conversation_history": [],
        "customer_aggregate": {}, "signals": []
    }
    trigger = {
        "id": "t1", "scope": "merchant", "kind": "research_digest", "source": "external",
        "payload": {"merchant_id": "m_001", "top_item": {"title": "New digest item", "source": "Source A", "trial_n": 2100}},
        "urgency": 2, "suppression_key": "research:dentists:2026-W1", "expires_at": "2026-10-01T00:00:00Z"
    }
    return category, merchant, trigger


def test_compose_has_required_keys():
    category, merchant, trigger = base_contexts()
    out = compose(category, merchant, trigger)
    assert set(out) == {"body", "cta", "send_as", "suppression_key", "rationale"}
    assert out["send_as"] == "vera"


def test_explicit_join_intent_routes_to_action():
    category, merchant, trigger = base_contexts()
    merchant["conversation_history"] = [{"role": "merchant", "message": "Mujhe magicpin join karna hai"}]
    out = compose(category, merchant, trigger)
    assert "action" in out["rationale"].lower()
    assert out["cta"] == "yes_stop"


def test_auto_reply_detector():
    d = AutoReplyDetector()
    r = d.detect("Thank you for contacting us. Our team will get back to you.", [])
    assert r.is_auto_reply
    assert r.should_retry_once


def test_repeated_auto_reply():
    d = AutoReplyDetector()
    msg = "Thank you for contacting us. Our team will get back to you."
    r = d.detect(msg, [msg, msg])
    assert r.is_auto_reply
    assert not r.should_retry_once


def test_intent_join():
    r = IntentDetector().classify("I want to join magicpin")
    assert r.intent == "join"
    assert r.confidence > 0.9


def test_not_interested_exit():
    state = ConversationState(merchant_id="m_001")
    out = respond(state, "Not interested")
    assert out["mode"] == "EXIT"


def test_customer_send_as():
    category, merchant, trigger = base_contexts()
    customer = {
        "customer_id": "c_001", "merchant_id": "m_001",
        "identity": {"name": "Priya", "language_pref": "hi-en"},
        "relationship": {"last_visit": "2026-05-12", "visits_total": 4},
        "state": "lapsed_soft",
        "preferences": {"preferred_time": "weekday evening"},
        "consent": {"scope": ["recall_reminders"]}
    }
    trigger["scope"] = "customer"
    trigger["kind"] = "recall_due"
    trigger["payload"] = {"merchant_id": "m_001", "customer_id": "c_001"}
    out = compose(category, merchant, trigger, customer)
    assert out["send_as"] == "merchant_on_behalf"
