"""
AstiScale Lead Generation Dashboard — FastAPI backend
Deploy on Railway: web: uvicorn app:app --host 0.0.0.0 --port $PORT
"""
import imaplib
import io
import logging
import os
import smtplib
import ssl
import sys
import threading
import email as email_lib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import base64
import hashlib
import secrets
from fastapi import FastAPI, BackgroundTasks, HTTPException, Query, Depends, Request
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ── Path setup ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database as db
from config import (
    CITIES, INDUSTRIES, OUTPUT_DIR,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
    AGENCY_NAME, AGENT_NAME, SERVICE_TARGETS,
)

# ── Auth ──────────────────────────────────────────────────────────────────────
_DASH_USER = os.getenv("DASHBOARD_USER", "astiscale")
_DASH_PASS = os.getenv("DASHBOARD_PASSWORD", "leads2025!")

# Public paths — no login required (email tracking pixel must work without auth)
_PUBLIC_PREFIXES = ("/track/",)

class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow public paths through without auth
        if any(request.url.path.startswith(p) for p in _PUBLIC_PREFIXES):
            return await call_next(request)

        # Check Authorization header
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
                username, _, password = decoded.partition(":")
                user_ok = secrets.compare_digest(
                    hashlib.sha256(username.encode()).digest(),
                    hashlib.sha256(_DASH_USER.encode()).digest(),
                )
                pass_ok = secrets.compare_digest(
                    hashlib.sha256(password.encode()).digest(),
                    hashlib.sha256(_DASH_PASS.encode()).digest(),
                )
                if user_ok and pass_ok:
                    return await call_next(request)
            except Exception:
                pass

        # Not authenticated — prompt browser login dialog
        return Response(
            content="Unauthorized",
            status_code=401,
            headers={"WWW-Authenticate": "Basic realm='AstiScale Leads'"},
        )

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="AstiScale Lead Generation Dashboard")
app.add_middleware(BasicAuthMiddleware)
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
    show_duplicates: bool = Query(False),
    limit: int = Query(100),
    offset: int = Query(0),
):
    return db.get_leads(
        run_date=date, city=city, industry=industry,
        status=status, service_target=service_target,
        search=search, show_duplicates=show_duplicates,
        limit=limit, offset=offset
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


class EditLeadRequest(BaseModel):
    company_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    notes: Optional[str] = None

@app.patch("/api/leads/{lead_id}/edit")
def edit_lead(lead_id: int, body: EditLeadRequest):
    if not db.get_lead(lead_id):
        raise HTTPException(404, "Lead not found")
    db.update_lead_edit(lead_id, body.company_name, body.email, body.phone, body.notes)
    return {"ok": True}


class BulkSendRequest(BaseModel):
    lead_ids: list

@app.post("/api/leads/bulk-send")
def bulk_send_emails(body: BulkSendRequest):
    """Send email drafts to multiple leads at once."""
    if not SMTP_PASSWORD:
        raise HTTPException(500, "SMTP slaptažodis nenurodytas")

    results = {"sent": [], "failed": [], "skipped": []}

    for lead_id in body.lead_ids:
        lead = db.get_lead(lead_id)
        if not lead:
            results["failed"].append({"id": lead_id, "reason": "Not found"})
            continue
        if not lead.get("email"):
            results["skipped"].append({"id": lead_id, "company": lead.get("company_name"), "reason": "Nėra el. pašto"})
            continue
        if lead.get("email_sent"):
            results["skipped"].append({"id": lead_id, "company": lead.get("company_name"), "reason": "Jau išsiųsta"})
            continue
        if not lead.get("email_draft"):
            results["skipped"].append({"id": lead_id, "company": lead.get("company_name"), "reason": "Nėra juodraščio"})
            continue

        draft = lead["email_draft"]
        subject = f"{AGENCY_NAME} — {lead['company_name']}"
        body_text = draft
        lines = draft.split("\n")
        if lines and lines[0].startswith("Tema:"):
            subject = lines[0].replace("Tema:", "").strip()
            body_text = "\n".join(lines[1:]).strip()

        dashboard_url = os.getenv("RAILWAY_PUBLIC_DOMAIN", "https://astiscalelead.up.railway.app")
        pixel = f'<img src="{dashboard_url}/track/{lead_id}.gif" width="1" height="1" style="display:none">'
        html_body = f"<html><body>{body_text.replace(chr(10), '<br>')}{pixel}</body></html>"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{AGENT_NAME} | {AGENCY_NAME} <{SMTP_USER}>"
        msg["To"] = lead["email"]
        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=15) as server:
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.sendmail(SMTP_USER, lead["email"], msg.as_string())
            db.mark_email_sent(lead_id)
            try:
                from processors.followup_generator import generate_followups
                b1, b2, b3 = generate_followups(lead, body_text, lead.get("service_target", ""))
                db.save_followup_emails(lead_id, b1, b2, b3)
            except Exception:
                pass
            try:
                from processors.lead_scorer import score_lead
                db.update_lead_score(lead_id, score_lead(dict(lead)))
            except Exception:
                pass
            results["sent"].append({"id": lead_id, "company": lead.get("company_name")})
        except Exception as e:
            results["failed"].append({"id": lead_id, "company": lead.get("company_name"), "reason": str(e)})

    return results


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

    dashboard_url = os.getenv("RAILWAY_PUBLIC_DOMAIN", "https://astiscalelead.up.railway.app")

    # Build MIME message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{AGENT_NAME} | {AGENCY_NAME} <{SMTP_USER}>"
    msg["To"]      = lead["email"]

    # Plain text part
    msg.attach(MIMEText(body, "plain", "utf-8"))

    # HTML part with tracking pixel
    pixel = f'<img src="{dashboard_url}/track/{lead_id}.gif" width="1" height="1" style="display:none">'
    html_body = f"<html><body>{body.replace(chr(10), '<br>')}{pixel}</body></html>"
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Send via SSL (port 465)
    try:
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=context, timeout=15) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, lead["email"], msg.as_string())

        db.mark_email_sent(lead_id)

        # Generate and save follow-up emails
        try:
            from processors.followup_generator import generate_followups
            service_target = lead.get("service_target", "")
            b1, b2, b3 = generate_followups(lead, body, service_target)
            db.save_followup_emails(lead_id, b1, b2, b3)
        except Exception as e:
            logging.warning(f"Follow-up generation failed for lead {lead_id}: {e}")

        # Score the lead
        try:
            from processors.lead_scorer import score_lead
            score = score_lead(dict(lead))
            db.update_lead_score(lead_id, score)
        except Exception as e:
            logging.warning(f"Lead scoring failed for lead {lead_id}: {e}")

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
        from sources.web_search import search_businesses as search_web, is_in_city
        from sources.website_analyzer import analyze_website
        from sources.contact_finder import find_contacts, detect_city
        from processors.service_recommender import recommend
        from processors.email_generator import generate_email
        from sources.rekvizitai import BusinessLead
        from config import LEADS_PER_RUN, ANTHROPIC_API_KEY, INDUSTRY_WEB_KEYWORDS
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

                def _add_leads(new_leads, source_name):
                    """Dedup and city-validate a batch of leads, return count added."""
                    added = 0
                    for lead in new_leads:
                        key = lead.company_name.lower().strip()
                        if not key or key in seen:
                            continue
                        # City validation — skip companies from wrong city
                        if lead.address and not is_in_city(lead, cty):
                            continue
                        seen.add(key)
                        lead.industry = ind["lt"]
                        raw_leads.append(lead)
                        added += 1
                    if new_leads:
                        log(f"  {source_name}: {len(new_leads)} rasta, {added} naujų")
                    return added

                # ── Source 1: OSM (fast, has some businesses with location data) ─
                osm_results = find_businesses_osm(ind["query"], cty, max_results=30)
                _add_leads(osm_results, "OSM")

                # ── Source 2: Web search (DuckDuckGo — finds RIGHT city+industry) ─
                if len(raw_leads) < target_raw:
                    try:
                        web_kw = INDUSTRY_WEB_KEYWORDS.get(ind["query"], ind["lt"])
                        web_results = search_web(ind["query"], web_kw, cty, max_results=20)
                        _add_leads(web_results, "Web paieška")
                    except Exception as e:
                        log(f"  Web paieška klaida: {e}")

                # ── Source 3: Rekvizitai (Lithuanian business registry) ──────────
                if len(raw_leads) < target_raw:
                    try:
                        rek_results = search_rekvizitai(ind["lt"], cty, max_results=30)
                        _add_leads(rek_results, "Rekvizitai")
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
                if lead.website and (not lead.email or not lead.phone or not lead.address):
                    try:
                        contacts = find_contacts(lead.website)
                        if not lead.email and contacts.get("email"):
                            lead.email = contacts["email"]
                        if not lead.phone and contacts.get("phone"):
                            lead.phone = contacts["phone"]
                        if not lead.address and contacts.get("address"):
                            lead.address = contacts["address"]
                        # Website-detected city is most reliable — override searched city
                        if contacts.get("city"):
                            lead.city = contacts["city"]
                    except Exception:
                        pass

                # Detect actual city from address if not yet determined from website
                if lead.address:
                    detected = detect_city(lead.address)
                    if detected:
                        lead.city = detected

                # Email fallback: search web for company email if still missing
                if not lead.email and lead.company_name:
                    try:
                        from sources.web_search import _ddg_search
                        q = f'"{lead.company_name}" el. paštas OR "info@" OR "kontaktai@"'
                        hits = _ddg_search(q, lead.city or "", lead.industry or "", set())
                        for hit in hits:
                            if hit.email:
                                lead.email = hit.email
                                break
                            if hit.website and not lead.website:
                                lead.website = hit.website
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

        # Mark cross-run duplicates
        try:
            db.dedup_after_run(run_id)
        except Exception as e:
            log(f"Dedup klaida: {e}")

        log(f"\n✅ Baigta! {len(processed)} leadų išsaugota.")
        db.finish_run(run_id, len(processed), "completed")

    except Exception as e:
        db.append_run_log(run_id, f"\n❌ Kritinė klaida: {e}")
        db.finish_run(run_id, 0, "failed")
    finally:
        with _run_lock:
            _active_run_id = None


# ── API: Tracking pixel ───────────────────────────────────────────────────────

@app.get("/track/{lead_id}.gif")
async def track_pixel(lead_id: int, background_tasks: BackgroundTasks):
    """1x1 transparent GIF — loads when email client renders images."""
    GIF = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
    background_tasks.add_task(_on_email_open, lead_id)
    return Response(content=GIF, media_type="image/gif", headers={
        "Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache"
    })

def _on_email_open(lead_id: int):
    result = db.track_email_open(lead_id)
    if result and result.get("open_count") == 1:
        try:
            import telegram_bot
            telegram_bot.notify_email_opened(result.get("company_name", ""), result.get("open_count", 1))
        except Exception:
            pass


# ── API: Analytics ────────────────────────────────────────────────────────────

@app.get("/api/analytics")
async def get_analytics():
    return db.get_analytics()


# ── API: CRM stage update ─────────────────────────────────────────────────────

@app.post("/api/leads/{lead_id}/stage")
async def update_stage(lead_id: int, body: dict):
    ok = db.update_crm_stage(lead_id, body.get("stage", ""))
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid stage")
    return {"ok": True}


# ── API: Check replies via IMAP ───────────────────────────────────────────────

@app.post("/api/check-replies")
async def check_replies(background_tasks: BackgroundTasks):
    background_tasks.add_task(_imap_check_replies)
    return {"ok": True, "message": "Tikrinama paštas..."}

def _imap_check_replies():
    from config import SMTP_USER, SMTP_PASSWORD
    if not SMTP_USER or not SMTP_PASSWORD:
        return
    try:
        mail = imaplib.IMAP4_SSL("imap.hostinger.com", 993)
        mail.login(SMTP_USER, SMTP_PASSWORD)
        mail.select("INBOX")
        _, data = mail.search(None, "UNSEEN")
        if not data[0]:
            mail.logout()
            return
        leads = db.get_leads(limit=9999)
        lead_email_map = {(l.get("email") or "").lower(): l for l in leads if l.get("email")}
        for num in data[0].split():
            try:
                _, msg_data = mail.fetch(num, "(RFC822)")
                msg = email_lib.message_from_bytes(msg_data[0][1])
                from_addr = msg.get("From", "").lower()

                # Extract plain text reply body
                reply_text = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            try:
                                reply_text = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                            except Exception:
                                pass
                            break
                else:
                    try:
                        reply_text = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
                    except Exception:
                        pass

                for lead_email, lead in lead_email_map.items():
                    if lead_email and lead_email in from_addr and not lead.get("replied"):
                        db.mark_reply_body(lead["id"], reply_text.strip())
                        try:
                            import telegram_bot
                            telegram_bot.notify_reply_received(lead.get("company_name", ""), lead_email)
                        except Exception:
                            pass
            except Exception:
                continue
        mail.logout()
    except Exception as e:
        logger.error(f"IMAP check failed: {e}")


# ── API: Send due follow-ups ──────────────────────────────────────────────────

@app.post("/api/followups/send-due")
async def send_due_followups_endpoint(background_tasks: BackgroundTasks):
    background_tasks.add_task(_send_due_followups)
    return {"ok": True}

@app.get("/api/followups/due-count")
async def due_followup_count():
    return {"count": len(db.get_due_followups())}

def _send_due_followups():
    due = db.get_due_followups()
    for lead in due:
        for num in [1, 2, 3]:
            if not lead.get(f"followup_{num}_sent") and lead.get(f"followup_{num}_body"):
                _send_followup(lead, num)
                break

def _send_followup(lead: dict, num: int):
    dashboard_url = os.getenv("RAILWAY_PUBLIC_DOMAIN", "https://astiscalelead.up.railway.app")

    if not lead.get("email"):
        return

    body = lead[f"followup_{num}_body"]
    subject_map = {1: "Re: dar vienas klausimas", 2: "Re: trumpas video demo?", 3: "Re: paskutinis laiškas"}
    subject = f"{subject_map.get(num, 'Re:')} — {lead['company_name']}"

    pixel = f'<img src="{dashboard_url}/track/{lead["id"]}.gif" width="1" height="1" style="display:none">'
    html = f"<html><body>{body.replace(chr(10), '<br>')}{pixel}</body></html>"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = lead["email"]
    msg.attach(MIMEText(body, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=15) as s:
            s.login(SMTP_USER, SMTP_PASSWORD)
            s.sendmail(SMTP_USER, lead["email"], msg.as_string())
        db.mark_followup_sent(lead["id"], num)
        try:
            import telegram_bot
            telegram_bot.notify_followup_sent(lead.get("company_name", ""), num)
        except Exception:
            pass
        logger.info(f"Follow-up #{num} sent to {lead['company_name']}")
    except Exception as e:
        logger.error(f"Follow-up #{num} send failed for {lead.get('company_name')}: {e}")


# ── API: Telegram test ────────────────────────────────────────────────────────

@app.post("/api/telegram/test")
async def telegram_test():
    try:
        import telegram_bot
        ok = telegram_bot.send("🔔 <b>AstiScale test</b>\nTelegram ryšys veikia! ✅")
        if ok:
            return {"ok": True}
        raise HTTPException(status_code=400, detail="Telegram not configured")
    except ImportError:
        raise HTTPException(status_code=500, detail="telegram_bot module not found")


# ── Background schedulers ───────────────────────────────────────────────────

def _scheduler_loop():
    """Check for due follow-ups every 30 minutes."""
    import time
    time.sleep(60)  # wait 1 min after startup
    while True:
        try:
            _send_due_followups()
        except Exception as e:
            logger.error(f"Follow-up scheduler error: {e}")
        time.sleep(30 * 60)

def _imap_loop():
    """Check for email replies every 4 hours."""
    import time
    time.sleep(300)  # wait 5 min after startup
    while True:
        try:
            _imap_check_replies()
        except Exception as e:
            logger.error(f"IMAP loop error: {e}")
        time.sleep(4 * 60 * 60)

threading.Thread(target=_scheduler_loop, daemon=True, name="followup-scheduler").start()
threading.Thread(target=_imap_loop, daemon=True, name="imap-checker").start()
