from __future__ import annotations
import glob
import json
from fastapi.testclient import TestClient
from api_server import app


def main() -> None:
    client = TestClient(app)
    for slug in ["dentists", "salons", "restaurants", "gyms", "pharmacies"]:
        payload = json.load(open(f"dataset/categories/{slug}.json", encoding="utf-8"))
        assert client.post("/v1/context", json={"scope":"category","context_id":slug,"version":1,"payload":payload}).status_code == 200
    for path in glob.glob("dataset/merchants/*.json"):
        payload = json.load(open(path, encoding="utf-8"))
        assert client.post("/v1/context", json={"scope":"merchant","context_id":payload["merchant_id"],"version":1,"payload":payload}).status_code == 200
    for path in glob.glob("dataset/customers/*.json"):
        payload = json.load(open(path, encoding="utf-8"))
        assert client.post("/v1/context", json={"scope":"customer","context_id":payload["customer_id"],"version":1,"payload":payload}).status_code == 200
    health = client.get("/v1/healthz").json()
    assert health["contexts_loaded"] == {"category":5,"merchant":50,"customer":200,"trigger":0}, health
    trigger = json.load(open("dataset/triggers/trg_001_research_digest_dentists.json", encoding="utf-8"))
    assert client.post("/v1/context", json={"scope":"trigger","context_id":trigger["id"],"version":1,"payload":trigger}).status_code == 200
    tick = client.post("/v1/tick", json={"now":"2026-04-26T10:35:00Z","available_triggers":[trigger["id"]]})
    assert tick.status_code == 200 and len(tick.json()["actions"]) == 1
    conv = tick.json()["actions"][0]["conversation_id"]
    msg = "Thank you for contacting Dr. Meera's Dental Clinic! Our team will respond shortly."
    for turn in [2,3,4]:
        r = client.post("/v1/reply", json={"conversation_id":conv,"merchant_id":trigger["merchant_id"],"from_role":"merchant","message":msg,"received_at":"2026-04-26T10:42:00Z","turn_number":turn})
        assert r.status_code == 200
    print("API smoke test passed")


if __name__ == "__main__":
    main()
