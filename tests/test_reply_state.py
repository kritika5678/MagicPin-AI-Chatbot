from fastapi.testclient import TestClient
from api_server import app

client = TestClient(app)


def test_repeated_auto_reply_same_conversation_backs_off_then_ends():
    conv = "test_auto_reply_same_conversation"
    msg = "Thank you for contacting us. Our team will get back to you."

    r1 = client.post("/v1/reply", json={
        "conversation_id": conv, "merchant_id": "m_auto", "from_role": "merchant",
        "message": msg, "received_at": "2026-04-26T10:42:00Z", "turn_number": 2,
    })
    assert r1.status_code == 200
    assert r1.json()["action"] == "wait"

    r2 = client.post("/v1/reply", json={
        "conversation_id": conv, "merchant_id": "m_auto", "from_role": "merchant",
        "message": msg, "received_at": "2026-04-26T10:43:00Z", "turn_number": 3,
    })
    assert r2.status_code == 200
    assert r2.json()["action"] == "wait"
    assert r2.json()["wait_seconds"] == 86400

    r3 = client.post("/v1/reply", json={
        "conversation_id": conv, "merchant_id": "m_auto", "from_role": "merchant",
        "message": msg, "received_at": "2026-04-27T10:43:00Z", "turn_number": 4,
    })
    assert r3.status_code == 200
    assert r3.json()["action"] == "end"


def test_intent_transition_moves_directly_to_action_mode():
    conv = "test_intent_transition"
    r = client.post("/v1/reply", json={
        "conversation_id": conv, "merchant_id": "m_intent", "from_role": "merchant",
        "message": "ok let's do it", "received_at": "2026-04-26T10:42:00Z", "turn_number": 2,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["action"] == "send"
    assert data["cta"] == "binary_yes_no"


def test_stop_ends_conversation():
    conv = "test_stop"
    r = client.post("/v1/reply", json={
        "conversation_id": conv, "merchant_id": "m_stop", "from_role": "merchant",
        "message": "STOP", "received_at": "2026-04-26T10:42:00Z", "turn_number": 2,
    })
    assert r.status_code == 200
    assert r.json()["action"] == "end"
