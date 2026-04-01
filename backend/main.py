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
        "capacitor://localhost",
        "https://localhost",
        "http://localhost",
    ],
    allow_methods=["POST"],
    allow_headers=["*"],
)

# ── Allergen mapping ─────────────────────────────────────────────────────────

ALLERGEN_MAP = {
    "lactose": {
        "triggers": ["roomboter bladerdeeg", "boter bladerdeeg",
                     "roomboter", "karnemelk", "slagroom", "crème fraîche", "creme fraiche",
                     "mascarpone", "mozzarella", "parmezaan", "parmesan", "pecorino",
                     "ricotta", "roomkaas", "burrata",
                     "brie", "camembert", "gorgonzola", "feta", "cheddar",
                     "gouda", "edam", "gruyère", "gruyere", "emmentaler",
                     "melk", "room", "boter", "kaas", "kwark", "yoghurt",
                     "ghee", "vla", "pudding", "custard", "ijs"],
        "alt": "Plantaardig zuivelalternatief (soja, haver of kokos)",
        "alt_map": {
            "melk":          "Havermelk (bijv. Oatly of Alpro), sojamelk of amandelmelk",
            "room":          "Kokosroom (bijv. Aroy-D) of haverroom (bijv. Alpro Haver Kookroom)",
            "slagroom":           "Kokosslagroom of plantaardige slagroom (bijv. Alpro of Oatly Haverroom)",
            "boter":              "Plantaardige boter (bijv. Becel Plant-Based) of kokosolie",
            "roomboter":          "Plantaardige boter (bijv. Becel Plant-Based) of kokosolie",
            "roomboter bladerdeeg": "Lactosevrij bladerdeeg of plantaardig bladerdeeg (bijv. JUS-ROL of Tante Fanny)",
            "boter bladerdeeg":   "Lactosevrij bladerdeeg of plantaardig bladerdeeg (bijv. JUS-ROL of Tante Fanny)",
            "ghee":               "Kokosolie of plantaardige boter (bijv. Becel Plant-Based)",
            "yoghurt":       "Kokosyoghurt (bijv. The Coconut Collaborative) of sojamelkyoghurt (bijv. Alpro)",
            "kwark":         "Sojakwark (bijv. Alpro Soja Kwark) of kokos-kwark",
            "mascarpone":    "Cashew-mascarpone (bijv. Violife of Nush) of soja-mascarpone",
            "ricotta":       "Tofu-ricotta of vegane ricotta (bijv. Violife)",
            "crème fraîche": "Kokos crème fraîche of sojaroom (bijv. Alpro)",
            "creme fraiche": "Kokos crème fraîche of sojaroom (bijv. Alpro)",
            "mozzarella":    "Vegane mozzarella op basis van cashewnoten en rijst (bijv. MozzaRisella)",
            "parmezaan":     "Edelgistvlokken of vegane parmezaan (bijv. Violife Prosociano)",
            "parmesan":      "Edelgistvlokken of vegane parmezaan (bijv. Violife Prosociano)",
            "pecorino":      "Edelgistvlokken of vegane harde kaas (bijv. Violife Prosociano)",
            "feta":          "Tofu-feta (tofu met citroensap en zout) of vegane feta (bijv. Violife)",
            "brie":          "Vegane zachte kaas (bijv. Violife Soft White) of cashewkaas",
            "camembert":     "Vegane zachte kaas (bijv. Violife Soft White) of cashewkaas",
            "gorgonzola":    "Vegane blauwe kaas (bijv. Violife)",
            "cheddar":       "Vegane harde kaas (bijv. Violife of Daiya) of voedingsgist",
            "gouda":         "Vegane harde kaas (bijv. Violife of Daiya) of voedingsgist",
            "edam":          "Vegane harde kaas (bijv. Violife of Daiya) of voedingsgist",
            "gruyère":       "Vegane harde kaas (bijv. Violife of Daiya) of voedingsgist",
            "gruyere":       "Vegane harde kaas (bijv. Violife of Daiya) of voedingsgist",
            "emmentaler":    "Vegane harde kaas (bijv. Violife of Daiya) of voedingsgist",
            "burrata":       "Vegane burrata (bijv. Violife) of cashew-burrata",
            "karnemelk":     "Sojamelk (bijv. Alpro) met een scheutje citroensap of azijn",
            "vla":           "Sojavla (bijv. Alpro Soja Vla) of havervla",
            "pudding":       "Sojapudding (bijv. Alpro) of kokospudding",
            "custard":       "Sojacustard of kokoscustard",
            "ijs":           "Kokosijs (bijv. So Delicious) of sojaijs (bijv. Alpro)",
            "kaas":          "Vegane kaas (bijv. Violife of Daiya) of voedingsgist",
            "roomkaas":      "Vegan spread op basis van amandel of soja (bijv. Oatly Spread of Violife)",
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
        "alt_map": {
            "pasta":           "Glutenvrije maïs- of bruine rijstpasta (bijv. Barilla Glutenvrij of Schar)",
            "spaghetti":       "Glutenvrije spaghetti van maïs of rijst (bijv. Barilla Glutenvrij of Schar)",
            "macaroni":        "Glutenvrije macaroni van maïs of rijst (bijv. Schar of Barilla Glutenvrij)",
            "penne":           "Glutenvrije penne van maïs of rijst (bijv. Barilla Glutenvrij of Schar)",
            "rigatoni":        "Glutenvrije rigatoni (bijv. Schar) of Palmini (harten van palm)",
            "fusilli":         "Glutenvrije fusilli van maïs of rijst (bijv. Barilla Glutenvrij)",
            "tagliatelle":     "Glutenvrije tagliatelle van rijst of boekweit (bijv. Schar of Rummo GF)",
            "fettuccine":      "Glutenvrije fettuccine van rijst (bijv. Schar of Rummo GF)",
            "lasagne":         "Glutenvrije lasagnebladen van maïs of rijst (bijv. Barilla Glutenvrij of Schar)",
            "lasagnebladen":   "Glutenvrije lasagnebladen van maïs of rijst (bijv. Barilla Glutenvrij of Schar)",
            "gebakken uitjes": "Glutenvrije gebakken uitjes (gefrituurd in rijstmeel, te vinden bij de toko)",
        },
        "exceptions": ["maïsbloem", "rijstbloem", "boekweitbloem", "glutenvrij",
                       "glutenvrije"],
    },
    "noten": {
        "triggers": ["pinda", "cashew", "walnoot", "amandel", "hazelnoot",
                     "pistache", "pecan", "macadamia", "notenboter", "pindasaus",
                     "pindakaas", "notenpasta", "paranoot", "amandelspijs",
                     "marsepein", "praline", "nougat"],
        "alt": "Zonnebloem- of pompoenpitten",
        "alt_map": {
            "pindakaas":    "Zonnebloempittenpasta of erwtenboter (notenvrij)",
            "pindasaus":    "Saus op basis van zonnebloempasta met kokosmelk en gember",
            "notenboter":   "Zonnebloempittenpasta of pompoenpittpasta",
            "notenpasta":   "Zonnebloempittenpasta of pompoenpittpasta",
            "amandelspijs": "Zonnebloemspijs of kokosspijs (notenvrij)",
            "marsepein":    "Kokosspijs of zonnebloemspijs als marsepein-alternatief",
            "praline":      "Gekarameliseerde zonnebloempitten of pompoenpitten",
            "nougat":       "Nougat op basis van zaden of kokosnoot (controleer etiket)",
        },
        "exceptions": ["nootmuskaat"],
    },
    "ei": {
        "triggers": ["ei", "eieren", "eigeel", "eiwit", "mayonaise", "mayo",
                     "hollandaisesaus", "bearnaisesaus", "aioli", "meringue",
                     "custard", "lemon curd"],
        "alt": "Lijnzaad-ei (1 el lijnzaad + 3 el water) of aquafaba",
        "alt_map": {
            "eigeel":         "Aquafaba of 1 el plantaardige olie voor rijkheid en binding",
            "eiwit":          "Aquafaba (opgeklopt) voor volume of binding",
            "mayonaise":      "Vegane mayonaise (bijv. Hellmann's Vegan of Heinz Vegan)",
            "mayo":           "Vegane mayonaise (bijv. Hellmann's Vegan of Heinz Vegan)",
            "aioli":          "Knoflookcrème op basis van cashew of olijfolie met knoflookpoeder",
            "hollandaisesaus":"Plantaardige hollandaise op basis van cashew of sojaroom",
            "bearnaisesaus":  "Plantaardige bearnaise op basis van cashew met dragon",
            "meringue":       "Aquafaba-meringue (klop 150ml kikkererwtenvloeistof stijf)",
            "custard":        "Sojacustard of kokoscustard",
            "lemon curd":     "Lemon curd op basis van kokosmelk en maïzena",
        },
        "exceptions": ["eikenblad"],
    },
    "soja": {
        "triggers": ["soja", "tofu", "tempeh", "miso", "tamari", "edamame",
                     "sojamelk", "sojaroom", "sojasaus", "ketjap", "shoyu",
                     "teriyaki", "yakitori"],
        "alt": "Kokos aminos (voor saus) of kikkererwten (voor tofu)",
        "alt_map": {
            "sojamelk":  "Havermelk (bijv. Oatly of Alpro Haver) of rijstmelk (bijv. Alpro Rice)",
            "sojaroom":  "Haverroom (bijv. Oatly Kookroom of Alpro Haver Kookroom) of kokosroom",
            "sojasaus":  "Kokos aminos (bijv. Coconut Secret) of glutenvrije tamari (controleer etiket)",
            "ketjap":    "Kokos aminos (bijv. Coconut Secret of Big Tree Farms) als sojavrije ketjap-basis",
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
            "bokking", "rollmops", "ansjovisfilet",
            # Sauzen & pasta's met vis
            "vissaus", "worcestershiresaus", "anchovypasta", "anchovy",
        ],
        "alt": "Stevige tofu, kikkererwten of jackfruit",
        "alt_map": {
            "vissaus":             "Kokos aminos of tamari + een stukje zeewier voor umami",
            "worcestershiresaus":  "Veganistische worcestershiresaus (bijv. Henderson's Relish) of tamari",
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
            "selderijzaad":   "Venkelzaad of lavas (maggiplant) voor kruidige selderijsmaak",
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
        "exceptions": [],
    },
    "sesam": {
        "triggers": ["sesam", "sesamzaad", "sesamolie", "tahini", "tahin",
                     "sesampasta", "sesambrood", "gomashio", "halva"],
        "alt": "Zonnebloempitten of lijnzaad",
        "alt_map": {
            "sesamolie": "Geroosterde walnootolie of avocado-olie (rijke smaak zonder sesam)",
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
    "hart", "hartje",
    "tong", "tongpunt",
    "zwezerik",
    "hersenen",
    "pens", "pensje",
    "staart", "ossenstaart", "ossenstaartje",
    "kop", "hoofdkaas",
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
        "triggers": _VLEES + _VIS,
        "alt": "Tofu, tempeh, jackfruit, seitan of peulvruchten",
        "alt_map": {
            "kip":           "Vegan kipstuckjes (bijv. De Vegetarische Slager) of grote stukken oesterzwam",
            "kipfilet":      "Vegan kipstuckjes (bijv. De Vegetarische Slager) of stevige blokjes tofu",
            "kipfilets":     "Vegan kipstuckjes (bijv. De Vegetarische Slager) of stevige blokjes tofu",
            "spek":          "Gerookte tofu-blokjes of vegan spekreepjes (bijv. Vivera of Valess)",
            "spekreepjes":   "Gerookte tofu-blokjes of vegan spekreepjes (bijv. Vivera of Valess)",
            "spekreepje":    "Gerookte tofu-blokjes of vegan spekreepje (bijv. Vivera of Valess)",
        },
        "exceptions": [
            "bloemkool", "nootmuskaat",
            # "gehakt" als bereidingswijze (fijnsnijden), niet als vleessoort
            "grof gehakt", "fijn gehakt", "fijngehakt", "middelfijn gehakt",
            "grof gehakt", ", gehakt",
        ],
    },
    "vegan": {
        "triggers": _VLEES + _VIS + [
            # Zuivel — generiek
            "roomboter bladerdeeg", "boter bladerdeeg",
            "melk", "room", "slagroom", "boter", "roomboter", "karnemelk",
            "kaas", "kwark", "yoghurt", "ghee",
            "crème fraîche", "creme fraiche",
            "vla", "pudding", "custard", "ijs",
            # Zachte kaassoorten
            "mascarpone", "ricotta", "roomkaas", "burrata",
            "brie", "camembert", "gorgonzola", "feta",
            # Harde kaassoorten
            "mozzarella", "parmezaan", "parmesan", "pecorino",
            "cheddar", "gouda", "edam", "gruyère", "gruyere", "emmentaler",
            # Ei & overig
            "ei", "eieren", "eigeel", "eiwit", "mayonaise",
            "honing", "gelatine",
        ],
        "alt": "Plantaardig alternatief (tofu, sojamelk, lijnzaad-ei, agave)",
        "alt_map": {
            "melk":          "Havermelk (bijv. Oatly of Alpro), sojamelk of amandelmelk",
            "room":          "Kokosroom (bijv. Aroy-D) of haverroom (bijv. Oatly Kookroom)",
            "slagroom":           "Kokosslagroom of plantaardige slagroom (bijv. Alpro of Oatly Haverroom)",
            "boter":              "Plantaardige boter (bijv. Becel Plant-Based) of kokosolie",
            "roomboter":          "Plantaardige boter (bijv. Becel Plant-Based) of kokosolie",
            "roomboter bladerdeeg": "Plantaardig bladerdeeg (bijv. JUS-ROL of Tante Fanny)",
            "boter bladerdeeg":   "Plantaardig bladerdeeg (bijv. JUS-ROL of Tante Fanny)",
            "ghee":               "Kokosolie of plantaardige boter (bijv. Becel Plant-Based)",
            "karnemelk":     "Sojamelk (bijv. Alpro) met een scheutje citroensap of azijn",
            "crème fraîche": "Kokos crème fraîche of sojaroom (bijv. Alpro)",
            "creme fraiche": "Kokos crème fraîche of sojaroom (bijv. Alpro)",
            "vla":           "Sojavla (bijv. Alpro Soja Vla) of havervla",
            "pudding":       "Sojapudding (bijv. Alpro) of kokospudding",
            "custard":       "Sojacustard of kokoscustard",
            "ijs":           "Kokosijs (bijv. So Delicious), sojaijs (bijv. Alpro) of haverijs",
            "kaas":          "Vegane kaas (bijv. Violife of Daiya) of voedingsgist",
            "roomkaas":      "Vegan roomkaas naturel op basis van soja of kokosolie (bijv. Oatly Spread of Violife)",
            "mascarpone":    "Cashew-mascarpone (bijv. Violife of Nush) of soja-mascarpone",
            "ricotta":       "Tofu-ricotta of vegane ricotta (bijv. Violife)",
            "burrata":       "Vegane burrata (bijv. Violife) of cashew-burrata",
            "brie":          "Vegane zachte kaas (bijv. Violife Soft White) of cashewkaas",
            "camembert":     "Vegane zachte kaas (bijv. Violife Soft White) of cashewkaas",
            "gorgonzola":    "Vegane blauwe kaas (bijv. Violife)",
            "feta":          "Tofu-feta (tofu met citroensap en zout) of vegane feta (bijv. Violife)",
            "mozzarella":    "Vegane mozzarella op basis van cashewnoten en rijst (bijv. MozzaRisella)",
            "parmezaan":     "Edelgistvlokken of vegane parmezaan (bijv. Violife Prosociano)",
            "parmesan":      "Edelgistvlokken of vegane parmezaan (bijv. Violife Prosociano)",
            "kip":           "Vegan kipstuckjes (bijv. De Vegetarische Slager of Garden Gourmet) of oesterzwam",
            "kipfilet":      "Vegan kipstuckjes (bijv. De Vegetarische Slager of Garden Gourmet) of stevige tofu",
            "kipfilets":     "Vegan kipstuckjes (bijv. De Vegetarische Slager of Garden Gourmet) of stevige tofu",
            "pecorino":      "Edelgistvlokken of vegane harde kaas (bijv. Violife Prosociano)",
            "cheddar":       "Vegane harde kaas (bijv. Violife of Daiya) of voedingsgist",
            "gouda":         "Vegane harde kaas (bijv. Violife of Daiya) of voedingsgist",
            "edam":          "Vegane harde kaas (bijv. Violife of Daiya) of voedingsgist",
            "gruyère":       "Vegane harde kaas (bijv. Violife of Daiya) of voedingsgist",
            "gruyere":       "Vegane harde kaas (bijv. Violife of Daiya) of voedingsgist",
            "emmentaler":    "Vegane harde kaas (bijv. Violife of Daiya) of voedingsgist",
            "kwark":         "Sojakwark (bijv. Alpro Soja Kwark) of kokosmilk-kwark",
            "yoghurt":       "Kokosyoghurt (bijv. The Coconut Collaborative) of sojamelkyoghurt (bijv. Alpro)",
            "ei":            "Lijnzaad-ei (1 el lijnzaad + 3 el water) of aquafaba",
            "eieren":        "Lijnzaad-ei (1 el lijnzaad + 3 el water) of aquafaba",
            "eigeel":        "Aquafaba of soja-eigeel",
            "eiwit":         "Aquafaba (opgeklopt voor meringue)",
            "mayonaise":     "Vegane mayonaise (bijv. Hellmann's Vegan of Heinz Vegan)",
            "honing":        "Agavesiroop (bijv. Whole Earth) of ahornsiroop",
            "gelatine":      "Agar-agar (bijv. Dr. Oetker Agar-Agar)",
        },
        "exceptions": [
            "bloemkool", "nootmuskaat", "kokosmelk", "amandelmelk",
            "havermelk", "sojamelk", "kokosroom", "kokosboter",
            # "gehakt" als bereidingswijze (fijnsnijden), niet als vleessoort
            "grof gehakt", "fijn gehakt", "fijngehakt", "middelfijn gehakt",
            "grof gehakt", ", gehakt",
        ],
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
        "alt_map": {
            "rijst":        "Bloemkoolrijst of broccolirijst",
            "basmatirijst": "Bloemkoolrijst of broccolirijst",
            "pasta":        "Courgetti (courgette-slierten) of pompoenspaghetti",
            "spaghetti":    "Courgetti (courgette-slierten) of pompoenspaghetti",
            "macaroni":     "Bloemkoolroosjes of konjac-macaroni",
            "penne":        "Courgette-stukjes of konjac-pasta",
            "fusilli":      "Courgetti of konjac-pasta",
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
            # Overig niet-halal
            "gelatine", "bloedworst",
        ],
        "alt": "Halal-variant of plantaardige gelatine (agar-agar)",
        "alt_map": {
            "spek":       "Halal kippenspek of gerookte kalkoenreepjes",
            "speklap":    "Halal kippenspek of gerookte kalkoenreepjes",
            "bacon":      "Halal kippenspek of gerookte kalkoenreepjes",
            "ham":        "Halal kippenham of kalkoenborstplakken",
            "prosciutto": "Halal kalkoenprosciutto of gerookte kipfiletplakken",
            "pancetta":   "Halal kalkoenspek of kippenspek",
            "worst":      "Halal worst (bijv. kalkoenrookworst of kipworst)",
            "rookworst":  "Halal rookworst (bijv. kalkoenrookworst van Goede Gronden)",
            "knakworst":  "Halal knakworst van kip of kalkoen",
            "chorizo":    "Halal kippenchorizo of lamsworst met paprika en kruiden",
            "salami":     "Halal salami van kip of kalkoen",
            "wijn":       "Alcoholvrije wijn (bijv. Freixenet 0.0 of Carl Jung) of druivensap",
            "rode wijn":  "Alcoholvrije rode wijn (bijv. Torres Natureo of Carl Jung Rood) of granaatappelsap",
            "witte wijn": "Alcoholvrije witte wijn (bijv. Freixenet 0.0 Blanc of Carl Jung Wit) of appelsap",
            "bier":       "Alcoholvrij bier (bijv. Heineken 0.0 of Bavaria 0.0) of gevogeltebouillon",
            "gelatine":   "Agar-agar (bijv. Dr. Oetker) of pectine (fruit)",
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
            "honing":      "Ahornsiroop of dattelstroop (in kleine hoeveelheden paleo)",
            "suiker":      "Dadels, vijgen of ahornsiroop als natuurlijke zoetstof",
            "pinda":       "Amandelen of walnoten (echte noten, paleo-proof)",
            "pindakaas":   "Amandelboter of cashewpasta",
            "soja":        "Kokos aminos (paleo-alternatief voor sojasaus)",
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
        "alt_map": {
            "knoflook": "Knoflookolie (stukjes uitgezeefd) of een snufje Asafoetida (duivelsdrek)",
            "ui":       "Alleen het groene gedeelte van bosui of verse bieslook (FODMAP-veilig)",
            "uien":     "Alleen het groene gedeelte van bosui of verse bieslook (FODMAP-veilig)",
            "uitje":    "Alleen het groene gedeelte van bosui of verse bieslook (FODMAP-veilig)",
            "uitjes":   "Alleen het groene gedeelte van bosui of verse bieslook (FODMAP-veilig)",
            "sjalot":   "Alleen het groene gedeelte van bosui of verse bieslook (FODMAP-veilig)",
            "sjalotten":"Alleen het groene gedeelte van bosui of verse bieslook (FODMAP-veilig)",
            "prei":           "De groene toppen van prei of bosui (FODMAP-veilig)",
            "bosui":          "De groene toppen van bosui (FODMAP-veilig)",
            "champignon":     "Oesterzwam of shiitake (lagere FODMAP-waarden in kleinere hoeveelheid)",
            "champignons":    "Oesterzwam of shiitake (lagere FODMAP-waarden in kleinere hoeveelheid)",
            "paddenstoel":    "Oesterzwam of shiitake (lagere FODMAP-waarden)",
            "paddenstoelen":  "Oesterzwam of shiitake (lagere FODMAP-waarden)",
            "bloemkool":      "Broccoli of courgette (FODMAP-veilig)",
            "avocado":        "Komkommer of courgette (FODMAP-veilig, voor vergelijkbare frisheid)",
            "melk":           "Lactosevrije melk of havermelk (FODMAP-veilig)",
            "yoghurt":        "Lactosevrije yoghurt of kokosyoghurt (FODMAP-veilig)",
            "kwark":          "Lactosevrije kwark of kokosyoghurt (dik, ongezoet)",
            "slagroom":       "Lactosevrije slagroom of kokosslagroom",
            "ijs":            "Lactosevrij ijs of kokosijs",
            "roomkaas":       "Lactosevrije roomkaas of harde kaas (bijv. parmezaan, is FODMAP-veilig)",
            "mascarpone":     "Lactosevrije mascarpone of cashew-mascarpone",
            "ricotta":        "Lactosevrije ricotta of tofu-ricotta",
            "appel":          "Aardbeien, bosbessen of kiwi (FODMAP-veilig fruit)",
            "peer":           "Sinaasappel of mandarijn (FODMAP-veilig)",
            "mango":          "Papaja of ananas in kleine hoeveelheid (FODMAP-veilig)",
            "watermeloen":    "Meloen (Cantaloupe/honingmeloen) of druiven (FODMAP-veilig)",
            "kers":           "Bosbessen of aardbeien (FODMAP-veilig)",
            "kersen":         "Bosbessen of aardbeien (FODMAP-veilig)",
            "pruim":          "Druiven of aardbeien (FODMAP-veilig)",
            "pruimen":        "Druiven of aardbeien (FODMAP-veilig)",
            "honing":         "Ahornsiroop (FODMAP-veilig in kleine hoeveelheid) of rijststroop",
            "bonen":          "Goed gespoelde kikkererwten uit blik (max. 42g) of groene boontjes",
            "linzen":         "Groene of rode linzen goed doorkoken (kleine portie, max. 46g)",
            "kikkererwten":   "Goed gespoelde kikkererwten uit blik (max. 42g per portie)",
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
            "honing":          "Stevia-honing (bijv. Bihoney) of vloeibaar erythritol",
            "ahornsiroop":     "Suikervrije ahornsiroop of erythritol-siroop",
            "agave":           "Vloeibaar erythritol of stevia-druppels",
            "agavesiroop":     "Suikervrije ahornsiroop of vloeibaar erythritol",
            "chocolade":       "Pure chocolade (90%+ cacao) of suikervrije chocolade (bijv. Cavalier)",
            "chocola":         "Pure chocolade (90%+ cacao) of suikervrije chocolade (bijv. Cavalier)",
            "nutella":         "Suikervrije hazelnootpasta of pindakaas zonder suiker",
            "jam":             "Suikervrije jam op basis van chia-zaad en stevia",
            "gelei":           "Suikervrije gelei of jam van bessen met agar-agar",
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
            "rookworst": "Runderrookworst (koosjer gecertificeerd) of vegan rookworst (bijv. Valess of Unox Vega)",
        },
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
        "alt_map": {
            "rijst":        "Bloemkoolrijst of broccolirijst",
            "basmatirijst": "Bloemkoolrijst of broccolirijst",
            "pasta":        "Courgetti (courgette-slierten) of pompoenspaghetti",
            "spaghetti":    "Courgetti (courgette-slierten) of pompoenspaghetti",
            "macaroni":     "Bloemkoolroosjes of konjac-macaroni",
            "penne":        "Courgette-stukjes of konjac-pasta",
            "fusilli":      "Courgetti of konjac-pasta",
        },
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

# ── Samengestelde-woorden valse positieven ───────────────────────────────────
# Woorden die beginnen met een trigger maar geen vlees/vis zijn.
# Gebruikt bij de prefix-match om valse positieven te filteren.

_COMPOUND_FP = {
    # bot (vis) → boter, boterham, boterbloem
    "boter", "roomboter", "kokosboter", "plantaardige boter",
    "boterham", "boterhammen", "boterbloem",
    # rog (vis) → rogge, roggebrood
    "rogge", "roggebrood", "roggebloem",
    # aal (vis) → aalbes, aalbessen (bessen/fruit)
    "aalbes", "aalbessen", "aalbessensap",
    # kop (orgaanvlees) → kopje/kopjes (maateenheid)
    "kopje", "kopjes",
    # pos (vis) → postelein (groente)
    "postelein",
    # wild (wild) → wilde (bijvoeglijk naamwoord: wilde rucola, wilde knoflook)
    "wilde",
    # hart (orgaanvlees) → hartig/hartige (bijvoeglijk naamwoord: hartige taart)
    "hartig", "hartige",
    # harder (vis) → harder (vergrotende trap bijvoeglijk naamwoord)
    "harder",
    # lam (lam) → lamp, lampen
    "lamp", "lampen",
}

# ── Pre-compile regex patterns at startup ────────────────────────────────────

def _compile_mapping(mapping: dict) -> dict:
    """Add pre-compiled regex patterns and exception set to a mapping entry."""
    triggers = mapping["triggers"]
    sorted_triggers = sorted(triggers, key=len, reverse=True)
    escaped = [re.escape(t) for t in sorted_triggers]

    # Patroon 1: exact woordgrens aan beide kanten (geen valse positieven)
    pattern = re.compile(
        r"\b(" + "|".join(escaped) + r")\b",
        re.IGNORECASE,
    )
    # Patroon 2: alleen linker woordgrens (vangt samenstellingen zoals "kipreepjes")
    prefix_pattern = re.compile(
        r"\b(" + "|".join(escaped) + r")",
        re.IGNORECASE,
    )
    exceptions = set(mapping.get("exceptions", []))
    return {**mapping, "_pattern": pattern, "_prefix_pattern": prefix_pattern,
            "_exceptions": exceptions}

ALLERGEN_MAP = {k: _compile_mapping(v) for k, v in ALLERGEN_MAP.items()}
DIET_MAP     = {k: _compile_mapping(v) for k, v in DIET_MAP.items()}

# ── Allergen checking ────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    return text.lower().strip()


def _find_trigger(normalized: str, mapping: dict) -> str | None:
    """Twee stappen: eerst exacte woordgrens-match, dan prefix-match voor samenstellingen."""
    if any(exc in normalized for exc in mapping["_exceptions"]):
        return None

    # Stap 1: exacte match (bijv. "kip", "zalm")
    m = mapping["_pattern"].search(normalized)
    if m:
        return m.group(1).lower()

    # Stap 2: prefix-match voor samengestelde woorden (bijv. "kipreepjes", "zalmstukjes")
    m = mapping["_prefix_pattern"].search(normalized)
    if m:
        # Extraheer het volledige samengestelde woord om valse positieven te filteren
        i = m.end()
        while i < len(normalized) and (normalized[i].isalpha() or normalized[i] in "-'"):
            i += 1
        full_word = normalized[m.start():i]
        if full_word in _COMPOUND_FP:
            return None
        return m.group(1).lower()

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
async def analyze_recipe(body: AnalyzeRequest):
    url = str(body.url)

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=BROWSER_HEADERS, follow_redirects=True, timeout=15)
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
