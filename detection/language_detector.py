from __future__ import annotations
import re

HINDI_DEVANAGARI = re.compile(r"[\u0900-\u097F]")
HI_EN_MARKERS = {
    "hai", "haan", "nahi", "nahin", "aap", "apka", "meri", "mujhe", "karna", "karo",
    "chalega", "ka", "ki", "ke", "mein", "me", "se", "par", "abhi", "please", "ji"
}


class LanguageDetector:
    def detect(self, text: str, preferred: str | None = None, history: list[str] | None = None) -> str:
        if preferred:
            p = preferred.lower().replace("_", "-")
            if "hi" in p and "en" in p:
                return "hi-en"
            if p.startswith("hi"):
                return "hindi"
            if p.startswith("en"):
                return "english"

        tokens = re.findall(r"[a-zA-Z]+", text.lower())
        hindi_marker_count = sum(t in HI_EN_MARKERS for t in tokens)
        if HINDI_DEVANAGARI.search(text):
            return "hindi"
        if hindi_marker_count >= 2:
            return "hi-en"
        return "english"
