"""
Web search-based business finder — DuckDuckGo HTML (no API key needed).

For each industry+city combination, we search:
  1. DuckDuckGo: "{industry LT keyword}" "{city LT name}" kontaktai
  2. DuckDuckGo: {industry keyword} {city} tel. el.paštas site:.lt
  3. Bing HTML fallback if DDG blocks us

Returns BusinessLead objects with real, verified website URLs.
This is the most reliable source for finding the RIGHT city + industry
because Google/DDG already geo-index business websites correctly.
"""
import re
import time
import random
import logging
from typing import List, Optional
from urllib.parse import quote_plus, unquote, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

from sources.rekvizitai import BusinessLead

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "lt-LT,lt;q=0.9,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://duckduckgo.com/",
}

# Lithuanian city names for search queries
CITY_LT = {
    "vilnius":      "Vilnius",
    "kaunas":       "Kaunas",
    "klaipeda":     "Klaipėda",
    "siauliai":     "Šiauliai",
    "panevezys":    "Panevėžys",
    "alytus":       "Alytus",
    "marijampole":  "Marijampolė",
    "mazeikiai":    "Mažeikiai",
    "jonava":       "Jonava",
    "utena":        "Utena",
}

# City name variants for address validation (used to verify a lead is in the right city)
CITY_VARIANTS = {
    "vilnius":      ["vilnius", "vilniaus"],
    "kaunas":       ["kaunas", "kauno"],
    "klaipeda":     ["klaipėda", "klaipėdos", "klaipeda"],
    "siauliai":     ["šiauliai", "šiaulių", "siauliai", "siauliu"],
    "panevezys":    ["panevėžys", "panevėžio", "panevezys"],
    "alytus":       ["alytus", "alytaus"],
    "marijampole":  ["marijampolė", "marijampolės"],
    "mazeikiai":    ["mažeikiai", "mažeikių"],
    "jonava":       ["jonava", "jonavos"],
    "utena":        ["utena", "utenos"],
}

# Domains to skip (not real business websites)
SKIP_DOMAINS = {
    "facebook.com", "instagram.com", "linkedin.com", "youtube.com",
    "twitter.com", "tiktok.com",
    "google.com", "maps.google.com", "goo.gl",
    "rekvizitai.vz.lt", "vz.lt", "registrucentras.lt", "sodra.lt",
    "cvbankas.lt", "cvonline.lt", "cv.lt", "work.lt", "jobs.lt",
    "wikipedia.org", "wikimedia.org",
    "118.lt", "yellow.lt", "imone.lt", "verslas.lt",
    "lrytas.lt", "delfi.lt", "15min.lt", "alfa.lt",
    "duckduckgo.com", "bing.com", "yahoo.com",
}

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+370|8)[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{3}")


def search_businesses(
    industry_query: str,
    industry_lt: str,
    city: str,
    max_results: int = 15,
) -> List[BusinessLead]:
    """
    Search the web for businesses in a specific city + industry.
    Uses multiple query strategies to maximize coverage.
    """
    city_name = CITY_LT.get(city.lower(), city.capitalize())
    seen_domains: set = set()
    leads: List[BusinessLead] = []

    # Strategy 1: Exact phrase search
    q1 = f'"{industry_lt}" "{city_name}" kontaktai'
    # Strategy 2: Broader search with contact signals
    q2 = f'{industry_lt} {city_name} tel el.paštas'
    # Strategy 3: Lithuanian .lt domains only
    q3 = f'{industry_lt} {city_name} site:.lt'

    for query in [q1, q2, q3]:
        if len(leads) >= max_results:
            break
        batch = _ddg_search(query, city, industry_lt, seen_domains)
        leads.extend(batch)

    # Fallback: Bing if DDG gave nothing
    if not leads:
        logger.info("DDG returned nothing — trying Bing fallback")
        leads = _bing_search(f'{industry_lt} {city_name} kontaktai', city, industry_lt, seen_domains)

    logger.info(f"WebSearch: {len(leads)} leads for '{industry_lt}' in '{city_name}'")
    return leads[:max_results]


def is_in_city(lead: BusinessLead, city: str) -> bool:
    """
    Check if a lead's address or city field matches the searched city.
    Used to filter out wrong-city results from rekvizitai.
    Returns True if city cannot be determined (give benefit of the doubt).
    """
    if not city:
        return True
    city_lower = city.lower()
    variants = CITY_VARIANTS.get(city_lower, [city_lower])
    addr = (lead.address or "").lower()
    lead_city = (lead.city or "").lower()
    # If address is empty we can't validate — keep the lead
    if not addr and not lead_city:
        return True
    return any(v in addr or v in lead_city for v in variants)


# ── DuckDuckGo ────────────────────────────────────────────────────────────────

def _ddg_search(
    query: str, city: str, industry: str, seen_domains: set
) -> List[BusinessLead]:
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}&kl=lt-lt"
    try:
        time.sleep(random.uniform(2.0, 4.0))   # be polite, DDG is sensitive
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            logger.warning(f"DDG returned {resp.status_code} for: {query}")
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        return _parse_ddg_results(soup, city, industry, seen_domains)
    except Exception as e:
        logger.warning(f"DDG search error: {e}")
        return []


def _parse_ddg_results(
    soup: BeautifulSoup, city: str, industry: str, seen_domains: set
) -> List[BusinessLead]:
    leads = []
    for result in soup.select(".result"):
        title_el = result.select_one(".result__title a")
        snippet_el = result.select_one(".result__snippet")

        if not title_el:
            continue

        # DDG wraps real URLs in redirect links — extract actual URL
        href = title_el.get("href", "")
        website = _extract_real_url(href)
        if not website:
            continue

        domain = _get_domain(website)
        if not domain or any(skip in domain for skip in SKIP_DOMAINS):
            continue
        if domain in seen_domains:
            continue
        seen_domains.add(domain)

        company_name = _clean(title_el.get_text())
        snippet = _clean(snippet_el.get_text()) if snippet_el else ""

        lead = BusinessLead(
            company_name=company_name,
            website=website,
            phone=_extract_phone(snippet),
            email=_extract_email(snippet),
            city=city,
            industry=industry,
        )
        leads.append(lead)

    return leads


# ── Bing fallback ─────────────────────────────────────────────────────────────

def _bing_search(
    query: str, city: str, industry: str, seen_domains: set
) -> List[BusinessLead]:
    url = f"https://www.bing.com/search?q={quote_plus(query)}&setlang=lt&cc=LT"
    bing_headers = {**HEADERS, "Referer": "https://www.bing.com/"}
    try:
        time.sleep(random.uniform(2.0, 3.0))
        resp = requests.get(url, headers=bing_headers, timeout=20)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        leads = []
        for result in soup.select("li.b_algo"):
            title_el = result.select_one("h2 a")
            snippet_el = result.select_one(".b_caption p")
            if not title_el:
                continue
            website = title_el.get("href", "")
            if not website.startswith("http"):
                continue
            domain = _get_domain(website)
            if not domain or any(skip in domain for skip in SKIP_DOMAINS):
                continue
            if domain in seen_domains:
                continue
            seen_domains.add(domain)
            snippet = _clean(snippet_el.get_text()) if snippet_el else ""
            lead = BusinessLead(
                company_name=_clean(title_el.get_text()),
                website=website,
                phone=_extract_phone(snippet),
                email=_extract_email(snippet),
                city=city,
                industry=industry,
            )
            leads.append(lead)
        return leads
    except Exception as e:
        logger.warning(f"Bing search error: {e}")
        return []


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_real_url(href: str) -> Optional[str]:
    """DDG wraps URLs — extract the real destination URL."""
    if not href:
        return None
    if "uddg=" in href:
        parsed = urlparse(href)
        params = parse_qs(parsed.query)
        real = params.get("uddg", [None])[0]
        if real:
            return unquote(real)
    if href.startswith("http"):
        return href
    return None


def _get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _extract_phone(text: str) -> str:
    m = PHONE_RE.search(text)
    return m.group(0).strip() if m else ""


def _extract_email(text: str) -> str:
    m = EMAIL_RE.search(text)
    if m:
        em = m.group(0).lower()
        if "example" not in em and "noreply" not in em:
            return em
    return ""


def _clean(text: str) -> str:
    return " ".join(text.split()).strip() if text else ""
