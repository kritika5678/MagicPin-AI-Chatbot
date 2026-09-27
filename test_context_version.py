from __future__ import annotations

import json
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE = os.getenv("VERA_BASE_URL", "http://127.0.0.1:8080")
CID = "context_version_test_category"
PAYLOAD = {"slug": "version-test"}


def post(version: int) -> tuple[int, dict]:
    data = json.dumps({
        "scope": "category",
        "context_id": CID,
        "version": version,
        "payload": PAYLOAD,
    }).encode("utf-8")
    req = Request(f"{BASE}/v1/context", data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))


def main() -> None:
    checks = [
        (1, 200, True),
        (1, 200, True),
        (2, 200, True),
        (2, 200, True),
        (1, 409, False),
    ]
    labels = ["VERSION 1", "VERSION 1 AGAIN", "VERSION 2", "VERSION 2 AGAIN", "VERSION 1 AFTER VERSION 2"]
    for label, (version, expected_status, expected_accepted) in zip(labels, checks):
        status, body = post(version)
        print(f"--- {label} ---")
        print(f"HTTP: {status}")
        print(json.dumps(body, ensure_ascii=False))
        assert status == expected_status, (label, status, body)
        assert body.get("accepted") is expected_accepted, (label, body)
    print("Context versioning test passed: 200, 200, 200, 200, 409")


if __name__ == "__main__":
    main()
