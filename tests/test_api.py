from fastapi.testclient import TestClient
from api_server import app, store
import json

client = TestClient(app)


def _push(scope, context_id, payload, version=1):
    r = client.post("/v1/context", json={"scope": scope, "context_id": context_id, "version": version, "delivered_at": "2026-04-26T09:45:00Z", "payload": payload})
    assert r.status_code == 200


def test_healthz_initial_shape():
    r = client.get("/v1/healthz")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "contexts_loaded" in data


def test_context_versioning_and_tick():
    category = json.loads(open("dataset/categories/dentists.json", encoding="utf-8").read())
    merchant = json.loads(open("dataset/merchants/m_001_drmeera_dentist_delhi.json", encoding="utf-8").read())
    trigger = json.loads(open("dataset/triggers/trg_001_research_digest_dentists.json", encoding="utf-8").read())
    _push("category", "dentists_test", {**category, "slug": "dentists_test"})
    _push("merchant", merchant["merchant_id"], merchant)
    trigger["merchant_id"] = merchant["merchant_id"]
    _push("trigger", trigger["id"], trigger)
    # Use the real category id because compose resolves from merchant.category_slug.
    _push("category", "dentists", category)
    # Same-version replay must be idempotent: accepted as a no-op.
    r_same = client.post("/v1/context", json={"scope":"merchant","context_id":merchant["merchant_id"],"version":1,"payload":merchant})
    assert r_same.status_code == 200
    assert r_same.json()["accepted"] is True
    tick = client.post("/v1/tick", json={"now":"2026-04-26T10:35:00Z","available_triggers":[trigger["id"]]})
    assert tick.status_code == 200
    assert "actions" in tick.json()
