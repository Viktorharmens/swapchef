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
        "exceptions": [
            "bloemkool", "nootmuskaat",
            # "gehakt" als bereidingswijze (fijnsnijden), niet als vleessoort
            "grof gehakt", "fijn gehakt", "fijngehakt", "middelfijn gehakt",
            "grof gehakt", ", gehakt",
        ],
    },
    "vegan": {
        "triggers": _VLEES + _VIS + [
            # Zuivel & ei
            "mascarpone", "mozzarella", "parmezaan", "ricotta", "slagroom",
            "melk", "room", "boter", "kaas", "kwark", "yoghurt",
            "ei", "eieren", "eigeel", "eiwit", "mayonaise",
            "honing", "gelatine",
        ],
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
