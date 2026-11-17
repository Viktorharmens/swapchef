import os
from urllib.parse import urljoin, urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, HttpUrl
from recipe_scrapers import scrape_html
from recipe_scrapers._exceptions import (
    NoSchemaFoundInWildMode,
    WebsiteNotImplementedError,
)

from matching import (
    DAIRY_TAILS,
    GLUTEN_FREE_PREFIXES,
    PLANT_PREFIXES,
    compile_mapping,
    find_trigger,
    is_equipment,
)
from quantities import parse_ingredient
from rate_limit import RateLimiter
from ratios import alternative_amount
from safe_fetch import FetchError, fetch_html

SCRAPINGBEE_API_KEY = os.getenv("SCRAPINGBEE_API_KEY")


app = FastAPI(title="Smart Recipe Substitute API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://swapchef.nl",
        "https://www.swapchef.nl",
        "capacitor://localhost",
        "https://localhost",
        "http://localhost",
    ],
    allow_methods=["POST"],
    allow_headers=["*"],
)

# ── Gedeelde lijsten ─────────────────────────────────────────────────────────
# Zuivel en ei gelden voor de allergie én voor vegan; daarom staan ze hier één keer.

_ZUIVEL = [
    "roomboter bladerdeeg", "boter bladerdeeg",
    "roomboter", "karnemelk", "slagroom", "crème fraîche", "creme fraiche",
    "mascarpone", "mozzarella", "parmezaan", "parmesan", "parmigiano", "pecorino",
    "grana padano", "ricotta", "roomkaas", "burrata",
    "brie", "camembert", "gorgonzola", "feta", "cheddar",
    "gouda", "edam", "gruyère", "gruyere", "emmentaler", "manchego",
    "halloumi", "paneer", "cottage cheese", "hüttenkäse", "huttenkase",
    "taleggio", "fontina", "provolone", "stilton", "roquefort", "raclette", "comté",
    "skyr", "kefir", "wei", "weipoeder", "bechamel", "béchamel",
    "witte chocolade", "melkchocolade",
    "melk", "room", "boter", "kaas", "kwark", "yoghurt",
    "ghee", "vla", "pudding", "custard", "ijs",
]
# Samenstellingen die hierop eindigen zijn ook zuivel: geitenkaas, kookroom, kruidenboter.
_ZUIVEL_HEADS = ["kaas", "melk", "room", "boter", "yoghurt", "kwark", "vla"]
# ... behalve deze: geen zuivel, of geen eten.
_ZUIVEL_HEAD_EXCEPTIONS = ["leverkaas", "hoofdkaas", "stroom", "droom", "aroom"]

_EI = [
    "ei", "eieren", "eitje", "eitjes", "eigeel", "eiwit", "eidooier", "eierdooier",
    "kippenei", "scharrelei", "kwartelei", "omelet", "advocaat",
    "mayonaise", "mayo", "hollandaisesaus", "bearnaisesaus", "aioli", "meringue",
    "custard", "lemon curd",
]
_EI_HEADS = ["eieren", "eitjes", "eidooier", "eidooiers"]

# Samenstellingen die hierop eindigen zijn vlees: stooflappen, duivenborst, kalfsworst.
_VLEES_HEADS = ["vlees", "worst", "lappen", "lapjes", "borst"]

# ── Allergen mapping ─────────────────────────────────────────────────────────

ALLERGEN_MAP = {
    "lactose": {
        "triggers": _ZUIVEL,
        "heads": _ZUIVEL_HEADS,
        "head_exceptions": _ZUIVEL_HEAD_EXCEPTIONS,
        "compound_skip": PLANT_PREFIXES,
        "alt": "Plantaardig zuivelalternatief (soja, haver of kokos)",
        "alt_map": {
            "melk":          "Ongezoete havermelk of sojamelk of rijstmelk",
            "room":          "Kokosroom of haverroom",
            "slagroom":           "Kokosslagroom of plantaardige slagroom",
            "boter":              "Plantaardige boter of kokosolie",
            "roomboter":          "Plantaardige boter of kokosolie",
            "roomboter bladerdeeg": "Lactosevrij bladerdeeg of plantaardig bladerdeeg",
            "boter bladerdeeg":   "Lactosevrij bladerdeeg of plantaardig bladerdeeg",
            "ghee":               "Kokosolie of plantaardige boter",
            "yoghurt":       "Kokosyoghurt of sojamelkyoghurt",
            "kwark":         "Sojakwark of kokos-kwark",
            "mascarpone":    "Cashew-mascarpone of soja-mascarpone",
            "ricotta":       "Tofu-ricotta of vegane ricotta",
            "crème fraîche": "Plantaardige crème fraîche (op basis van kokos of soja)",
            "creme fraiche": "Plantaardige crème fraîche (op basis van kokos of soja)",
            "mozzarella":    "Vegane mozzarella op basis van cashewnoten en rijst",
            "parmezaan":     "Edelgistvlokken of vegane parmezaan",
            "parmesan":      "Edelgistvlokken of vegane parmezaan",
            "pecorino":      "Edelgistvlokken of vegane harde kaas",
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
            "burrata":       "Vegane burrata of cashew-burrata",
            "karnemelk":     "Sojamelk met een scheutje citroensap of azijn",
            "vla":           "Sojavla of havervla",
            "pudding":       "Sojapudding of kokospudding",
            "custard":       "Sojacustard of kokoscustard",
            "ijs":           "Kokosijs of sojaijs",
            "kaas":          "Vegane kaas of voedingsgist",
            "roomkaas":      "Vegan spread op basis van amandel of soja",
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
                     "gnocchi", "dumpling", "gyoza", "bier", "seitan",
                     "panko", "tortilla", "griesmeel", "gort", "parelgort", "haver",
                     "havermout", "muesli", "granola", "croutons", "crouton",
                     "noedels", "mie", "bami", "udon", "ramen", "speculaas",
                     "koek", "ontbijtkoek", "bladerdeeg", "filodeeg", "pizzadeeg",
                     "sojasaus", "ketjap", "kecap", "bakmeel", "tarwebloem"],
        # Samenstellingen die hierop eindigen bevatten ook gluten: patentbloem, pitabrood.
        "heads": ["bloem", "meel", "brood", "deeg", "noedels", "koek"],
        "head_exceptions": ["zetmeel"],
        "compound_skip": GLUTEN_FREE_PREFIXES,
        "alt": "Glutenvrije variant (boekweit/rijst)",
        "alt_map": {
            "sojasaus":        "Glutenvrije tamari of kokos aminos (controleer etiket)",
            "ketjap":          "Glutenvrije ketjap of kokos aminos (controleer etiket)",
            "kecap":           "Glutenvrije ketjap of kokos aminos (controleer etiket)",
            "noedels":         "Rijstnoedels of glasnoedels",
            "mie":             "Rijstnoedels of glasnoedels",
            "bami":            "Rijstnoedels of glasnoedels",
            "udon":            "Rijstnoedels of glasnoedels",
            "ramen":           "Rijstnoedels of glasnoedels",
            "haver":           "Glutenvrije haver (controleer etiket)",
            "havermout":       "Glutenvrije havermout (controleer etiket)",
            "panko":           "Glutenvrij paneermeel of fijngemalen maïsvlokken",
            "pasta":           "Glutenvrije maïs- of bruine rijstpasta",
            "spaghetti":       "Glutenvrije spaghetti van maïs of rijst",
            "macaroni":        "Glutenvrije macaroni van maïs of rijst",
            "penne":           "Glutenvrije penne van maïs of rijst",
            "rigatoni":        "Glutenvrije rigatoni of Palmini (harten van palm)",
            "fusilli":         "Glutenvrije fusilli van maïs of rijst",
            "tagliatelle":     "Glutenvrije tagliatelle van rijst of boekweit",
            "fettuccine":      "Glutenvrije fettuccine van rijst",
            "lasagne":         "Glutenvrije lasagnebladen van maïs of rijst",
            "lasagnebladen":   "Glutenvrije lasagnebladen van maïs of rijst",
            "gebakken uitjes": "Glutenvrije gebakken uitjes (gefrituurd in rijstmeel, te vinden bij de toko)",
        },
        "exceptions": ["maïsbloem", "rijstbloem", "boekweitbloem", "glutenvrij",
                       "glutenvrije"],
    },
    "noten": {
        "triggers": ["pinda", "cashew", "walnoot", "amandel", "hazelnoot",
                     "pistache", "pecan", "macadamia", "notenboter", "pindasaus",
                     "pindakaas", "notenpasta", "paranoot", "amandelspijs",
                     "marsepein", "praline", "praliné", "nougat",
                     "noten", "nootjes", "walnoten", "hazelnoten", "paranoten",
                     "saté", "sate", "sateh", "satésaus", "satesaus", "arachide",
                     "studentenhaver", "pesto", "nutella", "gianduja",
                     "frangipane", "amaretti"],
        # walnoten, cashewnoten, een handje paranoten
        "heads": ["noot", "noten", "nootjes"],
        "compound_skip": ("kokos", "muskaat", "tijger"),
        "alt": "Zonnebloem- of pompoenpitten",
        "alt_map": {
            "pesto":        "Notenvrije pesto, bijvoorbeeld met zonnebloempitten (controleer etiket)",
            "saté":         "Saus op basis van zonnebloempasta met kokosmelk en gember",
            "sate":         "Saus op basis van zonnebloempasta met kokosmelk en gember",
            "sateh":        "Saus op basis van zonnebloempasta met kokosmelk en gember",
            "satésaus":     "Saus op basis van zonnebloempasta met kokosmelk en gember",
            "satesaus":     "Saus op basis van zonnebloempasta met kokosmelk en gember",
            "nutella":      "Chocoladepasta zonder noten (controleer etiket)",
            "praliné":      "Gekarameliseerde zonnebloempitten of pompoenpitten",
            "pindakaas":    "Zonnebloempittenpasta of erwtenboter",
            "pindasaus":    "Saus op basis van zonnebloempasta met kokosmelk en gember",
            "notenboter":   "Zonnebloempittenpasta of pompoenpittpasta",
            "notenpasta":   "Zonnebloempittenpasta of pompoenpittpasta",
            "amandelspijs": "Zonnebloemspijs of kokosspijs",
            "marsepein":    "Kokosspijs of zonnebloemspijs als marsepein-alternatief",
            "praline":      "Gekarameliseerde zonnebloempitten of pompoenpitten",
            "nougat":       "Notenvrije nougat op basis van zaden (controleer etiket)",
        },
        "exceptions": ["nootmuskaat"],
    },
    "ei": {
        "triggers": _EI,
        "heads": _EI_HEADS,
        "alt": "Lijnzaad-ei (1 el lijnzaad + 3 el water) of aquafaba",
        "alt_map": {
            "ei":             "Lijnzaad-ei (1 el gebroken lijnzaad + 3 el water, 5 min. laten staan) of aquafaba (3 el per stuk)",
            "eieren":         "Lijnzaad-ei per stuk (1 el lijnzaad + 3 el water) of appelmoes (60 g per stuk) of aquafaba",
            "eigeel":         "Aquafaba of 1 el plantaardige olie voor rijkheid en binding",
            "eiwit":          "Aquafaba (opgeklopt) voor volume of binding",
            "mayonaise":      "Vegane mayonaise",
            "mayo":           "Vegane mayonaise",
            "aioli":          "Knoflookcrème op basis van cashew of olijfolie met knoflookpoeder",
            "hollandaisesaus":"Plantaardige hollandaise op basis van cashew of sojaroom",
            "bearnaisesaus":  "Plantaardige bearnaise op basis van cashew met dragon",
            "meringue":       "Aquafaba-meringue (klop 150ml kikkererwtenvloeistof stijf)",
            "custard":        "Sojacustard of kokoscustard",
            "lemon curd":     "Plantaardige lemon curd op basis van kokosmelk en maïzena",
        },
        "exceptions": ["eikenblad", "wei-eiwit", "wei eiwit", "plantaardig eiwit"],
    },
    "soja": {
        "triggers": ["soja", "tofu", "tofoe", "tahoe", "tempeh", "tempé", "natto", "miso", "tamari", "edamame", "kecap",
                     "sojamelk", "sojaroom", "sojasaus", "ketjap", "shoyu",
                     "teriyaki", "yakitori"],
        "alt": "Kokos aminos (in sauzen) of kikkererwten (in gerechten)",
        "alt_map": {
            "sojamelk":  "Havermelk of rijstmelk",
            "sojaroom":  "Haverroom of kokosroom",
            "sojasaus":  "Kokos aminos",
            "ketjap":    "Kokos aminos als sojavrije ketjap-basis",
            "tofu":      "Stevige blokjes bloemkool of kikkererwten",
            "tempeh":    "Gebakken kikkererwten of gedroogde linzen",
        },
        "exceptions": [],
    },
    "schaaldieren": {
        "triggers": ["garnalen", "kreeft", "krab", "langoustine", "scampi",
                     "rivierkreeft", "noordzee garnaal", "gamba", "gamba's", "gambas",
                     "crevetten", "homard", "zeekreeft", "koningskrab", "spinkrab"],
        "alt": "Hartjes van palm of bloemkoolroosjes voor textuur",
        "alt_map": {
            "garnalen":       "Hartjes van palm of konjac-garnalen voor vergelijkbare textuur",
            "gamba":          "Hartjes van palm of konjac-garnalen voor vergelijkbare textuur",
            "gamba's":        "Hartjes van palm of konjac-garnalen voor vergelijkbare textuur",
            "gambas":         "Hartjes van palm of konjac-garnalen voor vergelijkbare textuur",
            "scampi":         "Hartjes van palm of konjac-garnalen voor vergelijkbare textuur",
            "kreeft":         "Hartjes van palm of stevige champignons (gegrild)",
            "homard":         "Hartjes van palm of stevige champignons (gegrild)",
            "zeekreeft":      "Hartjes van palm of stevige champignons (gegrild)",
            "krab":           "Hartjes van palm of artisjokharten voor vergelijkbare smaak",
            "koningskrab":    "Hartjes van palm of artisjokharten voor vergelijkbare smaak",
            "langoustine":    "Hartjes van palm of bloemkoolroosjes (gebakken in boter)",
        },
        "exceptions": [],
    },
    "paprika": {
        "triggers": ["paprika", "paprikapoeder", "paprikapasta", "paprikasaus",
                     "rode paprika", "groene paprika", "gele paprika", "oranje paprika",
                     "chilipoeder", "cayennepeper", "chilivlokken", "harissa",
                     "sriracha", "sambal", "piment", "peperoni"],
        "alt": "Courgette of wortel (voor vulling), kurkuma (voor kleur/poeder)",
        "alt_map": {
            "paprika":        "Courgette of wortel (vergelijkbare bite en vulling zonder capsaïcine)",
            "rode paprika":   "Courgette of wortel (qua vulling) of rode biet voor kleur",
            "groene paprika": "Courgette of bleekselderij voor vergelijkbare frisheid",
            "gele paprika":   "Courgette of gele courgette voor kleur en mildheid",
            "oranje paprika": "Wortel (geraspte of fijngesneden) voor vergelijkbare zoetheid",
            "paprikapoeder":  "Kurkuma en komijn voor kleur en aardse smaak (zonder capsaïcine)",
            "chilipoeder":    "Kurkuma en zwarte peper voor warmte zonder scherpte",
            "cayennepeper":   "Zwarte peper of gemberpoeder als milde pikante vervanging",
            "harissa":        "Geroosterde tomatenpuree met komijn en koriander (zonder peper)",
            "sambal":         "Gembergarnituur of mierikswortelsaus voor scherpte zonder capsaïcine",
        },
        "exceptions": [],
    },
    "ui": {
        "triggers": ["ui", "uien", "uitje", "uitjes", "sjalot", "sjalotten",
                     "bosui", "bosuitje", "lente-ui", "lenteui", "prei",
                     "rode ui", "witte ui", "gele ui", "zilverui",
                     "uienpoeder", "uienpasta",
                     "pesto", "groene pesto", "rode pesto", "pestosaus",
                     # Bouillon uit een blokje, poeder of pot bevat meestal ui.
                     "bouillon"],
        # kippenbouillon, groentebouillon
        "heads": ["bouillon"],
        "alt": "Venkel of bleekselderij (voor bite), bieslook (als topping)",
        "alt_map": {
            "ui":          "Fijngesneden venkel of bleekselderij (voor bite en zoetheid)",
            "uien":        "Fijngesneden venkel of bleekselderij (voor bite en zoetheid)",
            "uitje":       "Fijngesneden venkel of bleekselderij",
            "uitjes":      "Fijngesneden venkel of bleekselderij",
            "sjalot":      "Fijngesneden venkel of bleekselderij",
            "sjalotten":   "Fijngesneden venkel of bleekselderij",
            "prei":        "Venkelstengels of courgettereepjes",
            "bosui":       "Bieslook (voor vergelijkbare milde smaak)",
            "bosuitje":    "Bieslook",
            "lente-ui":    "Bieslook",
            "lenteui":     "Bieslook",
            "rode ui":     "Fijngesneden venkel of bleekselderij (rode biet voor kleur in salades)",
            "witte ui":    "Fijngesneden venkel of bleekselderij",
            "gele ui":     "Fijngesneden venkel of bleekselderij",
            "zilverui":    "Kleine kappertjes of ingelegde venkel als zoet-zuur alternatief",
            "uienpoeder":  "Asafoetida (snufje) of bleekselderijpoeder",
            "uienpasta":   "Venkelpoeder of bleekselderijpasta",
            "pesto":       "Zelfgemaakt van alleen basilicum, olie en pijnboompitten",
            "groene pesto":"Zelfgemaakt van alleen basilicum, olie en pijnboompitten",
            "rode pesto":  "Zelfgemaakt van alleen zongedroogde tomaten, olie en pijnboompitten",
            "pestosaus":   "Zelfgemaakt van alleen basilicum, olie en pijnboompitten",
            "bouillon":    "Uivrije groentebouillon (lees het etiket) of zelfgetrokken zonder ui",
        },
        "exceptions": ["bloemui", "knoflookui"],
    },
    "knoflook": {
        "triggers": ["knoflook", "knoflookteen", "knoflooktenen", "knoflookpoeder",
                     "knoflookpasta", "knoflookolie", "geperste knoflook",
                     "zwarte knoflook", "geroosterde knoflook", "knoflookgranulaat",
                     "aglio"],
        "alt": "Asafoetida (snufje, geeft vergelijkbare diepte) of bieslook",
        "alt_map": {
            "knoflook":           "Mespuntje Asafoetida (duivelsdrek) of bieslook voor vergelijkbare diepte",
            "knoflookteen":       "Mespuntje Asafoetida of bieslook",
            "knoflooktenen":      "Mespuntje Asafoetida of bieslook",
            "knoflookpoeder":     "Mespuntje Asafoetida of bieslookpoeder",
            "geperste knoflook":  "Mespuntje Asafoetida of bieslook (fijngehakt)",
            "knoflookpasta":      "Asafoetida-pasta of bieslookpasta (knoflookvrij alternatief)",
            "knoflookolie":       "Bieslookolie of neutrale olie met een snufje Asafoetida",
            "zwarte knoflook":    "Donkere miso of balsamico-reductie (voor vergelijkbare zoet-umami diepte)",
            "geroosterde knoflook": "Geroosterde knolselderij met asafoetida voor vergelijkbare aardse zoetheid",
            "knoflookgranulaat":  "Asafoetida-poeder of bieslookpoeder (doseer voorzichtig)",
            "aglio":              "Mespuntje Asafoetida of bieslook als knoflookvrij alternatief",
        },
        "exceptions": [],
    },
    # ── EU-allergenen (aanvullend op de 14 verplichte) ────────────────────────
    "vis": {
        "triggers": [
            # Zoetwatervis
            "forel", "zalm", "snoekbaars", "snoek", "baars", "karper",
            "paling", "aal", "spiering", "meerval", "brasem",
            # Zeevis
            "vis", "kabeljauw", "haring", "makreel", "tonijn", "sardine",
            "ansjovis", "tilapia", "pangasius", "bot", "zeetong", "schol",
            "heilbot", "tarbot", "zeebaars", "griet", "mul", "harder",
            "zeekarper", "zeebarbeel", "wijting", "schelvis", "pollak",
            "leng", "koolvis", "rog", "haai", "zwaardvis", "tongschar",
            "dorade", "zeebrasem", "roodbaars",
            # Gerookt/gezouten
            "gerookte zalm", "gerookte makreel", "gerookte haring",
            "bokking", "rollmops", "ansjovisfilet", "bottarga",
            # Vaak vergeten
            "tong", "poon", "sprot", "zeewolf", "zeeduivel", "kibbeling", "lekkerbek",
            "surimi", "kaviaar", "kuit", "dashi", "bonito", "bonitovlokken", "katsuobushi",
            "worcestersaus", "worcester",
            # Sauzen & pasta's met vis
            "vissaus", "worcestershiresaus", "anchovypasta", "anchovy",
        ],
        # stokvis, tintelvis; inktvis is een weekdier
        "heads": ["vis"],
        "compound_skip": ("inkt", "pijlinkt"),
        "alt": "Stevige tofu, kikkererwten of jackfruit",
        "alt_map": {
            "vissaus":             "Kokos aminos of tamari + een stukje zeewier voor umami",
            "worcestershiresaus":  "Veganistische worcestershiresaus of tamari",
            "ansjovis":            "Kappertjes of gedroogde tomaten voor vergelijkbare umami-diepte",
            "ansjovisfilet":       "Kappertjes of gedroogde tomaten voor vergelijkbare umami-diepte",
            "anchovypasta":        "Kappertjespasta of miso-pasta voor zoute diepte",
            "anchovy":             "Kappertjes of gedroogde tomaten voor vergelijkbare umami-diepte",
            "tonijn":              "Kikkererwten uit blik (vergelijkbare textuur en eiwitgehalte)",
            "zalm":                "Stevige tofu (gemarineerd) of wortelreepjes met rookaroma",
            "gerookte zalm":       "Gemarineerde wortelreepjes met rookaroma en dille",
            "gerookte makreel":    "Gerookte tofu of aubergine met rookaroma",
            "haring":              "Ingelegde augurk of bietjes voor vergelijkbare zure frisheid",
        },
        "exceptions": [],
    },
    "selderij": {
        "triggers": ["selderij", "bleekselderij", "knolselderij",
                     "selderijzaad", "selderijzout", "selderijpoeder"],
        "alt": "Venkel, courgette of pastinaak",
        "alt_map": {
            "bleekselderij":  "Venkelstengels of kohlrabi voor vergelijkbare crunch en frisheid",
            "knolselderij":   "Pastinaak of kohlrabi (vergelijkbare aardse smaak en textuur)",
            "selderijzaad":   "Venkelzaad of lavas (maggiplant)",
            "selderijzout":   "Venkelzout of lavas-poeder met zeezout",
            "selderijpoeder": "Venkelpoeder of gedroogde lavas",
        },
        "exceptions": [],
    },
    "mosterd": {
        "triggers": ["mosterd", "mosterdzaad", "mosterdsaus", "dijonmosterd",
                     "dijon", "mosterdpoeder", "mosterdolie", "mosterdkers",
                     "tafelmosterd", "grove mosterd"],
        "alt": "Mierikswortel of wasabi (minder intensief)",
        "alt_map": {
            "mosterd":      "Mierikswortelpasta of wasabi (voorzichtig doseren, is pittiger)",
            "dijonmosterd": "Mierikswortelpasta of een mespuntje wasabi",
            "dijon":        "Mierikswortelpasta of een mespuntje wasabi",
            "grove mosterd":"Mierikswortelpasta of wasabi (voorzichtig doseren)",
            "mosterdzaad":  "Fijngemalen komijnzaad of gemberpoeder voor pittigheid",
            "mosterdpoeder": "Wasabipoeder of fijngemalen komijn als alternatief",
        },
        "exceptions": [],
    },
    "sesam": {
        "triggers": ["sesam", "sesamzaad", "sesamolie", "tahini", "tahin",
                     "sesampasta", "sesambrood", "gomashio", "halva"],
        "alt": "Zonnebloempitten of lijnzaad",
        "alt_map": {
            "sesam":        "Geroosterde zonnebloempitten of maanzaad als garnering",
            "sesamzaad":    "Geroosterde zonnebloempitten of maanzaad als garnering",
            "sesamolie":    "Geroosterde walnootolie of avocado-olie (rijke smaak zonder sesam)",
            "tahini":       "Zonnebloemzaadpasta of pompoenpittpasta (vergelijkbare romige basis)",
            "tahin":        "Zonnebloemzaadpasta of pompoenpittpasta (vergelijkbare romige basis)",
            "sesampasta":   "Zonnebloemzaadpasta of pompoenpittpasta",
            "sesambrood":   "Brood zonder sesam (bijv. meerzadenbrood zonder sesam, controleer etiket)",
            "gomashio":     "Zeezout met geroosterde zonnebloempitten als sesamvrij kruidenzout",
            "halva":        "Zonnebloemhalva of dadel-notenspijs (controleer etiket op sesamvrij)",
        },
        "exceptions": [],
    },
    "weekdieren": {
        "triggers": ["inktvis", "pijlinktvis", "octopus", "mossel", "mosselen",
                     "oester", "oesters", "sint-jakobsschelp", "coquille",
                     "wulk", "alikruik", "slak", "abalone", "venusschelp"],
        "alt": "Champignons, hartjes van palm of stevige tofu",
        "alt_map": {
            "inktvis":          "Hartjes van palm of champignonreepjes (voor vergelijkbare textuur)",
            "pijlinktvis":      "Hartjes van palm of champignonreepjes (voor vergelijkbare textuur)",
            "octopus":          "Champignonpoten of stevige tofu (gegrild)",
            "mossel":           "Champignons in kruidenbouillon of zeewier-champignonmix",
            "mosselen":         "Champignons in kruidenbouillon of zeewier-champignonmix",
            "oester":           "Oesterzwam (vergelijkbare naam én textuur) of champignon",
            "oesters":          "Oesterzwam (vergelijkbare naam én textuur) of champignon",
            "sint-jakobsschelp":"Dikke plakken bleekselderij of bloemkoolroosjes (gebakken in boter)",
            "coquille":         "Dikke plakken bleekselderij of bloemkoolroosjes (gebakken in boter)",
        },
        "exceptions": [],
    },
    "lupine": {
        "triggers": ["lupine", "lupinebloem", "lupinezaad", "lupinemeel",
                     "lupinepasta"],
        "alt": "Kikkererwten of rijstmeel",
        "alt_map": {
            "lupinebloem":  "Rijstmeel of boekweitmeel (voor vergelijkbare textuur in bakken)",
            "lupinemeel":   "Rijstmeel of boekweitmeel (voor vergelijkbare textuur in bakken)",
            "lupinezaad":   "Kikkererwten of groene linzen (vergelijkbare eiwitrijke peulvrucht)",
            "lupinepasta":  "Rijstpasta of kikkererwtenspasta (eiwitrijk)",
        },
        "exceptions": [],
    },
    "sulfiet": {
        "triggers": ["sulfiet", "sulfieten", "zwaveldioxide", "wijn", "rode wijn",
                     "witte wijn", "porto", "sherry", "wijnazijn",
                     "gedroogde abrikozen", "rozijnen", "sultana's", "krenten"],
        "alt": "Vers alternatief zonder sulfiet (controleer etiket)",
        "alt_map": {
            "wijn":              "Verjus (ongerijpt druivensap) of druivensap zonder additieven",
            "rode wijn":         "Granaatappelsap of druivensap (rood) als sulfietvrij alternatief",
            "witte wijn":        "Verjus of water met een extra kneepje citroensap (voor friszure diepte)",
            "porto":             "Granaatappelsap of sulfietvrije portostijl-druivensap",
            "sherry":            "Appelsap of verjus",
            "gedroogde abrikozen": "Verse abrikozen of sulfietvrije gedroogde abrikozen (onzwaveld, controleer etiket)",
            "rozijnen":          "Verse druiven (gehalveerd) of sulfietvrije rozijnen",
        },
        "exceptions": ["wijnazijn naturel", "balsamicoazijn"],
    },
}

# ── Gedeelde vlees- en vislijsten ────────────────────────────────────────────

_VLEES = [
    # Algemeen
    "vlees", "vleesje", "vleesjes", "vleesproduct", "vleesproducten",
    "vleesgerecht", "vleessoort", "vleessoorten", "vleeswaar", "vleeswaren",
    "gegrild vlees", "gebraden vlees", "gestoofd vlees",
    # Kip & gevogelte
    "kip", "kipje", "kipjes", "kippen",
    "kipfilet", "kipfilets", "kipfiletstukje", "kipfiletstukjes",
    "kippenborst", "kippenborstje", "kippenborstjes", "kipborst",
    "kippendij", "kippendijen", "kippendijfilet", "kippendijfilets",
    "kipdij", "kipdijen", "kipdijfilet", "kipdijfilets",
    "kippenbouten", "kippenbout", "kippenboutje", "kippenboutjes",
    "kippenpoot", "kippenpootje", "kippenpootjes",
    "kippenvleugel", "kippenvleugels", "kippenvleugeltje", "kippenvleugeltjes",
    "kipvleugel", "kipvleugels", "kipvleugeltje", "kipvleugeltjes",
    "kipsate", "kippensate", "kipsateetje", "kipsaté",
    "hele kip", "halve kip",
    "kipkluif", "kipkluifjes",
    "kipstukje", "kipstukjes",
    "kippenhap", "kippenhapjes",
    "kipnuggets", "kip nuggets", "chicken nuggets",
    "chicken", "chicken breast", "chicken thigh",
    "popcorn chicken", "crispy chicken",
    # Kalkoen
    "kalkoen", "kalkoentje", "kalkoenen",
    "kalkoenfilet", "kalkoenfilets",
    "kalkoendij", "kalkoendijen",
    "kalkoenborst", "kalkoenborstje",
    "kalkoengehakt",
    "kalkoenrollade",
    # Overig gevogelte
    "eend", "eendje", "eenden",
    "eendenborst", "eendenborstje",
    "eendenbout", "eendenboutje",
    "eendenvet", "confit de canard",
    "gans", "ganzenborst", "ganzenvet",
    "parelhoen", "fazant", "duif", "kwartel", "kwarteltje",
    "struisvogel", "struisvogelfilet",
    "guinea fowl",
    # Rund
    "rund", "rundvlees",
    "gehakt", "gehaktje",
    "rundergehakt",
    "biefstuk", "biefstukje", "biefstukjes",
    "ribeye", "rib-eye", "ribeyesteak",
    "ossenhaas", "ossenhaasje",
    "entrecote", "entrecôte",
    "tartaar", "tartaartje",
    "rosbief", "rosbiefje",
    "bavette",
    "tomahawk", "tomahawksteak",
    "draadjesvlees",
    "stoofvlees", "stoofvleesje",
    "sucadelap", "sucadelapje", "sucadelappen",
    "kogelbiefstuk",
    "contrefilet",
    "runderhaas",
    "longhaas",
    "t-bone", "t-bone steak", "tbone",
    "côte de boeuf", "cote de boeuf",
    "runderrib", "runderribben",
    "runderrollade",
    "rundersteak", "steakje",
    "brisket", "runderborst",
    "flank steak", "flanksteak",
    "flat iron", "flat iron steak",
    "picanha",
    "hanger steak",
    "chuck",
    "runderburger", "runderburgertje",
    "ox cheek", "wangvlees", "runderwang",
    # Kalf
    "kalf", "kalfje", "kalveren",
    "kalfsvlees",
    "kalfsschnitzel",
    "kalfsfricandeau",
    "kalfsbiefstuk", "kalfsbiefstukje",
    "kalfsoester",
    "kalfsrollade",
    "kalfsschouder",
    "kalfskotelet", "kalfskoteletten",
    "kalfsburger",
    "kalfswang", "kalfswangen",
    "kalfsgehakt",
    "kalfsstoofvlees",
    "veal",
    # Varken
    "varken", "varkentje", "varkens",
    "varkensvlees",
    "varkenshaas", "varkenshaasje",
    "varkensbuik", "varkensbuikje",
    "buikspek", "buikspekje",
    "spek", "spekje", "spekjes",
    "speklap", "speklapje", "speklappen",
    "spekreepjes", "spekreepje",
    "spekkubus", "spekkubusjes",
    "gerookt spek",
    "ham", "hammetje", "hammetjes",
    "hamreepje", "hamreepjes",
    "hamblok",
    "gekookte ham", "gerookte ham",
    "parmaham", "serranoham", "bayonneham", "kookham", "rookham",
    "landham", "boerenham", "achterham", "voorham",
    "bacon", "baconreepje", "baconreepjes", "baconblokjes",
    "pancetta",
    "prosciutto", "prosciutto crudo", "prosciutto cotto",
    "mortadella",
    "coppa", "bresaola",
    "worst", "worstje", "worstjes",
    "braadworst", "braadworstje",
    "rookworst", "rookworstje",
    "metworst",
    "knakworst", "knakworstje", "knakworstjes",
    "chorizo", "chorizoslice",
    "salami", "salamislice", "salamiplak",
    "leverworst", "leverworstje",
    "bloedworst",
    "frankfurter", "frankfurterworst",
    "hotdog", "hot dog", "hotdogworst",
    "wiener", "wienertje",
    "cervelaat",
    "pepperoni",
    "karbonade", "karbonaadje", "karbonaadjes",
    "schouderkarbonade",
    "ribkarbonade",
    "kotelet", "koteletten",
    "spareribs", "sparerib", "spareribbetje",
    "babyback ribs", "baby back ribs",
    "pulled pork",
    "procureur",
    "varkensschouder", "varkensschouderlapje",
    "varkensnek",
    "rollade", "rolladetje",
    "gehaktbal", "gehaktballetje", "gehaktballen", "gehaktballetjes",
    "hamburger", "hamburgertje",
    "slavink", "slavinkje", "slavinkjes",
    "halfom", "half-om-half",
    "frikandel", "frikandellen", "frikadel",
    "kroket", "kroketten",
    "saucijs", "saucijsje", "saucijsjes",
    "lardo",
    "guanciale",
    "pork belly", "pork chop", "pork loin",
    # Lam & schaap
    "lam", "lammetje", "lammeren",
    "lamsvlees",
    "lamsgehakt",
    "lamsrack", "lamsrackje",
    "lamsschouder",
    "lamsbout", "lamsboutje",
    "lamskoteletten", "lamskotelet",
    "lamsnek",
    "lamsrib", "lamsribben",
    "lamsbiefstuk",
    "schaap", "schapenvlees",
    "mutton", "lamb",
    "lamsrollade",
    "lamsfilet",
    # Geit
    "geit", "geitenvlees", "geitje",
    # Wild
    "wild",
    "wildzwijn", "wildzwijngehakt", "wildzwijnfilet",
    "ree", "reefilet", "reebiefstuk",
    "hert", "hertenvlees", "hertenbiefstuk", "hertenstoofvlees",
    "hertenrug", "hertenfilet",
    "haas", "hazenpeper", "hazenrug",
    "konijn", "konijntje", "konijnenrug", "konijnenbouten",
    "eland", "rendier",
    "wild zwijn",
    "fazantenborst",
    "everzwijn",
    # Orgaanvlees & slachtafval
    "lever", "levertje",
    "nieren", "niertjes", "nier",
    "runderhart", "kalfshart", "varkenshart", "kippenhart", "kippenhartjes", "eendenhart",
    "tong", "tongpunt",
    "zwezerik",
    "hersenen",
    "pens", "pensje",
    "ossenstaart", "ossenstaartje",
    "hoofdkaas",
    "mergpijp",
    # Verwerkte producten
    "schnitzel", "schnitzels", "schnitzeltje",
    "cordon bleu", "cordon-bleu",
    "kipschnitzel", "kalkoenSchnitzel",
    "gehaktschijf",
    "vleesbrood",
    "paté", "pate", "paté de campagne",
    "rillettes",
    "terrine",
    "steak haché",
]

_VIS = [
    # Algemeen
    "vis", "visje", "visjes", "vissen",
    "visgerecht", "vissoort", "visproduct", "visproducten",
    "zeevruchten", "seafood",
    "filet", "visfilet", "visfiletje",
    # Zoetwatervis
    "forel", "foreltje", "regenboogforel", "beekforel",
    "zalm", "zalmfilet", "zalmsteak", "zalmstukje",
    "snoekbaars", "snoek",
    "baars", "baarsfilet",
    "karper",
    "paling", "palingetje", "gerookte paling",
    "aal", "aaltje",
    "spiering",
    "meerval",
    "brasem",
    "winde",
    "blankvoorn",
    "kolblei",
    "pos",
    # Zeevis — wit
    "kabeljauw", "kabeljauwfilet", "kabeljauwsteak",
    "wijting", "wijtingfilet",
    "schelvis", "schelvisfilet",
    "pollak", "pollakfilet",
    "koolvis", "koolvisfilet",
    "leng",
    "heilbot", "heilbotfilet",
    "tarbot",
    "griet",
    "bot", "botfilet",
    "zeetong", "tongfilet",
    "schol", "scholfilet",
    "tongschar",
    "zeebaars", "zeebaarsfilet",
    "mul", "mulfilet",
    "harder",
    "dorade", "zeebrasem",
    "roodbaars", "roodbaarfilet",
    "zeekarper",
    "zeebarbeel",
    "pangasius", "pangasiusfilet",
    "tilapia", "tilapiafilet",
    "wolfsbaars",
    # Zeevis — vet/blauw
    "haring", "haringetje", "maatjesharing", "maatjes",
    "makreel", "makreelfilet",
    "tonijn", "tonijnsteak", "tonijnfilet",
    "sardine", "sardinetje", "sardientje",
    "ansjovis", "ansjovisfilet",
    "sprot",
    "pilchard",
    "bonito",
    # Exotisch & bijzonder
    "rog", "rogvleugel",
    "haai", "haaienvin",
    "zwaardvis", "zwaardvisfilet",
    "barracuda",
    "mahi-mahi", "mahi mahi",
    "snapper", "rode snapper",
    "grouper",
    "wahoo",
    "amberjack",
    "zeewolf",
    "lotte", "zeeduivel",
    "monkfish",
    # Gerookt / gezouten / geconserveerd
    "gerookte zalm", "gerookte zalmfilet",
    "gerookte makreel",
    "gerookte haring",
    "gerookte forel",
    "bokking",
    "rollmops",
    "gezouten haring",
    "gravad lax", "gravlax",
    "lox",
    "gedroogde vis", "stockvis", "klipvis", "bacalao",
    # Sauzen & pasta's met vis
    "vissaus", "fish sauce",
    "worcestershiresaus", "worcestershire",
    "anchovypasta", "anchovy", "anchovies",
    "garnalencocktail", "krabbensalade",
    "vispasta", "visspread",
    "tarama", "taramasalata",
    # Schaaldieren
    "garnaal", "garnalen", "garnaaltje", "garnaaltjes",
    "grijze garnaal", "roze garnaal", "tijgergarnaal",
    "noordzeegarnaal",
    "kreeft", "zeekreeft",
    "rivierkreeft",
    "homard",
    "krab", "krabpoot", "krabstick", "krabvlees",
    "koningskrab", "sneeuwkrab",
    "scampi", "scampispies",
    "langoustine", "langoustines",
    "langoustine staart",
    "gamba", "gamba's", "gambas",
    "crevetten",
    "zijdegarnaal",
    "mantis garnaal",
    "lobster",
    "prawn", "shrimp",
    # Weekdieren — tweekleppigen
    "mossel", "mosselen", "mosseltje", "mosseltjes",
    "oester", "oesters", "oestertje",
    "kokkel", "kokkels",
    "venusschelp", "venusschelpen",
    "sint-jakobsschelp", "sint jakobsschelp", "coquille", "coquilles",
    "tapijtschelp",
    "mesheft", "mesheften",
    "zwaardschede",
    "clam", "clams",
    # Weekdieren — koppotigen
    "inktvis", "inktvissen", "inktvistentakel",
    "calamari", "calamares",
    "pijlinktvis",
    "octopus", "octopuspoot",
    "sepia", "zeekat",
    "squid",
    # Weekdieren — slakken
    "zeeslak",
    "alikruik",
    "abalone",
    # Sushi & Japanse context
    "sashimi",
    "nigiri",
    "maki",
    "temaki",
    "unagi",
    "ikura",
    "tobiko",
    "kuit", "viskuit", "kaviaar", "caviar",
    "lumpviskaviaar",
]

# ── Diet mapping ─────────────────────────────────────────────────────────────

DIET_MAP = {
    "vegetarisch": {
        "triggers": _VLEES + _VIS + [
            "kippenbouillon", "runderbouillon", "vleesbouillon", "visbouillon",
            "gelatine", "worcestersaus", "worcester", "kroepoek", "gyros",
            "shoarma", "kebab", "döner", "carpaccio", "riblap", "riblappen",
            "duivenborst", "dashi", "bonitovlokken", "surimi",
        ],
        "heads": _VLEES_HEADS,
        "compound_skip": PLANT_PREFIXES,
        # geitenkaas en kippenei zijn geen vlees
        "tail_exclude": DAIRY_TAILS,
        "alt": "Tofu, tempeh, jackfruit, seitan of peulvruchten",
        "alt_map": {
            "kip":              "Vegan kipstukjes of grote stukken oesterzwam",
            "kipfilet":         "Vegan kipstukjes of stevige blokjes tofu",
            "kipfilets":        "Vegan kipstukjes of stevige blokjes tofu",
            "spek":             "Gerookte tofu-blokjes of vegan spekreepjes",
            "spekreepjes":      "Gerookte tofu-blokjes of vegan spekreepjes",
            "spekreepje":       "Gerookte tofu-blokjes of vegan spekreepje",
            "kippenbouillon":   "Krachtige groentebouillon (of zelfgetrokken van ui, wortel en selderij)",
            "runderbouillon":   "Krachtige groentebouillon met een scheutje sojasaus voor diepte",
            "vleesbouillon":    "Groentebouillon versterkt met miso of sojasaus",
            "gelatine":         "Agar-agar of pectine",
            "worcestersaus":    "Vegetarische worcestersaus (zonder ansjovis) of sojasaus",
            "worcester":        "Vegetarische worcestersaus (zonder ansjovis) of sojasaus",
            "garnalen":         "Koningsoesterzwammen (in schijfjes, voor vergelijkbare textuur) of vegan garnalen",
            "gamba":            "Koningsoesterzwammen of vegan garnalen",
            "gamba's":          "Koningsoesterzwammen of vegan garnalen",
            "gambas":           "Koningsoesterzwammen of vegan garnalen",
        },
        "exceptions": [
            "bloemkool", "nootmuskaat",
            # "gehakt" als bereidingswijze (fijnsnijden), niet als vleessoort
            "grof gehakt", "fijn gehakt", "fijngehakt", "middelfijn gehakt",
        ],
    },
    "vegan": {
        "triggers": _VLEES + _VIS + _ZUIVEL + _EI + [
            "honing", "gelatine",
            # Bouillon en sauzen op basis van vlees of vis
            "kippenbouillon", "runderbouillon", "vleesbouillon", "visbouillon",
            "worcestersaus", "worcester", "kroepoek", "gyros", "shoarma", "kebab",
            "döner", "carpaccio", "riblap", "riblappen", "duivenborst", "dashi",
            "bonitovlokken", "surimi",
        ],
        "heads": _VLEES_HEADS + _ZUIVEL_HEADS + _EI_HEADS,
        "head_exceptions": _ZUIVEL_HEAD_EXCEPTIONS,
        "compound_skip": PLANT_PREFIXES,
        "alt": "Plantaardig alternatief (tofu, sojamelk, lijnzaad-ei, agave)",
        # Zuivel: dezelfde vervangers als bij lactose, met hieronder alleen wat bij vegan anders is.
        "alt_map": {
            **ALLERGEN_MAP["lactose"]["alt_map"],
            "melk":          "Havermelk, sojamelk of amandelmelk",
            "roomboter bladerdeeg": "Plantaardig bladerdeeg",
            "boter bladerdeeg":   "Plantaardig bladerdeeg",
            "ijs":           "Kokosijs, sojaijs of haverijs",
            "roomkaas":      "Vegan roomkaas naturel op basis van soja of kokosolie",
            "kip":           "Vegan kipstukjes of oesterzwam",
            "kipfilet":      "Vegan kipstukjes of stevige tofu",
            "kipfilets":     "Vegan kipstukjes of stevige tofu",
            "ei":            "Lijnzaad-ei (1 el lijnzaad + 3 el water) of aquafaba",
            "eieren":        "Lijnzaad-ei (1 el lijnzaad + 3 el water) of aquafaba",
            "eigeel":        "Aquafaba of soja-eigeel",
            "eiwit":         "Aquafaba (stijfgeklopt)",
            "mayonaise":     "Vegane mayonaise",
            "honing":           "Agavesiroop of ahornsiroop",
            "gelatine":         "Agar-agar",
            "gehakt":           "Vegan gehakt op basis van soja of erwten of linzenballetjes",
            "rundergehakt":     "Vegan gehakt op basis van soja of erwten of gekruide linzen",
            "kippenbouillon":   "Krachtige groentebouillon (of zelfgetrokken van ui, wortel en selderij)",
            "runderbouillon":   "Krachtige groentebouillon met een scheutje sojasaus of miso voor diepte",
            "vleesbouillon":    "Groentebouillon versterkt met miso of sojasaus",
        },
        "exceptions": [
            "bloemkool", "nootmuskaat", "kokosmelk", "amandelmelk",
            "havermelk", "sojamelk", "kokosroom", "kokosboter",
            # "gehakt" als bereidingswijze (fijnsnijden), niet als vleessoort
            "grof gehakt", "fijn gehakt", "fijngehakt", "middelfijn gehakt",
        ],
    },
    "keto": {
        "triggers": ["suiker", "basterdsuiker", "poedersuiker", "rietsuiker",
                     "aardappel", "aardappelen", "friet",
                     "pasta", "spaghetti", "macaroni", "penne", "fusilli",
                     "rigatoni", "tagliatelle", "fettuccine", "lasagne", "lasagnebladen",
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
        "alt_map": {
            "rijst":        "Bloemkoolrijst of broccolirijst",
            "basmatirijst": "Bloemkoolrijst of broccolirijst",
            "pasta":        "Courgetti (courgette-slierten) of pompoenspaghetti",
            "spaghetti":    "Courgetti (courgette-slierten) of pompoenspaghetti",
            "macaroni":     "Bloemkoolroosjes of konjac-macaroni",
            "penne":        "Courgette-stukjes of konjac-pasta",
            "fusilli":      "Courgetti of konjac-pasta",
            "rigatoni":     "Courgette-rollen (dikke plakken courgette) of Palmini (harten van palm)",
            "tagliatelle":  "Courgetti of palmini-linten",
            "fettuccine":   "Courgetti of palmini-linten",
            "lasagne":      "Plakken courgette of aubergine als lasagnebladen",
            "lasagnebladen":"Plakken courgette of aubergine als lasagnebladen",
            "bloem":        "Amandelmeel of lupinemeel (niet geschikt voor alle recepten)",
            "meel":         "Amandelmeel of kokosmeel",
            "mango":        "Avocado (voor romigheid) of kokoschunks (voor zoetheid)",
            "banaan":       "Avocado (in smoothies) of bevroren bloemkool met vanille",
            "aardappel":    "Knolselderij of bloemkool (gestoofd of geprakt)",
            "aardappelen":  "Knolselderij of bloemkool (gestoofd of geprakt)",
        },
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
            "mirin", "sake", "likeur", "amaretto", "wodka", "vodka", "gin",
            "brandy", "calvados", "vermout", "prosecco", "champagne", "cava",
            "cider", "kirsch", "limoncello", "tequila", "madeira",
            # Overig niet-halal
            "gelatine", "bloedworst",
        ],
        # rijstwijn, kookwijn, witbier, sinaasappellikeur; gemberbier is fris
        "heads": ["wijn", "likeur", "bier"],
        "compound_skip": ("gember", "wortel"),
        "tail_exclude": DAIRY_TAILS,
        "alt": "Halal-variant of plantaardige gelatine (agar-agar)",
        "alt_map": {
            "spek":       "Halal kippenspek of gerookte kalkoenreepjes",
            "speklap":    "Halal kippenspek of gerookte kalkoenreepjes",
            "bacon":      "Halal kippenspek of gerookte kalkoenreepjes",
            "ham":        "Halal kippenham of kalkoenborstplakken",
            "prosciutto": "Halal kalkoenprosciutto of gerookte kipfiletplakken",
            "pancetta":   "Halal kalkoenspek of kippenspek",
            "worst":      "Halal worst (bijv. kalkoenrookworst of kipworst)",
            "rookworst":  "Halal rookworst (bijv. kalkoenrookworst)",
            "knakworst":  "Halal knakworst van kip of kalkoen",
            "chorizo":    "Halal kippenchorizo of lamsworst met paprika en kruiden",
            "salami":     "Halal salami van kip of kalkoen",
            "wijn":       "Alcoholvrije wijn of druivensap",
            "rode wijn":  "Alcoholvrije rode wijn of granaatappelsap",
            "witte wijn": "Alcoholvrije witte wijn of appelsap",
            "bier":       "Alcoholvrij bier of gevogeltebouillon",
            "gelatine":   "Agar-agar of pectine (fruit)",
        },
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
        "alt_map": {
            "aardappel":   "Zoete aardappel, knolselderij of pastinaak",
            "aardappelen": "Zoete aardappel, knolselderij of pastinaak",
            "rijst":       "Bloemkoolrijst of pompoenblokjes",
            "pasta":       "Courgetti (courgette-slierten) of palmini (harten van palm)",
            "spaghetti":   "Courgetti (courgette-slierten) of pompoenspaghetti",
            "brood":       "Sla als wrap of paleo-brood van cassavemeel",
            "bloem":       "Amandelsmeel, kokosmeel of cassavemeel",
            "meel":        "Amandelsmeel, kokosmeel of cassavemeel",
            "melk":        "Kokosmelk of amandelmelk (ongezoet)",
            "room":        "Kokosroom of cashewroom",
            "yoghurt":     "Kokosyoghurt (ongezoet) of cashew-yoghurt",
            "kaas":        "Cashewkaas of voedingsgist voor smaak",
            "kwark":       "Kokosyoghurt (dik, ongezoet) of cashewcrème",
            "honing":      "Ahornsiroop of dadelstroop (in kleine hoeveelheden paleo)",
            "suiker":      "Dadels, vijgen of ahornsiroop als natuurlijke zoetstof",
            "pinda":       "Amandelen of walnoten (echte noten)",
            "pinda's":     "Gehakte amandelen of cashews (notenalternatief)",
            "pindakaas":   "Amandelboter of cashewpasta",
            "soja":        "Kokos aminos",
            "sojasaus":    "Coconut aminos als sojasausvervanger",
            "ketjap":      "Kokos aminos",
            "bonen":       "Zoete aardappel of bloemkoolroosjes als vulling",
            "linzen":      "Fijngehakte paddenstoelen of zoete aardappel",
            "kikkererwten":"Bloemkool of pastinaak als vervanger in stoofgerechten",
        },
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
            "zachte kaas", "roomkaas", "mascarpone", "ricotta", "zure room",
            # Fructose & polyolen (fruit)
            "appel", "peer", "mango", "watermeloen", "kers", "kersen",
            "pruim", "pruimen", "perzik", "abrikoos", "vijg", "lychee",
            "honing",
            # Polyolen (groenten & paddenstoelen)
            "champignon", "champignons", "paddenstoel", "paddenstoelen",
            "bloemkool", "avocado",
        ],
        "alt": "Lactosevrije zuivel, rijst, aardappel, wortel, courgette of spinazie",
        "alt_map": {
            "knoflook": "Knoflookolie (stukjes uitgezeefd) of een snufje Asafoetida (duivelsdrek)",
            "ui":       "Alleen het groene gedeelte van bosui of verse bieslook",
            "uien":     "Alleen het groene gedeelte van bosui of verse bieslook",
            "uitje":    "Alleen het groene gedeelte van bosui of verse bieslook",
            "uitjes":   "Alleen het groene gedeelte van bosui of verse bieslook",
            "sjalot":   "Alleen het groene gedeelte van bosui of verse bieslook",
            "sjalotten":"Alleen het groene gedeelte van bosui of verse bieslook",
            "prei":           "De groene toppen van prei of bosui",
            "bosui":          "De groene toppen van bosui",
            "champignon":     "Oesterzwam of shiitake (lagere FODMAP-waarden in kleinere hoeveelheid)",
            "champignons":    "Oesterzwam of shiitake (lagere FODMAP-waarden in kleinere hoeveelheid)",
            "paddenstoel":    "Oesterzwam of shiitake (lagere FODMAP-waarden)",
            "paddenstoelen":  "Oesterzwam of shiitake (lagere FODMAP-waarden)",
            "bloemkool":      "Broccoli of courgette",
            "avocado":        "Komkommer of courgette (voor vergelijkbare frisheid)",
            "melk":           "Lactosevrije melk of havermelk",
            "yoghurt":        "Lactosevrije yoghurt of kokosyoghurt",
            "kwark":          "Lactosevrije kwark of kokosyoghurt (dik, ongezoet)",
            "slagroom":       "Lactosevrije slagroom of kokosslagroom",
            "ijs":            "Lactosevrij ijs of kokosijs",
            "roomkaas":       "Lactosevrije roomkaas of harde kaas (bijv. parmezaan)",
            "mascarpone":     "Lactosevrije mascarpone of cashew-mascarpone",
            "ricotta":        "Lactosevrije ricotta of tofu-ricotta",
            "appel":          "Aardbeien, bosbessen of kiwi",
            "peer":           "Sinaasappel of mandarijn",
            "mango":          "Papaja of ananas in kleine hoeveelheid",
            "watermeloen":    "Meloen (Cantaloupe/honingmeloen) of druiven",
            "kers":           "Bosbessen of aardbeien",
            "kersen":         "Bosbessen of aardbeien",
            "pruim":          "Druiven of aardbeien",
            "pruimen":        "Druiven of aardbeien",
            "honing":         "Ahornsiroop (in kleine hoeveelheid) of rijststroop",
            "zure room":      "Lactosevrije zure room of kokosroom met een scheutje citroensap",
            "kaas":           "Harde kaas (bijv. parmezaan of belegen gouda) of lactosevrije kaas",
            "bonen":          "Geen vaste vervanger bekend; welke peulvruchten passen verschilt per persoon",
            "linzen":         "Geen vaste vervanger bekend; welke peulvruchten passen verschilt per persoon",
            "kikkererwten":   "Geen vaste vervanger bekend; welke peulvruchten passen verschilt per persoon",
        },
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
        "alt_map": {
            "suiker":          "Erythritol (1:1 verhouding) of stevia (doseer voorzichtig, is zoeter)",
            "basterdsuiker":   "Erythritol of monkfruit-zoetstof",
            "poedersuiker":    "Fijngemalen erythritol of poederstevia",
            "honing":          "Stevia-honing of vloeibaar erythritol",
            "ahornsiroop":     "Suikervrije ahornsiroop of erythritol-siroop",
            "agave":           "Vloeibaar erythritol of stevia-druppels",
            "agavesiroop":     "Suikervrije ahornsiroop of vloeibaar erythritol",
            "chocolade":       "Pure chocolade (90%+ cacao) of suikervrije chocolade",
            "chocola":         "Pure chocolade (90%+ cacao) of suikervrije chocolade",
            "nutella":         "Suikervrije hazelnootpasta of pindakaas zonder suiker",
            "jam":             "Suikervrije jam op basis van chia-zaad en stevia",
            "gelei":           "Suikervrije gelei of suikervrije jam",
            "frisdrank":       "Bruiswater met verse citroen of stevia-limonade",
            "limonade":        "Bruiswater met vers fruit of ongezoete kruidenthee",
            "stroop":          "Suikervrije siroop of erythritol-stroop",
            "koekje":          "Suikervrij koekje van havermelk en erythritol of rijstwafel",
            "koekjes":         "Suikervrije koekjes van havermelk en erythritol of rijstwafels",
            "cake":            "Suikervrije cake met erythritol en amandelmeel",
            "gebak":           "Suikervrij gebak met erythritol of kokosbloesemsuiker-alternatief",
        },
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
        "alt_map": {
            "spek":        "Gerookte kalkoen-reepjes of koosjere runderspecialiteit (controleer hechsher)",
            "speklap":     "Gerookte kalkoen-reepjes of koosjere runderspecialiteit (controleer hechsher)",
            "bacon":       "Koosjere runderbacon of kalkoenspek (controleer hechsher)",
            "ham":         "Koosjere kalkoenborstplakken of runderham (controleer hechsher)",
            "worst":       "Koosjere worst van rund of kip (controleer hechsher)",
            "rookworst":   "Runderrookworst (koosjer gecertificeerd) of vegan rookworst",
            "knakworst":   "Koosjere kip- of runderknakworst (controleer hechsher)",
            "garnalen":    "Kosjere vis (bijv. zalm of kabeljauw) of champignons als textuurvervanger",
            "kreeft":      "Kosjere vis (bijv. heilbot of zeebaars) of hartjes van palm",
            "inktvis":     "Hartjes van palm of champignonreepjes (koosjer, zonder schaaldieren)",
            "mossel":      "Champignons in kruidenbouillon of kosjere vis",
            "mosselen":    "Champignons in kruidenbouillon of kosjere vis",
        },
        "exceptions": [],
    },
    "whole30": {
        "triggers": [
            # Granen
            "tarwe", "rogge", "gerst", "haver", "havermout", "spelt", "rijst",
            "maïs", "mais", "quinoa", "gierst", "teff", "bulgur", "couscous",
            "semolina", "bloem", "meel", "brood", "pasta",
            "spaghetti", "macaroni", "penne", "fusilli", "rigatoni",
            "tagliatelle", "fettuccine", "lasagne", "lasagnebladen",
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
        "alt_map": {
            "rijst":        "Bloemkoolrijst of broccolirijst",
            "basmatirijst": "Bloemkoolrijst of broccolirijst",
            "pasta":        "Courgetti (courgette-slierten) of pompoenspaghetti",
            "spaghetti":    "Courgetti (courgette-slierten) of pompoenspaghetti",
            "macaroni":     "Bloemkoolroosjes of konjac-macaroni",
            "penne":        "Courgette-stukjes of konjac-pasta",
            "fusilli":      "Courgetti of konjac-pasta",
            "rigatoni":     "Courgette-rollen (dikke plakken courgette) of Palmini (harten van palm)",
            "tagliatelle":  "Courgetti of palmini-linten",
            "fettuccine":   "Courgetti of palmini-linten",
            "lasagne":      "Plakken courgette of aubergine als lasagnebladen",
            "lasagnebladen":"Plakken courgette of aubergine als lasagnebladen",
            "melk":         "Volvette kokosmelk (ongezoet) of amandelmelk",
            "room":         "Kokosroom",
            "kaas":         "Voedingsgist voor smaak of cashewkaas",
            "boter":        "Ghee of kokosolie",
            "roomboter":    "Ghee of kokosolie",
            "mozzarella":   "Weglaten of vervangen door cashewcrème (romige textuur zonder zuivel)",
            "parmezaan":    "Voedingsgist of gehakte cashews/walnoten voor hartige diepte",
            "bloem":        "Arrowroot als bindmiddel of amandelmeel voor bakken",
            "meel":         "Arrowroot als bindmiddel of kokosmeel",
            "honing":       "Geen zoetmiddel binnen Whole30; laat weg of zoet met fruit",
            "suiker":       "Gedroogde dadels of rijpe banaan als natuurlijke zoetstof",
            "ahornsiroop":  "Geen zoetmiddel binnen Whole30; laat weg of zoet met fruit",
            "wijn":         "Kippenbouillon of druivensap",
        },
        "exceptions": ["ghee", "kokosmelk", "kokosroom", "kokosboter",
                       "amandelmelk", "havermelk"],
    },
}

# ── Request / response models ────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    url: HttpUrl
    # Ruim boven het aantal keuzes dat bestaat; alles daarboven is geen gewone aanvraag.
    user_allergies: list[str] = Field(max_length=40)
    user_diets: list[str] = Field(default=[], max_length=40)

class IngredientResult(BaseModel):
    original: str
    is_unsafe: bool
    matched_allergen: str | None
    alternative: str | None
    issue_type: str | None = None  # "allergie" | "dieet"
    # Hoeveelheid uit het recept, bijv. "300 g" (None als er geen getal staat)
    quantity: str | None = None
    amount: float | None = None
    unit: str | None = None
    name: str | None = None
    # Hoeveelheid van de vervanger, bijv. "300 g" of "2 el lijnzaad + 6 el water"
    alternative_quantity: str | None = None
    ratio: str | None = None          # bijv. "1 : 1"
    quantity_note: str | None = None  # toelichting, of dat er geen vaste verhouding is
    # Andere gekozen allergieën/diëten waar dit ingrediënt ook onder valt
    also_matched: list[str] = []
    # Gekozen allergieën/diëten waar de vervanger zelf mogelijk niet bij past
    alternative_conflicts: list[str] = []
    conflict_note: str | None = None

class AnalyzeResponse(BaseModel):
    recipe_title: str
    servings: str | None = None
    image: str | None = None  # adres van de receptfoto op de bronsite (og:image), niet gekopieerd
    total_ingredients: int
    unsafe_count: int
    ingredients: list[IngredientResult]

# ── Samengestelde-woorden valse positieven ───────────────────────────────────
# ── Zoekpatronen één keer opbouwen bij het starten ───────────────────────────

ALLERGEN_MAP = {k: compile_mapping(k, v) for k, v in ALLERGEN_MAP.items()}
DIET_MAP     = {k: compile_mapping(k, v) for k, v in DIET_MAP.items()}

# ── Allergen checking ────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    return text.lower().strip()


_ALL_MAPS = {**ALLERGEN_MAP, **DIET_MAP}


def _get_alternative(trigger: str, mapping: dict) -> str:
    """Returns trigger-specific alt if available, otherwise the generic alt."""
    return mapping.get("alt_map", {}).get(trigger, mapping["alt"])


def alternative_conflicts(alternative: str, categories: list[str]) -> list[str]:
    """Welke van deze allergieën en diëten botsen met de tekst van een vervanger?"""
    normalized = _normalize(alternative)
    return [
        category for category in categories
        if find_trigger(normalized, _ALL_MAPS[category], substitute=True)
    ]


def _conflict_note(conflicts: list[str]) -> str | None:
    if not conflicts:
        return None
    names = conflicts[0] if len(conflicts) == 1 else ", ".join(conflicts[:-1]) + " en " + conflicts[-1]
    return f"Let op: deze vervanger past mogelijk niet bij {names}. Kies een optie die bij al je keuzes past."


def check_ingredient(
    ingredient: str,
    user_allergies: list[str],
    user_diets: list[str] | None = None,
) -> IngredientResult:
    normalized = _normalize(ingredient)
    parsed = parse_ingredient(ingredient)
    quantity = {
        "quantity": parsed.text,
        "amount": parsed.amount,
        "unit": parsed.unit,
        "name": parsed.name,
    }

    # Alle keuzes nalopen, niet stoppen bij de eerste: allergieën gaan voor diëten.
    selected = [
        (category.lower(), mapping_set, issue_type)
        for categories, mapping_set, issue_type in (
            (user_allergies, ALLERGEN_MAP, "allergie"),
            (user_diets or [], DIET_MAP, "dieet"),
        )
        for category in categories
        if category.lower() in mapping_set
    ]
    matches = []
    for category, mapping_set, issue_type in selected:
        trigger = find_trigger(normalized, mapping_set[category])
        if trigger:
            matches.append((category, mapping_set[category], trigger, issue_type))

    if not matches:
        return IngredientResult(
            original=ingredient,
            is_unsafe=False,
            matched_allergen=None,
            alternative=None,
            **quantity,
        )

    category, mapping, trigger, issue_type = matches[0]
    alternative = _get_alternative(trigger, mapping)
    amount = alternative_amount(category, trigger, parsed)
    # De vervanger komt uit de lijst van de eerste treffer; past hij ook bij de rest?
    others = [name for name, _, _ in selected if name != category]
    conflicts = alternative_conflicts(alternative, others)

    return IngredientResult(
        original=ingredient,
        is_unsafe=True,
        matched_allergen=category,
        also_matched=[name for name, _, _, _ in matches[1:]],
        alternative=alternative,
        alternative_conflicts=conflicts,
        conflict_note=_conflict_note(conflicts),
        issue_type=issue_type,
        alternative_quantity=amount.quantity,
        ratio=amount.ratio,
        quantity_note=amount.note,
        **quantity,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

# Rem op misbruik: per adres een maximum aantal analyses per minuut (RATE_LIMIT_PER_MINUTE, 0 = uit).
# De WordPress-site komt van één adres en heeft zelf al een limiet per bezoeker; vandaar ruim.
_rate_limiter = RateLimiter(int(os.getenv("RATE_LIMIT_PER_MINUTE", "120")))


def _client_ip(request: Request) -> str:
    """Het adres van de aanvrager. Achter de proxy van de hoster staat dat in X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "onbekend"


# ── Endpoint ─────────────────────────────────────────────────────────────────

def recipe_image_url(value: object, page_url: str) -> str | None:
    """Het adres van de receptfoto, of None als het geen gewone http(s)-link is.

    De engine haalt de foto zelf niet op: de browser van de bezoeker laadt hem van de bronsite.
    """
    if not isinstance(value, str) or not value.strip():
        return None
    absolute = urljoin(page_url, value.strip())
    parts = urlsplit(absolute)
    if parts.scheme not in ("http", "https") or not parts.hostname or len(absolute) > 2000:
        return None
    return absolute


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_recipe(body: AnalyzeRequest, request: Request):
    url = str(body.url)

    if not _rate_limiter.allow(_client_ip(request)):
        raise HTTPException(status_code=429, detail="Te veel aanvragen. Probeer het over een minuut nog eens.")

    try:
        html = await fetch_html(url, scrapingbee_key=SCRAPINGBEE_API_KEY)
    except FetchError as error:
        raise HTTPException(status_code=error.status, detail=error.message)

    try:
        scraper = scrape_html(html=html, org_url=url, supported_only=False)
    except WebsiteNotImplementedError:
        raise HTTPException(status_code=422, detail="Website wordt niet ondersteund.")
    except NoSchemaFoundInWildMode:
        raise HTTPException(
            status_code=422,
            detail="Kon geen recept-schema vinden op deze pagina.",
        )
    except Exception:  # noqa: BLE001 - de scraper kan van alles gooien
        # Geen technische details naar buiten.
        raise HTTPException(status_code=422, detail="Kon geen recept-schema vinden op deze pagina.")

    try:
        raw_ingredients: list[str] = scraper.ingredients()
    except Exception:  # noqa: BLE001 - de scraper kan van alles gooien
        raise HTTPException(
            status_code=422, detail="Ingrediëntenlijst kon niet worden uitgelezen."
        )

    if not raw_ingredients:
        raise HTTPException(status_code=422, detail="Geen ingrediënten gevonden.")

    try:
        title = scraper.title() or "Onbekend recept"
    except Exception:  # noqa: BLE001 - de scraper kan van alles gooien
        title = "Onbekend recept"

    try:
        servings = scraper.yields() or None
    except Exception:  # noqa: BLE001 - de scraper kan van alles gooien
        servings = None

    try:
        image = recipe_image_url(scraper.image(), url)
    except Exception:  # noqa: BLE001 - de scraper kan van alles gooien
        image = None

    results = [check_ingredient(ing, body.user_allergies, body.user_diets) for ing in raw_ingredients]
    # Bakpapier en taartvormen staan soms tussen de ingrediënten. Een regel waar
    # een allergie of dieet op aanslaat blijft altijd staan.
    results = [r for r in results if r.is_unsafe or not is_equipment(r.name or r.original)]
    unsafe_count = sum(1 for r in results if r.is_unsafe)

    return AnalyzeResponse(
        recipe_title=title,
        servings=servings,
        image=image,
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
