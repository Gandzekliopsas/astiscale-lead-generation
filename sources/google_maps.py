"""
Google Places API source — finds Lithuanian businesses by industry + city.
Requires GOOGLE_PLACES_API_KEY environment variable.
Falls back gracefully with a warning if key is missing.
"""
import logging
import os
import time
import requests
from typing import List

logger = logging.getLogger(__name__)

PLACES_TEXT_SEARCH = "https://maps.googleapis.com/maps/api/place/textsearch/json"
PLACES_DETAILS = "https://maps.googleapis.com/maps/api/place/details/json"

CITY_LT_NAMES = {
    "vilnius": "Vilnius", "kaunas": "Kaunas", "klaipeda": "Klaipėda",
    "siauliai": "Šiauliai", "panevezys": "Panevėžys", "alytus": "Alytus",
    "marijampole": "Marijampolė", "mazeikiai": "Mažeikiai",
    "jonava": "Jonava", "utena": "Utena",
}


def search_businesses(industry_query: str, city: str, max_results: int = 20) -> list:
    """Search Google Places for businesses. Returns list of dicts."""
    api_key = os.getenv("GOOGLE_PLACES_API_KEY", "")
    if not api_key:
        logger.debug("No GOOGLE_PLACES_API_KEY — skipping Google Maps source")
        return []

    city_name = CITY_LT_NAMES.get(city.lower(), city.capitalize())
    query = f"{industry_query} {city_name} Lietuva"
    results = []
    page_token = None

    for _ in range(3):  # up to 3 pages = 60 results
        params = {"query": query, "language": "lt", "key": api_key, "region": "lt"}
        if page_token:
            params["pagetoken"] = page_token
            time.sleep(2)
        try:
            resp = requests.get(PLACES_TEXT_SEARCH, params=params, timeout=15)
            data = resp.json()
        except Exception as e:
            logger.error(f"Google Maps request error: {e}")
            break

        status = data.get("status")
        if status == "ZERO_RESULTS":
            break
        if status != "OK":
            logger.warning(f"Places API: {status} — {data.get('error_message','')}")
            break

        for place in data.get("results", []):
            if len(results) >= max_results:
                break
            detail = _get_place_details(place["place_id"], api_key)
            results.append({
                "company_name": place.get("name", ""),
                "phone": detail.get("phone", ""),
                "website": detail.get("website", ""),
                "address": place.get("formatted_address", ""),
                "city": city,
                "rating": place.get("rating", 0),
                "review_count": place.get("user_ratings_total", 0),
                "google_maps_url": detail.get("url", ""),
                "source": "google_maps",
            })
            time.sleep(0.05)

        page_token = data.get("next_page_token")
        if not page_token or len(results) >= max_results:
            break

    logger.info(f"Google Maps: {len(results)} results for '{industry_query}' in {city_name}")
    return results[:max_results]


def _get_place_details(place_id: str, api_key: str) -> dict:
    try:
        resp = requests.get(PLACES_DETAILS, params={
            "place_id": place_id,
            "fields": "formatted_phone_number,website,url",
            "key": api_key,
        }, timeout=10)
        r = resp.json().get("result", {})
        return {"phone": r.get("formatted_phone_number", ""), "website": r.get("website", ""), "url": r.get("url", "")}
    except Exception:
        return {}
