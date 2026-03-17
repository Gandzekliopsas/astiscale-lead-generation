"""
Website Analyzer
Checks if a business has a website, and if so, how modern it is.

Returns:
  status : "none" | "old" | "modern"
  year   : detected copyright / creation year (int or None)
  notes  : short human-readable diagnosis
"""
import re
import time
import logging
from typing import Optional
from datetime import datetime

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "lt-LT,lt;q=0.9,en;q=0.8",
}

CURRENT_YEAR = datetime.now().year
OLD_THRESHOLD = 2020   # copyright year ≤ this → "old"


def analyze_website(url: str) -> dict:
    """
    Returns dict:
      status  : "none" | "old" | "modern"
      year    : int | None
      https   : bool
      mobile  : bool    (has viewport meta)
      notes   : str
    """
    result = {
        "status": "none",
        "year": None,
        "https": False,
        "mobile": False,
        "notes": "",
    }

    if not url:
        result["notes"] = "Nėra svetainės"
        return result

    # Normalize URL
    if not url.startswith("http"):
        url = "https://" + url

    try:
        resp = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        result["https"] = resp.url.startswith("https://")
    except requests.exceptions.SSLError:
        # Try http
        try:
            url_http = url.replace("https://", "http://")
            resp = requests.get(url_http, headers=HEADERS, timeout=12, allow_redirects=True)
            result["https"] = False
        except Exception as e:
            result["notes"] = f"Svetainė nepasiekiama: {e}"
            return result
    except Exception as e:
        result["notes"] = f"Svetainė nepasiekiama: {e}"
        return result

    if resp.status_code >= 400:
        result["notes"] = f"HTTP {resp.status_code} — svetainė neveikia"
        return result

    soup = BeautifulSoup(resp.text, "html.parser")

    # ── Mobile viewport ───────────────────────────────────────────────────────
    viewport = soup.find("meta", attrs={"name": re.compile("viewport", re.I)})
    result["mobile"] = viewport is not None

    # ── Copyright year ────────────────────────────────────────────────────────
    year = _extract_copyright_year(soup, resp.text)
    result["year"] = year

    # ── Old-website signals ───────────────────────────────────────────────────
    old_signals = []
    modern_signals = []

    # 1. Copyright year
    if year and year <= OLD_THRESHOLD:
        old_signals.append(f"© {year}")
    elif year and year >= 2022:
        modern_signals.append(f"© {year}")

    # 2. No mobile viewport
    if not result["mobile"]:
        old_signals.append("nėra viewport")

    # 3. No HTTPS
    if not result["https"]:
        old_signals.append("nėra HTTPS")

    # 4. Outdated tech signatures
    page_text = resp.text.lower()
    if "jquery/1." in page_text or "jquery-1." in page_text:
        old_signals.append("jQuery 1.x")
    if "bootstrap/3." in page_text or "bootstrap.min.css/3" in page_text:
        old_signals.append("Bootstrap 3")
    if "<table" in page_text and page_text.count("<table") > 5:
        old_signals.append("table layout")
    if "flash" in page_text or ".swf" in page_text:
        old_signals.append("Flash")

    # 5. Modern signals
    if any(fw in page_text for fw in ["react", "vue", "next.js", "nuxt", "svelte", "gatsby"]):
        modern_signals.append("modern JS framework")
    if "tailwind" in page_text:
        modern_signals.append("Tailwind CSS")
    if "bootstrap/5." in page_text or "bootstrap@5" in page_text:
        modern_signals.append("Bootstrap 5")
    if "wp-content" in page_text or "wordpress" in page_text:
        # WordPress can be old or new — check year
        pass

    # ── Decision ──────────────────────────────────────────────────────────────
    old_score = len(old_signals)
    modern_score = len(modern_signals)

    if old_score >= 2 or (year and year <= OLD_THRESHOLD):
        result["status"] = "old"
        result["notes"] = "Sena svetainė: " + ", ".join(old_signals) if old_signals else "Sena svetainė"
    elif modern_score >= 1 and old_score == 0:
        result["status"] = "modern"
        result["notes"] = "Moderni svetainė: " + ", ".join(modern_signals)
    else:
        # Default: if it loads, treat as modern unless year is old
        if year and year <= OLD_THRESHOLD:
            result["status"] = "old"
            result["notes"] = f"Sena svetainė (© {year})"
        else:
            result["status"] = "modern"
            result["notes"] = "Svetainė veikia" + (f", © {year}" if year else "")

    logger.info(
        f"  Website {url}: {result['status']} | year={year} | "
        f"https={result['https']} | mobile={result['mobile']}"
    )
    return result


def _extract_copyright_year(soup: BeautifulSoup, raw_html: str) -> Optional[int]:
    """Extract the most relevant copyright/creation year from a page."""
    # Look in footer first
    footer = soup.find("footer") or soup.find(id=re.compile("footer", re.I))
    search_text = footer.get_text() if footer else soup.get_text()

    # Pattern: © 2019, Copyright 2018, 2017-2021, etc.
    patterns = [
        r"©\s*(\d{4})",
        r"copyright\s*(?:©)?\s*(\d{4})",
        r"(\d{4})\s*[-–]\s*\d{4}\s*©",
        r"©\s*\d{4}\s*[-–]\s*(\d{4})",   # take the latest year in a range
    ]

    years = []
    for pat in patterns:
        for m in re.finditer(pat, search_text, re.IGNORECASE):
            y = int(m.group(1))
            if 2000 <= y <= CURRENT_YEAR:
                years.append(y)

    if years:
        return max(years)   # take the most recent year found

    # Fallback: look in meta tags
    for meta in soup.find_all("meta"):
        content = meta.get("content", "")
        m = re.search(r"\b(20\d{2})\b", content)
        if m:
            y = int(m.group(1))
            if 2000 <= y <= CURRENT_YEAR:
                return y

    return None
