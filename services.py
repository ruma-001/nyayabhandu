"""Business logic and search services."""

import json
from typing import Any

from database import get_connection


def _parse_json_field(value: str | None, default: Any = None) -> Any:
    if value is None:
        return default if default is not None else []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else []


def _enrich_judgment(row: dict) -> dict:
    row["keywords"] = _parse_json_field(row.get("keywords"))
    return row


def _enrich_proforma(row: dict) -> dict:
    row["tags"] = _parse_json_field(row.get("tags"))
    return row


def _enrich_outline(row: dict) -> dict:
    row["documents_required"] = _parse_json_field(row.get("documents_required"))
    row["steps"] = _parse_json_field(row.get("steps"))
    row["tips"] = _parse_json_field(row.get("tips"))
    row["relevant_acts"] = _parse_json_field(row.get("relevant_acts"))
    return row


def search_judgments(
    query: str = "",
    court: str = "",
    year: int | None = None,
    subject: str = "",
    limit: int = 50,
) -> list[dict]:
    conn = get_connection()
    conditions: list[str] = []
    params: list[Any] = []

    if query:
        q = f"%{query.lower()}%"
        conditions.append(
            """(
                LOWER(title) LIKE ? OR LOWER(citation) LIKE ? OR
                LOWER(summary) LIKE ? OR LOWER(keywords) LIKE ? OR
                LOWER(petitioner) LIKE ? OR LOWER(respondent) LIKE ?
            )"""
        )
        params.extend([q, q, q, q, q, q])

    if court:
        conditions.append("LOWER(court) LIKE ?")
        params.append(f"%{court.lower()}%")

    if year:
        conditions.append("year = ?")
        params.append(year)

    if subject:
        conditions.append("LOWER(subject) LIKE ?")
        params.append(f"%{subject.lower()}%")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM judgments {where} ORDER BY year DESC, date DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_enrich_judgment(dict(r)) for r in rows]


def get_judgment(judgment_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM judgments WHERE id = ?", (judgment_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _enrich_judgment(dict(row))


def get_citations_for(judgment_id: str) -> dict:
    conn = get_connection()

    cited_by = conn.execute(
        """
        SELECT j.*, c.treatment, c.context
        FROM citations c
        JOIN judgments j ON j.id = c.citing_id
        WHERE c.cited_id = ?
        ORDER BY j.year DESC
        """,
        (judgment_id,),
    ).fetchall()

    cites = conn.execute(
        """
        SELECT j.*, c.treatment, c.context
        FROM citations c
        JOIN judgments j ON j.id = c.cited_id
        WHERE c.citing_id = ?
        ORDER BY j.year DESC
        """,
        (judgment_id,),
    ).fetchall()

    conn.close()

    def enrich(rows):
        result = []
        for r in rows:
            d = _enrich_judgment(dict(r))
            result.append(d)
        return result

    return {"cited_by": enrich(cited_by), "cites": enrich(cites)}


def search_by_citation(citation: str) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT * FROM judgments
        WHERE LOWER(citation) LIKE ?
        ORDER BY year DESC
        """,
        (f"%{citation.lower()}%",),
    ).fetchall()
    conn.close()
    return [_enrich_judgment(dict(r)) for r in rows]


def get_filter_options() -> dict:
    conn = get_connection()
    courts = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT court FROM judgments ORDER BY court"
        ).fetchall()
    ]
    subjects = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT subject FROM judgments ORDER BY subject"
        ).fetchall()
    ]
    years = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT year FROM judgments ORDER BY year DESC"
        ).fetchall()
    ]
    conn.close()
    return {"courts": courts, "subjects": subjects, "years": years}


def search_proformas(
    case_type: str = "",
    state: str = "",
    query: str = "",
) -> list[dict]:
    conn = get_connection()
    conditions: list[str] = []
    params: list[Any] = []

    if case_type:
        conditions.append("LOWER(case_type) = ?")
        params.append(case_type.lower())

    if state:
        conditions.append("(LOWER(state) = ? OR state = 'All India')")
        params.append(state.lower())

    if query:
        q = f"%{query.lower()}%"
        conditions.append(
            "(LOWER(title) LIKE ? OR LOWER(description) LIKE ? OR LOWER(content) LIKE ?)"
        )
        params.extend([q, q, q])

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM proformas {where} ORDER BY state, case_type, title",
        params,
    ).fetchall()
    conn.close()
    return [_enrich_proforma(dict(r)) for r in rows]


def get_proforma(proforma_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM proformas WHERE id = ?", (proforma_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _enrich_proforma(dict(row))


def get_proforma_filters() -> dict:
    conn = get_connection()
    case_types = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT case_type FROM proformas ORDER BY case_type"
        ).fetchall()
    ]
    states = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT state FROM proformas ORDER BY state"
        ).fetchall()
    ]
    conn.close()
    return {"case_types": case_types, "states": states}


def search_outlines(
    case_type: str = "",
    state: str = "",
    query: str = "",
) -> list[dict]:
    conn = get_connection()
    conditions: list[str] = []
    params: list[Any] = []

    if case_type:
        conditions.append("LOWER(case_type) = ?")
        params.append(case_type.lower())

    if state:
        conditions.append("LOWER(state) = ?")
        params.append(state.lower())

    if query:
        q = f"%{query.lower()}%"
        conditions.append("(LOWER(title) LIKE ? OR LOWER(court) LIKE ?)")
        params.extend([q, q])

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = conn.execute(
        f"SELECT * FROM filing_outlines {where} ORDER BY state, case_type",
        params,
    ).fetchall()
    conn.close()
    return [_enrich_outline(dict(r)) for r in rows]


def get_outline(outline_id: str) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM filing_outlines WHERE id = ?", (outline_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _enrich_outline(dict(row))


def get_outline_filters() -> dict:
    conn = get_connection()
    case_types = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT case_type FROM filing_outlines ORDER BY case_type"
        ).fetchall()
    ]
    states = [
        r[0]
        for r in conn.execute(
            "SELECT DISTINCT state FROM filing_outlines ORDER BY state"
        ).fetchall()
    ]
    conn.close()
    return {"case_types": case_types, "states": states}


def get_stats() -> dict:
    conn = get_connection()
    stats = {
        "judgments": conn.execute("SELECT COUNT(*) FROM judgments").fetchone()[0],
        "citations": conn.execute("SELECT COUNT(*) FROM citations").fetchone()[0],
        "proformas": conn.execute("SELECT COUNT(*) FROM proformas").fetchone()[0],
        "outlines": conn.execute("SELECT COUNT(*) FROM filing_outlines").fetchone()[0],
        "courts": conn.execute(
            "SELECT COUNT(DISTINCT court) FROM judgments"
        ).fetchone()[0],
        "states": conn.execute(
            "SELECT COUNT(DISTINCT state) FROM filing_outlines"
        ).fetchone()[0],
    }
    conn.close()
    return stats