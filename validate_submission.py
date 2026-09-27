from __future__ import annotations
import json
from pathlib import Path

path = Path("submission.jsonl")
lines = path.read_text(encoding="utf-8").splitlines()
assert len(lines) == 30, f"Expected 30 lines, got {len(lines)}"
required = {"test_id", "body", "cta", "send_as", "suppression_key", "rationale"}
ids = set()
for i, line in enumerate(lines, 1):
    obj = json.loads(line)
    missing = required - obj.keys()
    assert not missing, f"Line {i} missing: {sorted(missing)}"
    assert obj["test_id"] not in ids, f"Duplicate test_id on line {i}"
    ids.add(obj["test_id"])
print("Submission valid: 30/30 cases")
