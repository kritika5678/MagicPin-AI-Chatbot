from __future__ import annotations
import re
from models import FullContext
from models.messages import ComposedMessage
from models.results import ValidationResult

NUMBER_RE = re.compile(r"(?<![A-Za-z])(?:₹\s*)?\d+(?:[\d,.]*\d)?%?(?![A-Za-z])")
ISO_TIME_RE = re.compile(r"(?<!\d)(\d{1,2}):(\d{2})(?!\d)")
ISO_DATE_RE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")


def normalized_num(token: str) -> str:
    return re.sub(r"[^\d%₹.\-]", "", token).replace(",", "")


def numeric_equivalents(token: str) -> set[str]:
    """Support context fractions such as delta_pct=0.15 when copy renders 15%."""
    n = normalized_num(token)
    out = {n}
    if n.endswith("%"):
        raw = n[:-1]
        try:
            out.add(str(round(float(raw) / 100, 6)))
        except ValueError:
            pass
    else:
        try:
            value = float(n)
            if 0 < abs(value) < 1:
                pct = round(value * 100, 6)
                out.add(f"{pct:g}%")
            out.add(f"{value:g}")
        except ValueError:
            pass
    return out


class FactValidator:
    def validate(self, message: ComposedMessage, ctx: FullContext) -> ValidationResult:
        serialized = str(ctx.model_dump(mode="json"))
        serialized_numbers = set()
        for x in NUMBER_RE.findall(serialized):
            serialized_numbers.update(numeric_equivalents(x))
        # Preserve numeric components embedded in ISO timestamps/dates such as T19:00 or 2026-05-02.
        for hour, minute in ISO_TIME_RE.findall(serialized):
            serialized_numbers.update({hour, minute})
        for year, month, day in ISO_DATE_RE.findall(serialized):
            serialized_numbers.update({year, month, day})

        errors = []
        for token in NUMBER_RE.findall(message.body):
            candidate = numeric_equivalents(token)
            if not candidate.intersection(serialized_numbers):
                errors.append(f"unsupported numeric claim: {token}")
        return ValidationResult(valid=not errors, errors=errors)
