"""
imones.lt scraper — Lithuanian business directory
Direct industry + city search, returns business name, website, phone, address.
"""
import re
import time
import random
import logging
from urllib.parse import quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

from sources.rekvizitai import BusinessLead

logger = logging.getLogger(__name__)

BASE_URL = "https://www.imones.lt"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "lt-LT,lt;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.imones.lt/",
}

# City slugs for imones.lt
CITY_SLUGS = {
    "vilnius":     "vilnius",
    "kaunas":      "kaunas",
    "klaipeda":    "klaipeda",
    "siauliai":    "siauliai",
    "panevezys":   "panevezys",
    "alytus":      "alytus",
    "marijampole": "marijampole",
    "mazeikiai":   "mazeikiai",
    "jonava":      "jonava",
    "utena":       "utena",
}


def find_businesses(industry_query: str, city: str, max_results: int = 20) -> list:
    """
    Search imones.lt for businesses matching industry + city.
    Returns list of BusinessLead objects.
    """
    leads = []
    city_slug = CITY_SLUGS.get(city.lower(), city.lower())

    # imones.lt search URL
    url = f"{BASE_URL}/paieska?query={quote_plus(industry_query)}&miestasSlug={city_slug}"
    logger.info(f"  imones.lt: {url}")

    soup = _get(url)
    if not soup:
        # Try alternative URL format
        url2 = f"{BASE_URL}/imones?q={quote_plus(industry_query)}&city={city_slug}"
        soup = _get(url2)

    if not soup:
        logger.warning(f"  imones.lt not reachable for {industry_query}/{city}")
        return []

    # Extract company listings
    leads = _parse_listings(soup, city=city, industry=industry_query)

    # Try next page if needed
    if len(leads) < max_results:
        next_url = _get_next_page(soup, url)
        if next_url:
            time.sleep(random.uniform(2, 4))
            soup2 = _get(next_url)
            if soup2:
                leads.extend(_parse_listings(soup2, city=city, industry=industry_query))

    logger.info(f"  imones.lt found {len(leads)} leads for '{industry_query}' in '{city}'")
    return leads[:max_results]


def _get(url: str, retries: int = 2) -> BeautifulSoup | None:
    for attempt in range(retries):
        try:
            time.sleep(random.uniform(2, 4))
            resp = requests.get(url, headers=HEADERS, timeout=20)
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, "html.parser")
            logger.debug(f"  imones.lt status {resp.status_code}")
        except Exception as e:
            logger.warning(f"  imones.lt error ({attempt+1}): {e}")
            time.sleep(5)
    return None


def _parse_listings(soup: BeautifulSoup, city: str, industry: str) -> list:
    """Parse company cards from imones.lt search results."""
    leads = []

    # Try multiple selectors for company cards
    cards = (
        soup.select(".company-card, .company-item, .imone-card")
        or soup.select("[class*='company'], [class*='imone']")
        or soup.select("article, .result-item, .list-item")
    )

    if not cards:
        # Fallback: look for links to company pages
        links = [
            a for a in soup.select("a[href]")
            if re.match(r".*/imones?/\d+", a.get("href", ""))
               or re.match(r".*/imone/", a.get("href", ""))
        ]
        for a in links[:max(20, len(links))]:
            href = urljoin(BASE_URL, a["href"])
            name = a.get_text().strip()
            if name and len(name) > 2:
                leads.append(BusinessLead(
                    company_name=name,
                    city=city,
                    industry=industry,
                    rekvizitai_url=href,
                ))
        return leads

    for card in cards:
        lead = _parse_card(card, city=city, industry=industry)
        if lead and lead.company_name:
            leads.append(lead)

    return leads


def _parse_card(card: BeautifulSoup, city: str, industry: str) -> BusinessLead | None:
    """Extract info from a single company card."""
    try:
        lead = BusinessLead(company_name="", city=city, industry=industry)

        # Name
        name_el = card.select_one("h2, h3, .name, .title, [class*='name']")
        if name_el:
            lead.company_name = name_el.get_text().strip()

        if not lead.company_name:
            a_el = card.select_one("a[href]")
            if a_el:
                lead.company_name = a_el.get_text().strip()

        if not lead.company_name:
            return None

        # Website
        for a in card.select("a[href^='http']"):
            href = a["href"]
            if "imones.lt" not in href and "facebook" not in href:
                lead.website = href
                break

        # Phone
        for a in card.select("a[href^='tel:']"):
            lead.phone = a["href"].replace("tel:", "").strip()
            break
        if not lead.phone:
            phones = re.findall(r"(?:\+370|8)[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{3}", card.get_text())
            if phones:
                lead.phone = phones[0]

        # Email
        for a in card.select("a[href^='mailto:']"):
            lead.email = a["href"].replace("mailto:", "").split("?")[0].strip()
            break

        # Address
        addr_el = card.select_one("[class*='address'], [class*='adresas'], [itemprop='address']")
        if addr_el:
            lead.address = addr_el.get_text().strip()

        # Company page URL (for enrichment)
        main_link = card.select_one("a[href*='/imone']")
        if main_link:
            lead.rekvizitai_url = urljoin(BASE_URL, main_link["href"])

        return lead

    except Exception as e:
        logger.debug(f"Card parse error: {e}")
        return None


def _get_next_page(soup: BeautifulSoup, current_url: str) -> str | None:
    """Find the next page URL in pagination."""
    next_el = soup.select_one("a[rel='next'], .pagination .next, a:contains('Kitas')")
    if next_el:
        href = next_el.get("href", "")
        if href:
            return urljoin(BASE_URL, href)
    return None
