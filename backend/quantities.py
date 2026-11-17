"""Hoeveelheden uit een ingrediëntregel halen en weer netjes opschrijven.

"300 g penne"            -> 300, "g", "penne"
"1½ el olijfolie"        -> 1.5, "el", "olijfolie"
"2-3 tenen knoflook"     -> 2 t/m 3, "teen", "knoflook"
"snufje zout"            -> geen getal, "snuf", "zout"
"peper en zout"          -> geen getal, "peper en zout"
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Geschreven eenheid -> vaste schrijfwijze. Alleen hele woorden tellen mee,
# zodat "eieren" of "ui" niet als eenheid worden gezien.
_UNITS = {
    "g": "g", "gr": "g", "gram": "g",
    "kg": "kg", "kilo": "kg", "kilogram": "kg",
    "mg": "mg",
    "ml": "ml", "milliliter": "ml",
    "cl": "cl", "dl": "dl",
    "l": "l", "liter": "l",
    "el": "el", "eetlepel": "el", "eetlepels": "el",
    "tl": "tl", "theelepel": "tl", "theelepels": "tl",
    "kl": "kl", "koffielepel": "kl", "koffielepels": "kl",
    "stuk": "stuk", "stuks": "stuk", "st": "stuk",
    "teen": "teen", "tenen": "teen", "teentje": "teen", "teentjes": "teen",
    "snuf": "snuf", "snufje": "snuf", "snufjes": "snuf",
    "mespunt": "mespunt", "mespuntje": "mespunt",
    "scheut": "scheut", "scheutje": "scheut",
    "blik": "blik", "blikje": "blik", "blikken": "blik", "blikjes": "blik",
    "pak": "pak", "pakje": "pak", "pakken": "pak", "pakjes": "pak",
    "zak": "zak", "zakje": "zak", "zakken": "zak", "zakjes": "zak",
    "pot": "pot", "potje": "pot", "potten": "pot", "potjes": "pot",
    "plak": "plak", "plakje": "plak", "plakken": "plak", "plakjes": "plak",
    "takje": "takje", "takjes": "takje",
    "bos": "bos", "bosje": "bos", "bosjes": "bos",
    "handje": "handje", "handjes": "handje", "handvol": "handje",
    "kop": "kop", "kopje": "kop", "kopjes": "kop",
    "glas": "glas", "glazen": "glas",
    "vel": "vel", "vellen": "vel",
    "blaadje": "blaadje", "blaadjes": "blaadje",
    "blokje": "blokje", "blokjes": "blokje",
    "blok": "blok", "blokken": "blok",
    "tablet": "tablet", "tabletten": "tablet", "tabletje": "tablet",
}

_FRACTIONS = {
    "½": 0.5, "⅓": 1 / 3, "⅔": 2 / 3, "¼": 0.25, "¾": 0.75,
    "⅕": 0.2, "⅛": 0.125,
}
_FRACTION_CHARS = "".join(_FRACTIONS)

# Eén getal: "1 1/2", "1/2", "1½", "½", "1,5", "300"
_NUMBER = (
    r"(?:\d+\s+\d+/\d+"
    r"|\d+/\d+"
    rf"|\d+\s?[{_FRACTION_CHARS}]"
    rf"|[{_FRACTION_CHARS}]"
    r"|\d+(?:[.,]\d+)?)"
)

_AMOUNT_RE = re.compile(
    rf"^\s*(?:ca\.?|circa|ongeveer|ong\.)?\s*"
    rf"(?P<first>{_NUMBER})"
    rf"(?:\s*(?:-|–|—|à|a|tot)\s*(?P<second>{_NUMBER}))?"
    rf"\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
_UNIT_RE = re.compile(r"^(?P<unit>[^\W\d_]+)\.?(?=\s|$)\s*(?P<rest>.*)$")
# Een maat zonder getal: "snufje komijn", "een scheutje olie". Alleen maten die
# ook zonder getal een hoeveelheid zijn; "blokjes kaas" of "pot pesto" niet.
_BARE_UNITS = frozenset({"snuf", "mespunt", "scheut", "handje", "takje", "bos", "blaadje"})
_BARE_UNIT_RE = re.compile(r"^(?P<text>(?:een\s+)?(?P<unit>[^\W\d_]+))\s+(?P<rest>\S.*)$", re.IGNORECASE)


@dataclass(frozen=True)
class Parsed:
    amount: float | None      # eerste (of enige) getal
    amount_max: float | None  # bovengrens bij "2-3"
    unit: str | None          # vaste schrijfwijze, bijv. "el"
    text: str | None          # hoeveelheid zoals geschreven, bijv. "300 g"
    name: str                 # de rest van de regel


def _to_number(raw: str) -> float | None:
    raw = raw.strip()
    try:
        if raw in _FRACTIONS:
            return _FRACTIONS[raw]
        if raw[-1] in _FRACTIONS:  # "1½" of "1 ½"
            return float(raw[:-1].strip()) + _FRACTIONS[raw[-1]]
        if "/" in raw:
            whole = 0.0
            if " " in raw:
                whole_part, raw = raw.split(None, 1)
                whole = float(whole_part)
            num, den = raw.split("/")
            return whole + float(num) / float(den)
        return float(raw.replace(",", "."))
    except (ValueError, ZeroDivisionError):
        return None


def parse_ingredient(line: str) -> Parsed:
    """Splits een ingrediëntregel in hoeveelheid, eenheid en naam."""
    line = " ".join(line.split())
    m = _AMOUNT_RE.match(line)
    if not m:
        bare = _BARE_UNIT_RE.match(line)
        unit = _UNITS.get(bare.group("unit").lower()) if bare else None
        if unit in _BARE_UNITS:
            return Parsed(None, None, unit, bare.group("text"), bare.group("rest"))
        return Parsed(None, None, None, None, line)

    amount = _to_number(m.group("first"))
    if amount is None:
        return Parsed(None, None, None, None, line)
    amount_max = _to_number(m.group("second")) if m.group("second") else None

    rest = m.group("rest")
    unit = None
    um = _UNIT_RE.match(rest)
    if um and um.group("unit").lower() in _UNITS:
        unit = _UNITS[um.group("unit").lower()]
        rest = um.group("rest")

    # De hoeveelheid zoals de receptschrijver hem noteerde.
    text = line[: len(line) - len(rest)].strip() if rest else line
    return Parsed(amount, amount_max, unit, text, rest.strip())


_NICE_FRACTIONS = [(0.25, "¼"), (1 / 3, "⅓"), (0.5, "½"), (2 / 3, "⅔"), (0.75, "¾")]


def format_number(value: float) -> str:
    """3.0 -> '3', 1.5 -> '1½', 1.3 -> '1,3'."""
    if abs(value - round(value)) < 0.02:
        return str(round(value))
    whole = int(value)
    frac = value - whole
    for target, char in _NICE_FRACTIONS:
        if abs(frac - target) < 0.02:
            return f"{whole}{char}" if whole else char
    return f"{value:.1f}".replace(".", ",")


def format_amount(value: float, value_max: float | None, unit: str | None) -> str:
    """Getal (of bereik) met eenheid, bijv. '2-3 el'."""
    number = format_number(value)
    if value_max is not None and value_max > value:
        number = f"{number}-{format_number(value_max)}"
    return f"{number} {unit}" if unit else number
