"""Herkenning van ingrediënten: wat moet gemarkeerd worden en wat juist niet.

De lijsten zijn gangbare schrijfwijzen uit Nederlandse recepten. Komt er een
nieuwe misser of een vals alarm binnen, zet hem er dan hier bij.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import (
    _ALL_MAPS,
    ALLERGEN_MAP,
    DIET_MAP,
    alternative_conflicts,
    check_ingredient,
)
from matching import find_trigger

# categorie -> (moet gemarkeerd worden, mag niet gemarkeerd worden), gescheiden door |
CASES = {
 "lactose": ("geitenkaas|schapenkaas|blauwe kaas|roomkaas|kookroom|zure room|volle melk|melkpoeder|geraspte kaas|kruidenboter|crème fraîche|Griekse yoghurt|slagroom|koffiemelk|gecondenseerde melk|mozzarella|halloumi|hüttenkäse|chocolademelk|paneer|wei-eiwit|roomijs|kwark|melkchocolade|witte chocolade|parmezaanse kaas|Parmigiano Reggiano|grana padano|manchego|cottage cheese|skyr|vanillevla|karnemelk|200 gr verse roombrie|300 ml (plantaardige) melk|boter, kokosmelk|kaasblokjes|roomsaus|geitenmelk|boterolie|kaasfondue",
             "pindakaas|kokosmelk|amandelmelk|cacaoboter|boterbonen|leverkaas|ijsbergsla|ijsblokjes|kaasschaaf|plantaardige boter|vegan kaas|100 ml room (plantaardig)|kokos-kwark|sojayoghurt|havermelk|edamame boontjes|paneermeel|lactosevrije melk|boterham|vlaaivorm|notenboter|pindaboter|stroom|sojaroom|kokosroom"),
 "gluten": ("tarwebloem|patentbloem|volkorenmeel|bloem|zelfrijzend bakmeel|paneermeel|panko|broodkruim|ciabatta|tortilla's|wraps|couscous|bulgur|griesmeel|spelt|speltmeel|rogge|gerst|parelgort|sojasaus|ketjap manis|bier|noedels|mie|bami|lasagnebladen|bladerdeeg|filodeeg|pizzadeeg|croutons|beschuit|ontbijtkoek|seitan|havermout|muesli|orzo|gnocchi|tagliatelle|udon|pitabrood|naanbrood|crackers|koekjes|speculaas|eiernoedels|zuurdesembrood|1 bloemkool en 2 el tarwebloem|mienestjes|pannenkoeken",
            "bloemkool|maizena|rijst|rijstnoedels|aardappelen|boekweitmeel|rijstmeel|amandelmeel|maiszetmeel|aardappelzetmeel|glutenvrije pasta|glutenvrij brood|zonnebloemolie|zonnebloempitten|zonnebloem- of pompoenpitten|courgettebloem|glasnoedels|bloemige aardappelen|eetbare bloemen|kikkererwtenmeel|Cakevorm|rijstwafels|kokosmeel"),
 "noten": ("amandelen|amandelmeel|walnoten|hazelnoten|cashewnoten|pecannoten|pistachenoten|pinda's|pindakaas|macadamia|paranoten|notenmix|hazelnootpasta|marsepein|pesto|amandelmelk|satésaus|nougat|praliné|walnootolie|arachideolie|studentenhaver|pindasaus|gemengde noten|borrelnoten|Nutella|handje nootjes",
           "nootmuskaat|kokosnoot|kokosmelk|muskaatnoot|pijnboompitten|kastanjes|notenvrije pasta"),
 "ei": ("eieren|ei|eidooier|eiwit|eigeel|2 eidooiers|mayonaise|eiernoedels|advocaat|meringue|omelet|kwarteleitjes|scharreleieren|gekookt ei|eierkoeken|custard|hollandaisesaus|aioli|3 eitjes|kippenei",
        "aubergine|eikenbladsla|1 eetlepel olie|eigen keuze|eigengemaakte jam|prei|selderij|vegan mayonaise|wei-eiwit|erwteneiwit"),
 "soja": ("sojasaus|tofu|tempeh|edamame|sojabonen|miso|ketjap|tahoe|sojamelk|sojaolie|sojalecithine|tamari|shoyu|sojayoghurt|tofublokjes|misopasta",
          "kokos aminos|kikkererwten|sojavrije saus"),
 "vis": ("zalm|zalmfilet|kabeljauw|tonijn|ansjovis|vissaus|visbouillon|makreel|haring|worcestersaus|sardines|pangasius|schol|tong|forel|surimi|kaviaar|bottarga|dashi|bonitovlokken|4 zalmmoten|witvis|stokvis|visfond|vissticks|botfilet|poon",
         "garnalen|oestersaus|roggebrood|1 pond aardappelen|botersaus|boter|in de lengte gehalveerd|inktvis|viskruiden|aalbessen|postelein|multivitamine"),
 "ui": ("ui|uien|rode ui|sjalotjes|bosui|uienpoeder|prei|gebakken uitjes|lente-ui|uienringen",
        "tomaten uit blik|uitgelekte bonen|maïs (uit blik)|knoflook|uitsteekvorm"),
 "vegetarisch": ("kipfilet|kippendijen|gehakt|rundergehakt|spekjes|ham|bacon|worst|chorizo|gelatine|kippenbouillon|zalm|garnalen|ansjovis|vissaus|lamsvlees|biefstuk|varkenshaas|eendenborst|kalkoenfilet|salami|parmaham|rookworst|oestersaus|worcestersaus|sucadelappen|riblappen|speklappen|shoarmavlees|gyros|kroepoek|tonijn uit blik|mosselen|duivenborst|konijn|hertenbiefstuk|ossenhaas|rosbief|carpaccio|spareribs|kipdrumsticks|leverworst|paté|kalfsfond|visfond|kipreepjes|hamblokjes|kipkerrie|runderlappen|stooflappen|kalfsworst|4 zalmmoten|200 gr (vega)kipstukjes|lamsbout|hamburger",
                 "reepjes paprika|hamburgerbroodjes|kipkruiden|gehaktkruiden|1 kopje rijst|wilde rijst|hartige taart|kikkererwten|eetlepel honing|vegetarische gehakt|vegan kipstukjes|kippenei|geitenkaas|2 kipschnitzels (vega)|gehaktballetjes (vegetarisch)|in de lengte gehalveerd|lamsoor|fijngehakte peterselie|60 gr walnoten (grof gehakt)|vruchtvlees|kokosvlees|1 portie rijst|portobello|1 kopje melk|posten|eigen keuze|plantaardige worst|rogge|wildrijst|geitenmelk|schapenkaas|eendeneieren"),
 "vegan": ("honing|melk|boter|eieren|kaas|gelatine|mayonaise|room|yoghurt|roomboter|ghee|parmezaan|melkchocolade|geitenkaas|kippenei|kookroom|scharreleieren|kipfilet|worcestersaus|lemon curd",
           "kokosmelk|plantaardige boter|vegan kaas|sojamelk|pindakaas|pure chocolade|vegan kipstukjes|ijsbergsla|plantaardige room|havermelk|cacaoboter"),
 "halal": ("spek|varkensvlees|witte wijn|rode wijn|bier|gelatine|rum|cognac|ham|sherry|marsala|port|bacon|chorizo|mirin|sake|amaretto|likeur|rijstwijn|kookwijn|witbier|sinaasappellikeur|spekblokjes|hamreepjes|portwijn|rumrozijnen",
           "kipfilet|rundergehakt|1 portie granola|portobello|gemberbier|alcoholvrij bier|halal worst|vegetarische spekjes|rumoer|spekkoek|hamburgerbroodjes"),
 "fodmap": ("ui|knoflook|melk|appel|kersen|champignons|honing|tarwe",
            "kerstomaten|ijsbergsla|tomaten uit blik|lactosevrije melk|harde kaas|kokosmelk"),
 "keto": ("suiker|pasta|rijst|brood|bloem|aardappelen|honing", "bloemkool|zoete aardappel|Cakevorm"),
}


def _check(category: str, line: str):
    allergies = [category] if category in ALLERGEN_MAP else []
    diets = [category] if category in DIET_MAP else []
    return check_ingredient(line, allergies, diets)


@pytest.mark.parametrize(
    ("category", "line"),
    [(category, line) for category, (must, _) in CASES.items() for line in must.split("|")],
)
def test_wordt_gemarkeerd(category, line):
    assert _check(category, line).is_unsafe, f"{line!r} hoort bij {category}"


@pytest.mark.parametrize(
    ("category", "line"),
    [(category, line) for category, (_, must_not) in CASES.items() for line in must_not.split("|")],
)
def test_wordt_niet_gemarkeerd(category, line):
    result = _check(category, line)
    assert not result.is_unsafe, f"{line!r} is geen {category}"


# ── Vervangers ───────────────────────────────────────────────────────────────

# Bewust: bij FODMAP gaat het om het deel van de plant (het groen van bosui,
# olie waar knoflook in getrokken is), niet om de plant zelf.
EIGEN_CATEGORIE_TOEGESTAAN = {
    ("fodmap", "knoflook"), ("fodmap", "ui"), ("fodmap", "uien"), ("fodmap", "uitje"),
    ("fodmap", "uitjes"), ("fodmap", "sjalot"), ("fodmap", "sjalotten"),
    ("fodmap", "prei"), ("fodmap", "bosui"), ("fodmap", "lente-ui"), ("fodmap", "lenteui"),
}


def _alternatives():
    for category, mapping in _ALL_MAPS.items():
        yield category, "(standaard)", mapping["alt"]
        for trigger, text in mapping.get("alt_map", {}).items():
            yield category, trigger, text


@pytest.mark.parametrize(("category", "trigger", "text"), list(_alternatives()))
def test_vervanger_bevat_niet_wat_hij_vervangt(category, trigger, text):
    """Geen tamari bij een soja-allergie: een vervanger valt nooit zelf onder zijn categorie."""
    if (category, trigger) in EIGEN_CATEGORIE_TOEGESTAAN:
        return
    found = find_trigger(text.lower(), _ALL_MAPS[category], substitute=True)
    assert found is None, f"{category}/{trigger}: {text!r} bevat {found!r}"


@pytest.mark.parametrize(("category", "trigger", "text"), list(_alternatives()))
def test_vervanger_belooft_niets(category, trigger, text):
    lowered = text.lower()
    for word in ("veilig", "gegarandeerd", "bijv. a", "compliant", "-proof"):
        assert word not in lowered, f"{category}/{trigger}: {text!r}"


def test_vervanger_wordt_nagelopen_op_andere_keuzes():
    result = check_ingredient("200 g mascarpone", ["lactose", "noten"], [])
    assert result.matched_allergen == "lactose"
    assert "cashew" in result.alternative.lower()
    assert result.alternative_conflicts == ["noten"]
    assert "noten" in result.conflict_note


def test_geen_waarschuwing_als_vervanger_past():
    result = check_ingredient("100 g kaas", ["lactose"], ["vegan"])
    assert result.also_matched == ["vegan"]
    assert result.alternative_conflicts == []
    assert result.conflict_note is None


def test_ei_vervanger_past_bij_vegan():
    result = check_ingredient("2 eieren", ["ei"], ["vegan"])
    assert result.alternative_conflicts == []


def test_sojamelk_als_vervanger_botst_met_soja():
    result = check_ingredient("500 ml melk", ["lactose", "soja"], [])
    assert result.alternative_conflicts == ["soja"]


def test_alle_keuzes_worden_nagelopen():
    result = check_ingredient("1 el sojasaus", ["gluten", "soja"], [])
    assert result.matched_allergen == "gluten"
    assert result.also_matched == ["soja"]


def test_conflicten_los():
    assert alternative_conflicts("Cashew-mascarpone of soja-mascarpone", ["noten", "soja", "gluten"]) == ["noten", "soja"]
    assert alternative_conflicts("Vegane harde kaas of voedingsgist", ["lactose", "vegan"]) == []


def test_onbekende_keuze_wordt_genegeerd():
    assert not check_ingredient("100 g kaas", ["bestaat-niet"], ["ook-niet"]).is_unsafe
