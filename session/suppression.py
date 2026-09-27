from __future__ import annotations
import hashlib
import re


def generate_suppression_key(trigger_key: str, merchant_id: str, customer_id: str | None = None) -> str:
    raw = "|".join([trigger_key, merchant_id, customer_id or "-"])
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    safe = re.sub(r"[^a-zA-Z0-9:_-]+", "_", trigger_key)
    return f"{safe}:{merchant_id}:{digest}"
