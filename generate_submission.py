from __future__ import annotations
import json
from pathlib import Path
from loaders.context_loader import ContextRepository
from bot import compose

ROOT = Path(__file__).resolve().parent
repo = ContextRepository(ROOT / "dataset")
pairs = json.loads((ROOT / "dataset" / "test_pairs.json").read_text(encoding="utf-8"))["pairs"]

with (ROOT / "submission.jsonl").open("w", encoding="utf-8") as f:
    for pair in pairs:
        trigger = repo.trigger(pair["trigger_id"]).model_dump(mode="json")
        merchant = repo.merchant(pair["merchant_id"]).model_dump(mode="json")
        category_slug = merchant["category_slug"]
        category = repo.category(category_slug).model_dump(mode="json")
        customer = None
        if pair.get("customer_id"):
            customer = repo.customer(pair["customer_id"]).model_dump(mode="json")
        result = compose(category, merchant, trigger, customer)
        result["test_id"] = pair["test_id"]
        f.write(json.dumps(result, ensure_ascii=False) + "\n")

print(f"Generated {len(pairs)} submission cases -> submission.jsonl")
