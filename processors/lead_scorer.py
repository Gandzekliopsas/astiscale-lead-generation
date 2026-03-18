"""
Lead scoring — rates each lead 0-100 based on contact data quality and fit.
Higher score = better lead = contact first.
"""


def score_lead(lead) -> int:
    """Score a lead (dict or sqlite3.Row) from 0 to 100."""
    def _get(key):
        try:
            v = lead[key]
            return v if v is not None else ""
        except Exception:
            return ""

    score = 0

    # Email — most valuable (40 pts)
    email = str(_get("email"))
    if email and "@" in email and "." in email.split("@")[-1]:
        score += 40

    # Phone (15 pts)
    phone = str(_get("phone"))
    if phone and len(phone) >= 8:
        score += 15

    # Website status (25 pts)
    ws = str(_get("website_status"))
    score += {"none": 25, "old": 18, "unreachable": 8, "modern": 5}.get(ws, 0)

    # Manager name known (10 pts)
    mgr = str(_get("manager_name"))
    if mgr and len(mgr) > 3:
        score += 10

    # Major city (5 pts)
    city = str(_get("city")).lower()
    if city in ("vilnius", "kaunas", "klaipeda"):
        score += 5

    # Google rating bonus (5 pts)
    try:
        rating = float(_get("rating") or 0)
        if rating >= 4.0:
            score += 5
    except Exception:
        pass

    return min(score, 100)


def score_label(score: int) -> str:
    if score >= 75:
        return "🔥 Karštas"
    elif score >= 50:
        return "⚡ Vidutinis"
    elif score >= 25:
        return "❄️ Šaltas"
    return "⬜ Silpnas"


def score_color(score: int) -> str:
    """Return CSS color class for the score."""
    if score >= 75:
        return "score-hot"
    elif score >= 50:
        return "score-warm"
    elif score >= 25:
        return "score-ok"
    return "score-cold"
