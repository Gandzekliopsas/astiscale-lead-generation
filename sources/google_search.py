"""
Google / DuckDuckGo based business finder.
Searches for real Lithuanian businesses by industry + city and extracts their
website URLs. No API key required — uses public search HTML.
"""
import re
import time
import random
import logging
from urllib.parse import quote_plus, urlparse

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

# Domains to skip in search results
SKIP_DOMAINS = {
    "facebook.com", "instagram.com", "linkedin.com", "youtube.com",
    "google.com", "wikipedia.org", "rekvizitai.vz.lt", "vz.lt",
    "delfi.lt", "15min.lt", "lrytas.lt", "lrt.lt",
    "tripadvisor.com", "foursquare.com", "yelp.com",
    "booking.com", "airbnb.com", "maps.app",
}

CITY_LT = {
    "vilnius": "Vilniuje",
    "kaunas": "Kaune",
    "klaipeda": "Klaipėdoje",
    "siauliai": "Šiauliuose",
    "panevezys": "Panevėžyje",
    "alytus": "Alytuje",
    "marijampole": "Marijampolėje",
    "mazeikiai": "Mažeikiuose",
    "jonava": "Jonavoje",
    "utena": "Utenoje",
}


def find_businesses(industry_query: str, city: str, max_results: int = 15) -> list:
    """
    Find business websites using DuckDuckGo search.
    Returns list of BusinessLead objects with at least company_name + website set.
    """
    leads = []
    city_lt = CITY_LT.get(city.lower(), city.capitalize())

    # Multiple search queries to get varied results
    queries = [
        f"{industry_query} {city_lt} kontaktai",
        f"{industry_query} {city_lt} svetainė",
        f'"{industry_query}" {city_lt} -facebook -instagram',
    ]

    seen_domains = set()

    for query in queries:
        if len(leads) >= max_results:
            break
        new_leads = _ddg_search(query, city=city, industry=industry_query, seen_domains=seen_domains)
        leads.extend(new_leads)
        time.sleep(random.uniform(3, 6))

    logger.info(f"  Google search found {len(leads)} business websites for '{industry_query}' in '{city}'")
    return leads[:max_results]


def _ddg_search(query: str, city: str, industry: str, seen_domains: set) -> list:
    """Search DuckDuckGo HTML and extract business website leads."""
    leads = []
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

    try:
        time.sleep(random.uniform(1, 2))
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code != 200:
            logger.warning(f"DDG returned {resp.status_code}")
            return []
    except Exception as e:
        logger.warning(f"DDG search failed: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")

    # DuckDuckGo HTML results have links in .result__a or .result__url
    results = soup.select(".result")
    if not results:
        results = soup.select(".web-result, .results_links")

    for result in results:
        # Get title
        title_el = result.select_one(".result__title, .result__a, h2")
        title = title_el.get_text().strip() if title_el else ""

        # Get URL
        url_el = result.select_one(".result__url, a.result__a")
        href = ""
        if url_el:
            if url_el.name == "a":
                href = url_el.get("href", "")
            else:
                href = url_el.get_text().strip()

        # Also try data-href
        if not href:
            a_el = result.select_one("a[href]")
            if a_el:
                href = a_el.get("href", "")

        if not href:
            continue

        # Clean DDG redirect URLs
        website = _clean_ddg_url(href)
        if not website:
            continue

        domain = urlparse(website).netloc.lower().replace("www.", "")
        if not domain or domain in SKIP_DOMAINS or any(s in domain for s in SKIP_DOMAINS):
            continue
        if domain in seen_domains:
            continue
        seen_domains.add(domain)

        # Extract company name from title (remove common suffixes)
        company_name = _extract_company_name(title)
        if not company_name:
            company_name = domain.replace(".lt", "").replace(".eu", "").replace(".com", "").title()

        # Get snippet for extra info
        snippet_el = result.select_one(".result__snippet")
        notes = snippet_el.get_text().strip()[:150] if snippet_el else ""

        lead = BusinessLead(
            company_name=company_name,
            website=website,
            city=city,
            industry=industry,
            notes=notes,
        )
        leads.append(lead)
        logger.debug(f"    Found: {company_name} → {website}")

    return leads


def _clean_ddg_url(href: str) -> str:
    """Extract the real URL from a DuckDuckGo redirect or raw URL."""
    if not href:
        return ""

    # DDG redirect: //duckduckgo.com/l/?uddg=https%3A%2F%2F...
    if "uddg=" in href:
        from urllib.parse import unquote, parse_qs, urlparse as up
        parsed = up(href)
        params = parse_qs(parsed.query)
        if "uddg" in params:
            return unquote(params["uddg"][0])

    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href

    return ""


def _extract_company_name(title: str) -> str:
    """Clean up a search result title to get a company name."""
    if not title:
        return ""
    # Remove common suffixes
    title = re.sub(
        r"\s*[-|–]\s*(Pradžia|Pagrindinis|Home|Kontaktai|Apie mus|Svetainė|\.lt|\.eu|\.com).*$",
        "", title, flags=re.I
    )
    title = re.sub(r"\s*\|\s*.*$", "", title)
    title = title.strip()
    return title[:60] if title else ""


def enrich_from_rekvizitai(lead: BusinessLead) -> BusinessLead:
    """
    Try to enrich a lead (found via Google) with rekvizitai data:
    vadovas name, company code, official address.
    Uses the company name to search on rekvizitai.
    """
    if not lead.company_name:
        return lead

    from sources.rekvizitai import search_companies
    time.sleep(random.uniform(3, 5))

    try:
        results = search_companies(lead.company_name, max_pages=1)
        # Take first result that matches company name
        for r in results:
            if _name_match(r.company_name, lead.company_name):
                if r.vadovas:
                    lead.vadovas = r.vadovas
                if r.phone and not lead.phone:
                    lead.phone = r.phone
                if r.email and not lead.email:
                    lead.email = r.email
                if r.company_code:
                    lead.company_code = r.company_code
                if r.address:
                    lead.address = r.address
                if r.rekvizitai_url:
                    lead.rekvizitai_url = r.rekvizitai_url
                break
    except Exception as e:
        logger.debug(f"Rekvizitai enrichment failed for {lead.company_name}: {e}")

    return lead


def _name_match(a: str, b: str) -> bool:
    """Fuzzy company name match."""
    def normalize(s):
        return re.sub(r'[^a-ząčęėįšųūž\s]', '', s.lower()).strip()
    na, nb = normalize(a), normalize(b)
    return na[:20] in nb or nb[:20] in na
