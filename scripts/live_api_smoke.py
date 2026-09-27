from __future__ import annotations

"""Smoke-test the real local HTTP server against the expanded challenge dataset.

Run the API first in another VS Code terminal:
    python run_server.py
Then run:
    python scripts/live_api_smoke.py
"""

import json
from pathlib import Path
import sys
import os
import httpx

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset"
BASE_URL = os.getenv("VERA_BASE_URL", "http://127.0.0.1:8080")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def post_context(client: httpx.Client, scope: str, context_id: str, payload: dict) -> None:
    response = client.post(
        "/v1/context",
        json={
            "scope": scope,
            "context_id": context_id,
            "version": 1,
            "delivered_at": "2026-04-26T09:45:00Z",
            "payload": payload,
        },
    )
    if response.status_code != 200:
        raise RuntimeError(f"context push failed: {scope}/{context_id}: {response.status_code} {response.text}")


def main() -> int:
    with httpx.Client(base_url=BASE_URL, timeout=10.0) as client:
        health = client.get("/v1/healthz")
        health.raise_for_status()
        print("INITIAL HEALTH:", health.json())

        for path in sorted((DATASET / "categories").glob("*.json")):
            payload = load(path)
            post_context(client, "category", payload["slug"], payload)

        for path in sorted((DATASET / "merchants").glob("*.json")):
            payload = load(path)
            post_context(client, "merchant", payload["merchant_id"], payload)

        for path in sorted((DATASET / "customers").glob("*.json")):
            payload = load(path)
            post_context(client, "customer", payload["customer_id"], payload)

        health = client.get("/v1/healthz")
        health.raise_for_status()
        print("AFTER WARMUP:", health.json())
        counts = health.json()["contexts_loaded"]
        expected = {"category": 5, "merchant": 50, "customer": 200, "trigger": 0}
        assert counts == expected, f"unexpected warmup counts: {counts}"

        trigger_path = DATASET / "triggers" / "trg_001_research_digest_dentists.json"
        trigger = load(trigger_path)
        post_context(client, "trigger", trigger["id"], trigger)

        tick = client.post(
            "/v1/tick",
            json={"now": "2026-04-26T10:35:00Z", "available_triggers": [trigger["id"]]},
        )
        tick.raise_for_status()
        tick_data = tick.json()
        print("TICK:", json.dumps(tick_data, ensure_ascii=False, indent=2))
        assert len(tick_data["actions"]) == 1

        action = tick_data["actions"][0]
        conv_id = action["conversation_id"]

        reply = client.post(
            "/v1/reply",
            json={
                "conversation_id": conv_id,
                "merchant_id": trigger["merchant_id"],
                "from_role": "merchant",
                "message": "Thank you for contacting Dr. Meera's Dental Clinic! Our team will respond shortly.",
                "received_at": "2026-04-26T10:42:00Z",
                "turn_number": 2,
            },
        )
        reply.raise_for_status()
        print("AUTO-REPLY:", reply.json())
        assert reply.json()["action"] == "wait"

        print("Live API smoke test passed.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
