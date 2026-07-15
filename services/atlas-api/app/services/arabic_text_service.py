import re
import unicodedata

DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")


def remove_diacritics(text: str) -> str:
    return DIACRITICS.sub("", unicodedata.normalize("NFKC", text))


def remove_arabic_diacritics(text: str) -> str:
    return remove_diacritics(text)


def normalize_alef(text: str) -> str:
    return re.sub("[إأآٱ]", "ا", text)


def normalize_yaa(text: str) -> str:
    return text.replace("ى", "ي")


def normalize_taa_marbuta(text: str) -> str:
    return text.replace("ة", "ه")


def collapse_whitespace(text: str) -> str:
    return " ".join(text.split())


def remove_tatweel(text: str) -> str:
    return text.replace("ـ", "")


def normalize_arabic_text(text: str) -> str:
    value = remove_tatweel(remove_diacritics(text).lower())
    value = normalize_taa_marbuta(normalize_yaa(normalize_alef(value)))
    return collapse_whitespace(value)


def prepare_search_query(text: str) -> str:
    return normalize_arabic_text(text).strip()


def normalize_english_text(text: str) -> str:
    return collapse_whitespace(unicodedata.normalize("NFKC", text).casefold())


def generate_query_tokens(text: str) -> list[str]:
    return list(dict.fromkeys(token for token in prepare_search_query(text).split(" ") if len(token) > 1))


def generate_alternative_forms(text: str) -> list[str]:
    normalized = prepare_search_query(text)
    forms = [collapse_whitespace(text), normalized]
    if "ه" in normalized:
        forms.append(normalized.replace("ه", "ة"))
    return list(dict.fromkeys(value for value in forms if value))
