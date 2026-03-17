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

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leads.db")


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
    """Create tables if they don't exist."""
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
            created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS runs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date     TEXT NOT NULL,
            status       TEXT DEFAULT 'running',
            city         TEXT DEFAULT '',
            industry     TEXT DEFAULT '',
            leads_found  INTEGER DEFAULT 0,
            log          TEXT DEFAULT '',
            started_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_leads_run_date ON leads(run_date);
        CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(website_status);
        CREATE INDEX IF NOT EXISTS idx_leads_city ON leads(city);
        """)


# ── Leads ─────────────────────────────────────────────────────────────────────

def insert_lead(run_date: str, lead) -> int:
    """Insert a BusinessLead and return its id."""
    from processors.service_recommender import build_service_summary, cold_call_script
    services_str = build_service_summary(lead.recommended_services)
    call_script   = cold_call_script(lead)
    with get_db() as db:
        cur = db.execute("""
            INSERT INTO leads (run_date, company_name, vadovas, phone, email, website,
                address, city, industry, website_status, website_year,
                recommended_services, email_draft, cold_call_script, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
        ))
        return cur.lastrowid


def get_leads(
    run_date: str = None,
    city: str = None,
    industry: str = None,
    status: str = None,
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


def get_stats(run_date: str = None) -> dict:
    where = "WHERE run_date=?" if run_date else ""
    params = [run_date] if run_date else []
    with get_db() as db:
        total   = db.execute(f"SELECT COUNT(*) FROM leads {where}", params).fetchone()[0]
        no_site = db.execute(f"SELECT COUNT(*) FROM leads {where} {'AND' if where else 'WHERE'} website_status='none'", params).fetchone()[0]
        old_site= db.execute(f"SELECT COUNT(*) FROM leads {where} {'AND' if where else 'WHERE'} website_status='old'", params).fetchone()[0]
        modern  = db.execute(f"SELECT COUNT(*) FROM leads {where} {'AND' if where else 'WHERE'} website_status='modern'", params).fetchone()[0]
        has_email=db.execute(f"SELECT COUNT(*) FROM leads {where} {'AND' if where else 'WHERE'} email != ''", params).fetchone()[0]
        contacted=db.execute(f"SELECT COUNT(*) FROM leads {where} {'AND' if where else 'WHERE'} contacted=1", params).fetchone()[0]
        dates   = db.execute("SELECT DISTINCT run_date FROM leads ORDER BY run_date DESC LIMIT 30").fetchall()
        by_day  = db.execute("SELECT run_date, COUNT(*) as cnt FROM leads GROUP BY run_date ORDER BY run_date DESC LIMIT 14").fetchall()
        cities  = db.execute(f"SELECT city, COUNT(*) as cnt FROM leads {where} GROUP BY city ORDER BY cnt DESC", params).fetchall()
        industries = db.execute(f"SELECT industry, COUNT(*) as cnt FROM leads {where} GROUP BY industry ORDER BY cnt DESC", params).fetchall()
    return {
        "total": total,
        "no_site": no_site,
        "old_site": old_site,
        "modern": modern,
        "has_email": has_email,
        "contacted": contacted,
        "dates": [r[0] for r in dates],
        "by_day": [{"date": r[0], "count": r[1]} for r in by_day],
        "cities": [{"city": r[0], "count": r[1]} for r in cities],
        "industries": [{"industry": r[0], "count": r[1]} for r in industries],
    }


# ── Runs ──────────────────────────────────────────────────────────────────────

def create_run(city: str, industry: str) -> int:
    run_date = datetime.now().strftime("%Y-%m-%d")
    with get_db() as db:
        cur = db.execute(
            "INSERT INTO runs (run_date, status, city, industry) VALUES (?,?,?,?)",
            (run_date, "running", city, industry)
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
