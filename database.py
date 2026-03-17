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
