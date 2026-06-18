"""eCourts case lookup client — eCourtsIndia API with local cache fallback."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

API_BASE = os.environ.get("ECOURTSINDIA_API_BASE", "https://api.ecourtsindia.com/v1")
USER_AGENT = "NyayaBhandu/1.0"


def normalize_cnr(cnr: str) -> str:
    return re.sub(r"[\s\-]", "", cnr.strip().upper())


def validate_cnr(cnr: str) -> bool:
    normalized = normalize_cnr(cnr)
    return len(normalized) == 16 and normalized.isalnum()


class ECourtsClient:
    def __init__(self, api_key: str | None = None, delay_seconds: float = 0.5):
        self.api_key = api_key or os.environ.get("ECOURTSINDIA_API_KEY")
        self.delay_seconds = delay_seconds
        self._last_request = 0.0

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key)

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        self._last_request = time.time()

    def _request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError(
                "ECOURTSINDIA_API_KEY not set. Get a key at https://ecourtsindia.com/api"
            )

        self._throttle()
        url = f"{API_BASE.rstrip('/')}/{path.lstrip('/')}"
        data = json.dumps(body).encode("utf-8") if body else None
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        if data:
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"eCourts API error ({exc.code}): {err_body[:400]}") from exc

        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Invalid JSON from eCourts API: {raw[:200]}") from exc

    def fetch_by_cnr(self, cnr: str) -> dict[str, Any]:
        normalized = normalize_cnr(cnr)
        if not validate_cnr(normalized):
            raise ValueError("CNR must be 16 alphanumeric characters (e.g. DLHC010012342020)")

        payload = self._request("GET", f"cases/{normalized}")
        return normalize_api_case(payload, normalized)

    def search_cases(
        self,
        query: str = "",
        party_name: str = "",
        status: str = "",
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"page": page, "pageSize": min(page_size, 100)}
        if query:
            body["query"] = query
        if party_name:
            body["query"] = party_name
        if status:
            body["caseStatuses"] = status.upper()

        payload = self._request("POST", "cases/search", body)
        results = []
        data = payload.get("data", payload)
        raw_results = data.get("results", data.get("cases", []))
        if isinstance(raw_results, list):
            for item in raw_results:
                cnr = item.get("cnr") or item.get("cino") or ""
                if cnr:
                    results.append(normalize_api_case({"data": item}, normalize_cnr(cnr)))

        return {
            "results": results,
            "total": data.get("total", data.get("totalHits", len(results))),
            "page": page,
        }


def _first(*values: Any) -> str:
    for v in values:
        if v is None:
            continue
        if isinstance(v, list):
            if v:
                return str(v[0])
            continue
        text = str(v).strip()
        if text:
            return text
    return ""


def _join_names(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(v).strip() for v in value if str(v).strip())
    return str(value or "").strip()


def normalize_api_case(payload: dict, cnr: str) -> dict[str, Any]:
    """Map eCourtsIndia (or similar) API JSON to NyayaBhandu case format."""
    data = payload.get("data", payload)
    if isinstance(data, dict) and "case" in data:
        data = data["case"]

    case_id = f"cnr-{cnr.lower()}"
    petitioner = _join_names(
        data.get("petitioners")
        or data.get("petitioner")
        or data.get("petitionerName")
    )
    respondent = _join_names(
        data.get("respondents")
        or data.get("respondent")
        or data.get("respondentName")
    )

    hearings = []
    for h in data.get("hearingHistory", data.get("hearings", [])) or []:
        hearings.append(
            {
                "business_date": h.get("businessDate") or h.get("business_date", ""),
                "hearing_date": h.get("hearingDate") or h.get("hearing_date", ""),
                "judge": h.get("judge", ""),
                "purpose": h.get("purpose") or h.get("purposeOfHearing", ""),
            }
        )

    orders = []
    for o in data.get("orders", data.get("orderDetails", [])) or []:
        orders.append(
            {
                "order_date": o.get("orderDate") or o.get("order_date", ""),
                "order_number": o.get("orderNumber") or o.get("order_number", ""),
                "order_details": o.get("orderDetails") or o.get("details", ""),
            }
        )

    return {
        "id": case_id,
        "cnr": cnr,
        "case_type": _first(data.get("caseType"), data.get("case_type")),
        "case_number": _first(data.get("caseNumber"), data.get("case_number")),
        "filing_number": _first(data.get("filingNumber"), data.get("filing_number")),
        "court": _first(data.get("courtName"), data.get("court"), data.get("courtComplex")),
        "court_complex": _first(data.get("courtComplex"), data.get("court_complex")),
        "state": _first(data.get("state")),
        "district": _first(data.get("district")),
        "status": _first(data.get("caseStatus"), data.get("status"), "Unknown"),
        "stage": _first(data.get("caseStage"), data.get("stage")),
        "petitioner": petitioner,
        "respondent": respondent,
        "filing_date": _first(data.get("filingDate"), data.get("filing_date")),
        "registration_date": _first(data.get("registrationDate"), data.get("registration_date")),
        "next_hearing_date": _first(data.get("nextHearingDate"), data.get("next_hearing_date")),
        "decision_date": _first(data.get("decisionDate"), data.get("decision_date")),
        "judges": _first(data.get("judge"), data.get("judges")),
        "acts_sections": _first(data.get("actsAndSections"), data.get("acts_sections")),
        "summary": _first(data.get("brief"), data.get("summary")),
        "judgment_id": None,
        "source": "ecourtsindia",
        "hearings": hearings,
        "orders": orders,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "raw": data,
    }