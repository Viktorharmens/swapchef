"""Herkennen of een ingrediëntregel bij een allergie of dieet hoort.

De gegevens (triggers, uitzonderingen, vervangers) staan in main.py; hier staat
alleen hoe er gezocht wordt. In vier stappen:

0. Voorbereiden: "vegan kaas" of "glutenvrije pasta" telt niet mee voor de
   categorie waar die toevoeging over gaat, en uitzonderingen als "kokosmelk"
   worden uit de regel gehaald (de rest van de regel telt nog wel).
1. Het hele woord: "melk", "kipfilet".
2. Het begin van een samenstelling: "kipreepjes", "melkpoeder". Bij korte
   triggers (t/m 4 letters) alleen als de rest een bekend etenswoord is, anders
   wordt "lengte" een vis (leng) en "uit blik" een ui.
3. Het eind van een samenstelling: "geitenkaas", "patentbloem", "walnoten".
   Alleen voor de woorden die een categorie als "heads" opgeeft, en niet als
   het eerste deel plantaardig of glutenvrij is ("kokosmelk", "rijstmeel").

Missen is erger dan een keer te veel waarschuwen, maar een tool die bij
"bloemkool" om gluten roept, gelooft niemand meer. Vandaar de lijsten hieronder.
"""

from __future__ import annotations

import re

# ── Toevoegingen die een categorie opheffen ──────────────────────────────────

_DIERLIJK = frozenset({
    "lactose", "ei", "vis", "schaaldieren", "weekdieren",
    "vegetarisch", "vegan", "halal", "koosjer",
})

# (woorden, categorieën waarvoor het volgende woord dan niet meetelt)
_QUALIFIERS: list[tuple[str, frozenset[str]]] = [
    (r"vegan|vegane|veganistisch|veganistische|vega|plantaardig|plantaardige", _DIERLIJK),
    (r"vegetarisch|vegetarische",
     frozenset({"vis", "schaaldieren", "weekdieren", "vegetarisch", "halal", "koosjer"})),
    (r"glutenvrij|glutenvrije", frozenset({"gluten"})),
    (r"lactosevrij|lactosevrije", frozenset({"lactose", "fodmap"})),
    (r"zuivelvrij|zuivelvrije", frozenset({"lactose"})),
    (r"suikervrij|suikervrije", frozenset({"suikervrij", "keto"})),
    (r"alcoholvrij|alcoholvrije", frozenset({"halal", "whole30"})),
    (r"sojavrij|sojavrije", frozenset({"soja"})),
    (r"notenvrij|notenvrije", frozenset({"noten"})),
    (r"eivrij|eivrije", frozenset({"ei"})),
    (r"halal", frozenset({"halal"})),
    (r"koosjer|koosjere", frozenset({"koosjer"})),
]
# Het woord waar een toevoeging over gaat, eventueel met een bijvoeglijk naamwoord
# ervoor ("harde kaas", "rode wijn", "crème fraîche").
_NOUN = r"(?:[^\s,()]+e\s+)?[^\s,()]+"

# "zonder noten", "zonder knoflook/ui" en "als lasagnebladen" noemen iets wat er
# juist níet in zit.
_NEGATION_RE = re.compile(r"\b(?:zonder|als|in plaats van)\s+[^\s,()]+")

_QUALIFIER_RE = [
    (
        # "vegan kaas", en met een bijvoeglijk naamwoord ertussen: "vegane harde kaas"
        re.compile(rf"\b(?:{words})\s+{_NOUN}"),
        # Erachter: "kaas (vegan)", "kaas, vegan". Ervoor tussen haakjes betekent
        # "mag ook": "(plantaardige) melk" blijft gewoon melk.
        re.compile(rf"[(,]\s*(?:{words})\s*\)?\s*(?:$|[,(])"),
        categories,
    )
    for words, categories in _QUALIFIERS
]

# ── Samenstellingen ──────────────────────────────────────────────────────────

# Eerste delen die van een zuivel- of vleeswoord iets plantaardigs maken.
PLANT_PREFIXES = (
    "kokos", "amandel", "haver", "soja", "rijst", "cashew", "hazelnoot",
    "erwten", "erwt", "noten", "pinda", "hennep", "spelt", "lupine", "sesam",
    "cacao", "shea", "appel", "zonnebloem", "pompoen", "walnoot", "pistache",
    "macadamia", "lijnzaad", "quinoa", "boekweit", "mais", "maïs", "aardappel",
    "tofu", "vegan", "vega", "plantaardig", "vrucht", "tomaten",
)

# Eerste delen die van meel, bloem, brood of noedels iets glutenvrijs maken.
GLUTEN_FREE_PREFIXES = (
    "rijst", "mais", "maïs", "amandel", "kokos", "boekweit", "kikkererwt",
    "aardappel", "soja", "lupine", "cassave", "tapioca", "teff", "quinoa",
    "gierst", "johannesbroodpit", "guarpit", "lijnzaad", "hazelnoot",
    "kastanje", "sorghum", "arrowroot", "linzen", "erwten", "bananen", "sesam",
    "hennep", "pompoenpit", "zonnebloem", "zonne", "glas", "konjac", "courgette",
    "zoete", "glutenvrij", "koren", "kamille", "lavendel", "vlier", "hibiscus",
    "rozen", "gouds",
)

# Woorden die met een trigger beginnen maar iets anders zijn.
COMPOUND_FP = {
    # bot (vis) → boter, boterham; boter (zuivel) → boterbonen
    "boter", "roomboter", "kokosboter", "boterham", "boterhammen",
    "boterbloem", "boterbonen", "boterboon", "botersla",
    # rog (vis) → rogge
    "rogge", "roggebrood", "roggebloem", "roggemeel",
    # aal (vis) → aalbes
    "aalbes", "aalbessen", "aalbessensap",
    # kop (orgaanvlees) → kopje (maat)
    "kopje", "kopjes",
    # pos (vis) → postelein
    "postelein",
    # wild → wilde rucola
    "wilde",
    # hart (orgaanvlees) → hartig
    "hartig", "hartige",
    # harder (vis) → harder (bijvoeglijk)
    "harder",
    # lam → lamp
    "lamp", "lampen",
    # ree (wild) → reep, reepjes (snijwijze)
    "reep", "reepje", "reepjes", "repen",
    # bloem (gluten) → bloemig, bloemen
    "bloemig", "bloemige", "bloemen", "bloemetje", "bloemetjes",
    # hamburger (vlees) → het broodje eromheen
    "hamburgerbroodje", "hamburgerbroodjes", "hamburgerbrood", "hamburgersaus",
    # rollade (vlees) → het touw eromheen
    "rolladetouw", "rolladenet",
    # kip → kippenei (ei is vegetarisch; bij vegan vangt "ei" het zelf)
    "kippenei", "kippeneieren",
}

# Per trigger: begin van woorden die níet bedoeld zijn.
TRIGGER_FP_PREFIXES: dict[str, tuple[str, ...]] = {
    "bot": ("boter",),
    "bloem": ("bloemkool",),
    "ei": ("eigen", "eind", "eiland", "eik"),
    "ijs": ("ijsberg", "ijsblok", "ijsklont", "ijswater", "ijskoud"),
    "spek": ("spekkoek",),
    "vla": ("vlas",),
    "ui": ("uit",),
    "kers": ("kerst", "kerstomaat", "kerstomaten"),
    "paneer": ("paneermeel",),
    "oester": ("oesterzwam",),
    "honing": ("honingmeloen",),
    "nier": ("nierbonen", "nierboon"),
}

# Een samenstelling die hierop eindigt is een kruidenmix, geen vlees of vis.
_NEUTRAL_TAILS = ("kruiden", "kruidenmix", "kruiderij")

# Etenswoorden die achter een korte trigger mogen staan: kip+reepjes, vis+saus.
_TAILS = sorted({
    "reep", "reepje", "blok", "blokje", "stuk", "stukje", "plak", "plakje",
    "schijf", "schijfje", "filet", "filetje", "poeder", "saus", "bouillon",
    "fond", "vlees", "gehakt", "haas", "haasje", "dij", "bout", "boutje",
    "borst", "vleugel", "poot", "pootje", "spies", "spiesje", "burger",
    "worst", "worstje", "ham", "lap", "lapje", "lappen", "rollade",
    "schnitzel", "snipper", "ring", "stick", "vinger", "kruimel", "vlok",
    "vlokken", "rasp", "schaafsel", "pasta", "puree", "pit", "pitten", "olie",
    "vet", "taart", "cake", "koek", "koekje", "brood", "broodje", "deeg",
    "mix", "salade", "soep", "steak", "tartaar", "ragout", "kluif", "kluifje",
    "dooier", "wit", "geel", "blad", "bladen", "vel", "vellen", "korrel",
    "meel", "bloem", "siroop", "stroop", "jam", "gelei", "drank", "likeur",
    "azijn", "wijn", "kerrie", "saté", "sate", "curry", "pannetje", "schotel",
    "gerecht", "cocktail", "beslag", "zaad", "zaden", "kiem", "boon", "bonen",
    "noot", "noten", "nootje", "melk", "room", "kaas", "yoghurt", "boter",
    "kwark", "ijs", "vla", "ei", "eieren", "crème", "creme", "spread",
    "beleg", "waren", "waar", "product", "producten", "soort", "nugget",
    "bal", "ballen", "balletje", "rib", "ribben", "ribbetje", "kotelet",
    "karbonade", "bief", "biefstuk", "medaillon", "stoof", "stoofvlees",
    "lever", "nier", "tong", "staart", "wang", "hals", "nek", "schouder",
    "rug", "zadel", "rack", "bil", "buik", "spek", "lende", "tournedos",
    "carpaccio", "paté", "pate", "mousse", "pastei", "terrine", "moot", "moten",
    "fondue", "brie", "lecithine", "eiwit", "isolaat", "brokken", "plakken", "schijven", "stukken", "blokken", "repen", "dijen",
    "kuit", "goulash", "drumstick", "noedel", "noedels", "nest", "nestje",
    "kolf", "zetmeel", "aroma", "extract", "essence", "rozijn", "rozijnen",
    "tosti", "tostie", "pizza", "wrap", "sandwich", "hapje", "snack", "dip",
    "roerbak", "wok", "gyros", "shoarma", "kebab", "saucijs", "gehaktbal",
    "fricandeau", "confit", "rookvlees", "tentakel", "graat", "haring",
}, key=len, reverse=True)
_TAILS_ALT = "|".join(re.escape(t) for t in _TAILS)
_ENDING = r"(?:en|eren|s|n|e|er|je|jes|tje|tjes|etje|etjes|pje|pjes|'s)"

# Achter een dier maakt dit er zuivel of ei van, geen vlees: geitenkaas, kippenei.
DAIRY_TAILS = ("kaas", "melk", "yoghurt", "boter", "room", "kwark", "ei", "eieren")

_SHORT = 4
_WORD_RE = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")


def _is_food_tail(trigger: str, rest: str) -> bool:
    """Is wat achter een korte trigger staat een buiging of een etenswoord?"""
    doubled = re.escape(trigger[-1])
    pattern = rf"(?:{doubled}?{_ENDING})?(?:-?(?:{_TAILS_ALT}){_ENDING}?)*"
    return re.fullmatch(pattern, rest) is not None


def _false_compound(trigger: str, word: str, mapping: dict) -> bool:
    """Begint het woord met de trigger, maar is het iets anders?"""
    if word in COMPOUND_FP or word.endswith(_NEUTRAL_TAILS):
        return True
    not_meant = TRIGGER_FP_PREFIXES.get(trigger)
    if not_meant and word.startswith(not_meant):
        return True
    rest = word[len(trigger):]
    if mapping["_tail_exclude"] and rest.endswith(mapping["_tail_exclude"]):
        return True
    if len(trigger) <= _SHORT:
        # "roombrie": room + nog een trigger van dezelfde categorie.
        return not (_is_food_tail(trigger, rest) or rest in mapping["_trigger_set"])
    return False


# ── Voorbereiden ─────────────────────────────────────────────────────────────

def compile_mapping(name: str, mapping: dict) -> dict:
    """Zet de lijsten van één categorie om in zoekpatronen."""
    triggers = sorted(mapping["triggers"], key=len, reverse=True)
    alternation = "|".join(re.escape(t) for t in triggers)

    # Een uitzondering waar een trigger in zit ("kokosmelk") halen we uit de regel.
    # De rest ("lactosevrij", "ghee") zegt iets over de hele regel.
    mask, whole_line = [], []
    for exc in mapping.get("exceptions", []):
        is_claim = exc.endswith(("vrij", "vrije"))
        contains_trigger = any(t in exc for t in triggers)
        (mask if contains_trigger and not is_claim else whole_line).append(exc)
    mask.sort(key=len, reverse=True)

    return {
        **mapping,
        "_name": name,
        "_trigger_set": frozenset(triggers),
        "_pattern": re.compile(rf"\b({alternation})\b", re.IGNORECASE),
        "_prefix_pattern": re.compile(rf"\b({alternation})", re.IGNORECASE),
        "_line_exceptions": tuple(whole_line),
        # Het hele woord dat met de uitzondering begint: "bloemkool" haalt ook "bloemkoolrijst" weg.
        "_mask": re.compile(r"\b(?:" + "|".join(re.escape(e) for e in mask) + r")\w*") if mask else None,
        "_heads": tuple(sorted(mapping.get("heads", []), key=len, reverse=True)),
        "_compound_skip": tuple(mapping.get("compound_skip", ())),
        "_head_exceptions": frozenset(mapping.get("head_exceptions", ())),
        "_tail_exclude": tuple(mapping.get("tail_exclude", ())),
    }


def _neutralize(text: str, category: str) -> str:
    """Haalt "vegan kaas" weg voor zuivel, "glutenvrije pasta" voor gluten."""
    for before, after, categories in _QUALIFIER_RE:
        if category not in categories:
            continue
        if after.search(text):
            return ""
        text = before.sub(" ", text)
    # "sesamvrij", "ui-vrij", "sulfietvrije rozijnen": de categorie zelf met -vrij.
    text = re.sub(rf"\b{re.escape(category)}-?vrije?\b(?:\s+{_NOUN})?", " ", text)
    return _NEGATION_RE.sub(" ", text)


def _word_at(text: str, position: int) -> str:
    """Het hele woord (met koppeltekens) rond een positie in de tekst."""
    for match in _WORD_RE.finditer(text):
        if match.start() <= position < match.end():
            return match.group(0)
    return ""


def _plant_compound(text: str, start: int, skip: tuple[str, ...]) -> bool:
    """Staat de trigger achter een koppelteken in iets plantaardigs? ("kokos-kwark")"""
    if not skip or start == 0 or text[start - 1] != "-":
        return False
    return _word_at(text, start).startswith(skip)


# ── Zoeken ───────────────────────────────────────────────────────────────────

def find_trigger(normalized: str, mapping: dict, *, substitute: bool = False) -> str | None:
    """Geeft de trigger terug waarop de regel bij deze categorie hoort, of None.

    Met substitute=True is de tekst een vervanger uit onze eigen lijst. Daar is
    "cashew-mascarpone" geen mascarpone maar iets van cashew: van zo'n woord met
    een koppelteken telt alleen het eerste deel.
    """
    if substitute:
        normalized = _WORD_RE.sub(
            lambda m: m.group(0) if "-" not in m.group(0) or m.group(0) in mapping["_trigger_set"]
            else m.group(0).split("-", 1)[0],
            normalized,
        )
    text = _neutralize(normalized, mapping["_name"])
    if not text.strip():
        return None
    if any(exc in text for exc in mapping["_line_exceptions"]):
        return None
    if mapping["_mask"]:
        text = mapping["_mask"].sub(" ", text)

    skip = mapping["_compound_skip"]

    # Stap 1: het hele woord. "kokos-kwark" is geen kwark.
    for match in mapping["_pattern"].finditer(text):
        if _plant_compound(text, match.start(), skip):
            continue
        return match.group(1).lower()

    # Stap 2: het begin van een samenstelling.
    for match in mapping["_prefix_pattern"].finditer(text):
        if _plant_compound(text, match.start(), skip):
            continue
        trigger = match.group(1).lower()
        end = match.end()
        while end < len(text) and (text[end].isalpha() or text[end] in "-'"):
            end += 1
        if _false_compound(trigger, text[match.start():end], mapping):
            continue
        return trigger

    # Stap 3: het eind van een samenstelling.
    heads = mapping["_heads"]
    if heads:
        for word in _WORD_RE.findall(text):
            if word in mapping["_head_exceptions"]:
                continue
            for head in heads:
                if len(word) > len(head) and word.endswith(head):
                    stem = word[: -len(head)].rstrip("-")
                    if skip and stem.startswith(skip):
                        break
                    return head
    return None
