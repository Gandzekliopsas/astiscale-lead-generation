"""
AstiScale Lead Generation Dashboard — FastAPI backend
Deploy on Railway: web: uvicorn app:app --host 0.0.0.0 --port $PORT
"""
import io
import logging
import os
import smtplib
import ssl
import sys
import threading
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db
from config import (
    CITIES, INDUSTRIES, OUTPUT_DIR,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    AGENCY_NAME, AGENT_NAME, SERVICE_TARGETS,
)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="AstiScale Lead Generation Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files ──────────────────────────────────────────────────────────────
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# ── Startup ───────────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    db.init_db()
    _import_excel_leads()


def _import_excel_leads():
    """Import any existing Excel lead files into SQLite on first startup."""
    import glob, openpyxl
    excel_files = sorted(glob.glob(os.path.join(OUTPUT_DIR, "leads_*.xlsx")))
    if not excel_files:
        return
    with db.get_db() as conn:
        existing_dates = {r[0] for r in conn.execute("SELECT DISTINCT run_date FROM leads").fetchall()}

    for path in excel_files:
        date_str = os.path.basename(path).replace("leads_", "").replace(".xlsx", "")
        if date_str in existing_dates:
            continue
        try:
            wb = openpyxl.load_workbook(path)
            ws = wb["Potencialūs klientai"]
            with db.get_db() as conn:
                for row in ws.iter_rows(min_row=3, values_only=True):
                    if not row[0]:
                        continue
                    conn.execute("""
                        INSERT OR IGNORE INTO leads
                        (run_date, company_name, vadovas, phone, email, website,
                         city, industry, website_status, recommended_services,
                         email_draft, cold_call_script, notes)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """, (
                        date_str,
                        row[0] or '', row[1] or '', row[2] or '', row[3] or '',
                        row[4] or '', row[5] or '', row[6] or '',
                        _status_from_label(str(row[7] or '')),
                        row[8] or '', row[10] or '', row[11] or '', row[12] or '',
                    ))
            logging.info(f"Imported {path}")
        except Exception as e:
            logging.warning(f"Could not import {path}: {e}")


def _status_from_label(label: str) -> str:
    if "nėra" in label.lower() or "none" in label.lower() or "❌" in label:
        return "none"
    if "sena" in label.lower() or "old" in label.lower() or "⚠" in label:
        return "old"
    return "modern"


# ── Active runs state ─────────────────────────────────────────────────────────
_active_run_id: Optional[int] = None
_run_lock = threading.Lock()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def root():
    template_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    with open(template_path, encoding="utf-8") as f:
        return f.read()


# ── API: Stats ────────────────────────────────────────────────────────────────

@app.get("/api/stats")
def stats(date: str = Query(None)):
    return db.get_stats(date)


# ── API: Leads ────────────────────────────────────────────────────────────────

@app.get("/api/leads")
def leads(
    date: str = Query(None),
    city: str = Query(None),
    industry: str = Query(None),
    status: str = Query(None),
    service_target: str = Query(None),
    search: str = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
):
    return db.get_leads(
        run_date=date, city=city, industry=industry,
        status=status, service_target=service_target,
        search=search, limit=limit, offset=offset
    )


@app.get("/api/leads/{lead_id}")
def lead_detail(lead_id: int):
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")
    return lead


@app.patch("/api/leads/{lead_id}/contacted")
def mark_contacted(lead_id: int, contacted: bool = True, notes: str = ""):
    db.update_lead_contacted(lead_id, contacted, notes)
    return {"ok": True}


# ── API: Send email ───────────────────────────────────────────────────────────

@app.post("/api/leads/{lead_id}/send-email")
def send_lead_email(lead_id: int):
    """Send the email draft to the lead via Hostinger SMTP (port 465 SSL)."""
    lead = db.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "Lead not found")

    if not lead.get("email"):
        raise HTTPException(400, "Šis lead'as neturi el. pašto adreso")

    if not lead.get("email_draft"):
        raise HTTPException(400, "El. laiško juodraštis neegzistuoja")

    if not SMTP_PASSWORD:
        raise HTTPException(500, "SMTP slaptažodis nenurodytas (Railway kintamieji)")

    # Parse subject and body from the draft
    draft = lead["email_draft"]
    subject = f"{AGENCY_NAME} — {lead['company_name']}"
    body = draft

    lines = draft.split("\n")
    if lines and lines[0].startswith("Tema:"):
        subject = lines[0].replace("Tema:", "").strip()
        body = "\n".join(lines[1:]).strip()

    # Build MIME message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{AGENT_NAME} | {AGENCY_NAME} <{SMTP_USER}>"
    msg["To"]      = lead["email"]

    # Plain text part
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # Send via SSL (port 465)
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=15) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, lead["email"], msg.as_string())

        db.mark_email_sent(lead_id)
        return {"ok": True, "message": f"El. laiškas išsiųstas į {lead['email']}"}

    except smtplib.SMTPAuthenticationError:
        raise HTTPException(500, "SMTP autentifikacijos klaida — patikrinkite SMTP_USER ir SMTP_PASSWORD")
    except smtplib.SMTPException as e:
        raise HTTPException(500, f"SMTP klaida: {str(e)}")
    except Exception as e:
        raise HTTPException(500, f"Klaida siunčiant el. laišką: {str(e)}")


# ── API: Config ───────────────────────────────────────────────────────────────

@app.get("/api/config")
def config():
    return {
        "cities": CITIES,
        "industries": [i["query"] for i in INDUSTRIES],
        "industries_full": INDUSTRIES,
        "service_targets": SERVICE_TARGETS,
    }


# ── API: Run lead generation ──────────────────────────────────────────────────

class RunRequest(BaseModel):
    city: str = ""
    industry: str = ""
    service_target: str = ""   # "svetaine" | "meta_ads" | "chatbot" | "verslo_valdymas"
    limit: int = 20
    generate_emails: bool = True


@app.post("/api/run")
def start_run(req: RunRequest, background_tasks: BackgroundTasks):
    global _active_run_id
    with _run_lock:
        if _active_run_id is not None:
            run = db.get_run(_active_run_id)
            if run and run["status"] == "running":
                return {"error": "A run is already in progress", "run_id": _active_run_id}

        run_id = db.create_run(req.city, req.industry, req.service_target)
        _active_run_id = run_id

    background_tasks.add_task(_do_run, run_id, req)
    return {"run_id": run_id, "status": "started"}


@app.get("/api/run/{run_id}")
def run_status(run_id: int):
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


@app.get("/api/runs")
def recent_runs():
    return db.get_recent_runs(20)


# ── API: Download Excel ───────────────────────────────────────────────────────

@app.get("/api/download/{date}")
def download_excel(date: str):
    import glob
    files = glob.glob(os.path.join(OUTPUT_DIR, f"leads_{date}.xlsx"))
    if not files:
        raise HTTPException(404, "Excel file not found for this date")
    return FileResponse(
        files[0],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"leads_{date}.xlsx",
    )


# ── Background run task ───────────────────────────────────────────────────────

def _do_run(run_id: int, req: RunRequest):
    global _active_run_id

    def log(msg: str):
        db.append_run_log(run_id, msg)

    try:
        log(f"[{datetime.now().strftime('%H:%M:%S')}] Starting lead generation...")

        from sources.osm_search import find_businesses as find_businesses_osm
        from sources.rekvizitai import search_fast as search_rekvizitai
        from sources.website_analyzer import analyze_website
        from sources.contact_finder import find_contacts
        from processors.service_recommender import recommend
        from processors.email_generator import generate_email
        from sources.rekvizitai import BusinessLead
        from config import LEADS_PER_RUN, ANTHROPIC_API_KEY
        import random

        date_str = datetime.now().strftime("%Y-%m-%d")
        service_target = req.service_target

        # ── Determine which industries to search ──────────────────────────────
        if service_target and service_target in SERVICE_TARGETS:
            tgt = SERVICE_TARGETS[service_target]
            tgt_label = tgt["label"]
            website_filter = tgt["website_filter"]
            log(f"  Paslauga: {tgt_label}")

            # If user also picked a specific industry, use only that one
            if req.industry:
                industry_queries = [req.industry]
                log(f"  Industrija (pasirinkta): {req.industry}")
            else:
                industry_queries = tgt["industries"]
                log(f"  Industrijos: {', '.join(industry_queries)}")

            # Build industry dicts from config INDUSTRIES or create inline
            industries = []
            for q in industry_queries:
                match = next((i for i in INDUSTRIES if i["query"] == q), None)
                if match:
                    industries.append(match)
                else:
                    industries.append({"query": q, "lt": q.capitalize(), "en": q})
        else:
            # No service_target — classic mode: random industries
            service_target = ""
            website_filter = ["none", "old", "modern", "unreachable"]
            if req.industry:
                industries = [next((i for i in INDUSTRIES if i["query"] == req.industry),
                                   {"query": req.industry, "lt": req.industry, "en": req.industry})]
            else:
                random.shuffle(INDUSTRIES)
                industries = INDUSTRIES[:6]

        cities = [req.city] if req.city else random.sample(CITIES, min(5, len(CITIES)))
        log(f"  Miestai: {cities}")
        log(f"  Industrijos: {[i['lt'] for i in industries]}")
        if website_filter != ["none", "old", "modern", "unreachable"]:
            log(f"  Svetainės filtras: {website_filter}")

        # ── Search ────────────────────────────────────────────────────────────
        # Collect up to 10× the requested limit as raw candidates so the
        # website-status filter has enough material to reach req.limit leads.
        raw_leads = []
        seen = set()
        target_raw = req.limit * 10

        for ind in industries:
            for cty in cities:
                if len(raw_leads) >= target_raw:
                    break
                log(f"\n[{datetime.now().strftime('%H:%M:%S')}] Ieškoma: {ind['lt']} / {cty.capitalize()}...")

                # ── Source 1: OSM (fast, sparse data) ─────────────────────────
                osm_results = find_businesses_osm(ind["query"], cty, max_results=30)
                osm_added = 0
                for lead in osm_results:
                    key = lead.company_name.lower().strip()
                    if key and key not in seen:
                        seen.add(key)
                        lead.industry = ind["lt"]
                        raw_leads.append(lead)
                        osm_added += 1
                if osm_results:
                    log(f"  OSM: {len(osm_results)} rasta, {osm_added} naujų")

                # ── Source 2: Rekvizitai (comprehensive Lithuanian registry) ───
                if len(raw_leads) < target_raw:
                    try:
                        rek_keyword = ind["lt"]  # Lithuanian label works well on rekvizitai
                        log(f"  Rekvizitai: ieškoma '{rek_keyword}'...")
                        rek_results = search_rekvizitai(rek_keyword, cty, max_results=30)
                        rek_added = 0
                        for lead in rek_results:
                            key = lead.company_name.lower().strip()
                            if key and key not in seen:
                                seen.add(key)
                                lead.industry = ind["lt"]
                                raw_leads.append(lead)
                                rek_added += 1
                        log(f"  Rekvizitai: {len(rek_results)} rasta, {rek_added} naujų")
                    except Exception as e:
                        log(f"  Rekvizitai klaida: {e}")

            if len(raw_leads) >= target_raw:
                break

        # Prioritize by contact info
        def priority(l):
            return (3 if l.email else 0) + (2 if l.phone else 0)
        raw_leads.sort(key=priority, reverse=True)

        # ── Process ───────────────────────────────────────────────────────────
        log(f"\n[{datetime.now().strftime('%H:%M:%S')}] Apdorojama {len(raw_leads)} potencialių...")

        processed = []
        skipped   = 0

        for lead in raw_leads:
            if len(processed) >= req.limit:
                break

            try:
                # Website analysis
                if lead.website and lead.website.strip():
                    wa = analyze_website(lead.website.strip())
                    lead.website_status = wa["status"]
                    lead.website_year   = wa.get("year")
                    lead.notes          = wa.get("notes", "")
                else:
                    lead.website_status = "none"
                    lead.notes          = "Nėra svetainės"

                # ── Apply service filter ───────────────────────────────────────
                if lead.website_status not in website_filter:
                    log(f"  ⏭ Praleista '{lead.company_name}': svetainė={lead.website_status} (reikia: {website_filter})")
                    skipped += 1
                    continue

                log(f"\n[{len(processed)+1}] {lead.company_name} ({lead.website_status.upper()})")

                # Contact scraping from website
                if lead.website and (not lead.email or not lead.phone):
                    try:
                        contacts = find_contacts(lead.website)
                        if not lead.email and contacts.get("email"):
                            lead.email = contacts["email"]
                        if not lead.phone and contacts.get("phone"):
                            lead.phone = contacts["phone"]
                    except Exception:
                        pass

                # Services
                lead.service_target       = service_target
                lead.recommended_services = recommend(lead.website_status, lead.industry, service_target)

                # Email generation
                if req.generate_emails and ANTHROPIC_API_KEY:
                    lead.email_draft = generate_email(lead, lead.recommended_services, service_target)
                    log(f"  El. laiškas: sugeneruotas")

                # Save to DB
                db.insert_lead(date_str, lead, service_target)
                processed.append(lead)

            except Exception as e:
                log(f"  KLAIDA: {e}")

        if skipped:
            log(f"\n  Praleista (neatitiko filtro): {skipped}")

        # Save Excel
        try:
            from output.excel_report import save_excel
            save_excel(processed, date_str)
            log(f"\n[{datetime.now().strftime('%H:%M:%S')}] Excel išsaugotas.")
        except Exception as e:
            log(f"Excel klaida: {e}")

        log(f"\n✅ Baigta! {len(processed)} leadų išsaugota.")
        db.finish_run(run_id, len(processed), "completed")

    except Exception as e:
        db.append_run_log(run_id, f"\n❌ Kritinė klaida: {e}")
        db.finish_run(run_id, 0, "failed")
    finally:
        with _run_lock:
            _active_run_id = None
