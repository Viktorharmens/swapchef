from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import httpx
from recipe_scrapers import scrape_html
from recipe_scrapers._exceptions import WebsiteNotImplementedError, NoSchemaFoundInWildMode
import re

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
}

app = FastAPI(title="Smart Recipe Substitute API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

# ── Allergen mapping ─────────────────────────────────────────────────────────

ALLERGEN_MAP = {
    "lactose": {
        "triggers": ["melk", "room", "boter", "roomboter", "kaas", "kwark", "yoghurt",
                     "slagroom", "crème fraîche", "creme fraiche", "mascarpone",
                     "mozzarella", "parmezaan", "parmesan", "ricotta", "ghee",
                     "karnemelk", "vla", "pudding", "custard", "ijs",
                     "brie", "camembert", "gorgonzola", "feta", "cheddar",
                     "gouda", "edam", "gruyère", "gruyere", "emmentaler",
                     "pecorino", "burrata", "roomkaas"],
        "alt": "Haver- of soja-alternatief",
        "exceptions": ["kokosmelk", "amandelmelk", "havermelk", "sojamelk",
                       "rijstmelk", "kokosroom", "kokosboter", "lactosevrij",
                       "lactosevrije"],
    },
    "gluten": {
        "triggers": ["bloem", "tarwe", "pasta", "couscous", "paneermeel", "brood",
                     "broodkruimels", "crackers", "rogge", "gerst", "spelt",
                     "bulgur", "semolina", "meel", "macaroni", "spaghetti",
                     "tagliatelle", "fettuccine", "penne", "rigatoni", "fusilli",
                     "linguine", "farfalle", "lasagne", "lasagnebladen", "orzo",
                     "vermicelli", "capellini", "tortellini", "ravioli",
                     "stokbrood", "baguette", "ciabatta", "focaccia", "pistolet",
                     "bagel", "broodje", "beschuit", "knäckebröd", "pitabrood",
                     "pita", "naan", "chapati", "wrap", "croissant", "toast",
                     "boterham", "roggebrood", "pannenkoek", "wafel", "biscuit",
                     "koekje", "koekjes", "cake", "gebak", "muffin",
                     "gnocchi", "dumpling", "gyoza", "bier", "seitan"],
        "alt": "Glutenvrije variant (boekweit/rijst)",
        "exceptions": ["maïsbloem", "rijstbloem", "boekweitbloem", "glutenvrij",
                       "glutenvrije"],
    },
    "noten": {
        "triggers": ["pinda", "cashew", "walnoot", "amandel", "hazelnoot",
                     "pistache", "pecan", "macadamia", "notenboter", "pindasaus",
                     "pindakaas", "notenpasta", "paranoot", "amandelspijs",
                     "marsepein", "praline", "nougat"],
        "alt": "Zonnebloem- of pompoenpitten",
        "exceptions": ["nootmuskaat"],
    },
    "ei": {
        "triggers": ["ei", "eieren", "eigeel", "eiwit", "mayonaise", "mayo",
                     "hollandaisesaus", "bearnaisesaus", "aioli", "meringue",
                     "custard", "lemon curd"],
        "alt": "Lijnzaad-ei (1 el lijnzaad + 3 el water) of aquafaba",
        "exceptions": ["eikenblad"],
    },
    "soja": {
        "triggers": ["soja", "tofu", "tempeh", "miso", "tamari", "edamame",
                     "sojamelk", "sojaroom", "sojasaus", "ketjap", "shoyu",
                     "teriyaki", "yakitori"],
        "alt": "Kokos aminos (voor saus) of kikkererwten (voor tofu)",
        "exceptions": [],
    },
    "schaaldieren": {
        "triggers": ["garnalen", "kreeft", "krab", "langoustine", "scampi",
                     "rivierkreeft", "noordzee garnaal", "gamba", "gamba's", "gambas",
                     "crevetten", "homard", "zeekreeft", "koningskrab", "spinkrab"],
        "alt": "Stukjes witvis of bloemkool",
        "exceptions": [],
    },
    "paprika": {
        "triggers": ["paprika", "paprikapoeder", "paprikapasta", "paprikasaus",
                     "rode paprika", "groene paprika", "gele paprika", "oranje paprika",
                     "chilipoeder", "cayennepeper", "chilivlokken", "harissa",
                     "sriracha", "sambal", "piment", "peperoni"],
        "alt": "Courgette of wortel (voor vulling), kurkuma (voor kleur/poeder)",
        "exceptions": [],
    },
    "ui": {
        "triggers": ["ui", "uien", "uitje", "uitjes", "sjalot", "sjalotten",
                     "bosui", "bosuitje", "lente-ui", "lenteui", "prei",
                     "rode ui", "witte ui", "gele ui", "zilverui",
                     "uienpoeder", "uienpasta"],
        "alt": "Venkel of bleekselderij (voor bite), bieslook (als topping)",
        "exceptions": ["bloemui", "knoflookui"],
    },
    "knoflook": {
        "triggers": ["knoflook", "knoflookteen", "knoflooktenen", "knoflookpoeder",
                     "knoflookpasta", "knoflookolie", "geperste knoflook",
                     "zwarte knoflook", "geroosterde knoflook", "knoflookgranulaat",
                     "aglio"],
        "alt": "Asafoetida (snufje, geeft vergelijkbare diepte) of bieslook",
        "exceptions": [],
    },
    # ── EU-allergenen (aanvullend op de 14 verplichte) ────────────────────────
    "vis": {
        "triggers": ["vis", "zalm", "tonijn", "makreel", "haring", "kabeljauw",
                     "forel", "tilapia", "pangasius", "ansjovis", "sardine",
                     "bot", "zeetong", "schol", "heilbot", "tarbot", "zeebaars",
                     "baars", "paling", "aal", "spiering", "snoekbaars",
                     "vissaus", "worcestershiresaus", "anchovy", "anchovypasta"],
        "alt": "Tofu, jackfruit of bloemkool",
        "exceptions": [],
    },
    "selderij": {
        "triggers": ["selderij", "bleekselderij", "knolselderij",
                     "selderijzaad", "selderijzout", "selderijpoeder"],
        "alt": "Venkel, courgette of pastinaak",
        "exceptions": [],
    },
    "mosterd": {
        "triggers": ["mosterd", "mosterdzaad", "mosterdsaus", "dijonmosterd",
                     "dijon", "mosterdpoeder", "mosterdolie", "mosterdkers",
                     "tafelmosterd", "grove mosterd"],
        "alt": "Mierikswortel of wasabi (minder intensief)",
        "exceptions": [],
    },
    "sesam": {
        "triggers": ["sesam", "sesamzaad", "sesamolie", "tahini", "tahin",
                     "sesampasta", "sesambrood", "gomashio", "halva"],
        "alt": "Zonnebloempitten of lijnzaad",
        "exceptions": [],
    },
    "weekdieren": {
        "triggers": ["inktvis", "pijlinktvis", "octopus", "mossel", "mosselen",
                     "oester", "oesters", "sint-jakobsschelp", "coquille",
                     "wulk", "alikruik", "slak", "abalone", "venusschelp"],
        "alt": "Stevige witvis of champignons",
        "exceptions": [],
    },
    "lupine": {
        "triggers": ["lupine", "lupinebloem", "lupinezaad", "lupinemeel",
                     "lupinepasta"],
        "alt": "Kikkererwten of rijstmeel",
        "exceptions": [],
    },
    "sulfiet": {
        "triggers": ["sulfiet", "sulfieten", "zwaveldioxide", "wijn", "rode wijn",
                     "witte wijn", "porto", "sherry", "wijnazijn",
                     "gedroogde abrikozen", "rozijnen", "sultana's", "krenten"],
        "alt": "Vers alternatief zonder sulfiet (controleer etiket)",
        "exceptions": ["wijnazijn naturel", "balsamicoazijn"],
    },
}

# ── Diet mapping ─────────────────────────────────────────────────────────────

DIET_MAP = {
    "vegetarisch": {
        "triggers": ["vlees", "kip", "kipfilet", "kippenborst", "kippendij", "kippendijfilet"
                     "rund", "rundvlees", "gehakt", "rundergehakt", "biefstuk",
                     "ribeye", "ossenhaas", "entrecote", "tartaar",
                     "varken", "varkensvlees", "varkenshaas", "spek", "ham",
                     "bacon", "worst", "chorizo", "salami", "prosciutto", "pancetta",
                     "lam", "lamsvlees", "lamsrack", "lamsschouder",
                     "kalkoen", "eend", "wild", "konijn", "hert",
                     "vis", "zalm", "tonijn", "makreel", "haring",
                     "kabeljauw", "forel", "tilapia", "pangasius",
                     "garnalen", "kreeft", "krab", "scampi", "langoustine",
                     "ansjovis", "gamba", "gamba's", "gambas", "sardine"],
        "alt": "Tofu, tempeh, jackfruit, seitan of peulvruchten",
        "exceptions": ["bloemkool", "nootmuskaat"],
    },
    "vegan": {
        "triggers": ["vlees", "kip", "kipfilet", "kippenborst", "kippendij",
                     "rund", "rundvlees", "gehakt", "rundergehakt", "biefstuk",
                     "ribeye", "ossenhaas", "entrecote", "tartaar",
                     "varken", "varkensvlees", "varkenshaas", "spek", "ham",
                     "bacon", "worst", "chorizo", "salami", "prosciutto", "pancetta",
                     "lam", "lamsvlees", "lamsrack",
                     "kalkoen", "eend", "wild", "konijn", "hert",
                     "vis", "zalm", "tonijn", "makreel", "haring",
                     "kabeljauw", "forel", "tilapia", "pangasius",
                     "garnalen", "kreeft", "krab", "scampi", "langoustine",
                     "ansjovis", "sardine",
                     "melk", "room", "boter", "kaas", "kwark", "yoghurt",
                     "slagroom", "mascarpone", "mozzarella", "parmezaan", "ricotta",
                     "ei", "eieren", "eigeel", "eiwit", "mayonaise",
                     "honing", "gelatine"],
        "alt": "Plantaardig alternatief (tofu, sojamelk, lijnzaad-ei, agave)",
        "exceptions": ["bloemkool", "nootmuskaat", "kokosmelk", "amandelmelk",
                       "havermelk", "sojamelk", "kokosroom", "kokosboter"],
    },
    "keto": {
        "triggers": ["suiker", "basterdsuiker", "poedersuiker", "rietsuiker",
                     "aardappel", "aardappelen", "friet",
                     "pasta", "spaghetti", "macaroni", "penne", "fusilli",
                     "rijst", "basmatirijst", "zilvervliesrijst",
                     "brood", "boterham", "toast",
                     "bloem", "tarwebloem", "meel",
                     "couscous", "bulgur", "quinoa", "haver", "havermout",
                     "mais", "maïs",
                     "banaan", "druiven", "mango", "ananas", "meloen", "vijg",
                     "honing", "siroop", "ahornsiroop",
                     "bonen", "linzen", "kikkererwten", "erwten",
                     "crackers", "koekje", "koekjes", "cake", "gebak"],
        "alt": "Bloemkool, courgette, selderij, noten, zaden of konjac",
        "exceptions": ["bloemkool", "zoete aardappel"],
    },
    "halal": {
        "triggers": ["varken", "varkensvlees", "varkenshaas", "spek", "ham",
                     "bacon", "worst", "chorizo", "salami", "prosciutto", "pancetta",
                     "alcohol", "wijn", "bier", "rum", "cognac", "whisky",
                     "jenever", "port", "sherry", "marsala", "gelatine"],
        "alt": "Halal-variant of plantaardige gelatine (agar-agar)",
        "exceptions": [],
    },
    "paleo": {
        "triggers": ["tarwe", "rogge", "gerst", "haver", "spelt",
                     "brood", "pasta", "rijst", "couscous", "bulgur",
                     "bonen", "linzen", "kikkererwten", "pinda", "soja",
                     "melk", "room", "kaas", "yoghurt", "kwark",
                     "suiker", "basterdsuiker", "honing", "siroop",
                     "aardappel"],
        "alt": "Groenten, fruit, vlees, vis, noten of zaden",
        "exceptions": ["zoete aardappel", "kokosmelk", "kokosroom",
                       "kokosboter", "amandelmelk"],
    },
    "fodmap": {
        "triggers": [
            # Fructanen (ui-familie & granen)
            "ui", "uien", "uitje", "uitjes", "sjalot", "sjalotten",
            "prei", "lente-ui", "lenteui", "bosui", "knoflook",
            "tarwe", "rogge", "gerst", "couscous", "bulgur",
            # GOS (peulvruchten)
            "bonen", "linzen", "kikkererwten", "erwten", "kidneybonen",
            "bruine bonen", "kapucijners",
            # Lactose
            "melk", "yoghurt", "kwark", "slagroom", "room", "ijs",
            "zachte kaas", "roomkaas", "mascarpone", "ricotta",
            # Fructose & polyolen (fruit)
            "appel", "peer", "mango", "watermeloen", "kers", "kersen",
            "pruim", "pruimen", "perzik", "abrikoos", "vijg", "lychee",
            "honing",
            # Polyolen (groenten & paddenstoelen)
            "champignon", "champignons", "paddenstoel", "paddenstoelen",
            "bloemkool", "avocado",
        ],
        "alt": "Lactosevrije zuivel, rijst, aardappel, wortel, courgette of spinazie",
        "exceptions": ["kokosmelk", "lactosevrij", "harde kaas",
                       "parmezaan", "cheddar"],
    },
}

# ── Request / response models ────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    url: HttpUrl
    user_allergies: list[str]
    user_diets: list[str] = []

class IngredientResult(BaseModel):
    original: str
    is_unsafe: bool
    matched_allergen: str | None
    alternative: str | None
    issue_type: str | None = None  # "allergie" | "dieet"

class AnalyzeResponse(BaseModel):
    recipe_title: str
    total_ingredients: int
    unsafe_count: int
    ingredients: list[IngredientResult]

# ── Allergen checking ────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    return text.lower().strip()


def _check_mapping(normalized: str, key: str, mapping: dict) -> bool:
    """Returns True if the ingredient matches a trigger in the given mapping."""
    is_exception = any(exc in normalized for exc in mapping["exceptions"])
    if is_exception:
        return False
    for trigger in mapping["triggers"]:
        pattern = rf"\b{re.escape(trigger)}\b"
        if re.search(pattern, normalized):
            return True
    return False


def check_ingredient(
    ingredient: str,
    user_allergies: list[str],
    user_diets: list[str] = [],
) -> IngredientResult:
    normalized = _normalize(ingredient)

    for allergen in user_allergies:
        allergen = allergen.lower()
        if allergen not in ALLERGEN_MAP:
            continue
        if _check_mapping(normalized, allergen, ALLERGEN_MAP[allergen]):
            return IngredientResult(
                original=ingredient,
                is_unsafe=True,
                matched_allergen=allergen,
                alternative=ALLERGEN_MAP[allergen]["alt"],
                issue_type="allergie",
            )

    for diet in user_diets:
        diet = diet.lower()
        if diet not in DIET_MAP:
            continue
        if _check_mapping(normalized, diet, DIET_MAP[diet]):
            return IngredientResult(
                original=ingredient,
                is_unsafe=True,
                matched_allergen=diet,
                alternative=DIET_MAP[diet]["alt"],
                issue_type="dieet",
            )

    return IngredientResult(
        original=ingredient,
        is_unsafe=False,
        matched_allergen=None,
        alternative=None,
    )


# ── Endpoint ─────────────────────────────────────────────────────────────────

@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_recipe(body: AnalyzeRequest):
    url = str(body.url)

    try:
        response = httpx.get(url, headers=BROWSER_HEADERS, follow_redirects=True, timeout=15)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Website gaf fout {exc.response.status_code} terug.")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Kon URL niet bereiken: {exc}")

    try:
        scraper = scrape_html(html=response.text, org_url=url, supported_only=False)
    except WebsiteNotImplementedError:
        raise HTTPException(status_code=422, detail="Website wordt niet ondersteund.")
    except NoSchemaFoundInWildMode:
        raise HTTPException(
            status_code=422,
            detail="Kon geen recept-schema vinden op deze pagina.",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Fout bij verwerken recept: {exc}")

    try:
        raw_ingredients: list[str] = scraper.ingredients()
    except Exception:
        raise HTTPException(
            status_code=422, detail="Ingrediëntenlijst kon niet worden uitgelezen."
        )

    if not raw_ingredients:
        raise HTTPException(status_code=422, detail="Geen ingrediënten gevonden.")

    try:
        title = scraper.title() or "Onbekend recept"
    except Exception:
        title = "Onbekend recept"

    results = [check_ingredient(ing, body.user_allergies, body.user_diets) for ing in raw_ingredients]
    unsafe_count = sum(1 for r in results if r.is_unsafe)

    return AnalyzeResponse(
        recipe_title=title,
        total_ingredients=len(results),
        unsafe_count=unsafe_count,
        ingredients=results,
    )


@app.get("/allergens")
def list_allergens():
    return {"allergens": list(ALLERGEN_MAP.keys())}


@app.get("/diets")
def list_diets():
    return {"diets": list(DIET_MAP.keys())}
