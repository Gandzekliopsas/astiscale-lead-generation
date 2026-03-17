"""
AstiScale Lead Generation System
─────────────────────────────────
Runs daily to find Lithuanian businesses that need:
  • AI Chatbot
  • Website creation / modernization
  • Meta Ads (Facebook/Instagram)
  • AI business automation

Usage:
  python main.py                  # run now (find today's leads)
  python main.py --city vilnius   # target specific city
  python main.py --industry "kirpykla"  # target specific industry
  python main.py --limit 20       # max leads
  python main.py --no-email       # skip email generation (faster)
"""
import argparse
import io
import logging
import os
import random
import sys
from datetime import datetime
from typing import List

# Fix Windows console encoding for Lithuanian/Unicode characters
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Local imports ─────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from config import CITIES, INDUSTRIES, LEADS_PER_RUN, ANTHROPIC_API_KEY
from sources.rekvizitai import BusinessLead
from sources.osm_search import find_businesses as find_businesses_osm
from sources.google_search import enrich_from_rekvizitai
from sources.website_analyzer import analyze_website
from sources.contact_finder import find_contacts
from processors.service_recommender import recommend, build_service_summary
from processors.email_generator import generate_email
from output.excel_report import save_excel

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "output", "leads", f"run_{datetime.now().strftime('%Y-%m-%d')}.log"),
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)


# ── ANSI colors ───────────────────────────────────────────────────────────────
class C:
    RED    = "\033[91m"
    YEL    = "\033[93m"
    GRN    = "\033[92m"
    BLU    = "\033[94m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RESET  = "\033[0m"


def print_banner():
    print(f"""
{C.BOLD}{C.BLU}
  +----------------------------------------------+
  |   AstiScale Lead Generation System           |
  |   Automatinis klientu paieskas irankis       |
  +----------------------------------------------+
{C.RESET}""")


def process_lead(lead: BusinessLead, generate_emails: bool = True) -> BusinessLead:
    """Enrich a single lead: website analysis → contacts → service rec → email."""

    # 1. Analyze website
    logger.info(f"Analyzing website for: {lead.company_name}")
    if lead.website and lead.website.strip():
        wa = analyze_website(lead.website.strip())
        lead.website_status = wa["status"]
        lead.website_year = wa.get("year")
        lead.notes = wa.get("notes", "")
    else:
        lead.website_status = "none"
        lead.notes = "Nėra svetainės"

    # 2. Try to find more contacts from their website
    if lead.website and lead.website.strip() and (not lead.email or not lead.phone):
        contacts = find_contacts(lead.website)
        if not lead.email and contacts.get("email"):
            lead.email = contacts["email"]
        if not lead.phone and contacts.get("phone"):
            lead.phone = contacts["phone"]
        if not lead.vadovas and contacts.get("owner_name"):
            lead.vadovas = contacts["owner_name"]

    # 3. Recommend services
    lead.recommended_services = recommend(lead.website_status, lead.industry)

    # 4. Generate personalized email
    if generate_emails and ANTHROPIC_API_KEY:
        logger.info(f"  Generating email for: {lead.company_name}")
        lead.email_draft = generate_email(lead, lead.recommended_services)
    elif generate_emails and not ANTHROPIC_API_KEY:
        logger.warning("  ANTHROPIC_API_KEY not set — skipping email generation")

    return lead


def run(
    city: str = None,
    industry: str = None,
    limit: int = None,
    generate_emails: bool = True,
) -> List[BusinessLead]:
    """Main lead generation run."""
    print_banner()

    date_str = datetime.now().strftime("%Y-%m-%d")
    limit = limit or LEADS_PER_RUN

    # ── Select search targets ─────────────────────────────────────────────────
    if city:
        cities = [city]
    else:
        # Rotate through cities — pick 2-3 different ones per day
        random.shuffle(CITIES)
        cities = CITIES[:3]

    if industry:
        industries = [next((i for i in INDUSTRIES if i["query"] == industry), {"query": industry, "lt": industry, "en": industry})]
    else:
        # Pick a random subset of industries each day
        random.shuffle(INDUSTRIES)
        industries = INDUSTRIES[:6]

    logger.info(f"Target cities: {cities}")
    logger.info(f"Target industries: {[i['lt'] for i in industries]}")

    # ── Collect raw leads ─────────────────────────────────────────────────────
    raw_leads: List[BusinessLead] = []
    seen_names = set()

    for ind in industries:
        for cty in cities:
            if len(raw_leads) >= limit * 2:  # over-collect, filter duplicates later
                break
            logger.info(f"\n{'─'*50}")
            logger.info(f"Searching: {ind['lt']} in {cty.capitalize()}")
            new_leads = find_businesses_osm(ind["query"], cty, max_results=15)
            for lead in new_leads:
                key = lead.company_name.lower().strip()
                if key and key not in seen_names:
                    seen_names.add(key)
                    lead.industry = ind["lt"]
                    raw_leads.append(lead)
        if len(raw_leads) >= limit * 2:
            break

    logger.info(f"\n✅ Collected {len(raw_leads)} unique raw leads")

    # ── Prioritize leads ──────────────────────────────────────────────────────
    # Prefer leads that have email or phone (easier to contact)
    def priority(lead: BusinessLead) -> int:
        score = 0
        if lead.email:
            score += 3
        if lead.phone:
            score += 2
        if lead.vadovas:
            score += 1
        return score

    raw_leads.sort(key=priority, reverse=True)
    raw_leads = raw_leads[:limit]

    # ── Process each lead ─────────────────────────────────────────────────────
    processed: List[BusinessLead] = []

    for i, lead in enumerate(raw_leads, 1):
        print(f"\n{C.BOLD}[{i}/{len(raw_leads)}] {lead.company_name}{C.RESET}")
        try:
            enriched = process_lead(lead, generate_emails=generate_emails)
            processed.append(enriched)
            _print_lead_summary(enriched)
        except Exception as e:
            logger.error(f"Error processing {lead.company_name}: {e}")
            processed.append(lead)  # add partial lead anyway

    # ── Save Excel report ─────────────────────────────────────────────────────
    if processed:
        filepath = save_excel(processed, date_str)
        print(f"\n{C.BOLD}{C.GRN}✅ Baigta! {len(processed)} leadų išsaugota:{C.RESET}")
        print(f"   📁 {filepath}")

        # Print summary table
        _print_summary(processed)
    else:
        logger.warning("No leads found. Try different city/industry.")

    return processed


def _print_lead_summary(lead: BusinessLead):
    """Pretty-print one lead to console."""
    status_icon = {"none": f"{C.RED}❌", "old": f"{C.YEL}⚠️ ", "modern": f"{C.GRN}✅"}.get(
        lead.website_status, "  "
    )
    services = build_service_summary(lead.recommended_services)
    print(f"  {status_icon}{C.RESET}  Svetainė: {lead.website_status.upper()}")
    print(f"  👤 {lead.vadovas or '—'}")
    print(f"  📞 {lead.phone or '—'}")
    print(f"  📧 {lead.email or '—'}")
    print(f"  🛍️  {services}")
    if lead.email_draft:
        # Show subject line only
        first_line = lead.email_draft.split("\n")[0]
        print(f"  ✉️  {first_line[:80]}")


def _print_summary(leads: List[BusinessLead]):
    """Print final summary table."""
    total = len(leads)
    no_site = sum(1 for l in leads if l.website_status == "none")
    old_site = sum(1 for l in leads if l.website_status == "old")
    modern  = sum(1 for l in leads if l.website_status == "modern")
    has_email = sum(1 for l in leads if l.email)
    has_draft = sum(1 for l in leads if l.email_draft)

    print(f"""
{C.BOLD}{'─'*50}
📊 SANTRAUKA
{'─'*50}{C.RESET}
  Iš viso leadų    : {total}
  {C.RED}❌ Nėra svetainės{C.RESET} : {no_site}
  {C.YEL}⚠️  Sena svetainė{C.RESET}  : {old_site}
  {C.GRN}✅ Moderni svetainė{C.RESET}: {modern}
  📧 Turi el. paštą : {has_email}
  ✉️  Laiškai parašyti: {has_draft}
{C.BOLD}{'─'*50}{C.RESET}
""")


def main():
    os.makedirs(os.path.join(os.path.dirname(__file__), "output", "leads"), exist_ok=True)

    parser = argparse.ArgumentParser(
        description="AstiScale Lead Generation — automatinis klientų paieškos įrankis"
    )
    parser.add_argument("--city", help="Miestas (vilnius, kaunas, klaipeda...)")
    parser.add_argument("--industry", help="Industrija (kirpykla, restoranas...)")
    parser.add_argument("--limit", type=int, default=LEADS_PER_RUN, help="Maks. leadų skaičius")
    parser.add_argument("--no-email", action="store_true", help="Negeneruoti el. laiškų (greitesnis režimas)")
    args = parser.parse_args()

    run(
        city=args.city,
        industry=args.industry,
        limit=args.limit,
        generate_emails=not args.no_email,
    )


if __name__ == "__main__":
    main()
