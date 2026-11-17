import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from main import ALLERGEN_MAP, DIET_MAP
from quantities import format_amount, format_number, parse_ingredient
from ratios import RATIOS


@pytest.mark.parametrize("line, amount, amount_max, unit, text, name", [
    ("300 g penne", 300, None, "g", "300 g", "penne"),
    ("200ml kookroom", 200, None, "ml", "200ml", "kookroom"),
    ("1,5 el olijfolie", 1.5, None, "el", "1,5 el", "olijfolie"),
    ("1½ tl zout", 1.5, None, "tl", "1½ tl", "zout"),
    ("½ ui", 0.5, None, None, "½", "ui"),
    ("1/2 citroen", 0.5, None, None, "1/2", "citroen"),
    ("1 1/2 eetlepel honing", 1.5, None, "el", "1 1/2 eetlepel", "honing"),
    ("2-3 tenen knoflook", 2, 3, "teen", "2-3 tenen", "knoflook"),
    ("2 à 3 el sojasaus", 2, 3, "el", "2 à 3 el", "sojasaus"),
    ("2 eieren", 2, None, None, "2", "eieren"),
    ("ca. 100 gram spek", 100, None, "g", "ca. 100 gram", "spek"),
    ("1 blik (400 g) tomatenblokjes", 1, None, "blik", "1 blik", "(400 g) tomatenblokjes"),
    ("1 l melk", 1, None, "l", "1 l", "melk"),
    ("0.5 blokje kippenbouillon", 0.5, None, "blokje", "0.5 blokje", "kippenbouillon"),
    ("2 bouillontabletten", 2, None, None, "2", "bouillontabletten"),
])
def test_parse(line, amount, amount_max, unit, text, name):
    p = parse_ingredient(line)
    assert p.amount == pytest.approx(amount)
    assert p.amount_max == amount_max
    assert (p.unit, p.text, p.name) == (unit, text, name)


@pytest.mark.parametrize("line, unit, text, name", [
    ("snufje komijn", "snuf", "snufje", "komijn"),
    ("Snufje zout", "snuf", "Snufje", "zout"),
    ("een scheutje olijfolie", "scheut", "een scheutje", "olijfolie"),
    ("handje verse basilicum", "handje", "handje", "verse basilicum"),
])
def test_parse_maat_zonder_getal(line, unit, text, name):
    p = parse_ingredient(line)
    assert p.amount is None
    assert (p.unit, p.text, p.name) == (unit, text, name)


@pytest.mark.parametrize("line", ["peper en zout", "sap van 1 citroen", "verse basilicum", "blokjes kaas", "pot pesto", "el olie"])
def test_parse_zonder_getal(line):
    p = parse_ingredient(line)
    assert p.amount is None and p.text is None
    assert p.name == line


@pytest.mark.parametrize("value, expected", [
    (3.0, "3"), (1.5, "1½"), (0.5, "½"), (0.25, "¼"), (2 / 3, "⅔"), (1.3, "1,3"),
])
def test_format_number(value, expected):
    assert format_number(value) == expected


def test_format_amount_met_bereik():
    assert format_amount(2, 3, "el") == "2-3 el"
    assert format_amount(6, None, None) == "6"


def test_elke_verhouding_hoort_bij_een_bestaande_trigger():
    """Een tikfout in ratios.py zou stil niets doen; dit vangt dat af."""
    maps = {**ALLERGEN_MAP, **DIET_MAP}
    for category, spec in RATIOS.items():
        assert category in maps, category
        triggers = set(maps[category]["triggers"]) | set(maps[category].get("alt_map", {}))
        used = set(spec.get("same", [])) | set(spec.get("same_for", {})) | set(spec.get("per_piece", {}))
        assert used <= triggers, f"{category}: onbekend {sorted(used - triggers)}"
