#!/usr/bin/env python3
"""Import judgments from Indian Kanoon into NyayaBhandu.

Uses the official API when INDIANKANOON_TOKEN is set (recommended for bulk imports).
Falls back to the public website for small demo imports.

Get an API token: https://api.indiankanoon.org/

Examples:
  export INDIANKANOON_TOKEN=your_token_here

  # Search and import
  python import_kanoon.py --query "right to privacy"
  python import_kanoon.py --query "bail" --court karnataka --pages 3
  python import_kanoon.py --court supremecourt --fromdate 1-1-2024 --pages 5

  # Import a single known document
  python import_kanoon.py --docid 257876

  # Import with citation links extracted from judgment text
  python import_kanoon.py --query "kesavananda" --pages 1 --citations
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from database import init_db
from import_data import import_citations, import_judgments
from kanoon_client import (
    COURT_DOCTYPES,
    KanoonClient,
    build_query,
    extract_citations_from_html,
    kanoon_to_judgment,
)


def _save_backup(path: Path, judgments: list[dict], citations: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"judgments": judgments, "citations": citations}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"Backup saved to {path}")


def run_import(args: argparse.Namespace) -> int:
    init_db()
    client = KanoonClient(delay_seconds=args.delay)

    if client.uses_api:
        print("Using Indian Kanoon API (token found).")
    else:
        print("No INDIANKANOON_TOKEN — using public search (slower, best for small imports).")
        print("For bulk imports, get a token at https://api.indiankanoon.org/")

    judgments: list[dict] = []
    citations: list[dict] = []
    items: list[tuple[int, dict | None]] = []

    if args.docid:
        items = [(docid, None) for docid in args.docid]
    else:
        query = build_query(
            query=args.query,
            court=args.court,
            fromdate=args.fromdate,
            todate=args.todate,
            sortby=args.sortby,
        )
        if not query:
            print("Error: provide --query, --court, or --docid", file=sys.stderr)
            return 1

        print(f"Searching: {query}")
        seen_docs: set[int] = set()
        for page in range(args.pages):
            result = client.search(query, pagenum=page, maxpages=1)
            if "errmsg" in result:
                print(f"Search error: {result['errmsg']}", file=sys.stderr)
                break
            docs = result.get("docs", [])
            if not docs:
                break
            print(f"  Page {page + 1}: {len(docs)} results (total found: {result.get('found', '?')})")
            for doc in docs:
                tid = int(doc["tid"])
                if tid not in seen_docs:
                    seen_docs.add(tid)
                    items.append((tid, doc))

    for idx, item in enumerate(items, start=1):
        if isinstance(item, tuple):
            docid, search_hit = item
        else:
            docid, search_hit = item, None

        print(f"[{idx}/{len(items)}] Fetching doc {docid}...")
        try:
            payload = client.fetch_doc(
                docid,
                maxcites=args.maxcites if args.citations else 0,
                maxcitedby=0,
            )
        except RuntimeError as exc:
            print(f"  Skipped: {exc}")
            continue

        if "errmsg" in payload:
            print(f"  Skipped: {payload['errmsg']}")
            continue

        judgment = kanoon_to_judgment(docid, search_hit=search_hit, doc_payload=payload)
        judgments.append(judgment)

        if args.citations and payload.get("doc"):
            doc_citations = extract_citations_from_html(payload["doc"], judgment["id"])
            citations.extend(doc_citations[: args.max_citation_links])
            cited_ids = {
                int(c["cited_id"].replace("ik-", ""))
                for c in doc_citations[: args.max_citation_links]
            }
            existing = {j["id"] for j in judgments}
            fetch_limit = min(10, args.max_citation_links)
            for cited_docid in list(cited_ids)[:fetch_limit]:
                cited_key = f"ik-{cited_docid}"
                if cited_key in existing:
                    continue
                try:
                    cited_payload = client.fetch_doc(cited_docid)
                    if "errmsg" not in cited_payload:
                        judgments.append(
                            kanoon_to_judgment(cited_docid, doc_payload=cited_payload)
                        )
                        existing.add(cited_key)
                except RuntimeError:
                    continue
            print(f"  Extracted {len(doc_citations)} citation links")

    if not judgments:
        print("No judgments imported.")
        return 1

    from database import get_connection

    conn = get_connection()
    try:
        jcount = import_judgments(conn, judgments)
        ccount = import_citations(conn, citations) if citations else 0
        conn.commit()
    finally:
        conn.close()

    print(f"\nImported {jcount} judgments, {ccount} citation links into NyayaBhandu.")

    if args.backup:
        _save_backup(Path(args.backup), judgments, citations)

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Import judgments from Indian Kanoon")
    parser.add_argument("--query", "-q", help="Search query (e.g. 'right to privacy')")
    parser.add_argument(
        "--court", "-c",
        choices=sorted(COURT_DOCTYPES.keys()),
        help="Court doctype filter (e.g. supremecourt, delhi, karnataka)",
    )
    parser.add_argument("--fromdate", help="From date DD-MM-YYYY")
    parser.add_argument("--todate", help="To date DD-MM-YYYY")
    parser.add_argument("--sortby", choices=["mostrecent", "leastrecent", ""], default="")
    parser.add_argument("--pages", "-p", type=int, default=1, help="Search pages to fetch (max ~10 recommended)")
    parser.add_argument("--docid", "-d", type=int, nargs="+", help="Import specific Indian Kanoon document IDs")
    parser.add_argument("--citations", action="store_true", help="Extract citation links from judgment HTML")
    parser.add_argument("--maxcites", type=int, default=25, help="Max cites to request from API per doc")
    parser.add_argument("--max-citation-links", type=int, default=50, help="Max citation links to store per doc")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between requests (public mode)")
    parser.add_argument("--backup", help="Also save imported data to this JSON file")
    parser.add_argument("--token", help="Indian Kanoon API token (or set INDIANKANOON_TOKEN)")
    args = parser.parse_args()

    if args.token:
        os.environ["INDIANKANOON_TOKEN"] = args.token

    return run_import(args)


if __name__ == "__main__":
    raise SystemExit(main())