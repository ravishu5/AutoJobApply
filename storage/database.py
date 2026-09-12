"""
storage/database.py — SQLite Database Manager & State Machine
Manages persistence and status transitions for jobs, applications,
LinkedIn post leads, referral contacts, and outreach logs.
"""

import sqlite3
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone


DEFAULT_DB_PATH = "data/job_hunt.db"


class Database:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            # Jobs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT,
                    job_url TEXT,
                    description TEXT,
                    salary_min REAL,
                    salary_max REAL,
                    match_score REAL DEFAULT 0.0,
                    matched_keywords TEXT,
                    missing_keywords TEXT,
                    status TEXT DEFAULT 'new',
                    source TEXT,
                    date_posted TEXT,
                    scraped_at TEXT
                )
            """)

            # Applications table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT,
                    company TEXT,
                    title TEXT,
                    applied_to TEXT,
                    apply_method TEXT,
                    status TEXT DEFAULT 'pending',
                    screenshot_path TEXT,
                    notes TEXT,
                    applied_at TEXT,
                    FOREIGN KEY (job_id) REFERENCES jobs(id)
                )
            """)

            # LinkedIn hiring posts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS linkedin_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    author TEXT,
                    company TEXT,
                    role TEXT,
                    snippet TEXT,
                    post_url TEXT,
                    email TEXT,
                    outreach_status TEXT DEFAULT 'draft_ready',
                    date_found TEXT
                )
            """)

            # Referral contacts table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS referral_contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    headline TEXT,
                    company TEXT,
                    linkedin_url TEXT UNIQUE,
                    connection_note TEXT,
                    referral_pitch TEXT,
                    status TEXT DEFAULT 'new',
                    date_added TEXT
                )
            """)

            # Outreach logs table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS outreach_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contact_email TEXT,
                    company TEXT,
                    subject TEXT,
                    body TEXT,
                    status TEXT,
                    sent_at TEXT
                )
            """)

            # Sent connections table (Rate Limiting & Tracking)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sent_connections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_url TEXT NOT NULL,
                    name TEXT,
                    company TEXT,
                    note TEXT,
                    status TEXT DEFAULT 'sent',
                    sent_at TEXT
                )
            """)

            # Dynamic migrations for optional columns
            for col_sql in [
                "ALTER TABLE jobs ADD COLUMN hiring_manager_name TEXT",
                "ALTER TABLE jobs ADD COLUMN hiring_manager_url TEXT",
                "ALTER TABLE jobs ADD COLUMN is_early_applicant INTEGER DEFAULT 0",
                "ALTER TABLE applications ADD COLUMN recruiter_status TEXT"
            ]:
                try:
                    conn.execute(col_sql)
                except sqlite3.OperationalError:
                    pass

            conn.commit()

    # --- Jobs Operations ---
    def upsert_job(self, job: Dict[str, Any]):
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO jobs (
                    id, title, company, location, job_url, description,
                    salary_min, salary_max, match_score, matched_keywords,
                    missing_keywords, status, source, date_posted, scraped_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    match_score=excluded.match_score,
                    matched_keywords=excluded.matched_keywords,
                    missing_keywords=excluded.missing_keywords,
                    status=CASE WHEN jobs.status='new' THEN excluded.status ELSE jobs.status END
            """, (
                job["id"],
                job.get("title", ""),
                job.get("company", ""),
                job.get("location", ""),
                job.get("job_url", ""),
                job.get("description", ""),
                job.get("salary_min"),
                job.get("salary_max"),
                float(job.get("match_score", 0.0)),
                json.dumps(job.get("matched_keywords", [])),
                json.dumps(job.get("missing_keywords", [])),
                job.get("status", "new"),
                job.get("source", ""),
                job.get("date_posted", ""),
                job.get("scraped_at", datetime.now(timezone.utc).isoformat())
            ))
            conn.commit()

    def get_all_jobs(self, min_score: float = 0.0, status: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM jobs WHERE match_score >= ?"
        params = [min_score]
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY match_score DESC, scraped_at DESC"

        with self.get_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                d["matched_keywords"] = json.loads(d["matched_keywords"]) if d.get("matched_keywords") else []
                d["missing_keywords"] = json.loads(d["missing_keywords"]) if d.get("missing_keywords") else []
                results.append(d)
            return results

    def update_job_status(self, job_id: str, new_status: str):
        with self.get_connection() as conn:
            conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (new_status, job_id))
            conn.commit()

    # --- Applications Operations ---
    def record_application(
        self,
        job_id: str,
        company: str,
        title: str,
        applied_to: str,
        apply_method: str,
        status: str,
        screenshot_path: str = "",
        notes: str = ""
    ):
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO applications (
                    job_id, company, title, applied_to, apply_method,
                    status, screenshot_path, notes, applied_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id, company, title, applied_to, apply_method,
                status, screenshot_path, notes, datetime.now(timezone.utc).isoformat()
            ))
            # Update corresponding job status
            if status in ("submitted", "applied"):
                conn.execute("UPDATE jobs SET status = 'applied' WHERE id = ?", (job_id,))
            conn.commit()

    def get_all_applications(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM applications ORDER BY applied_at DESC").fetchall()
            return [dict(r) for r in rows]

    # --- LinkedIn Posts Operations ---
    def insert_linkedin_post(self, post: Dict[str, Any]):
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO linkedin_posts (
                    author, company, role, snippet, post_url, email, outreach_status, date_found
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                post.get("author", ""),
                post.get("company", ""),
                post.get("role", ""),
                post.get("snippet", ""),
                post.get("post_url", ""),
                post.get("email", ""),
                post.get("outreach_status", "draft_ready"),
                post.get("date_found", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
            ))
            conn.commit()

    def get_all_linkedin_posts(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM linkedin_posts ORDER BY id DESC").fetchall()
            return [dict(r) for r in rows]

    # --- Referral Contacts Operations ---
    def insert_referral_contact(self, contact: Dict[str, Any]):
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO referral_contacts (
                    name, headline, company, linkedin_url, connection_note, referral_pitch, status, date_added
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(linkedin_url) DO UPDATE SET
                    connection_note=excluded.connection_note,
                    referral_pitch=excluded.referral_pitch
            """, (
                contact.get("name", ""),
                contact.get("headline", ""),
                contact.get("company", ""),
                contact.get("linkedin_url", ""),
                contact.get("connection_note", ""),
                contact.get("referral_pitch", ""),
                contact.get("status", "new"),
                datetime.now(timezone.utc).strftime("%Y-%m-%d")
            ))
            conn.commit()

    def get_all_referral_contacts(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM referral_contacts ORDER BY id DESC").fetchall()
            return [dict(r) for r in rows]

    # --- Connection Rate Limiting & Tracking ---
    def record_sent_connection(
        self,
        profile_url: str,
        name: str = "",
        company: str = "",
        note: str = "",
        status: str = "sent"
    ):
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO sent_connections (profile_url, name, company, note, status, sent_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                profile_url,
                name,
                company,
                note,
                status,
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()

    def get_daily_connection_count(self, date_str: Optional[str] = None) -> int:
        target_date = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT COUNT(*) FROM sent_connections
                WHERE sent_at LIKE ?
            """, (f"{target_date}%",)).fetchone()
            return row[0] if row else 0

    def can_send_connection(self, max_daily: int = 15) -> bool:
        return self.get_daily_connection_count() < max_daily

    def update_job_hiring_manager(self, job_id: str, name: str, url: str):
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE jobs SET hiring_manager_name = ?, hiring_manager_url = ?
                WHERE id = ?
            """, (name, url, job_id))
            conn.commit()

    def update_application_recruiter_status(self, company: str, title: str, recruiter_status: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.execute("""
                UPDATE applications SET recruiter_status = ?
                WHERE LOWER(company) LIKE LOWER(?) AND LOWER(title) LIKE LOWER(?)
            """, (recruiter_status, f"%{company}%", f"%{title}%"))
            conn.commit()
            return cursor.rowcount > 0

    # --- Metrics ---
    def get_metrics(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            total_jobs = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
            shortlisted = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'shortlisted'").fetchone()[0]
            applied = conn.execute("SELECT COUNT(*) FROM applications WHERE status IN ('submitted', 'applied')").fetchone()[0]
            leads = conn.execute("SELECT COUNT(*) FROM linkedin_posts").fetchone()[0]
            referrals = conn.execute("SELECT COUNT(*) FROM referral_contacts").fetchone()[0]
            sent_today = self.get_daily_connection_count()
            avg_score_row = conn.execute("SELECT AVG(match_score) FROM jobs WHERE match_score > 0").fetchone()
            avg_score = round(avg_score_row[0], 1) if avg_score_row and avg_score_row[0] else 0.0

            return {
                "total_jobs": total_jobs,
                "shortlisted_jobs": shortlisted,
                "applied_jobs": applied,
                "linkedin_leads": leads,
                "referral_contacts": referrals,
                "sent_connections_today": sent_today,
                "avg_match_score": avg_score
            }
