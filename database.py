"""
SQLite database layer for AstiScale Lead Generation Dashboard.
Stores leads and run history.
"""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

_DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.db")
DB_PATH = os.getenv("DB_PATH", _DEFAULT_DB)


@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist, and run migrations for new columns."""
    with get_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date             TEXT NOT NULL,
            company_name         TEXT NOT NULL,
            vadovas              TEXT DEFAULT '',
            phone                TEXT DEFAULT '',
            email                TEXT DEFAULT '',
            website              TEXT DEFAULT '',
            address              TEXT DEFAULT '',
            city                 TEXT DEFAULT '',
            industry             TEXT DEFAULT '',
            website_status       TEXT DEFAULT 'none',
            website_year         INTEGER,
            recommended_services TEXT DEFAULT '',
            email_draft          TEXT DEFAULT '',
            cold_call_script     TEXT DEFAULT '',
            notes                TEXT DEFAULT '',
            contacted            INTEGER DEFAULT 0,
            contact_notes        TEXT DEFAULT '',
            service_target       TEXT DEFAULT '',
            email_sent           INTEGER DEFAULT 0,
            email_sent_at        TIMESTAMP,
            created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS runs (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date       TEXT NOT NULL,
            status         TEXT DEFAULT 'running',
            city           TEXT DEFAULT '',
            industry       TEXT DEFAULT '',
            service_target TEXT DEFAULT '',
            leads_found    INTEGER DEFAULT 0,
            log            TEXT DEFAULT '',
            started_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at   TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_leads_run_date    ON leads(run_date);
        CREATE INDEX IF NOT EXISTS idx_leads_status      ON leads(website_status);
        CREATE INDEX IF NOT EXISTS idx_leads_city        ON leads(city);
        CREATE INDEX IF NOT EXISTS idx_leads_service     ON leads(service_target);
        """)

    # ── Migrations: add columns if upgrading from old schema ──────────────────
    _migrate()


def _migrate():
    """Add missing columns to existing tables without dropping data."""
    migrations = [
        ("leads",  "service_target",  "TEXT DEFAULT ''"),
        ("leads",  "email_sent",      "INTEGER DEFAULT 0"),
        ("leads",  "email_sent_at",   "TIMESTAMP"),
        ("runs",   "service_target",  "TEXT DEFAULT ''"),
    ]
    with get_db() as db:
        for table, col, col_def in migrations:
            try:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
            except Exception:
                pass  # Column already exists — fine

    def _add_col(table, col_def):
        with get_db() as db:
            try:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")
            except Exception:
                pass  # Column already exists — fine

    _add_col("leads", "score INTEGER DEFAULT 0")
    _add_col("leads", "crm_stage TEXT DEFAULT 'rastas'")
    _add_col("leads", "open_count INTEGER DEFAULT 0")
    _add_col("leads", "first_opened_at TIMESTAMP")
    _add_col("leads", "last_opened_at TIMESTAMP")
    _add_col("leads", "replied INTEGER DEFAULT 0")
    _add_col("leads", "replied_at TIMESTAMP")
    _add_col("leads", "followup_1_body TEXT")
    _add_col("leads", "followup_2_body TEXT")
    _add_col("leads", "followup_3_body TEXT")
    _add_col("leads", "followup_1_at TIMESTAMP")
    _add_col("leads", "followup_2_at TIMESTAMP")
    _add_col("leads", "followup_3_at TIMESTAMP")
    _add_col("leads", "followup_1_sent INTEGER DEFAULT 0")
    _add_col("leads", "followup_2_sent INTEGER DEFAULT 0")
    _add_col("leads", "followup_3_sent INTEGER DEFAULT 0")
    _add_col("leads", "source TEXT DEFAULT 'osm'")
    _add_col("leads", "google_maps_url TEXT DEFAULT ''")
    _add_col("leads", "rating REAL DEFAULT 0")
    _add_col("leads", "review_count INTEGER DEFAULT 0")
    _add_col("leads", "reply_body TEXT DEFAULT ''")
    _add_col("leads", "is_duplicate INTEGER DEFAULT 0")


# ── Leads ─────────────────────────────────────────────────────────────────────

def insert_lead(run_date: str, lead, service_target: str = "") -> int:
    """Insert a BusinessLead and return its id."""
    from processors.service_recommender import build_service_summary, cold_call_script
    services_str = build_service_summary(lead.recommended_services)
    call_script   = cold_call_script(lead)
    with get_db() as db:
        cur = db.execute("""
            INSERT INTO leads (run_date, company_name, vadovas, phone, email, website,
                address, city, industry, website_status, website_year,
                recommended_services, email_draft, cold_call_script, notes, service_target)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            run_date,
            lead.company_name,
            lead.vadovas or '',
            lead.phone or '',
            lead.email or '',
            lead.website or '',
            lead.address or '',
            lead.city or '',
            lead.industry or '',
            lead.website_status or 'none',
            lead.website_year,
            services_str,
            lead.email_draft or '',
            call_script,
            lead.notes or '',
            service_target or getattr(lead, 'service_target', '') or '',
        ))
        return cur.lastrowid


def get_leads(
    run_date: str = None,
    city: str = None,
    industry: str = None,
    status: str = None,
    service_target: str = None,
    search: str = None,
    show_duplicates: bool = False,
    limit: int = 200,
    offset: int = 0,
) -> list:
    filters = []
    params  = []

    if run_date:
        filters.append("run_date = ?"); params.append(run_date)
    if city:
        filters.append("city = ?"); params.append(city)
    if industry:
        filters.append("industry = ?"); params.append(industry)
    if status:
        filters.append("website_status = ?"); params.append(status)
    if service_target:
        filters.append("service_target = ?"); params.append(service_target)
    if search:
        filters.append("(company_name LIKE ? OR email LIKE ? OR phone LIKE ?)")
        params += [f"%{search}%"] * 3
    if not show_duplicates:
        filters.append("COALESCE(is_duplicate, 0) = 0")

    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    params += [limit, offset]

    with get_db() as db:
        rows = db.execute(
            f"SELECT * FROM leads {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params
        ).fetchall()
    return [dict(r) for r in rows]


def get_lead(lead_id: int) -> Optional[dict]:
    with get_db() as db:
        row = db.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone()
    return dict(row) if row else None


def update_lead_contacted(lead_id: int, contacted: bool, notes: str = ""):
    with get_db() as db:
        db.execute(
            "UPDATE leads SET contacted=?, contact_notes=? WHERE id=?",
            (int(contacted), notes, lead_id)
        )


def mark_email_sent(lead_id: int):
    with get_db() as db:
        db.execute(
            "UPDATE leads SET email_sent=1, email_sent_at=CURRENT_TIMESTAMP WHERE id=?",
            (lead_id,)
        )


def get_stats(run_date: str = None) -> dict:
    where  = "WHERE run_date=?" if run_date else ""
    and_or = "AND" if where else "WHERE"
    params = [run_date] if run_date else []
    with get_db() as db:
        total      = db.execute(f"SELECT COUNT(*) FROM leads {where}", params).fetchone()[0]
        no_site    = db.execute(f"SELECT COUNT(*) FROM leads {where} {and_or} website_status='none'",    params).fetchone()[0]
        old_site   = db.execute(f"SELECT COUNT(*) FROM leads {where} {and_or} website_status='old'",     params).fetchone()[0]
        modern     = db.execute(f"SELECT COUNT(*) FROM leads {where} {and_or} website_status='modern'",  params).fetchone()[0]
        unreachable= db.execute(f"SELECT COUNT(*) FROM leads {where} {and_or} website_status='unreachable'", params).fetchone()[0]
        has_email  = db.execute(f"SELECT COUNT(*) FROM leads {where} {and_or} email != ''",              params).fetchone()[0]
        contacted  = db.execute(f"SELECT COUNT(*) FROM leads {where} {and_or} contacted=1",              params).fetchone()[0]
        email_sent = db.execute(f"SELECT COUNT(*) FROM leads {where} {and_or} email_sent=1",             params).fetchone()[0]
        dates      = db.execute("SELECT DISTINCT run_date FROM leads ORDER BY run_date DESC LIMIT 30").fetchall()
        by_day     = db.execute("SELECT run_date, COUNT(*) as cnt FROM leads GROUP BY run_date ORDER BY run_date DESC LIMIT 14").fetchall()
        cities     = db.execute(f"SELECT city, COUNT(*) as cnt FROM leads {where} GROUP BY city ORDER BY cnt DESC", params).fetchall()
        industries = db.execute(f"SELECT industry, COUNT(*) as cnt FROM leads {where} GROUP BY industry ORDER BY cnt DESC", params).fetchall()
        services   = db.execute(f"SELECT service_target, COUNT(*) as cnt FROM leads {where} GROUP BY service_target ORDER BY cnt DESC", params).fetchall()
    return {
        "total":       total,
        "no_site":     no_site,
        "old_site":    old_site,
        "modern":      modern,
        "unreachable": unreachable,
        "has_email":   has_email,
        "contacted":   contacted,
        "email_sent":  email_sent,
        "dates":       [r[0] for r in dates],
        "by_day":      [{"date": r[0], "count": r[1]} for r in by_day],
        "cities":      [{"city": r[0], "count": r[1]} for r in cities],
        "industries":  [{"industry": r[0], "count": r[1]} for r in industries],
        "services":    [{"service": r[0], "count": r[1]} for r in services],
    }


def track_email_open(lead_id: int) -> dict:
    """Increment open count and record timestamps. Returns updated lead info."""
    with get_db() as db:
        db.execute("""
            UPDATE leads SET
                open_count = open_count + 1,
                last_opened_at = datetime('now'),
                first_opened_at = COALESCE(first_opened_at, datetime('now'))
            WHERE id = ?
        """, (lead_id,))
        db.commit()
        row = db.execute("SELECT open_count, company_name FROM leads WHERE id=?", (lead_id,)).fetchone()
        return dict(row) if row else {}


def update_crm_stage(lead_id: int, stage: str) -> bool:
    """Move lead to a CRM pipeline stage."""
    valid = {"rastas", "susisiekta", "atidare", "atsake", "demo", "pasiulymas", "laimeta", "prarasta"}
    if stage not in valid:
        return False
    with get_db() as db:
        db.execute("UPDATE leads SET crm_stage=? WHERE id=?", (stage, lead_id))
        db.commit()
    return True


def mark_replied(lead_id: int):
    with get_db() as db:
        db.execute(
            "UPDATE leads SET replied=1, replied_at=datetime('now'), crm_stage='atsake' WHERE id=?",
            (lead_id,)
        )
        db.commit()


def save_followup_emails(lead_id: int, body1: str, body2: str, body3: str):
    """Schedule follow-up emails: +3, +7, +14 days from now."""
    with get_db() as db:
        db.execute("""
            UPDATE leads SET
                followup_1_body=?, followup_1_at=datetime('now','+3 days'),
                followup_2_body=?, followup_2_at=datetime('now','+7 days'),
                followup_3_body=?, followup_3_at=datetime('now','+14 days')
            WHERE id=?
        """, (body1, body2, body3, lead_id))
        db.commit()


def mark_followup_sent(lead_id: int, num: int):
    col = f"followup_{num}_sent"
    with get_db() as db:
        db.execute(f"UPDATE leads SET {col}=1 WHERE id=?", (lead_id,))
        db.commit()


def update_lead_score(lead_id: int, score: int):
    with get_db() as db:
        db.execute("UPDATE leads SET score=? WHERE id=?", (score, lead_id))
        db.commit()


def update_lead_edit(lead_id: int, company_name: str = None, email: str = None,
                     phone: str = None, notes: str = None):
    """Edit basic lead fields from the UI."""
    fields, params = [], []
    if company_name is not None:
        fields.append("company_name=?"); params.append(company_name)
    if email is not None:
        fields.append("email=?"); params.append(email)
    if phone is not None:
        fields.append("phone=?"); params.append(phone)
    if notes is not None:
        fields.append("notes=?"); params.append(notes)
    if not fields:
        return
    params.append(lead_id)
    with get_db() as db:
        db.execute(f"UPDATE leads SET {', '.join(fields)} WHERE id=?", params)


def mark_reply_body(lead_id: int, body: str):
    """Store the text of a reply received via IMAP."""
    with get_db() as db:
        db.execute(
            "UPDATE leads SET reply_body=?, replied=1, replied_at=datetime('now'), crm_stage='atsake' WHERE id=?",
            (body[:4000], lead_id)
        )
        db.commit()


def dedup_after_run(run_id: int):
    """Mark newly inserted leads as duplicates if same company+city was already emailed before this run."""
    with get_db() as db:
        # Get leads from this run
        new_leads = db.execute(
            "SELECT id, company_name, city FROM leads WHERE id IN "
            "(SELECT id FROM leads WHERE rowid > (SELECT MIN(rowid) FROM leads WHERE "
            "id IN (SELECT id FROM leads ORDER BY id DESC LIMIT 9999)))"
        ).fetchall()

        # Simpler: get run start time from runs table then find duplicates
        run = db.execute("SELECT started_at FROM runs WHERE id=?", (run_id,)).fetchone()
        if not run:
            return
        started_at = run[0]

        # Find leads from this run that have a prior email_sent=1 lead with same company+city
        db.execute("""
            UPDATE leads SET is_duplicate=1
            WHERE id IN (
                SELECT n.id FROM leads n
                INNER JOIN leads o ON
                    LOWER(TRIM(o.company_name)) = LOWER(TRIM(n.company_name))
                    AND LOWER(TRIM(o.city)) = LOWER(TRIM(n.city))
                    AND o.email_sent = 1
                    AND o.id != n.id
                WHERE n.created_at >= ? AND n.is_duplicate = 0
            )
        """, (started_at,))


def get_due_followups() -> list:
    """Return leads whose follow-up emails are due to be sent now."""
    with get_db() as db:
        rows = db.execute("""
            SELECT * FROM leads WHERE email_sent=1 AND replied=0 AND (
                (followup_1_sent=0 AND followup_1_at IS NOT NULL AND followup_1_at <= datetime('now') AND followup_1_body IS NOT NULL AND followup_1_body != '')
                OR (followup_1_sent=1 AND followup_2_sent=0 AND followup_2_at IS NOT NULL AND followup_2_at <= datetime('now') AND followup_2_body IS NOT NULL AND followup_2_body != '')
                OR (followup_1_sent=1 AND followup_2_sent=1 AND followup_3_sent=0 AND followup_3_at IS NOT NULL AND followup_3_at <= datetime('now') AND followup_3_body IS NOT NULL AND followup_3_body != '')
            )
        """).fetchall()
        return [dict(r) for r in rows]


def get_analytics() -> dict:
    """Analytics data for the dashboard."""
    with get_db() as db:
        total = db.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        contacted = db.execute("SELECT COUNT(*) FROM leads WHERE email_sent=1").fetchone()[0]
        opened = db.execute("SELECT COUNT(*) FROM leads WHERE open_count > 0").fetchone()[0]
        replied_count = db.execute("SELECT COUNT(*) FROM leads WHERE replied=1").fetchone()[0]

        weekly = [dict(r) for r in db.execute("""
            SELECT strftime('%Y-W%W', created_at) as week, COUNT(*) as count
            FROM leads GROUP BY week ORDER BY week DESC LIMIT 8
        """).fetchall()]

        by_source = [dict(r) for r in db.execute("""
            SELECT COALESCE(NULLIF(source,''),'osm') as src, COUNT(*) as cnt
            FROM leads GROUP BY src ORDER BY cnt DESC
        """).fetchall()]

        by_stage = [dict(r) for r in db.execute("""
            SELECT COALESCE(NULLIF(crm_stage,''),'rastas') as stage, COUNT(*) as cnt
            FROM leads GROUP BY stage ORDER BY cnt DESC
        """).fetchall()]

        by_industry = [dict(r) for r in db.execute("""
            SELECT industry, COUNT(*) as cnt FROM leads
            WHERE industry != '' GROUP BY industry ORDER BY cnt DESC LIMIT 8
        """).fetchall()]

        hot = db.execute("SELECT COUNT(*) FROM leads WHERE score >= 75").fetchone()[0]
        warm = db.execute("SELECT COUNT(*) FROM leads WHERE score >= 50 AND score < 75").fetchone()[0]
        cold = db.execute("SELECT COUNT(*) FROM leads WHERE score < 50").fetchone()[0]

        return {
            "total": total, "contacted": contacted, "opened": opened, "replied": replied_count,
            "open_rate": round(opened / contacted * 100, 1) if contacted > 0 else 0,
            "reply_rate": round(replied_count / contacted * 100, 1) if contacted > 0 else 0,
            "weekly": weekly, "by_source": by_source, "by_stage": by_stage,
            "by_industry": by_industry,
            "score_hot": hot, "score_warm": warm, "score_cold": cold,
        }


# ── Runs ──────────────────────────────────────────────────────────────────────

def create_run(city: str, industry: str, service_target: str = "") -> int:
    run_date = datetime.now().strftime("%Y-%m-%d")
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO runs (run_date, status, city, industry, service_target) VALUES (?,?,?,?,?)",
            (run_date, "running", city, industry, service_target)
        )
        return cur.lastrowid


def append_run_log(run_id: int, text: str):
    with get_db() as db:
        db.execute(
            "UPDATE runs SET log = log || ? WHERE id=?",
            (text + "\n", run_id)
        )


def finish_run(run_id: int, leads_found: int, status: str = "completed"):
    with get_db() as db:
        db.execute(
            "UPDATE runs SET status=?, leads_found=?, completed_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, leads_found, run_id)
        )


def get_run(run_id: int) -> Optional[dict]:
    with get_db() as db:
        row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    return dict(row) if row else None


def get_recent_runs(limit: int = 20) -> list:
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
