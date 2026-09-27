import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = "https://magicpin-ai-chatbot.onrender.com"

CATEGORY_FILE = Path("dataset/categories/dentists.json")
MERCHANT_FILE = Path("dataset/merchants/m_001_drmeera_dentist_delhi.json")
CUSTOMER_FILE = Path("dataset/customers/c_001_priya_for_m001.json")
TRIGGER_FILE = Path("dataset/triggers/trg_003_recall_due_priya.json")

# The trigger JSON does not expose trigger_id directly,
# so use the official dataset trigger ID from its filename.
TRIGGER_ID = "trg_003_recall_due_priya"


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def request_json(method: str, path: str, body=None):
    url = BASE + path

    data = None
    headers = {}

    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = Request(
        url,
        data=data,
        method=method,
        headers=headers,
    )

    try:
        with urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = raw

            return response.status, payload

    except HTTPError as e:
        raw = e.read().decode("utf-8")

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = raw

        return e.code, payload

    except URLError as e:
        print(f"NETWORK ERROR: {e}")
        return None, None


def check(name: str, method: str, path: str, body=None):
    print(f"\n--- {name} ---")

    status, payload = request_json(method, path, body)

    print(f"HTTP: {status}")
    print(payload)

    if status != 200:
        print(f"[FAIL] {name}")
        return False

    print(f"[PASS] {name}")
    return True


def main():
    category = load_json(CATEGORY_FILE)
    merchant = load_json(MERCHANT_FILE)
    customer = load_json(CUSTOMER_FILE)
    trigger = load_json(TRIGGER_FILE)

    merchant_id = merchant["merchant_id"]
    customer_id = customer["customer_id"]

    delivered = "2026-09-27T09:00:00Z"

    results = []

    # ============================================================
    # 1. HEALTH
    # ============================================================

    results.append(
        check(
            "HEALTH",
            "GET",
            "/v1/healthz",
        )
    )

    # ============================================================
    # 2. METADATA
    # ============================================================

    results.append(
        check(
            "METADATA",
            "GET",
            "/v1/metadata",
        )
    )

    # ============================================================
    # 3. CATEGORY CONTEXT
    # ============================================================

    results.append(
        check(
            "CONTEXT: CATEGORY",
            "POST",
            "/v1/context",
            {
                "scope": "category",
                "context_id": "dentists",
                "version": 1,
                "payload": category,
                "delivered_at": delivered,
            },
        )
    )

    # ============================================================
    # 4. MERCHANT CONTEXT
    # ============================================================

    results.append(
        check(
            "CONTEXT: MERCHANT",
            "POST",
            "/v1/context",
            {
                "scope": "merchant",
                "context_id": merchant_id,
                "version": 1,
                "payload": merchant,
                "delivered_at": delivered,
            },
        )
    )

    # ============================================================
    # 5. CUSTOMER CONTEXT
    # ============================================================

    results.append(
        check(
            "CONTEXT: CUSTOMER",
            "POST",
            "/v1/context",
            {
                "scope": "customer",
                "context_id": customer_id,
                "version": 1,
                "payload": customer,
                "delivered_at": delivered,
            },
        )
    )

    # ============================================================
    # 6. TRIGGER CONTEXT
    # ============================================================

    results.append(
        check(
            "CONTEXT: TRIGGER",
            "POST",
            "/v1/context",
            {
                "scope": "trigger",
                "context_id": TRIGGER_ID,
                "version": 1,
                "payload": trigger,
                "delivered_at": delivered,
            },
        )
    )

    # ============================================================
    # 7. TICK
    # ============================================================

    results.append(
        check(
            "TICK",
            "POST",
            "/v1/tick",
            {
                "now": "2026-09-27T09:01:00Z",
                "available_triggers": [TRIGGER_ID],
            },
        )
    )

    # ============================================================
    # 8. REPLY
    # ============================================================

    results.append(
        check(
            "REPLY: INTENT TRANSITION",
            "POST",
            "/v1/reply",
            {
                "conversation_id": "public_test_conversation_001",
                "merchant_id": merchant_id,
                "customer_id": None,
                "from_role": "merchant",
                "message": "Ok lets do it. Whats next?",
                "received_at": "2026-09-27T09:01:30Z",
                "turn_number": 2,
            },
        )
    )

    # ============================================================
    # FINAL SUMMARY
    # ============================================================

    print("\n" + "=" * 60)

    passed = sum(results)
    total = len(results)

    print(f"PUBLIC API TEST: {passed}/{total} PASSED")

    if passed == total:
        print("ALL PUBLIC ENDPOINT TESTS PASSED")
        print(f"PUBLIC BOT URL: {BASE}")
        print("=" * 60)
        return 0

    print("SOME PUBLIC ENDPOINT TESTS FAILED")
    print("=" * 60)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())