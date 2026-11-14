import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import check_ingredient

# ── Allergenen ────────────────────────────────────────────────────────────────

def test_lactose_melk():
    r = check_ingredient("100 ml volle melk", ["lactose"], [])
    assert r.is_unsafe
    assert r.matched_allergen == "lactose"

def test_lactose_exception_kokosmelk():
    r = check_ingredient("200 ml kokosmelk", ["lactose"], [])
    assert not r.is_unsafe

def test_gluten_pasta():
    r = check_ingredient("200 g spaghetti", ["gluten"], [])
    assert r.is_unsafe

def test_noten_pindakaas():
    r = check_ingredient("2 el pindakaas", ["noten"], [])
    assert r.is_unsafe

def test_noten_exception_nootmuskaat():
    r = check_ingredient("snufje nootmuskaat", ["noten"], [])
    assert not r.is_unsafe

def test_ei():
    r = check_ingredient("2 eieren", ["ei"], [])
    assert r.is_unsafe

def test_vis_zalm():
    r = check_ingredient("150 g verse zalm", ["vis"], [])
    assert r.is_unsafe

def test_schaaldieren_garnalen():
    r = check_ingredient("200 g garnalen", ["schaaldieren"], [])
    assert r.is_unsafe


# ── Diëten ───────────────────────────────────────────────────────────────────

def test_vegetarisch_kipfilet():
    r = check_ingredient("300 g kipfilet", [], ["vegetarisch"])
    assert r.is_unsafe
    assert r.issue_type == "dieet"

def test_vegetarisch_bacon():
    r = check_ingredient("100 g bacon", [], ["vegetarisch"])
    assert r.is_unsafe

def test_vegan_melk():
    r = check_ingredient("200 ml melk", [], ["vegan"])
    assert r.is_unsafe

def test_vegan_honing():
    r = check_ingredient("1 el honing", [], ["vegan"])
    assert r.is_unsafe

def test_halal_spek():
    r = check_ingredient("100 g spek", [], ["halal"])
    assert r.is_unsafe

def test_halal_wijn():
    r = check_ingredient("1 glas rode wijn", [], ["halal"])
    assert r.is_unsafe

def test_keto_aardappel():
    r = check_ingredient("300 g aardappelen", [], ["keto"])
    assert r.is_unsafe

def test_suikervrij_honing():
    r = check_ingredient("2 el honing", [], ["suikervrij"])
    assert r.is_unsafe


# ── Veilige ingrediënten ─────────────────────────────────────────────────────

def test_veilig_olijfolie():
    r = check_ingredient("2 el olijfolie", ["lactose", "gluten", "noten"], ["vegetarisch"])
    assert not r.is_unsafe

def test_veilig_courgette():
    r = check_ingredient("1 courgette", ["lactose", "gluten"], ["vegan", "keto"])
    assert not r.is_unsafe


# ── Hoeveelheden ─────────────────────────────────────────────────────────────

def test_hoeveelheid_wordt_uitgelezen():
    r = check_ingredient("300 g penne", ["gluten"], [])
    assert (r.quantity, r.amount, r.unit, r.name) == ("300 g", 300, "g", "penne")

def test_hoeveelheid_ook_bij_veilig_ingredient():
    r = check_ingredient("2 el olijfolie", ["gluten"], [])
    assert not r.is_unsafe
    assert r.quantity == "2 el"

def test_een_op_een_vervanger_neemt_hoeveelheid_over():
    r = check_ingredient("300 g penne", ["gluten"], [])
    assert r.alternative_quantity == "300 g"
    assert r.ratio == "1 : 1"
    assert r.quantity_note is None

def test_een_op_een_geldt_voor_een_van_de_opties():
    r = check_ingredient("50 g boter", ["lactose"], [])
    assert r.alternative_quantity == "50 g"
    assert r.quantity_note == "Geldt voor plantaardige boter."

def test_eieren_worden_omgerekend_naar_lijnzaad_ei():
    r = check_ingredient("2 eieren", ["ei"], [])
    assert r.alternative_quantity == "2 el gebroken lijnzaad + 6 el water"
    assert "per ei" in r.quantity_note

def test_ei_in_grammen_wordt_niet_omgerekend():
    r = check_ingredient("50 g ei", ["ei"], [])
    assert r.alternative_quantity is None
    assert "per ei" in r.quantity_note

def test_geen_vaste_verhouding_wordt_eerlijk_gemeld():
    r = check_ingredient("2 tenen knoflook", ["knoflook"], [])
    assert r.is_unsafe
    assert r.alternative_quantity is None
    assert r.ratio is None
    assert r.quantity_note == "Geen vaste verhouding bekend."

def test_zonder_getal_blijft_de_verhouding_staan():
    r = check_ingredient("scheutje melk", ["lactose"], [])
    assert r.quantity is None
    assert r.alternative_quantity is None
    assert r.ratio == "1 : 1"

def test_sojasaus_krijgt_geen_tamari_bij_soja_allergie():
    r = check_ingredient("2 el sojasaus", ["soja"], [])
    assert "tamari" not in r.alternative.lower()


def test_bloemkool_is_geen_bloem():
    assert not check_ingredient("1 grote bloemkool, in roosjes", ["gluten"]).is_unsafe
    assert not check_ingredient("200 g bloemkoolrijst", ["gluten"]).is_unsafe
    assert not check_ingredient("500 g bloemige aardappelen", ["gluten"]).is_unsafe


def test_bloem_na_bloemkool_wordt_nog_gevonden():
    result = check_ingredient("1 bloemkool en 2 el tarwebloem", ["gluten"])
    assert result.is_unsafe


def test_reepjes_is_geen_ree():
    assert not check_ingredient("1 rode ui, in dunne reepjes", [], ["vegetarisch"]).is_unsafe
    assert check_ingredient("300 g kipreepjes", [], ["vegetarisch"]).is_unsafe
