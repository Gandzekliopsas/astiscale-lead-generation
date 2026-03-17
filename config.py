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

# ── Email (for sending cold emails later) ─────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "astiscaleautomation@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# ── Agency Info ───────────────────────────────────────────────────────────────
AGENCY_NAME = "AstiScale"
AGENCY_EMAIL = "astiscaleautomation@gmail.com"
AGENCY_WEBSITE = "https://astiscale.com"
AGENT_NAME = "Mantas"   # Cold caller name
AGENT_PHONE = os.getenv("AGENT_PHONE", "")

# ── Search Settings ───────────────────────────────────────────────────────────
LEADS_PER_RUN = int(os.getenv("LEADS_PER_RUN", "30"))  # leads to find per day

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
    {"query": "kirpykla", "lt": "Kirpykla", "en": "Hair Salon"},
    {"query": "grožio salonas", "lt": "Grožio salonas", "en": "Beauty Salon"},
    {"query": "nagų salonas", "lt": "Nagų salonas", "en": "Nail Salon"},
    {"query": "restoranas", "lt": "Restoranas", "en": "Restaurant"},
    {"query": "kavinė", "lt": "Kavinė", "en": "Cafe"},
    {"query": "picerija", "lt": "Picerija", "en": "Pizzeria"},
    {"query": "odontologas", "lt": "Odontologas", "en": "Dentist"},
    {"query": "advokatų kontora", "lt": "Advokatų kontora", "en": "Law Firm"},
    {"query": "nekilnojamasis turtas", "lt": "NT agentūra", "en": "Real Estate"},
    {"query": "sporto klubas", "lt": "Sporto klubas", "en": "Gym"},
    {"query": "autoservisas", "lt": "Autoservisas", "en": "Auto Repair"},
    {"query": "viešbutis", "lt": "Viešbutis", "en": "Hotel"},
    {"query": "statybos", "lt": "Statybos", "en": "Construction"},
    {"query": "interjero dizainas", "lt": "Interjero dizainas", "en": "Interior Design"},
    {"query": "buhalterinės paslaugos", "lt": "Buhalterija", "en": "Accounting"},
    {"query": "veterinarija", "lt": "Veterinarija", "en": "Veterinary"},
    {"query": "masažo salonas", "lt": "Masažo salonas", "en": "Massage Salon"},
    {"query": "valymo paslaugos", "lt": "Valymo paslaugos", "en": "Cleaning Services"},
    {"query": "saugos paslaugos", "lt": "Apsauga", "en": "Security"},
    {"query": "transporto paslaugos", "lt": "Transportas", "en": "Transport"},
]

# ── Service Recommendation Thresholds ─────────────────────────────────────────
OLD_WEBSITE_YEAR_THRESHOLD = 2020   # copyright year older than this = "old website"
OLD_WEBSITE_AGE_THRESHOLD = 5       # years since last update (Wayback Machine)

# ── Services Offered ─────────────────────────────────────────────────────────
SERVICES = {
    "chatbot": {
        "name": "AI Chatbot",
        "lt": "AI Pokalbių robotas",
        "price": "nuo 99€/mėn",
        "pitch_lt": "automatizuoja klientų aptarnavimą 24/7, atsako į klausimus, renka kontaktus",
    },
    "website": {
        "name": "Website (modernizavimas / sukūrimas)",
        "lt": "Svetainės kūrimas / atnaujinimas",
        "price": "nuo 499€",
        "pitch_lt": "moderni, greita, optimizuota svetainė su SEO",
    },
    "meta_ads": {
        "name": "Meta Ads (Facebook/Instagram)",
        "lt": "Meta reklama",
        "price": "nuo 299€/mėn",
        "pitch_lt": "tikslinė reklama Facebook ir Instagram, kuri atneša realių klientų",
    },
    "ai_automation": {
        "name": "AI Automatizavimas",
        "lt": "AI verslo automatizavimas",
        "price": "nuo 199€/mėn",
        "pitch_lt": "automatizuoja pasikartojančias užduotis: rezervacijas, el. laiškus, ataskaitas",
    },
}

# ── Output ────────────────────────────────────────────────────────────────────
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output", "leads")
