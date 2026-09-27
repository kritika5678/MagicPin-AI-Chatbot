from __future__ import annotations
import json
from pathlib import Path
from typing import Any, TypeVar, Type

T = TypeVar("T")


def load_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        obj = json.load(f)
    if not isinstance(obj, dict):
        raise ValueError(f"Expected JSON object at {p}")
    return obj


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    p = Path(path)
    rows = []
    with p.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"Expected JSON object on line {line_no}")
            rows.append(row)
    return rows


def load_model(path: str | Path, model_cls: Type[T]) -> T:
    return model_cls.model_validate(load_json(path))
