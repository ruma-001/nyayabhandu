"""SQLite database layer for NyayaBhandu."""

import json
import shutil
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / "data" / "nyayabhandu.db"
_LEGACY_DB_PATH = Path(__file__).parent / "data" / "nyayasetu.db"
SEED_PATH = Path(__file__).parent / "data" / "seed.json"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists() and _LEGACY_DB_PATH.exists():
        shutil.copy2(_LEGACY_DB_PATH, DB_PATH)
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS judgments (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            citation TEXT NOT NULL,
            court TEXT NOT NULL,
            bench TEXT,
            judges TEXT,
            date TEXT NOT NULL,
            year INTEGER NOT NULL,
            case_number TEXT,
            petitioner TEXT,
            respondent TEXT,
            subject TEXT,
            summary TEXT NOT NULL,
            full_text TEXT,
            keywords TEXT
        );

        CREATE TABLE IF NOT EXISTS citations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            citing_id TEXT NOT NULL,
            cited_id TEXT NOT NULL,
            treatment TEXT,
            context TEXT,
            FOREIGN KEY (citing_id) REFERENCES judgments(id),
            FOREIGN KEY (cited_id) REFERENCES judgments(id)
        );

        CREATE TABLE IF NOT EXISTS proformas (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            case_type TEXT NOT NULL,
            state TEXT NOT NULL,
            court_level TEXT NOT NULL,
            description TEXT,
            content TEXT NOT NULL,
            tags TEXT
        );

        CREATE TABLE IF NOT EXISTS filing_outlines (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            case_type TEXT NOT NULL,
            state TEXT NOT NULL,
            court TEXT NOT NULL,
            limitation_period TEXT,
            court_fee TEXT,
            documents_required TEXT,
            steps TEXT NOT NULL,
            tips TEXT,
            relevant_acts TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_judgments_court ON judgments(court);
        CREATE INDEX IF NOT EXISTS idx_judgments_year ON judgments(year);
        CREATE INDEX IF NOT EXISTS idx_judgments_subject ON judgments(subject);
        CREATE INDEX IF NOT EXISTS idx_proformas_state ON proformas(state);
        CREATE INDEX IF NOT EXISTS idx_proformas_case_type ON proformas(case_type);
        CREATE INDEX IF NOT EXISTS idx_outlines_state ON filing_outlines(state);
        """
    )
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM judgments").fetchone()[0]
    if count == 0:
        _seed_database(conn)
    conn.close()


def _seed_database(conn: sqlite3.Connection) -> None:
    with open(SEED_PATH, encoding="utf-8") as f:
        data = json.load(f)

    for j in data["judgments"]:
        conn.execute(
            """
            INSERT INTO judgments
            (id, title, citation, court, bench, judges, date, year,
             case_number, petitioner, respondent, subject, summary, full_text, keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                j["id"],
                j["title"],
                j["citation"],
                j["court"],
                j.get("bench"),
                j.get("judges"),
                j["date"],
                j["year"],
                j.get("case_number"),
                j.get("petitioner"),
                j.get("respondent"),
                j["subject"],
                j["summary"],
                j.get("full_text"),
                json.dumps(j.get("keywords", [])),
            ),
        )

    for c in data["citations"]:
        conn.execute(
            """
            INSERT INTO citations (citing_id, cited_id, treatment, context)
            VALUES (?, ?, ?, ?)
            """,
            (c["citing_id"], c["cited_id"], c.get("treatment"), c.get("context")),
        )

    for p in data["proformas"]:
        conn.execute(
            """
            INSERT INTO proformas
            (id, title, case_type, state, court_level, description, content, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                p["id"],
                p["title"],
                p["case_type"],
                p["state"],
                p["court_level"],
                p.get("description"),
                p["content"],
                json.dumps(p.get("tags", [])),
            ),
        )

    for o in data["filing_outlines"]:
        conn.execute(
            """
            INSERT INTO filing_outlines
            (id, title, case_type, state, court, limitation_period, court_fee,
             documents_required, steps, tips, relevant_acts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                o["id"],
                o["title"],
                o["case_type"],
                o["state"],
                o["court"],
                o.get("limitation_period"),
                o.get("court_fee"),
                json.dumps(o.get("documents_required", [])),
                json.dumps(o["steps"]),
                json.dumps(o.get("tips", [])),
                json.dumps(o.get("relevant_acts", [])),
            ),
        )

    conn.commit()


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)