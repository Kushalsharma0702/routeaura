"""Deterministic English/Hindi understanding: language detection, numbers, slots and intents. Pure functions.

The assistant never needs an LLM to work. (An LLM may optionally propose an intent; it is validated and any
failure falls back to these rules.) Matching is deliberately conservative: when unsure the intent is `unknown`
and the assistant asks instead of acting.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DEVANAGARI = re.compile(r"[ऀ-ॿ]")
LATIN = re.compile(r"[A-Za-z]")
HINDI_ROMAN_MARKERS = {
    "mujhe",
    "chahiye",
    "kitna",
    "kitne",
    "dikhao",
    "batao",
    "banao",
    "yatra",
    "ghoomne",
    "jagah",
    "hai",
    "kya",
    "mera",
    "meri",
    "haan",
    "nahi",
    "aur",
}

HI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
WORD_NUMBERS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "एक": 1,
    "दो": 2,
    "तीन": 3,
    "चार": 4,
    "पांच": 5,
    "पाँच": 5,
    "छह": 6,
    "छः": 6,
    "छे": 6,
    "सात": 7,
    "आठ": 8,
    "नौ": 9,
    "दस": 10,
    "ek": 1,
    "do": 2,
    "teen": 3,
    "char": 4,
    "paanch": 5,
    "chhe": 6,
    "saat": 7,
    "aath": 8,
    "nau": 9,
    "das": 10,
}
DESTINATION_ALIASES = {
    "जयपुर": "jaipur",
    "गोवा": "goa",
    "मनाली": "manali",
    "केरल": "kerala",
    "केरला": "kerala",
    "लद्दाख": "ladakh",
    "लेह": "ladakh",
}
INTEREST_WORDS = {
    "history": "history",
    "historical": "history",
    "इतिहास": "history",
    "ऐतिहासिक": "history",
    "food": "food",
    "खाना": "food",
    "भोजन": "food",
    "beach": "beach",
    "beaches": "beach",
    "समुद्र": "beach",
    "बीच": "beach",
    "adventure": "adventure",
    "रोमांच": "adventure",
    "एडवेंचर": "adventure",
    "nature": "nature",
    "प्रकृति": "nature",
    "wildlife": "wildlife",
    "culture": "culture",
    "संस्कृति": "culture",
    "temples": "culture",
    "मंदिर": "culture",
    "shopping": "shopping",
    "scenic": "scenic",
}

KEYWORDS: dict[str, dict[str, list[str]]] = {
    "yes": {
        "en": ["yes", "yeah", "yep", "ok", "okay", "confirm", "sure", "go ahead", "do it"],
        "hi": ["हाँ", "हां", "जी", "ठीक है", "कर दो", "कर दीजिए", "पक्का"],
    },
    "no": {
        "en": ["no", "nope", "cancel", "don't", "do not", "never mind", "stop"],
        "hi": ["नहीं", "नही", "रहने दो", "मत", "रुको"],
    },
    "remove": {"en": ["remove", "delete", "drop", "take out", "get rid"], "hi": ["हटा", "निकाल", "मिटा", "डिलीट"]},
    "add": {"en": ["add", "include", "put in"], "hi": ["जोड़", "जोड", "शामिल"]},
    "move": {"en": ["move", "shift", "reschedule"], "hi": ["शिफ्ट", "बदल", "खिसका"]},
    "show": {
        "en": [
            "show my itinerary",
            "show me my itinerary",
            "my itinerary",
            "my plan",
            "my trip",
            "what's my plan",
            "read my itinerary",
        ],
        "hi": ["मेरी यात्रा", "मेरा प्लान", "मेरी योजना"],
    },
    "plan": {
        "en": ["plan", "itinerary", "create a trip", "make a trip", "organize", "organise"],
        "hi": ["प्लान", "योजना", "यात्रा बना", "ट्रिप", "यात्रा की"],
    },
    "booking": {"en": ["booking", "bookings", "reservation", "my stay", "reservations"], "hi": ["बुकिंग", "आरक्षण"]},
    "hotels": {
        "en": ["hotel", "hotels", "stay", "room", "rooms", "accommodation"],
        "hi": ["होटल", "रहने", "कमरा", "कमरे"],
    },
    "recommend": {
        "en": [
            "recommend",
            "suggest",
            "where should",
            "where to go",
            "best place",
            "places to visit",
            "what should i visit",
            "ideas",
        ],
        "hi": ["सुझा", "सुझाव", "कहाँ", "कहां", "घूमने", "जगह", "बताओ", "बताइए"],
    },
    "greeting": {"en": ["hello", "hi", "hey", "good morning", "good evening"], "hi": ["नमस्ते", "नमस्कार", "हैलो", "हेलो"]},
    "help": {"en": ["help", "what can you do", "how do you work"], "hi": ["मदद", "सहायता", "क्या कर सकते"]},
}
ORDER = ["remove", "move", "add", "show", "plan", "booking", "hotels", "recommend", "help", "greeting"]


def detect_language(text: str) -> tuple[str, str]:
    """('en'|'hi', method). Script-based (Devanagari share of letters), with a small romanised-Hindi marker list.
    This is a heuristic: it only SUGGESTS a language; the conversation language is the user's explicit choice."""
    dev, lat = len(DEVANAGARI.findall(text)), len(LATIN.findall(text))
    if dev + lat == 0:
        return "en", "default"
    if dev >= 2 and dev / (dev + lat) >= 0.2:  # a Hindi word inside an English sentence still counts
        return "hi", "script"
    words = set(re.findall(r"[a-z]+", text.lower()))
    if len(words & HINDI_ROMAN_MARKERS) >= 2:
        return "hi", "romanised-markers"
    return "en", "script"


def _norm(text: str) -> str:
    return text.translate(HI_DIGITS).lower().strip()


def _has(text: str, words: list[str], whole: bool = False) -> bool:
    """Keyword match. Latin keywords match whole words/phrases. Devanagari keywords must START a token (so stems such as
    'हटा' match 'हटाओ') and, with whole=True, must be the entire token (so 'हाँ' never matches inside 'कहाँ')."""
    t = f" {text} "
    for w in words:
        if DEVANAGARI.search(w):
            pattern = rf"(?<![\u0900-\u097F]){re.escape(w)}" + (r"(?![\u0900-\u097F])" if whole else "")
            if re.search(pattern, text):
                return True
        elif re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", t):
            return True
    return False


@dataclass
class Slots:
    destination: str | None = None  # slug
    days: int | None = None
    day: int | None = None  # a specific day ("to day 2")
    budget_minor: int | None = None
    travelers: int | None = None
    interests: list[str] = field(default_factory=list)
    activity_text: str | None = None


@dataclass
class Understanding:
    intent: str
    slots: Slots
    language: str
    matched_by: str = "rules"


def extract_number_after(text: str, patterns: list[str]) -> int | None:
    for p in patterns:
        m = re.search(p, text)
        if m:
            raw = m.group(1)
            return int(raw) if raw.isdigit() else WORD_NUMBERS.get(raw)
    return None


NUM = r"(\d{1,3}|" + "|".join(sorted((re.escape(w) for w in WORD_NUMBERS), key=len, reverse=True)) + r")"


def extract_days(t: str) -> int | None:
    n = extract_number_after(
        t, [rf"{NUM}\s*[- ]?\s*(?:days?|day|nights?)", rf"{NUM}\s*(?:दिन|रात)", rf"for\s+{NUM}\s+days?"]
    )
    if n is None and re.search(r"\bweekend\b|वीकेंड", t):
        return 2
    return n


def extract_budget_minor(t: str) -> int | None:
    m = (
        re.search(r"(?:₹|rs\.?|inr|रु\.?|रुपये|rupees?)\s*([\d,]+(?:\.\d+)?)\s*(k|हज़ार|हजार|thousand|lakh|lakhs|लाख)?", t)
        or re.search(r"([\d,]+(?:\.\d+)?)\s*(k|हज़ार|हजार|thousand|lakh|lakhs|लाख)?\s*(?:rupees?|rs\.?|inr|रुपये|रुपए)", t)
        or re.search(r"budget(?: of| is)?\s*([\d,]+(?:\.\d+)?)\s*(k|thousand|lakh)?", t)
        or re.search(r"बजट\s*([\d,]+(?:\.\d+)?)\s*(हज़ार|हजार|लाख)?", t)
    )
    if not m:
        return None
    value = float(m.group(1).replace(",", ""))
    unit = (m.group(2) or "").lower()
    value *= 1000 if unit in ("k", "हज़ार", "हजार", "thousand") else 100_000 if unit in ("lakh", "lakhs", "लाख") else 1
    return int(value * 100) if 0 < value <= 10_000_000 else None


def extract_travelers(t: str) -> int | None:
    n = extract_number_after(
        t,
        [
            rf"for\s+{NUM}\s+(?:people|persons|adults|travell?ers|of us)",
            rf"{NUM}\s+(?:people|persons|adults|travell?ers)",
            rf"{NUM}\s*(?:लोग|व्यक्ति|यात्री)",
        ],
    )
    if n is None and re.search(r"\bfor (?:two|a couple)\b|\bcouple\b|\bhoneymoon\b|कपल", t):
        return 2
    if n is None and re.search(r"\bsolo\b|\bby myself\b|अकेले", t):
        return 1
    return n


def extract_interests(t: str) -> list[str]:
    found = []
    for word, interest in INTEREST_WORDS.items():
        if (
            word in t if DEVANAGARI.search(word) else re.search(rf"(?<![a-z]){word}(?![a-z])", t)
        ) and interest not in found:
            found.append(interest)
    return found


def extract_destination(t: str, names: dict[str, str]) -> str | None:
    """`names` maps slug -> display name for published destinations."""
    for alias, slug in DESTINATION_ALIASES.items():
        if alias in t and slug in names:
            return slug
    best = None
    for slug, name in names.items():
        if re.search(rf"(?<![a-z]){re.escape(name.lower())}(?![a-z])", t):
            best = slug if best is None or len(name) > len(names[best]) else best
    return best


def match_name(text: str, candidates: dict[str, str]) -> str | None:
    """Best fuzzy match of a free-text mention to one of `candidates` (id -> name) by token overlap. None if ambiguous/absent."""
    tokens = set(re.findall(r"[a-z0-9]+", text.lower())) - {
        "the",
        "a",
        "an",
        "to",
        "from",
        "my",
        "trip",
        "itinerary",
        "day",
        "of",
        "please",
        "remove",
        "add",
        "move",
        "delete",
    }
    scored = []
    for cid, name in candidates.items():
        name_tokens = set(re.findall(r"[a-z0-9]+", name.lower()))
        if name_tokens and name_tokens <= tokens | {"fort", "mahal", "palace"} and name_tokens & tokens:
            scored.append((len(name_tokens & tokens) / len(name_tokens), len(name_tokens & tokens), cid))
    if not scored:
        return None
    scored.sort(reverse=True)
    if len(scored) > 1 and scored[0][:2] == scored[1][:2]:
        return None
    return scored[0][2] if scored[0][0] >= 0.5 else None


def understand(text: str, language: str, destinations: dict[str, str]) -> Understanding:
    t = _norm(text)
    slots = Slots(
        destination=extract_destination(t, destinations),
        days=extract_days(t),
        budget_minor=extract_budget_minor(t),
        travelers=extract_travelers(t),
        interests=extract_interests(t),
    )
    m = extract_number_after(t, [rf"(?:to|on|into)\s+day\s*{NUM}", rf"दिन\s*{NUM}\s*(?:में|पर)", rf"day\s*{NUM}"])
    slots.day = m
    slots.activity_text = text
    langs = ("en", "hi")
    for intent in ("yes", "no"):
        if len(t.split()) <= 4 and any(_has(t, KEYWORDS[intent][lang], whole=True) for lang in langs):
            return Understanding(intent, slots, language)
    for intent in ORDER:
        if any(_has(t, KEYWORDS[intent][lang]) for lang in langs):
            if intent == "hotels" and _has(t, KEYWORDS["plan"]["en"] + KEYWORDS["plan"]["hi"]):
                continue
            if intent == "recommend" and slots.days and slots.destination:
                return Understanding("plan", slots, language)
            return Understanding(intent, slots, language)
    if slots.destination and slots.days:
        return Understanding("plan", slots, language)
    return Understanding("unknown", slots, language)
