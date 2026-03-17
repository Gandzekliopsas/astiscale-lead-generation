"""
OpenStreetMap Overpass API — free business finder.
Returns real Lithuanian businesses with names, phones, websites, emails.
No API key needed, no bot protection issues.
"""
import time
import logging
from typing import Optional

import requests

from sources.rekvizitai import BusinessLead

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Lithuanian city bounding boxes [south, west, north, east]
CITY_BBOX = {
    "vilnius":     (54.580, 25.020, 54.760, 25.400),
    "kaunas":      (54.840, 23.820, 54.960, 24.040),
    "klaipeda":    (55.650, 21.070, 55.780, 21.250),
    "siauliai":    (55.880, 23.230, 55.980, 23.380),
    "panevezys":   (55.700, 24.290, 55.780, 24.430),
    "alytus":      (54.370, 24.010, 54.430, 24.110),
    "marijampole": (54.540, 23.280, 54.590, 23.380),
    "mazeikiai":   (56.280, 22.280, 56.360, 22.380),
    "jonava":      (55.060, 24.240, 55.110, 24.310),
    "utena":       (55.480, 25.580, 55.530, 25.680),
}

# OSM tags for each industry (query → list of tag matchers)
INDUSTRY_TAGS = {
    "kirpykla":                   [('shop', 'hairdresser'), ('amenity', 'hairdresser')],
    "grožio salonas":             [('shop', 'beauty'), ('shop', 'cosmetics')],
    "nagų salonas":               [('shop', 'nail_salon'), ('shop', 'beauty')],
    "restoranas":                 [('amenity', 'restaurant')],
    "kavinė":                     [('amenity', 'cafe'), ('amenity', 'bar')],
    "picerija":                   [('amenity', 'restaurant')],   # filter by cuisine later
    "odontologas":                [('amenity', 'dentist'), ('healthcare', 'dentist')],
    "advokatų kontora":           [('office', 'lawyer'), ('office', 'legal')],
    "nekilnojamasis turtas":      [('office', 'estate_agent'), ('office', 'real_estate_agent')],
    "sporto klubas":              [('leisure', 'fitness_centre'), ('leisure', 'sports_centre'), ('sport', 'fitness')],
    "autoservisas":               [('shop', 'car_repair'), ('amenity', 'car_repair')],
    "viešbutis":                  [('tourism', 'hotel'), ('tourism', 'motel')],
    "statybos":                   [('office', 'construction_company'), ('craft', 'construction')],
    "interjero dizainas":         [('office', 'interior_design')],
    "buhalterinės paslaugos":     [('office', 'accountant'), ('office', 'tax_advisor')],
    "veterinarija":               [('amenity', 'veterinary'), ('shop', 'veterinary')],
    "masažo salonas":             [('leisure', 'massage_room'), ('shop', 'massage')],
    "valymo paslaugos":           [('office', 'cleaning')],
    "saugos paslaugos":           [('office', 'security')],
    "transporto paslaugos":       [('office', 'transport'), ('office', 'logistics')],
    "logistika":                  [('office', 'logistics'), ('landuse', 'industrial')],
    "sandėliavimas":              [('building', 'warehouse'), ('landuse', 'warehouse')],
    "gamyba":                     [('landuse', 'industrial'), ('building', 'industrial')],
}


def find_businesses(industry_query: str, city: str, max_results: int = 20) -> list:
    """
    Use OSM Overpass API to find businesses by industry + city.
    Returns list of BusinessLead objects.
    """
    bbox = CITY_BBOX.get(city.lower())
    if not bbox:
        logger.warning(f"No bounding box for city: {city}")
        return []

    tags = INDUSTRY_TAGS.get(industry_query.lower(), [])
    if not tags:
        # Generic fallback: search by name keyword
        return _search_by_name(industry_query, bbox, city, max_results)

    leads = []
    seen = set()

    for key, value in tags:
        if len(leads) >= max_results:
            break
        results = _overpass_query(key, value, bbox)
        for item in results:
            name = item.get("tags", {}).get("name", "").strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            lead = _to_lead(item, city=city, industry=industry_query)
            if lead:
                leads.append(lead)

    logger.info(f"  OSM found {len(leads)} leads for '{industry_query}' in '{city}'")
    return leads[:max_results]


def _overpass_query(key: str, value: str, bbox: tuple) -> list:
    """Run a single Overpass query for a specific tag in a bounding box."""
    s, w, n, e = bbox
    # Query nodes, ways, and relations with this tag
    query = f"""
[out:json][timeout:25];
(
  node["{key}"="{value}"]({s},{w},{n},{e});
  way["{key}"="{value}"]({s},{w},{n},{e});
);
out body;
"""
    import urllib.parse
    try:
        time.sleep(1.0)   # Be polite to Overpass
        url = OVERPASS_URL + "?data=" + urllib.parse.quote(query)
        resp = requests.get(url, timeout=30, headers={"User-Agent": "AstiScaleLeadGen/1.0"})
        if resp.status_code == 200 and resp.text.strip():
            data = resp.json()
            return data.get("elements", [])
        else:
            logger.warning(f"Overpass returned {resp.status_code}")
    except Exception as e:
        logger.warning(f"Overpass error: {e}")
    return []


def _search_by_name(keyword: str, bbox: tuple, city: str, max_results: int) -> list:
    """Fallback: search OSM nodes/ways with 'name' matching keyword."""
    s, w, n, e = bbox
    query = f"""
[out:json][timeout:25];
(
  node["name"~"{keyword}",i]({s},{w},{n},{e});
  way["name"~"{keyword}",i]({s},{w},{n},{e});
);
out body;
"""
    import urllib.parse
    leads = []
    try:
        time.sleep(1.0)
        url = OVERPASS_URL + "?data=" + urllib.parse.quote(query)
        resp = requests.get(url, timeout=30, headers={"User-Agent": "AstiScaleLeadGen/1.0"})
        if resp.status_code == 200 and resp.text.strip():
            for item in resp.json().get("elements", [])[:max_results]:
                lead = _to_lead(item, city=city, industry=keyword)
                if lead:
                    leads.append(lead)
    except Exception as e:
        logger.warning(f"OSM name search error: {e}")
    return leads


def _to_lead(item: dict, city: str, industry: str) -> Optional[BusinessLead]:
    """Convert an OSM element to a BusinessLead."""
    tags = item.get("tags", {})
    name = tags.get("name", "").strip()
    if not name:
        return None

    # Build address
    street    = tags.get("addr:street", "")
    housenr   = tags.get("addr:housenumber", "")
    addr_city = tags.get("addr:city", city.capitalize())
    address   = f"{street} {housenr}, {addr_city}".strip(", ")

    # Phone — OSM uses various contact tags
    phone = (
        tags.get("phone")
        or tags.get("contact:phone")
        or tags.get("phone:lt")
        or ""
    )

    # Email
    email = (
        tags.get("email")
        or tags.get("contact:email")
        or ""
    )

    # Website — store None when missing so the analyzer is called correctly
    website = (
        tags.get("website")
        or tags.get("contact:website")
        or tags.get("url")
        or None
    )
    if website:
        website = website.strip()
        if not website.startswith("http"):
            website = "https://" + website

    return BusinessLead(
        company_name=name,
        phone=phone,
        email=email,
        website=website,
        address=address,
        city=city,
        industry=industry,
    )
