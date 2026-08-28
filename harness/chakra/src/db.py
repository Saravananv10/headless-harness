import os
import sqlite3
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Path to the SQLite database (relative to project root)
DB_PATH = Path(__file__).resolve().parents[1] / "data" / "levellens.db"

def _ensure_db_dir() -> None:
    """Make sure the directory for the DB exists."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with row factory for dict‑like access."""
    _ensure_db_dir()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    """Create tables if they do not already exist."""
    schema = """
    CREATE TABLE IF NOT EXISTS resume_assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        filename TEXT NOT NULL,
        mime TEXT NOT NULL,
        raw_text TEXT NOT NULL,
        char_count INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS job_descriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        raw_text TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS analysis_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        resume_id INTEGER NOT NULL REFERENCES resume_assets(id),
        jd_id INTEGER NOT NULL REFERENCES job_descriptions(id),
        mode TEXT CHECK(mode IN ('live','demo')) NOT NULL,
        match_score REAL NOT NULL,
        seniority_band TEXT NOT NULL,
        seniority_score REAL NOT NULL,
        skill_coverage REAL NOT NULL,
        scores_json TEXT NOT NULL,
        duration_ms INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    conn = get_connection()
    conn.executescript(schema)
    conn.commit()
    conn.close()

# Helper CRUD utilities ----------------------------------------------------

def add_resume(filename: str, mime: str, raw_text: str) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO resume_assets (filename, mime, raw_text, char_count) VALUES (?,?,?,?)",
        (filename, mime, raw_text, len(raw_text)),
    )
    resume_id = cur.lastrowid
    conn.commit()
    conn.close()
    return resume_id

def add_job_description(title: str, raw_text: str) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO job_descriptions (title, raw_text) VALUES (?,?)",
        (title, raw_text),
    )
    jd_id = cur.lastrowid
    conn.commit()
    conn.close()
    return jd_id

def add_analysis_run(
    resume_id: int,
    jd_id: int,
    mode: str,
    match_score: float,
    seniority_band: str,
    seniority_score: float,
    skill_coverage: float,
    scores_json: str,
    duration_ms: int,
) -> int:
    conn = get_connection()
    cur = conn.execute(
        """
        INSERT INTO analysis_runs (
            resume_id, jd_id, mode, match_score, seniority_band,
            seniority_score, skill_coverage, scores_json, duration_ms
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            resume_id,
            jd_id,
            mode,
            match_score,
            seniority_band,
            seniority_score,
            skill_coverage,
            scores_json,
            duration_ms,
        ),
    )
    run_id = cur.lastrowid
    conn.commit()
    conn.close()
    return run_id

def get_recent_analyses(limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM analysis_runs ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_analysis(run_id: int) -> Dict[str, Any]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM analysis_runs WHERE id = ?", (run_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else {}

# Initialise DB on import so routes can assume tables exist
init_db()
