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
       allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://swapchef.nl",
        "https://www.swapchef.nl",
    ],
    allow_methods=["POST"],
    allow_headers=["*"],
)

# ── Allergen mapping ─────────────────────────────────────────────────────────

ALLERGEN_MAP = {
    "lactose": {
        "triggers": ["roomboter", "karnemelk", "slagroom", "crème fraîche", "creme fraiche",
                     "mascarpone", "mozzarella", "parmezaan", "parmesan", "pecorino",
                     "ricotta", "roomkaas", "burrata",
                     "brie", "camembert", "gorgonzola", "feta", "cheddar",
                     "gouda", "edam", "gruyère", "gruyere", "emmentaler",
                     "melk", "room", "boter", "kaas", "kwark", "yoghurt",
                     "ghee", "vla", "pudding", "custard", "ijs"],
        "alt": "Plantaardig zuivelalternatief (soja, haver of kokos)",
        "alt_map": {
            "melk":          "Havermelk, sojamelk of amandelmelk",
            "room":          "Kokosroom of haverroom",
            "slagroom":      "Kokosslagroom of plantaardige slagroom (bijv. haver of soja)",
            "boter":         "Plantaardige boter (bijv. Becel) of kokosolie",
            "roomboter":     "Plantaardige boter (bijv. Becel) of kokosolie",
            "ghee":          "Kokosolie of plantaardige boter",
            "yoghurt":       "Sojamelkyoghurt, kokosyoghurt of havermelkyoghurt",
            "kwark":         "Sojakwark of kokosmilk-kwark",
            "mascarpone":    "Cashew-mascarpone of soja-mascarpone",
            "ricotta":       "Tofu-ricotta of cashew-ricotta",
            "crème fraîche": "Kokos crème fraîche of sojaroom",
            "creme fraiche": "Kokos crème fraîche of sojaroom",
            "roomkaas":      "Sojaroomkaas of cashewroomkaas",
            "mozzarella":    "Vegane mozzarella (bijv. op basis van cashew of rijst)",
            "parmezaan":     "Voedingsgist of vegane parmezaan",
            "parmesan":      "Voedingsgist of vegane parmezaan",
            "pecorino":      "Voedingsgist of vegane harde kaas",
            "feta":          "Tofu-feta (tofu met citroensap en zout) of vegane feta",
            "brie":          "Vegane zachte kaas of cashewkaas",
            "camembert":     "Vegane zachte kaas of cashewkaas",
            "gorgonzola":    "Vegane blauwe kaas",
            "cheddar":       "Vegane harde kaas of voedingsgist",
            "gouda":         "Vegane harde kaas of voedingsgist",
            "edam":          "Vegane harde kaas of voedingsgist",
            "gruyère":       "Vegane harde kaas of voedingsgist",
            "gruyere":       "Vegane harde kaas of voedingsgist",
            "emmentaler":    "Vegane harde kaas of voedingsgist",
            "burrata":       "Cashew-burrata of vegane burrata",
            "karnemelk":     "Sojamelk met een scheutje citroensap of azijn",
            "vla":           "Sojavla of havervla",
            "pudding":       "Sojapudding of kokospudding",
            "custard":       "Sojacustard of kokosmilk-custard",
            "ijs":           "Kokosijs, sojaijs of haverijs",
            "kaas":          "Vegane kaas of voedingsgist",
        },
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
        "triggers": [
            # Algemeen
            "vlees", "vleesproduct",
            # Kip & gevogelte
            "kip", "kipfilet", "kippenborst", "kippendij", "kippendijfilet",
            "kipdij", "kipdijen", "kippenbouten", "kippenbout", "kippenpoot",
            "kippenvleugel", "kippenvleugels", "kipvleugel", "kipsate", "kippensate",
            "hele kip", "kalkoen", "kalkoenfilet", "kalkoendij", "kalkoenborst",
            "eend", "eendenborst", "eendenbout", "gans", "parelhoen", "fazant",
            "duif", "kwartel",
            # Rund
            "rund", "rundvlees", "rundergehakt", "gehakt",
            "biefstuk", "ribeye", "rib-eye", "ossenhaas", "entrecote", "tartaar",
            "rosbief", "bavette", "tomahawk", "draadjesvlees", "stoofvlees",
            "sucadelap", "kogelbiefstuk", "contrefilet", "runderhaas",
            "longhaas", "t-bone", "côte de boeuf", "cote de boeuf",
            "runderrib", "runderrollade",
            # Kalf
            "kalf", "kalfsvlees", "kalfsschnitzel", "kalfsfricandeau",
            "kalfsbiefstuk", "kalfsoester", "kalfsrollade", "kalfsschouder",
            "kalfskotelet", "kalfsburger",
            # Varken
            "varken", "varkensvlees", "varkenshaas", "varkensbuik", "buikspek",
            "spek", "speklap", "ham", "bacon", "pancetta", "prosciutto",
            "worst", "braadworst", "rookworst", "metworst", "knakworst",
            "chorizo", "salami", "leverworst", "bloedworst", "frankfurter",
            "karbonade", "schouderkarbonade", "ribkarbonade", "kotelet",
            "spareribs", "sparerib", "pulled pork", "procureur",
            "varkensschouder", "varkensnek", "rollade",
            "gehaktbal", "gehaktballen", "hamburger", "slavink",
            "halfom", "half-om-half",
            # Lam
            "lam", "lamsvlees", "lamsrack", "lamsschouder", "lamsbout",
            "lamskoteletten", "lamsnek", "lamsrib",
            # Wild & overig
            "wild", "wildzwijn", "ree", "hert", "haas", "konijn", "eland",
            "hertenbiefstuk", "hertenstoofvlees",
            # Vis & zeevruchten
            "vis", "zalm", "tonijn", "makreel", "haring", "kabeljauw",
            "forel", "tilapia", "pangasius", "ansjovis", "sardine",
            "garnalen", "kreeft", "krab", "scampi", "langoustine",
            "gamba", "gamba's", "gambas",
            # Orgaanvlees
            "lever", "nieren", "niertjes", "hart", "tong",
        ],
        "alt": "Tofu, tempeh, jackfruit, seitan of peulvruchten",
        "exceptions": ["bloemkool", "nootmuskaat"],
    },
    "vegan": {
        "triggers": [
            # Algemeen
            "vlees", "vleesproduct",
            # Kip & gevogelte
            "kip", "kipfilet", "kippenborst", "kippendij", "kippendijfilet",
            "kipdij", "kipdijen", "kippenbouten", "kippenbout", "kippenpoot",
            "kippenvleugel", "kippenvleugels", "kipvleugel", "kipsate", "kippensate",
            "hele kip", "kalkoen", "kalkoenfilet", "kalkoendij", "kalkoenborst",
            "eend", "eendenborst", "eendenbout", "gans", "parelhoen", "fazant",
            "duif", "kwartel",
            # Rund
            "rund", "rundvlees", "rundergehakt", "gehakt",
            "biefstuk", "ribeye", "rib-eye", "ossenhaas", "entrecote", "tartaar",
            "rosbief", "bavette", "tomahawk", "draadjesvlees", "stoofvlees",
            "sucadelap", "kogelbiefstuk", "contrefilet", "runderhaas",
            "longhaas", "t-bone", "côte de boeuf", "cote de boeuf",
            "runderrib", "runderrollade",
            # Kalf
            "kalf", "kalfsvlees", "kalfsschnitzel", "kalfsfricandeau",
            "kalfsbiefstuk", "kalfsoester", "kalfsrollade", "kalfsschouder",
            "kalfskotelet", "kalfsburger",
            # Varken
            "varken", "varkensvlees", "varkenshaas", "varkensbuik", "buikspek",
            "spek", "speklap", "ham", "bacon", "pancetta", "prosciutto",
            "worst", "braadworst", "rookworst", "metworst", "knakworst",
            "chorizo", "salami", "leverworst", "bloedworst", "frankfurter",
            "karbonade", "schouderkarbonade", "ribkarbonade", "kotelet",
            "spareribs", "sparerib", "pulled pork", "procureur",
            "varkensschouder", "varkensnek", "rollade",
            "gehaktbal", "gehaktballen", "hamburger", "slavink",
            "halfom", "half-om-half",
            # Lam
            "lam", "lamsvlees", "lamsrack", "lamsschouder", "lamsbout",
            "lamskoteletten", "lamsnek", "lamsrib",
            # Wild & overig
            "wild", "wildzwijn", "ree", "hert", "haas", "konijn", "eland",
            "hertenbiefstuk", "hertenstoofvlees",
            # Vis & zeevruchten
            "vis", "zalm", "tonijn", "makreel", "haring", "kabeljauw",
            "forel", "tilapia", "pangasius", "ansjovis", "sardine",
            "garnalen", "kreeft", "krab", "scampi", "langoustine",
            "gamba", "gamba's", "gambas",
            # Orgaanvlees
            "lever", "nieren", "niertjes", "hart", "tong",
            # Zuivel & ei (vegan-specifiek)
                     "mascarpone", "mozzarella", "parmezaan", "ricotta", "slagroom",
                     "melk", "room", "boter", "kaas", "kwark", "yoghurt",
                     "ei", "eieren", "eigeel", "eiwit", "mayonaise",
                     "honing", "gelatine"],
        "alt": "Plantaardig alternatief (tofu, sojamelk, lijnzaad-ei, agave)",
        "alt_map": {
            "melk":      "Havermelk, sojamelk of amandelmelk",
            "room":      "Kokosroom of haverroom",
            "slagroom":  "Kokosslagroom of plantaardige slagroom",
            "boter":     "Plantaardige boter (bijv. Becel) of kokosolie",
            "kaas":      "Vegane kaas of voedingsgist",
            "mozzarella":"Vegane mozzarella (bijv. op basis van cashew)",
            "parmezaan": "Voedingsgist of vegane parmezaan",
            "mascarpone":"Cashew-mascarpone of soja-mascarpone",
            "ricotta":   "Tofu-ricotta of cashew-ricotta",
            "kwark":     "Sojakwark of kokosmilk-kwark",
            "yoghurt":   "Sojamelkyoghurt, kokosyoghurt of havermelkyoghurt",
            "ei":        "Lijnzaad-ei (1 el lijnzaad + 3 el water) of aquafaba",
            "eieren":    "Lijnzaad-ei (1 el lijnzaad + 3 el water) of aquafaba",
            "eigeel":    "Aquafaba of soja-eigeel",
            "eiwit":     "Aquafaba (opgeklopt voor meringue)",
            "mayonaise": "Vegane mayonaise (bijv. op basis van aquafaba)",
            "honing":    "Agavesiroop of ahornsiroop",
            "gelatine":  "Agar-agar (plantaardig geleermiddel)",
        },
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
        "triggers": [
            # Varkensvlees & afgeleide producten
            "varken", "varkensvlees", "varkenshaas", "varkensbuik", "buikspek",
            "spek", "speklap", "ham", "bacon", "pancetta", "prosciutto",
            "worst", "braadworst", "rookworst", "metworst", "knakworst",
            "chorizo", "salami", "leverworst", "bloedworst", "frankfurter",
            "karbonade", "schouderkarbonade", "ribkarbonade", "kotelet",
            "spareribs", "sparerib", "pulled pork", "procureur",
            "varkensschouder", "varkensnek", "slavink", "halfom", "half-om-half",
            # Alcohol
            "alcohol", "wijn", "bier", "rum", "cognac", "whisky",
            "jenever", "port", "sherry", "marsala",
            # Overig niet-halal
            "gelatine", "bloedworst",
        ],
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
    "suikervrij": {
        "triggers": ["suiker", "basterdsuiker", "poedersuiker", "rietsuiker",
                     "bruine suiker", "kristalsuiker", "kandijsuiker",
                     "kokosbloesemsuiker", "palmsuiker", "druivensuiker",
                     "honing", "ahornsiroop", "agave", "agavesiroop",
                     "glucosestroop", "fructosestroop", "maltosestroop",
                     "invertsuiker", "melasse", "golden syrup", "stroop",
                     "frisdrank", "limonade", "vruchtensap", "snoep",
                     "chocolade", "chocola", "nutella", "jam", "gelei",
                     "koekje", "koekjes", "cake", "gebak", "snoepgoed"],
        "alt": "Erythritol, stevia of xylitol als zoetstof",
        "exceptions": ["pure chocolade", "85% chocolade", "suikervrij",
                       "suikervrije", "stevia", "erythritol", "xylitol"],
    },
    "koosjer": {
        "triggers": [
            # Varkensvlees & afgeleide producten
            "varken", "varkensvlees", "varkenshaas", "varkensbuik", "buikspek",
            "spek", "speklap", "ham", "bacon", "pancetta", "prosciutto", "lardo",
            "worst", "braadworst", "rookworst", "metworst", "knakworst",
            "chorizo", "salami", "bloedworst", "frankfurter",
            "karbonade", "schouderkarbonade", "ribkarbonade", "kotelet",
            "spareribs", "sparerib", "pulled pork", "procureur",
            "varkensschouder", "varkensnek", "slavink", "halfom", "half-om-half",
            # Schaaldieren (niet koosjer)
            "garnalen", "kreeft", "krab", "langoustine", "scampi",
            "gamba", "gamba's", "gambas", "crevetten", "homard",
            "zeekreeft", "koningskrab", "rivierkreeft",
            # Weekdieren & overige niet-kosjere vis
            "inktvis", "pijlinktvis", "octopus", "mossel", "mosselen",
            "oester", "oesters", "sint-jakobsschelp", "coquille",
            "wulk", "paling", "aal", "haai",
        ],
        "alt": "Koosjer vlees of plantaardig alternatief",
        "exceptions": [],
    },
    "whole30": {
        "triggers": [
            # Granen
            "tarwe", "rogge", "gerst", "haver", "havermout", "spelt", "rijst",
            "maïs", "mais", "quinoa", "gierst", "teff", "bulgur", "couscous",
            "semolina", "bloem", "meel", "brood", "pasta",
            # Peulvruchten
            "bonen", "linzen", "kikkererwten", "erwten", "pinda", "pindakaas",
            "soja", "tofu", "tempeh", "edamame",
            # Zuivel
            "melk", "room", "kaas", "kwark", "yoghurt", "slagroom",
            "mascarpone", "mozzarella", "parmezaan", "ricotta", "boter",
            "roomboter", "karnemelk",
            # Suiker & zoetstoffen
            "suiker", "basterdsuiker", "honing", "ahornsiroop", "agave",
            "glucosestroop", "fructosestroop", "maltosestroop", "stroop",
            # Alcohol
            "wijn", "bier", "rum", "cognac", "whisky", "jenever", "port",
            "sherry", "marsala",
        ],
        "alt": "Groenten, fruit, vlees, vis, eieren, noten of zaden",
        "exceptions": ["ghee", "kokosmelk", "kokosroom", "kokosboter",
                       "amandelmelk", "havermelk"],
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


def _find_trigger(normalized: str, mapping: dict) -> str | None:
    """Returns the first matched trigger, or None if excepted or no match."""
    is_exception = any(exc in normalized for exc in mapping["exceptions"])
    if is_exception:
        return None
    for trigger in mapping["triggers"]:
        pattern = rf"\b{re.escape(trigger)}\b"
        if re.search(pattern, normalized):
            return trigger
    return None


def _get_alternative(trigger: str, mapping: dict) -> str:
    """Returns trigger-specific alt if available, otherwise the generic alt."""
    return mapping.get("alt_map", {}).get(trigger, mapping["alt"])


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
        trigger = _find_trigger(normalized, ALLERGEN_MAP[allergen])
        if trigger:
            return IngredientResult(
                original=ingredient,
                is_unsafe=True,
                matched_allergen=allergen,
                alternative=_get_alternative(trigger, ALLERGEN_MAP[allergen]),
                issue_type="allergie",
            )

    for diet in user_diets:
        diet = diet.lower()
        if diet not in DIET_MAP:
            continue
        trigger = _find_trigger(normalized, DIET_MAP[diet])
        if trigger:
            return IngredientResult(
                original=ingredient,
                is_unsafe=True,
                matched_allergen=diet,
                alternative=_get_alternative(trigger, DIET_MAP[diet]),
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
