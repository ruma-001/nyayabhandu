"""Case filing lookup and tracking services."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from database import get_connection
from ecourts_client import ECourtsClient, normalize_cnr, validate_cnr


def _parse_json_field(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default if default is not None else []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else []


def _enrich_case(row: dict) -> dict:
    row["hearings"] = _parse_json_field(row.pop("hearings_json", None))
    row["orders"] = _parse_json_field(row.pop("orders_json", None))
    return row


def save_case(case: dict) -> dict:
    conn = get_connection()
    hearings = case.pop("hearings", [])
    orders = case.pop("orders", [])
    raw = case.pop("raw", None)

    conn.execute(
        """
        INSERT OR REPLACE INTO cases
        (id, cnr, case_type, case_number, filing_number, court, court_complex,
         state, district, status, stage, petitioner, respondent, filing_date,
         registration_date, next_hearing_date, decision_date, judges, acts_sections,
         summary, judgment_id, source, raw_json, hearings_json, orders_json, fetched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            case["id"],
            case["cnr"],
            case.get("case_type"),
            case.get("case_number"),
            case.get("filing_number"),
            case.get("court"),
            case.get("court_complex"),
            case.get("state"),
            case.get("district"),
            case.get("status"),
            case.get("stage"),
            case.get("petitioner"),
            case.get("respondent"),
            case.get("filing_date"),
            case.get("registration_date"),
            case.get("next_hearing_date"),
            case.get("decision_date"),
            case.get("judges"),
            case.get("acts_sections"),
            case.get("summary"),
            case.get("judgment_id"),
            case.get("source", "local"),
            json.dumps(raw) if raw else None,
            json.dumps(hearings),
            json.dumps(orders),
            case.get("fetched_at") or datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    conn.close()
    case["hearings"] = hearings
    case["orders"] = orders
    return case


def get_case(case_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return _enrich_case(dict(row))


def get_case_by_cnr(cnr: str) -> dict | None:
    normalized = normalize_cnr(cnr)
    conn = get_connection()
    row = conn.execute("SELECT * FROM cases WHERE cnr = ?", (normalized,)).fetchone()
    conn.close()
    if not row:
        return None
    return _enrich_case(dict(row))


def lookup_cnr(cnr: str, *, refresh: bool = False) -> dict[str, Any]:
    normalized = normalize_cnr(cnr)
    if not validate_cnr(normalized):
        return {"error": "Invalid CNR. Enter 16 alphanumeric characters (e.g. DLHC010012342020)."}

    if not refresh:
        cached = get_case_by_cnr(normalized)
        if cached:
            cached["from_cache"] = True
            return {"case": cached}

    client = ECourtsClient()
    if not client.has_api_key:
        cached = get_case_by_cnr(normalized)
        if cached:
            cached["from_cache"] = True
            return {"case": cached, "notice": "Showing cached data. Set ECOURTSINDIA_API_KEY for live eCourts lookup."}
        return {
            "error": "Live CNR lookup requires ECOURTSINDIA_API_KEY.",
            "help": "Get an API key at https://ecourtsindia.com/api — or browse sample cases below.",
        }

    try:
        case = client.fetch_by_cnr(normalized)
        save_case(case)
        case["from_cache"] = False
        return {"case": case}
    except RuntimeError as exc:
        cached = get_case_by_cnr(normalized)
        if cached:
            cached["from_cache"] = True
            return {"case": cached, "notice": f"API unavailable ({exc}). Showing cached data."}
        return {"error": str(exc)}


def search_cases(
    query: str = "",
    status: str = "",
    limit: int = 50,
    *,
    live: bool = False,
) -> dict[str, Any]:
    results: list[dict] = []

    if live and query:
        client = ECourtsClient()
        if client.has_api_key:
            try:
                live_data = client.search_cases(query=query, status=status, page_size=limit)
                for case in live_data.get("results", []):
                    save_case(case)
                    results.append(case)
                if results:
                    return {"results": results, "source": "ecourtsindia", "total": live_data.get("total", len(results))}
            except RuntimeError:
                pass

    conn = get_connection()
    conditions: list[str] = []
    params: list[Any] = []

    if query:
        q = f"%{query.lower()}%"
        conditions.append(
            """(
                LOWER(cnr) LIKE ? OR LOWER(petitioner) LIKE ? OR
                LOWER(respondent) LIKE ? OR LOWER(case_number) LIKE ? OR
                LOWER(court) LIKE ?
            )"""
        )
        params.extend([q, q, q, q, q])

    if status:
        conditions.append("LOWER(status) LIKE ?")
        params.append(f"%{status.lower()}%")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM cases {where} ORDER BY fetched_at DESC LIMIT ?",
        params + [limit],
    ).fetchall()
    conn.close()

    results = [_enrich_case(dict(r)) for r in rows]
    return {"results": results, "source": "local", "total": len(results)}


def list_recent_cases(limit: int = 20) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM cases ORDER BY fetched_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [_enrich_case(dict(r)) for r in rows]


