from __future__ import annotations
import json
import re
from models.messages import ComposedMessage


class LLMOutputParser:
    def parse(self, raw: str) -> ComposedMessage:
        text = raw.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
            text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)
        return ComposedMessage.model_validate(data)
