import sys
import os
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
