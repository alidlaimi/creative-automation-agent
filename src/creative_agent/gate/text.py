"""Textwerkzeuge für den Faktencheck: Normalisierung, Zahlen, Preise, Einheiten."""

import re
from decimal import Decimal, InvalidOperation

SPACES = re.compile(r"[   \s]+")

# Synonyme -> kanonische Einheit (60 h = 60 Std. = 60 Stunden)
UNIT_SYNONYMS = {
    "h": "h",
    "std.": "h",
    "std": "h",
    "stunden": "h",
    "stunde": "h",
    "min": "min",
    "minuten": "min",
    "zoll": "zoll",
    '"': "zoll",
    "″": "zoll",
    "l": "l",
    "liter": "l",
    "w": "w",
    "watt": "w",
}

PRICE = re.compile(
    r"(?:\b(?:CHF|Fr\.)\s*)(\d{1,3}(?:['’]\d{3})+|\d+)(?:[.,](\d{2}|–|-{1,2}))?"
    r"|\b(\d{1,3}(?:['’]\d{3})+|\d+)[.,](?:–|-{1,2})(?!\d)",
    re.IGNORECASE,
)
NUMBER = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)?(?![\w])")


def normalize(text: str) -> str:
    return SPACES.sub(" ", text).strip()


def to_decimal(raw: str) -> Decimal | None:
    try:
        return Decimal(raw.replace("'", "").replace("’", "").replace(",", "."))
    except InvalidOperation:
        return None


def find_prices(text: str) -> list[tuple[Decimal, tuple[int, int]]]:
    found = []
    for m in PRICE.finditer(text):
        whole = m.group(1) or m.group(3)
        cents = m.group(2) if m.group(1) and m.group(2) and m.group(2).isdigit() else None
        value = to_decimal(f"{whole}.{cents}" if cents else whole)
        if value is not None:
            found.append((value, m.span()))
    return found


def unit_pattern(units: list[str]) -> re.Pattern:
    alts = sorted({u.lower() for u in units} | set(UNIT_SYNONYMS), key=len, reverse=True)
    body = "|".join(re.escape(u) for u in alts)
    return re.compile(rf"(\d+(?:[.,]\d+)?)\s?({body})(?![a-zäöüA-ZÄÖÜ])", re.IGNORECASE)


def find_unit_values(text: str, pattern: re.Pattern) -> list[tuple[Decimal, str, tuple[int, int]]]:
    found = []
    for m in pattern.finditer(normalize(text)):
        value = to_decimal(m.group(1))
        unit = UNIT_SYNONYMS.get(m.group(2).lower(), m.group(2).lower())
        if value is not None:
            found.append((value, unit, m.span()))
    return found


NUMBER_WORDS = {
    "zwei": 2,
    "drei": 3,
    "vier": 4,
    "fünf": 5,
    "sechs": 6,
    "sieben": 7,
    "acht": 8,
    "neun": 9,
    "zehn": 10,
    "elf": 11,
    "zwölf": 12,
}  # «ein/eine» bewusst nicht: zu mehrdeutig


def word_numbers(text: str) -> set[Decimal]:
    """Zahlwörter im Beleg («drei Brenner» belegt «3 Brenner»)."""
    return {Decimal(NUMBER_WORDS[w]) for w in words(text) if w in NUMBER_WORDS}


def numbers(text: str) -> set[Decimal]:
    return {d for d in (to_decimal(n) for n in NUMBER.findall(normalize(text))) if d is not None}


def term_pattern(term: str) -> re.Pattern:
    """Wortgrenzen nur dort, wo der Begriff mit Buchstabe/Ziffer beginnt bzw. endet."""
    left = r"(?<![\wäöüÄÖÜ])" if term[:1].isalnum() else ""
    right = r"(?![\wäöüÄÖÜ])" if term[-1:].isalnum() else ""
    return re.compile(left + re.escape(term) + right, re.IGNORECASE)


def words(text: str) -> list[str]:
    return re.findall(r"[\wäöüÄÖÜ]+", normalize(text).lower())
