"""
AstiScale Lead Generation Dashboard — FastAPI backend
Deploy on Railway: web: uvicorn app:app --host 0.0.0.0 --port $PORT
"""
import io
import logging
import os
import sys
import threading
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, BackgroundTasks, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db
from config import CITIES, INDUSTRIES, OUTPUT_DIR

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
    search: str = Query(None),
    limit: int = Query(100),
    offset: int = Query(0),
):
    return db.get_leads(
        run_date=date, city=city, industry=industry,
        status=status, search=search, limit=limit, offset=offset
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


# ── API: Config ───────────────────────────────────────────────────────────────

@app.get("/api/config")
def config():
    return {
        "cities": CITIES,
        "industries": [i["query"] for i in INDUSTRIES],
        "industries_full": INDUSTRIES,
    }


# ── API: Run lead generation ──────────────────────────────────────────────────

class RunRequest(BaseModel):
    city: str = ""
    industry: str = ""
    limit: int = 20
    generate_emails: bool = True


@app.post("/api/run")
def start_run(req: RunRequest, background_tasks: BackgroundTasks):
    global _active_run_id
    with _run_lock:
        # Check if already running
        if _active_run_id is not None:
            run = db.get_run(_active_run_id)
            if run and run["status"] == "running":
                return {"error": "A run is already in progress", "run_id": _active_run_id}

        run_id = db.create_run(req.city, req.industry)
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
        log(f"  City: {req.city or 'auto'} | Industry: {req.industry or 'auto'} | Limit: {req.limit}")

        # Patch main.run to capture logs and save leads to DB
        from sources.osm_search import find_businesses as find_businesses_osm
        from sources.website_analyzer import analyze_website
        from sources.contact_finder import find_contacts
        from processors.service_recommender import recommend
        from processors.email_generator import generate_email
        from sources.rekvizitai import BusinessLead
        from config import CITIES, INDUSTRIES, LEADS_PER_RUN, ANTHROPIC_API_KEY
        import random

        date_str = datetime.now().strftime("%Y-%m-%d")

        cities = [req.city] if req.city else random.sample(CITIES, min(3, len(CITIES)))
        if req.industry:
            industries = [next((i for i in INDUSTRIES if i["query"] == req.industry),
                               {"query": req.industry, "lt": req.industry, "en": req.industry})]
        else:
            random.shuffle(INDUSTRIES)
            industries = INDUSTRIES[:6]

        log(f"  Cities: {cities}")
        log(f"  Industries: {[i['lt'] for i in industries]}")

        raw_leads = []
        seen = set()

        for ind in industries:
            for cty in cities:
                if len(raw_leads) >= req.limit * 2:
                    break
                log(f"\n[{datetime.now().strftime('%H:%M:%S')}] Searching {ind['lt']} in {cty.capitalize()}...")
                new = find_businesses_osm(ind["query"], cty, max_results=15)
                for lead in new:
                    key = lead.company_name.lower().strip()
                    if key and key not in seen:
                        seen.add(key)
                        lead.industry = ind["lt"]
                        raw_leads.append(lead)
                log(f"  Found {len(new)} leads")
            if len(raw_leads) >= req.limit * 2:
                break

        # Prioritize
        def priority(l):
            return (3 if l.email else 0) + (2 if l.phone else 0)
        raw_leads.sort(key=priority, reverse=True)
        raw_leads = raw_leads[:req.limit]

        log(f"\n[{datetime.now().strftime('%H:%M:%S')}] Processing {len(raw_leads)} leads...")

        processed = []
        for i, lead in enumerate(raw_leads, 1):
            log(f"\n[{i}/{len(raw_leads)}] {lead.company_name}")
            try:
                # Website
                if lead.website:
                    wa = analyze_website(lead.website)
                    lead.website_status = wa["status"]
                    lead.website_year = wa.get("year")
                    lead.notes = wa.get("notes", "")
                    log(f"  Website: {wa['status'].upper()}")
                else:
                    lead.website_status = "none"
                    lead.notes = "Nėra svetainės"
                    log(f"  Website: NONE")

                # Contacts from website
                if lead.website and (not lead.email or not lead.phone):
                    contacts = find_contacts(lead.website)
                    if not lead.email and contacts.get("email"):
                        lead.email = contacts["email"]
                    if not lead.phone and contacts.get("phone"):
                        lead.phone = contacts["phone"]

                # Services
                lead.recommended_services = recommend(lead.website_status, lead.industry)

                # Email
                if req.generate_emails and ANTHROPIC_API_KEY:
                    lead.email_draft = generate_email(lead, lead.recommended_services)
                    log(f"  Email: generated")

                # Save to DB
                db.insert_lead(date_str, lead)
                processed.append(lead)

            except Exception as e:
                log(f"  ERROR: {e}")

        # Also save Excel
        try:
            from output.excel_report import save_excel
            save_excel(processed, date_str)
            log(f"\n[{datetime.now().strftime('%H:%M:%S')}] Excel saved.")
        except Exception as e:
            log(f"Excel save error: {e}")

        log(f"\n✅ Done! {len(processed)} leads saved.")
        db.finish_run(run_id, len(processed), "completed")

    except Exception as e:
        db.append_run_log(run_id, f"\n❌ Fatal error: {e}")
        db.finish_run(run_id, 0, "failed")
    finally:
        with _run_lock:
            _active_run_id = None
