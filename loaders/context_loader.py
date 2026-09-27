from __future__ import annotations
from pathlib import Path
from .json_loader import load_model
from models import CategoryContext, MerchantContext, CustomerContext, TriggerContext


class ContextRepository:
    def __init__(self, dataset_root: str | Path):
        self.root = Path(dataset_root)

    def category(self, path_or_slug: str | Path) -> CategoryContext:
        p = Path(path_or_slug)
        if not p.suffix:
            p = self.root / "categories" / f"{p}.json"
        return load_model(p, CategoryContext)

    def merchant(self, path_or_id: str | Path) -> MerchantContext:
        p = Path(path_or_id)
        if not p.suffix:
            candidates = list((self.root / "merchants").glob(f"{p}*.json"))
            if not candidates:
                raise FileNotFoundError(f"Merchant {path_or_id} not found")
            p = candidates[0]
        return load_model(p, MerchantContext)

    def customer(self, path_or_id: str | Path) -> CustomerContext:
        p = Path(path_or_id)
        if not p.suffix:
            candidates = list((self.root / "customers").glob(f"{p}*.json"))
            if not candidates:
                raise FileNotFoundError(f"Customer {path_or_id} not found")
            p = candidates[0]
        return load_model(p, CustomerContext)

    def trigger(self, path_or_id: str | Path) -> TriggerContext:
        p = Path(path_or_id)
        if not p.suffix:
            candidates = list((self.root / "triggers").glob(f"{p}*.json"))
            if not candidates:
                raise FileNotFoundError(f"Trigger {path_or_id} not found")
            p = candidates[0]
        return load_model(p, TriggerContext)
