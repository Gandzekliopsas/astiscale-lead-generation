"""
Rekvizitai.vz.lt scraper — Lithuanian business registry
Searches by industry keyword + city, extracts company info.

Strategy:
  1. Search the listing page for company slugs
  2. Fetch individual company pages (with long polite delays)
  3. Validate/filter extracted text to avoid picking up UI elements
"""
import re
import time
import random
import logging
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL  = "https://rekvizitai.vz.lt"
SEARCH_URL = "https://rekvizitai.vz.lt/imones/"

# Rekvizitai city ID map
CITY_IDS = {
    "vilnius":      "1",
    "kaunas":       "2",
    "klaipeda":     "3",
    "siauliai":     "4",
    "panevezys":    "5",
    "alytus":       "6",
    "marijampole":  "7",
    "mazeikiai":    "8",
    "jonava":       "9",
    "utena":        "10",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "lt-LT,lt;q=0.9,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Text that must NOT appear in a vadovas name
VADOVAS_BLOCKLIST = {
    "juridinio asmens istorija",
    "juridinis asmuo",
    "imones istorija",
    "daugiau informacijos",
    "perziureti",
    "registru centras",
    "rekvizitai",
    "veikla",
    "kontaktai",
    "apie mus",
    "pradzia",
    "pagrindinis",
}

# Looks like "Vardas Pavardė" — two tokens, both title-cased, Lithuanian chars ok
LT_NAME_RE = re.compile(
    r"^[A-ZĄČĘĖĮŠŲŪŽ][a-ząčęėįšųūž]{1,20}"
    r"\s+"
    r"[A-ZĄČĘĖĮŠŲŪŽ][a-ząčęėįšųūž]{1,25}$"
)


@dataclass
class BusinessLead:
    company_name: str
    company_code: str = ""
    vadovas: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""
    address: str = ""
    city: str = ""
    industry: str = ""
    rekvizitai_url: str = ""
    # Filled later
    website_status: str = ""
    website_year: Optional[int] = None
    recommended_services: list = field(default_factory=list)
    email_draft: str = ""
    notes: str = ""


def _get(url: str, timeout: int = 25, retries: int = 2) -> Optional[BeautifulSoup]:
    """GET with retry and polite delay."""
    for attempt in range(retries):
        try:
            time.sleep(random.uniform(3.0, 6.0))
            resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, "html.parser")
            elif resp.status_code == 429:
                logger.warning("Rate limited — sleeping 60s")
                time.sleep(60)
            elif resp.status_code in (403, 404):
                return None
        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on {url} (attempt {attempt+1})")
            time.sleep(10 * (attempt + 1))
        except Exception as e:
            logger.warning(f"Request error: {e}")
            time.sleep(5)
    return None


def _clean(text: str) -> str:
    return " ".join(text.split()).strip() if text else ""


def _is_valid_name(text: str) -> bool:
    """Check that text looks like a Lithuanian personal name."""
    if not text:
        return False
    text_lower = text.lower().strip()
    if any(bad in text_lower for bad in VADOVAS_BLOCKLIST):
        return False
    # Must match "Vardas Pavardė" pattern
    return bool(LT_NAME_RE.match(text.strip()))


def search_companies(query: str, city: str = "", max_pages: int = 2) -> list:
    """
    Search rekvizitai.vz.lt and return list of BusinessLead objects.
    """
    leads = []
    seen_slugs = set()

    city_param = ""
    if city.lower() in CITY_IDS:
        city_param = f"&city={CITY_IDS[city.lower()]}"

    for page in range(1, max_pages + 1):
        page_param = f"&page={page}" if page > 1 else ""
        url = f"{SEARCH_URL}?search={quote_plus(query)}{city_param}{page_param}"
        logger.info(f"Searching: {url}")

        soup = _get(url)
        if not soup:
            break

        # Collect company page slugs/URLs from search results
        slugs = _extract_company_links(soup)
        if not slugs:
            logger.info("  No company links found on this page")
            break

        for slug_url in slugs:
            if slug_url in seen_slugs:
                continue
            seen_slugs.add(slug_url)

            lead = _parse_company_page(slug_url, city=city, industry=query)
            if lead and lead.company_name:
                leads.append(lead)

    logger.info(f"  => {len(leads)} leads from '{query}' / '{city}'")
    return leads


def _extract_company_links(soup: BeautifulSoup) -> list:
    """Get all company page URLs from a search results page."""
    urls = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Company URLs look like /imone/{slug}/ — NOT /imones/
        if re.match(r".*/imone/[^/]+/?$", href):
            full = urljoin(BASE_URL, href)
            if full not in seen and "/imone/" in full:
                seen.add(full)
                urls.append(full)
    return urls


def _parse_company_page(url: str, city: str = "", industry: str = "") -> Optional[BusinessLead]:
    """Fetch and parse a single company detail page."""
    soup = _get(url)
    if not soup:
        return None

    try:
        lead = BusinessLead(
            company_name="",
            city=city,
            industry=industry,
            rekvizitai_url=url,
        )

        # ── Company name ──────────────────────────────────────────────────────
        for selector in ["h1.company-name", "h1[itemprop='name']", "h1"]:
            el = soup.select_one(selector)
            if el:
                lead.company_name = _clean(el.get_text())
                break

        if not lead.company_name:
            # Try title tag
            if soup.title:
                title = soup.title.get_text()
                # "CompanyName - Rekvizitai.lt" → take first part
                lead.company_name = title.split("-")[0].split("|")[0].strip()

        if not lead.company_name or "nerastas" in lead.company_name.lower():
            return None

        # ── Company code ──────────────────────────────────────────────────────
        text = soup.get_text()
        code_m = re.search(r"(?:kodas|Kodas)\s*[:\s]*(\d{7,9})", text)
        if code_m:
            lead.company_code = code_m.group(1)

        # ── Vadovas — strict validation ────────────────────────────────────────
        # Try various label patterns
        for label_re in [
            r"Vadovas",
            r"Direktorius",
            r"Generalinis direktorius",
            r"CEO",
            r"Savininkas",
        ]:
            el = soup.find(string=re.compile(label_re, re.I))
            if not el:
                continue
            # Walk up then find next sibling/element with text
            parent = el.find_parent()
            if not parent:
                continue
            for candidate in [parent.find_next_sibling(), parent.find_parent()]:
                if not candidate:
                    continue
                candidate_text = _clean(candidate.get_text())
                # Strip the label itself
                candidate_text = re.sub(label_re, "", candidate_text, flags=re.I).strip(": \n")
                # Take only first "name-like" part
                candidate_text = candidate_text.split("\n")[0].strip()
                if _is_valid_name(candidate_text):
                    lead.vadovas = candidate_text
                    break
            if lead.vadovas:
                break

        # Fallback: look for [Role]: [Name] patterns in raw text
        if not lead.vadovas:
            for m in re.finditer(
                r"(?:Vadovas|Direktorius|Savininkas)\s*[:\-–]\s*"
                r"([A-ZĄČĘĖĮŠŲŪŽ][a-ząčęėįšųūž]+\s+[A-ZĄČĘĖĮŠŲŪŽ][a-ząčęėįšųūž]+)",
                text
            ):
                if _is_valid_name(m.group(1)):
                    lead.vadovas = m.group(1)
                    break

        # ── Phone ─────────────────────────────────────────────────────────────
        for a in soup.select("a[href^='tel:']"):
            ph = a["href"].replace("tel:", "").strip()
            if ph and len(re.sub(r"\D", "", ph)) >= 8:
                lead.phone = ph
                break

        if not lead.phone:
            phones = re.findall(r"(?:\+370|8)[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{3}", text)
            if phones:
                lead.phone = phones[0].strip()

        # ── Email ─────────────────────────────────────────────────────────────
        for a in soup.select("a[href^='mailto:']"):
            em = a["href"].replace("mailto:", "").split("?")[0].strip().lower()
            if "@" in em and "rekvizitai" not in em:
                lead.email = em
                break

        if not lead.email:
            emails = re.findall(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
            for em in emails:
                if "rekvizitai" not in em and "example" not in em:
                    lead.email = em.lower()
                    break

        # ── Website ───────────────────────────────────────────────────────────
        SKIP_DOMAINS = {"rekvizitai.vz.lt", "facebook.com", "linkedin.com",
                        "google.com", "vz.lt", "registrucentras.lt"}
        for a in soup.select("a[href^='http']"):
            href = a["href"]
            if not any(d in href for d in SKIP_DOMAINS):
                lead.website = href
                break

        # ── Address ───────────────────────────────────────────────────────────
        addr_el = soup.select_one("[itemprop='address'], span.address, .adresas")
        if addr_el:
            lead.address = _clean(addr_el.get_text())

        logger.info(
            f"  Parsed: {lead.company_name[:40]} | "
            f"vadovas={lead.vadovas or '--'} | "
            f"email={lead.email or '--'} | "
            f"web={bool(lead.website)}"
        )
        return lead

    except Exception as e:
        logger.warning(f"Error parsing {url}: {e}")
        return None
