#!/usr/bin/env python3
"""Bulk import judgments, proformas, and filing guides into NyayaSetu.

Usage:
  python import_data.py data/seed.json              # import everything
  python import_data.py data/my_judgments.json --type judgments
  python import_data.py data/my_proformas.json --type proformas
  python import_data.py data/my_guides.json --type outlines
  python import_data.py data/seed.json --reset      # wipe DB and reimport
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from database import DB_PATH, get_connection, init_db


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def import_judgments(conn, items: list[dict], replace: bool = False) -> int:
    count = 0
    for j in items:
        if replace:
            conn.execute("DELETE FROM judgments WHERE id = ?", (j["id"],))
        conn.execute(
            """
            INSERT OR REPLACE INTO judgments
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
        count += 1
    return count


def import_citations(conn, items: list[dict]) -> int:
    count = 0
    for c in items:
        exists = conn.execute(
            """
            SELECT 1 FROM judgments WHERE id IN (?, ?)
            """,
            (c["citing_id"], c["cited_id"]),
        ).fetchall()
        if len(exists) < 2:
            continue
        conn.execute(
            """
            INSERT INTO citations (citing_id, cited_id, treatment, context)
            SELECT ?, ?, ?, ?
            WHERE NOT EXISTS (
                SELECT 1 FROM citations
                WHERE citing_id = ? AND cited_id = ?
            )
            """,
            (
                c["citing_id"],
                c["cited_id"],
                c.get("treatment"),
                c.get("context"),
                c["citing_id"],
                c["cited_id"],
            ),
        )
        count += 1
    return count


def import_proformas(conn, items: list[dict]) -> int:
    count = 0
    for p in items:
        conn.execute(
            """
            INSERT OR REPLACE INTO proformas
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
        count += 1
    return count


def import_outlines(conn, items: list[dict]) -> int:
    count = 0
    for o in items:
        conn.execute(
            """
            INSERT OR REPLACE INTO filing_outlines
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
        count += 1
    return count


def reset_database() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db()


def import_file(path: Path, data_type: str = "all") -> dict[str, int]:
    init_db()
    data = _load_json(path)
    conn = get_connection()
    stats: dict[str, int] = {}

    try:
        if data_type in ("all", "judgments") and "judgments" in data:
            stats["judgments"] = import_judgments(conn, data["judgments"])
        if data_type in ("all", "citations") and "citations" in data:
            stats["citations"] = import_citations(conn, data["citations"])
        if data_type in ("all", "proformas") and "proformas" in data:
            stats["proformas"] = import_proformas(conn, data["proformas"])
        if data_type in ("all", "outlines") and "filing_outlines" in data:
            stats["outlines"] = import_outlines(conn, data["filing_outlines"])
        conn.commit()
    finally:
        conn.close()

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Import legal data into NyayaSetu")
    parser.add_argument("file", type=Path, help="JSON file to import")
    parser.add_argument(
        "--type",
        choices=["all", "judgments", "citations", "proformas", "outlines"],
        default="all",
        help="Which section to import (default: all)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete existing database before import",
    )
    args = parser.parse_args()

    if not args.file.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        return 1

    if args.reset:
        reset_database()
        print("Database reset.")

    stats = import_file(args.file, args.type)
    if not stats:
        print("Nothing imported. Check file format and --type flag.")
        return 1

    print("Import complete:")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())