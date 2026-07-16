from __future__ import annotations

import re
import unicodedata

_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_NON_WORD = re.compile(r"[^\w\s]", flags=re.UNICODE)
_SPACES = re.compile(r"\s+")


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKC", str(value)).strip().lower()
    text = text.replace("ـ", "")
    text = _DIACRITICS.sub("", text)
    text = text.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي", "ؤ": "و", "ئ": "ي", "ة": "ه"}))
    text = _NON_WORD.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def compact_name(value: object) -> str:
    text = normalize_text(value)
    stopwords = {"فندق", "hotel", "منتجع", "resort", "اقامه", "السياحيه", "السياحي"}
    return " ".join(token for token in text.split() if token not in stopwords)
