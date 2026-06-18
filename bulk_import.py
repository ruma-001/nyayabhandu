#!/usr/bin/env python3
"""Bulk judgment ingestion pipeline for NyayaBhandu.

Systematically imports judgments from Indian Kanoon by court and year.
Requires INDIANKANOON_TOKEN for large-scale imports.

Usage:
  export INDIANKANOON_TOKEN=your_token

  # Import all Supreme Court judgments from 2020-2024
  python bulk_import.py --courts supremecourt --years 2020-2024 --pages-per-year 20

  # Import multiple High Courts
  python bulk_import.py --courts delhi,bombay,karnataka --years 2023-2024

  # Import all courts (takes days/weeks — run in background)
  python bulk_import.py --courts all --years 2015-2024 --pages-per-year 10

  # Resume after interruption
  python bulk_import.py --courts supremecourt --years 2020-2024 --resume

Progress is saved to data/import_progress.json so imports can resume.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from database import init_db
from import_data import import_citations, import_judgments
from kanoon_client import COURT_DOCTYPES, KanoonClient, build_query, kanoon_to_judgment

PROGRESS_FILE = Path(__file__).parent / "data" / "import_progress.json"

HIGH_COURTS = [
    "delhi", "bombay", "chennai", "kolkata", "allahabad", "andhra",
    "chattisgarh", "gauhati", "jammu", "kerala", "orissa", "gujarat",
    "himachal_pradesh", "jharkhand", "karnataka", "madhyapradesh",
    "patna", "punjab", "rajasthan", "sikkim", "uttaranchal", "meghalaya",
]

ALL_COURTS = ["supremecourt"] + HIGH_COURTS


def parse_years(spec: str) -> list[int]:
    if "-" in spec:
        start, end = spec.split("-", 1)
        return list(range(int(start), int(end) + 1))
    return [int(spec)]


def load_progress() -> dict:
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"completed": [], "stats": {"judgments": 0, "errors": 0}}


def save_progress(progress: dict) -> None:
    PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2)


def task_key(court: str, year: int) -> str:
    return f"{court}:{year}"


def import_court_year(
    client: KanoonClient,
    court: str,
    year: int,
    pages: int,
    delay: float,
) -> tuple[int, int]:
    from database import get_connection

    query = build_query(
        court=court,
        fromdate=f"1-1-{year}",
        todate=f"31-12-{year}",
        sortby="mostrecent",
    )

    judgments: list[dict] = []
    seen: set[int] = set()

    for page in range(pages):
        try:
            result = client.search(query, pagenum=page, maxpages=1)
        except RuntimeError as exc:
            print(f"    Search error page {page}: {exc}")
            time.sleep(delay * 5)
            continue

        if "errmsg" in result:
            print(f"    API error: {result['errmsg']}")
            break

        docs = result.get("docs", [])
        if not docs:
            break

        print(f"    Page {page + 1}: {len(docs)} docs (found: {result.get('found', '?')})")

        for doc in docs:
            docid = int(doc["tid"])
            if docid in seen:
                continue
            seen.add(docid)

            try:
                payload = client.fetch_doc(docid)
            except RuntimeError as exc:
                print(f"      Skip doc {docid}: {exc}")
                continue

            if "errmsg" in payload:
                continue

            judgments.append(
                kanoon_to_judgment(docid, search_hit=doc, doc_payload=payload)
            )

        if len(docs) < 10:
            break

    if not judgments:
        return 0, 0

    conn = get_connection()
    try:
        jcount = import_judgments(conn, judgments)
        conn.commit()
    finally:
        conn.close()

    return jcount, 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk import judgments into NyayaBhandu")
    parser.add_argument(
        "--courts",
        default="supremecourt",
        help="Comma-separated court codes, or 'all' for all courts",
    )
    parser.add_argument("--years", default="2024", help="Year or range e.g. 2020-2024")
    parser.add_argument("--pages-per-year", type=int, default=10, help="Max search pages per court/year")
    parser.add_argument("--delay", type=float, default=1.5, help="Seconds between API calls")
    parser.add_argument("--resume", action="store_true", help="Skip already-completed court/year pairs")
    parser.add_argument("--token", help="Indian Kanoon API token (or INDIANKANOON_TOKEN env)")
    args = parser.parse_args()

    if args.token:
        os.environ["INDIANKANOON_TOKEN"] = args.token

    client = KanoonClient(delay_seconds=args.delay)
    if not client.uses_api:
        print("WARNING: No API token. Bulk import will be very slow and may get blocked.")
        print("Get a token at https://api.indiankanoon.org/")
        print("Set: export INDIANKANOON_TOKEN=your_token\n")

    if args.courts == "all":
        courts = ALL_COURTS
    else:
        courts = [c.strip() for c in args.courts.split(",")]
        for c in courts:
            if c not in COURT_DOCTYPES:
                print(f"Unknown court: {c}. Available: {', '.join(COURT_DOCTYPES.keys())}")
                return 1

    years = parse_years(args.years)
    init_db()
    progress = load_progress()
    completed = set(progress["completed"]) if args.resume else set()

    total_imported = 0
    tasks = [(court, year) for court in courts for year in years]

    print(f"Bulk import: {len(tasks)} court/year combinations")
    print(f"Courts: {', '.join(courts)}")
    print(f"Years: {years[0]}–{years[-1]}")
    print(f"Pages per year: {args.pages_per_year}\n")

    for i, (court, year) in enumerate(tasks, 1):
        key = task_key(court, year)
        if key in completed:
            print(f"[{i}/{len(tasks)}] SKIP {key} (already done)")
            continue

        court_name = COURT_DOCTYPES.get(court, court)
        print(f"[{i}/{len(tasks)}] Importing {court_name} — {year}...")

        try:
            count, _ = import_court_year(
                client, court, year, args.pages_per_year, args.delay
            )
            total_imported += count
            progress["stats"]["judgments"] += count
            completed.add(key)
            progress["completed"] = sorted(completed)
            progress["last_run"] = datetime.now().isoformat()
            save_progress(progress)
            print(f"    → Imported {count} judgments (session total: {total_imported})")
        except KeyboardInterrupt:
            print("\nInterrupted. Progress saved — rerun with --resume to continue.")
            save_progress(progress)
            return 130
        except Exception as exc:
            print(f"    ERROR: {exc}")
            progress["stats"]["errors"] = progress["stats"].get("errors", 0) + 1
            save_progress(progress)

    print(f"\nDone. Imported {total_imported} judgments this session.")
    print(f"All-time total: {progress['stats']['judgments']}")
    print(f"Progress file: {PROGRESS_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())