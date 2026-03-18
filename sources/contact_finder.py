"""
Contact Finder
Scrapes additional contact info (email, phone, owner name) from a business's own website.
Used to supplement / improve data from rekvizitai.lt.
"""
import re
import logging
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
}

# Lithuanian city names found in addresses → canonical city key
CITY_PATTERNS = {
    "vilnius":      ["vilnius", "vilniuje", "vilniaus"],
    "kaunas":       ["kaunas", "kaune", "kauno"],
    "klaipeda":     ["klaipėda", "klaipėdoje", "klaipėdos"],
    "siauliai":     ["šiauliai", "šiauliuose", "šiaulių"],
    "panevezys":    ["panevėžys", "panevėžyje", "panevėžio"],
    "alytus":       ["alytus", "alytuje", "alytaus"],
    "marijampole":  ["marijampolė", "marijampolėje", "marijampolės"],
    "mazeikiai":    ["mažeikiai", "mažeikiuose", "mažeikių"],
    "jonava":       ["jonava", "jonavoje", "jonavos"],
    "utena":        ["utena", "utenoje", "utenos"],
}

# Sub-pages likely to have contact info
CONTACT_PATHS = [
    "/kontaktai", "/kontaktas", "/contact", "/contacts",
    "/apie-mus", "/apie", "/about", "/about-us",
    "/susisiekite", "/ryšiai",
]

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+370|8|00370)[\s\-]?\(?\d{1,3}\)?[\s\-]?\d{2,4}[\s\-]?\d{2,4}[\s\-]?\d{0,4}")

SPAM_DOMAINS = {
    "example.com", "test.com", "domain.com", "email.com",
    "sentry.io", "wix.com", "wordpress.com", "squarespace.com",
    "google.com", "facebook.com", "instagram.com",
}


def detect_city(text: str) -> str:
    """
    Detect which Lithuanian city is mentioned in an address string or webpage text.
    Returns the canonical city key (e.g. 'vilnius') or '' if not found.
    Prefers the first city found in the text — typically the city in the address line.
    """
    text_lower = text.lower()
    for city_key, variants in CITY_PATTERNS.items():
        for v in variants:
            if v in text_lower:
                return city_key
    return ""


def find_contacts(website_url: str) -> dict:
    """
    Returns dict with best email + phone + city found on the website.
    Falls back gracefully if site is unreachable.
    """
    result = {"email": "", "phone": "", "owner_name": "", "city": "", "address": ""}

    if not website_url:
        return result

    base = _normalize_url(website_url)
    pages_to_check = [base] + [base.rstrip("/") + p for p in CONTACT_PATHS]

    emails = set()
    phones = set()

    for url in pages_to_check[:5]:   # limit to 5 pages per business
        html = _safe_get(url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")

        # ── Emails ────────────────────────────────────────────────────────────
        # 1. mailto links (most reliable)
        for a in soup.select("a[href^='mailto:']"):
            em = a["href"].replace("mailto:", "").split("?")[0].strip().lower()
            if _valid_email(em):
                emails.add(em)

        # 2. Regex in page text
        for em in EMAIL_RE.findall(soup.get_text()):
            if _valid_email(em):
                emails.add(em.lower())

        # ── Phones ────────────────────────────────────────────────────────────
        for a in soup.select("a[href^='tel:']"):
            ph = a["href"].replace("tel:", "").strip()
            if ph:
                phones.add(_clean_phone(ph))

        for ph in PHONE_RE.findall(soup.get_text()):
            phones.add(_clean_phone(ph))

        # ── Owner / contact person name ───────────────────────────────────────
        if not result["owner_name"]:
            result["owner_name"] = _extract_contact_person(soup)

        # ── Address / city from structured markup or address elements ──────────
        if not result["address"]:
            addr_el = (
                soup.select_one("[itemprop='address']")
                or soup.select_one(".address")
                or soup.select_one(".kontaktai address")
                or soup.select_one("address")
            )
            if addr_el:
                result["address"] = " ".join(addr_el.get_text().split()).strip()

    # Pick best email (prefer non-generic)
    if emails:
        result["email"] = _best_email(emails)

    # Pick first valid phone
    valid_phones = [p for p in phones if len(re.sub(r"\D", "", p)) >= 8]
    if valid_phones:
        result["phone"] = valid_phones[0]

    # Detect city from address or full page text of first page
    if result["address"]:
        result["city"] = detect_city(result["address"])

    logger.debug(
        f"  Contact finder: email={result['email']} phone={result['phone']} city={result['city']}"
    )
    return result


def _safe_get(url: str) -> Optional[str]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        pass
    return None


def _normalize_url(url: str) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    return url.rstrip("/")


def _valid_email(email: str) -> bool:
    if not email or "@" not in email:
        return False
    domain = email.split("@")[-1].lower()
    if domain in SPAM_DOMAINS:
        return False
    if any(s in email for s in ["noreply", "no-reply", "donotreply", "example"]):
        return False
    return True


def _clean_phone(phone: str) -> str:
    """Normalize Lithuanian phone number."""
    digits = re.sub(r"[^\d+]", "", phone)
    # Convert 8xxxxxxxx → +3708xxxxxxxx
    if digits.startswith("8") and len(digits) == 9:
        digits = "+370" + digits[1:]
    elif digits.startswith("370") and not digits.startswith("+"):
        digits = "+" + digits
    return digits


def _best_email(emails: set) -> str:
    """Prefer business/info emails over generic ones."""
    generic_prefixes = {"info", "hello", "kontaktai", "contact", "parama", "support"}
    specific = [e for e in emails if e.split("@")[0].lower() not in generic_prefixes]
    if specific:
        return sorted(specific)[0]
    return sorted(emails)[0]


def _extract_contact_person(soup: BeautifulSoup) -> str:
    """Try to find a named contact person on the page."""
    # Look for common patterns: "Vardas Pavardė — tel:"
    patterns = [
        r"([A-ZĄČĘĖĮŠŲŪŽ][a-ząčęėįšųūž]+\s+[A-ZĄČĘĖĮŠŲŪŽ][a-ząčęėįšųūž]+)\s*[—–\-|]\s*(?:tel|mob|el\. paštas)",
        r"(?:Vadovas|Direktorius|Savininkas|Owner|CEO|Manager)[:\s]+([A-ZĄČĘĖĮŠŲŪŽ][a-ząčęėįšųūž]+\s+[A-ZĄČĘĖĮŠŲŪŽ][a-ząčęėįšųūž]+)",
    ]
    text = soup.get_text()
    for pat in patterns:
        m = re.search(pat, text, re.MULTILINE)
        if m:
            return m.group(1).strip()
    return ""
