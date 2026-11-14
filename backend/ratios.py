"""Hoeveel van de vervanger heb je nodig?

Alleen vervangers waarvoor een vaste verhouding geldt staan hier. Dat zijn
vooral één-op-één-ruil (glutenvrije pasta voor pasta, plantaardige melk voor
melk). Staat een vervanger hier niet, dan zegt de engine eerlijk dat er geen
vaste verhouding bekend is in plaats van te gokken.

Het zijn kookrichtlijnen, geen medisch advies.

Vorm per allergie/dieet:
    "same":     triggers waarvan de vervanger 1 : 1 gaat
    "same_for": trigger -> voor welke van de genoemde vervangers 1 : 1 geldt
                (als de andere optie géén gelijke hoeveelheid is)
    "per_piece": trigger -> onderdelen per stuk, bijv. per ei
"""

from __future__ import annotations

from dataclasses import dataclass

from quantities import Parsed, format_amount

NO_RATIO_NOTE = "Geen vaste verhouding bekend."

_ZUIVEL_SAME = [
    "melk", "room", "slagroom", "karnemelk", "yoghurt", "kwark",
    "mascarpone", "ricotta", "crème fraîche", "creme fraiche",
    "mozzarella", "burrata", "brie", "camembert", "gorgonzola", "feta",
    "roomkaas", "vla", "pudding", "custard", "ijs",
    "roomboter bladerdeeg", "boter bladerdeeg",
]
_ZUIVEL_SAME_FOR = {
    "boter": "plantaardige boter",
    "roomboter": "plantaardige boter",
    "kaas": "vegane kaas",
    "cheddar": "vegane kaas",
    "gouda": "vegane kaas",
    "edam": "vegane kaas",
    "gruyère": "vegane kaas",
    "gruyere": "vegane kaas",
    "emmentaler": "vegane kaas",
    "parmezaan": "vegane parmezaan",
    "parmesan": "vegane parmezaan",
    "pecorino": "vegane harde kaas",
}
_LIJNZAAD_EI = {
    "unit_names": ("ei", "eieren"),
    "parts": [(1, "el", "gebroken lijnzaad"), (3, "el", "water")],
    "applies_to": "lijnzaad-ei",
}
_BOUILLON = ["kippenbouillon", "runderbouillon", "vleesbouillon"]
_VARKEN_SAME = ["spek", "speklap", "bacon", "ham", "prosciutto", "pancetta",
                "worst", "rookworst", "knakworst", "chorizo", "salami"]

RATIOS: dict[str, dict] = {
    # ── Allergieën ───────────────────────────────────────────────────────────
    "lactose": {"same": _ZUIVEL_SAME, "same_for": _ZUIVEL_SAME_FOR},
    "gluten": {
        "same": ["pasta", "spaghetti", "macaroni", "penne", "fusilli",
                 "tagliatelle", "fettuccine", "lasagne", "lasagnebladen",
                 "gebakken uitjes"],
        "same_for": {"rigatoni": "glutenvrije rigatoni"},
    },
    "noten": {
        "same": ["pindakaas", "notenboter", "notenpasta", "amandelspijs", "marsepein"],
    },
    "ei": {
        "same": ["mayonaise", "mayo"],
        "per_piece": {"ei": _LIJNZAAD_EI, "eieren": _LIJNZAAD_EI},
    },
    "soja": {"same": ["sojamelk", "sojaroom", "sojasaus", "ketjap"]},
    "sesam": {"same": ["sesam", "sesamzaad", "sesamolie", "tahini", "tahin", "sesampasta"]},
    "lupine": {"same": ["lupinepasta"]},
    "sulfiet": {
        "same": ["wijn", "rode wijn", "witte wijn", "porto", "sherry"],
        "same_for": {
            "rozijnen": "sulfietvrije rozijnen",
            "gedroogde abrikozen": "sulfietvrije gedroogde abrikozen",
        },
    },
    # ── Diëten ───────────────────────────────────────────────────────────────
    "vegetarisch": {
        "same": _BOUILLON,
        "same_for": {
            "kip": "vegan kipstukjes",
            "kipfilet": "vegan kipstukjes",
            "kipfilets": "vegan kipstukjes",
            "spek": "vegan spekreepjes",
            "spekreepjes": "vegan spekreepjes",
            "spekreepje": "vegan spekreepjes",
        },
    },
    "vegan": {
        "same": _ZUIVEL_SAME + _BOUILLON + ["mayonaise", "honing"],
        "same_for": {
            **_ZUIVEL_SAME_FOR,
            "kip": "vegan kipstukjes",
            "kipfilet": "vegan kipstukjes",
            "kipfilets": "vegan kipstukjes",
            "gehakt": "vegan gehakt",
            "rundergehakt": "vegan gehakt",
        },
        "per_piece": {"ei": _LIJNZAAD_EI, "eieren": _LIJNZAAD_EI},
    },
    "halal": {"same": _VARKEN_SAME + ["wijn", "rode wijn", "witte wijn", "bier"]},
    "koosjer": {"same": ["spek", "speklap", "bacon", "ham", "worst", "rookworst", "knakworst"]},
    "paleo": {"same": ["melk", "room", "yoghurt"]},
    "fodmap": {
        "same": ["melk", "yoghurt", "kwark", "slagroom", "ijs", "roomkaas",
                 "mascarpone", "ricotta", "zure room"],
    },
    "suikervrij": {
        "same": ["chocolade", "chocola", "jam", "gelei"],
        "same_for": {"suiker": "erythritol"},
    },
    "whole30": {
        "same": ["melk", "room"],
        "same_for": {"boter": "ghee", "roomboter": "ghee"},
    },
}


@dataclass(frozen=True)
class AlternativeAmount:
    quantity: str | None  # bijv. "300 g" of "2 el gebroken lijnzaad + 6 el water"
    ratio: str | None     # bijv. "1 : 1"
    note: str | None      # toelichting of "Geen vaste verhouding bekend."


def alternative_amount(category: str, trigger: str, parsed: Parsed) -> AlternativeAmount:
    """Bepaalt de hoeveelheid van de vervanger voor één ingrediënt."""
    spec = RATIOS.get(category, {})

    per_piece = spec.get("per_piece", {}).get(trigger)
    if per_piece:
        return _per_piece(per_piece, parsed)

    applies_to = spec.get("same_for", {}).get(trigger)
    if applies_to or trigger in spec.get("same", ()):
        note = f"Geldt voor {applies_to}." if applies_to else None
        return AlternativeAmount(parsed.text, "1 : 1", note)

    return AlternativeAmount(None, None, NO_RATIO_NOTE)


def _per_piece(spec: dict, parsed: Parsed) -> AlternativeAmount:
    unit_name = spec["unit_names"][0]
    per_one = " + ".join(format_amount(n, None, unit) + " " + name
                         for n, unit, name in spec["parts"])
    note = f"Geldt voor {spec['applies_to']}: {per_one} per {unit_name}."

    # Alleen omrekenen als het recept in stuks telt ("2 eieren"), niet bij "50 g ei".
    counted = parsed.amount is not None and parsed.unit in (None, "stuk")
    if not counted:
        return AlternativeAmount(None, None, note)

    parts = []
    for n, unit, name in spec["parts"]:
        high = parsed.amount_max * n if parsed.amount_max else None
        parts.append(f"{format_amount(parsed.amount * n, high, unit)} {name}")
    return AlternativeAmount(" + ".join(parts), None, note)
