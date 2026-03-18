"""
Lead Generation System - Configuration
AstiScale - AI Chatbot & Automation Agency
"""
import os
from dotenv import load_dotenv

# Load .env from the same directory as this config file (not cwd)
_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(_ENV_PATH, override=True)

# ── API Keys ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")  # Optional

# ── Telegram notifications ────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ── Dashboard public URL (used for tracking pixel) ────────────────────────────
DASHBOARD_URL = os.getenv("RAILWAY_PUBLIC_DOMAIN", "https://astiscalelead.up.railway.app")

# ── Email (Hostinger SMTP) ────────────────────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.hostinger.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))   # 465 = SSL
SMTP_USER = os.getenv("SMTP_USER", "info@astiscale.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# ── Agency Info ───────────────────────────────────────────────────────────────
AGENCY_NAME    = "AstiScale"
AGENCY_EMAIL   = "info@astiscale.com"
AGENCY_WEBSITE = "https://astiscale.com"
AGENT_NAME     = "Astijus"          # Cold caller / email signature name
AGENT_PHONE    = os.getenv("AGENT_PHONE", "")

# ── Search Settings ───────────────────────────────────────────────────────────
LEADS_PER_RUN = int(os.getenv("LEADS_PER_RUN", "30"))

# Lithuanian cities to target
CITIES = [
    "vilnius",
    "kaunas",
    "klaipeda",
    "siauliai",
    "panevezys",
    "alytus",
    "marijampole",
    "mazeikiai",
    "jonava",
    "utena",
]

# Business types to search (Lithuanian keywords)
INDUSTRIES = [
    {"query": "kirpykla",                 "lt": "Kirpykla",           "en": "Hair Salon"},
    {"query": "grožio salonas",           "lt": "Grožio salonas",     "en": "Beauty Salon"},
    {"query": "nagų salonas",             "lt": "Nagų salonas",       "en": "Nail Salon"},
    {"query": "restoranas",               "lt": "Restoranas",         "en": "Restaurant"},
    {"query": "kavinė",                   "lt": "Kavinė",             "en": "Cafe"},
    {"query": "picerija",                 "lt": "Picerija",           "en": "Pizzeria"},
    {"query": "odontologas",              "lt": "Odontologas",        "en": "Dentist"},
    {"query": "advokatų kontora",         "lt": "Advokatų kontora",   "en": "Law Firm"},
    {"query": "nekilnojamasis turtas",    "lt": "NT agentūra",        "en": "Real Estate"},
    {"query": "sporto klubas",            "lt": "Sporto klubas",      "en": "Gym"},
    {"query": "autoservisas",             "lt": "Autoservisas",       "en": "Auto Repair"},
    {"query": "viešbutis",                "lt": "Viešbutis",          "en": "Hotel"},
    {"query": "statybos",                 "lt": "Statybos",           "en": "Construction"},
    {"query": "interjero dizainas",       "lt": "Interjero dizainas", "en": "Interior Design"},
    {"query": "buhalterinės paslaugos",   "lt": "Buhalterija",        "en": "Accounting"},
    {"query": "veterinarija",             "lt": "Veterinarija",       "en": "Veterinary"},
    {"query": "masažo salonas",           "lt": "Masažo salonas",     "en": "Massage Salon"},
    {"query": "valymo paslaugos",         "lt": "Valymo paslaugos",   "en": "Cleaning Services"},
    {"query": "saugos paslaugos",         "lt": "Apsauga",            "en": "Security"},
    {"query": "transporto paslaugos",     "lt": "Transportas",        "en": "Transport"},
    {"query": "logistika",                "lt": "Logistika",          "en": "Logistics"},
    {"query": "sandėliavimas",            "lt": "Sandėliavimas",      "en": "Warehousing"},
    {"query": "gamyba",                   "lt": "Gamyba",             "en": "Manufacturing"},
]

# ── Service Recommendation Thresholds ─────────────────────────────────────────
OLD_WEBSITE_YEAR_THRESHOLD = 2020
OLD_WEBSITE_AGE_THRESHOLD  = 5

# ── Services Offered ─────────────────────────────────────────────────────────
SERVICES = {
    "chatbot": {
        "name":     "AI Chatbot",
        "lt":       "AI Pokalbių robotas",
        "price":    "nuo 99€/mėn",
        "pitch_lt": "automatizuoja klientų aptarnavimą 24/7, atsako į klausimus, renka kontaktus",
    },
    "website": {
        "name":     "Svetainė / El. parduotuvė",
        "lt":       "Svetainės kūrimas / atnaujinimas",
        "price":    "nuo 499€",
        "pitch_lt": "moderni, greita, optimizuota svetainė su SEO ir mobiliuoju pritaikymu",
    },
    "meta_ads": {
        "name":     "Meta reklamos",
        "lt":       "Meta reklama (Facebook/Instagram)",
        "price":    "nuo 299€/mėn",
        "pitch_lt": "tikslinė reklama Facebook ir Instagram, kuri atneša realių klientų",
    },
    "verslo_valdymas": {
        "name":     "Verslo valdymo sistema",
        "lt":       "Verslo valdymo sistemos",
        "price":    "nuo 299€/mėn",
        "pitch_lt": "automatizuoja maršrutus, dokumentus, darbo laiko apskaitą, transporto logistiką",
    },
}

# ── Service Targets — defines what to search for each service ─────────────────
# Each entry maps a service to:
#   label       — displayed in the UI
#   description — subtitle in UI
#   icon        — emoji icon
#   industries  — list of industry query strings to search
#   website_filter — which website statuses qualify ("none","old","modern","unreachable")
SERVICE_TARGETS = {
    "svetaine": {
        "label":         "Svetainė / El. parduotuvė",
        "description":   "Įmonės be svetainės arba su sena, pasenusia svetaine",
        "icon":          "🌐",
        "industries":    [
            "kirpykla", "grožio salonas", "nagų salonas", "restoranas", "kavinė",
            "autoservisas", "statybos", "valymo paslaugos", "veterinarija",
            "masažo salonas", "saugos paslaugos", "sporto klubas",
        ],
        "website_filter": ["none", "old"],
    },
    "meta_ads": {
        "label":         "Meta reklamos",
        "description":   "Įmonės su svetaine, kurioms reikia Facebook/Instagram reklamos",
        "icon":          "📣",
        "industries":    [
            "restoranas", "kavinė", "viešbutis", "grožio salonas", "kirpykla",
            "sporto klubas", "odontologas", "nekilnojamasis turtas",
            "interjero dizainas", "autoservisas",
        ],
        "website_filter": ["old", "modern"],
    },
    "chatbot": {
        "label":         "AI Chatbot",
        "description":   "Įmonės su svetaine, kurioms reikia 24/7 automatinio aptarnavimo",
        "icon":          "🤖",
        "industries":    [
            "restoranas", "odontologas", "veterinarija", "viešbutis", "grožio salonas",
            "advokatų kontora", "nekilnojamasis turtas", "buhalterinės paslaugos",
            "sporto klubas", "masažo salonas",
        ],
        "website_filter": ["old", "modern"],
    },
    "verslo_valdymas": {
        "label":         "Verslo valdymo sistemos",
        "description":   "Transporto, logistikos, gamybos ir sandėliavimo įmonės",
        "icon":          "⚙️",
        "industries":    [
            "transporto paslaugos", "logistika", "sandėliavimas",
            "gamyba", "statybos",
        ],
        "website_filter": ["none", "old", "modern", "unreachable"],
    },
}

# ── Web search keywords (Lithuanian terms for DuckDuckGo/Bing search) ─────────
# Maps industry query → better Lithuanian search term used on company websites
INDUSTRY_WEB_KEYWORDS = {
    "kirpykla":                 "kirpykla",
    "grožio salonas":           "grožio salonas",
    "nagų salonas":             "nagų salonas studija",
    "restoranas":               "restoranas",
    "kavinė":                   "kavinė kavos baras",
    "picerija":                 "picerija pica",
    "odontologas":              "odontologas odontologijos klinika",
    "advokatų kontora":         "advokatų kontora teisinės paslaugos",
    "nekilnojamasis turtas":    "nekilnojamojo turto agentūra",
    "sporto klubas":            "sporto klubas fitneso centras",
    "autoservisas":             "autoservisas automobilių remontas",
    "viešbutis":                "viešbutis nakvynė",
    "statybos":                 "statybos paslaugos statybos įmonė",
    "interjero dizainas":       "interjero dizainas",
    "buhalterinės paslaugos":   "buhalterinės paslaugos apskaita",
    "veterinarija":             "veterinarinė klinika veterinarija",
    "masažo salonas":           "masažo salonas masažo paslaugos",
    "valymo paslaugos":         "valymo paslaugos patalpų valymas",
    "saugos paslaugos":         "apsaugos paslaugos apsaugos sistemos",
    "transporto paslaugos":     "krovinių pervežimas transporto paslaugos",
    "logistika":                "logistikos paslaugos logistika",
    "sandėliavimas":            "sandėliavimas sandėlių nuoma",
    "gamyba":                   "gamybos įmonė pramonė",
}

# ── Output ────────────────────────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "leads")
