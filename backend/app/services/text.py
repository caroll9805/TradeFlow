"""Text normalization for multilingual (Uzbek Latin/Cyrillic, Russian) product names."""
import re
import unicodedata

# Uzbek/Russian Cyrillic -> Latin transliteration so "Сахар" / "Shakar" style variants normalise consistently.
_CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "ь": "",
    "э": "e", "ю": "yu", "я": "ya", "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h",
}
_STRIP = re.compile(r"[^a-z0-9\s.]")
_SPACES = re.compile(r"\s+")
_DEC_COMMA = re.compile(r"(\d),(\d)")
_LONE_DOT = re.compile(r"(?<!\d)\.|\.(?!\d)")
_NUM_UNIT = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|g|l|ml|m|mm|sm|cm|kv|m2|m3|dona|sht|pcs)\b")


def transliterate(s: str) -> str:
    return "".join(_CYR.get(ch, ch) for ch in s)


def normalize_text(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s).lower()
    s = s.replace("ʻ", "").replace("'", "").replace("`", "").replace("‘", "").replace("’", "")
    s = transliterate(s)
    s = _DEC_COMMA.sub(r"\1.\2", s)  # 2,5 -> 2.5
    s = _STRIP.sub(" ", s)
    s = _LONE_DOT.sub(" ", s)  # keep dots only inside numbers
    s = _NUM_UNIT.sub(lambda m: f"{m.group(1)}{m.group(2)}", s)  # "50 kg" -> "50kg"
    return _SPACES.sub(" ", s).strip()


def tokens(s: str | None) -> set[str]:
    return {t for t in normalize_text(s).split(" ") if t}
