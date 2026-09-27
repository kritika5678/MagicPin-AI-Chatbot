from fastapi.testclient import TestClient
from api_server import app


def test_equal_version_is_idempotent_and_lower_version_is_stale():
    client = TestClient(app)
    payload = {"slug": "version-test"}

    r1 = client.post("/v1/context", json={
        "scope": "category", "context_id": "version_test_category",
        "version": 1, "payload": payload,
    })
    assert r1.status_code == 200
    assert r1.json()["accepted"] is True

    r1_again = client.post("/v1/context", json={
        "scope": "category", "context_id": "version_test_category",
        "version": 1, "payload": payload,
    })
    assert r1_again.status_code == 200
    assert r1_again.json()["accepted"] is True

    r2 = client.post("/v1/context", json={
        "scope": "category", "context_id": "version_test_category",
        "version": 2, "payload": {**payload, "version": 2},
    })
    assert r2.status_code == 200

    r2_again = client.post("/v1/context", json={
        "scope": "category", "context_id": "version_test_category",
        "version": 2, "payload": {**payload, "version": 2},
    })
    assert r2_again.status_code == 200
    assert r2_again.json()["accepted"] is True

    r1_after_v2 = client.post("/v1/context", json={
        "scope": "category", "context_id": "version_test_category",
        "version": 1, "payload": payload,
    })
    assert r1_after_v2.status_code == 409
    assert r1_after_v2.json()["reason"] == "stale_version"
    assert r1_after_v2.json()["current_version"] == 2
