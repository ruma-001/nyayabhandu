"""Indian Kanoon client — official API (token) or public HTML fallback."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html import unescape
from typing import Any

from bs4 import BeautifulSoup

API_HOST = "api.indiankanoon.org"
PUBLIC_HOST = "https://indiankanoon.org"
USER_AGENT = "NyayaSetu/1.0 (+https://github.com/ruma-001/nyayasetu)"

COURT_DOCTYPES: dict[str, str] = {
    "supremecourt": "Supreme Court of India",
    "delhi": "Delhi High Court",
    "bombay": "Bombay High Court",
    "chennai": "Madras High Court",
    "kolkata": "Calcutta High Court",
    "allahabad": "Allahabad High Court",
    "andhra": "Andhra Pradesh High Court",
    "chattisgarh": "Chhattisgarh High Court",
    "gauhati": "Gauhati High Court",
    "jammu": "Jammu & Kashmir and Ladakh High Court",
    "kerala": "Kerala High Court",
    "lucknow": "Allahabad High Court",
    "orissa": "Orissa High Court",
    "gujarat": "Gujarat High Court",
    "himachal_pradesh": "Himachal Pradesh High Court",
    "jharkhand": "Jharkhand High Court",
    "karnataka": "Karnataka High Court",
    "madhyapradesh": "Madhya Pradesh High Court",
    "patna": "Patna High Court",
    "punjab": "Punjab & Haryana High Court",
    "rajasthan": "Rajasthan High Court",
    "sikkim": "Sikkim High Court",
    "uttaranchal": "Uttarakhand High Court",
    "meghalaya": "Meghalaya High Court",
    "highcourts": "High Courts",
    "judgments": "Indian Courts",
}

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


class KanoonClient:
    def __init__(
        self,
        token: str | None = None,
        delay_seconds: float = 1.0,
    ):
        self.token = token or os.environ.get("INDIANKANOON_TOKEN")
        self.delay_seconds = delay_seconds
        self._last_request = 0.0

    @property
    def uses_api(self) -> bool:
        return bool(self.token)

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_request
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        self._last_request = time.time()

    def _request(
        self,
        url: str,
        *,
        api: bool = False,
        accept_json: bool = False,
    ) -> str:
        self._throttle()
        headers = {"User-Agent": USER_AGENT}
        if api and self.token:
            headers["Authorization"] = f"Token {self.token}"
            if accept_json:
                headers["Accept"] = "application/json"
        req = urllib.request.Request(url, headers=headers, method="POST" if api else "GET")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Kanoon request failed ({exc.code}): {body[:300]}") from exc
        return data.decode("utf-8", errors="replace")

    def search(
        self,
        query: str,
        pagenum: int = 0,
        maxpages: int = 1,
    ) -> dict[str, Any]:
        if self.uses_api:
            encoded = urllib.parse.quote_plus(query)
            url = f"https://{API_HOST}/search/?formInput={encoded}&pagenum={pagenum}&maxpages={maxpages}"
            raw = self._request(url, api=True, accept_json=True)
            return json.loads(raw)
        return self._search_public(query, pagenum)

    def fetch_doc(
        self,
        docid: int,
        maxcites: int = 0,
        maxcitedby: int = 0,
    ) -> dict[str, Any]:
        if self.uses_api:
            url = f"https://{API_HOST}/doc/{docid}/"
            params = []
            if maxcites:
                params.append(f"maxcites={maxcites}")
            if maxcitedby:
                params.append(f"maxcitedby={maxcitedby}")
            if params:
                url += "?" + "&".join(params)
            raw = self._request(url, api=True, accept_json=True)
            return json.loads(raw)
        return self._fetch_doc_public(docid)

    def _extract_docid_from_result(self, block: BeautifulSoup) -> int | None:
        for link in block.select("a[href]"):
            href = link.get("href", "")
            for pattern in (r"/doc/(\d+)/", r"/docfragment/(\d+)/"):
                match = re.search(pattern, href)
                if match:
                    return int(match.group(1))
        return None

    def _search_public(self, query: str, pagenum: int) -> dict[str, Any]:
        encoded = urllib.parse.quote_plus(query)
        url = f"{PUBLIC_HOST}/search/?formInput={encoded}&pagenum={pagenum}"
        html = self._request(url)
        soup = BeautifulSoup(html, "html.parser")

        docs: list[dict[str, Any]] = []
        seen: set[int] = set()
        for block in soup.select("article.result"):
            docid = self._extract_docid_from_result(block)
            if not docid or docid in seen:
                continue
            seen.add(docid)

            title_el = block.select_one("h4.result_title a")
            headline_el = block.select_one(".headline")
            source_el = block.select_one(".docsource")
            title = unescape(title_el.get_text(" ", strip=True)) if title_el else f"Document {docid}"
            headline = unescape(headline_el.get_text(" ", strip=True)) if headline_el else ""

            docs.append(
                {
                    "tid": docid,
                    "title": title,
                    "headline": headline,
                    "docsource": unescape(source_el.get_text(strip=True)) if source_el else "",
                    "publishdate": "",
                    "citation": _extract_citation_from_text(headline),
                }
            )

        found_el = soup.select_one(".results-count b, .found b, .found")
        found_text = found_el.get_text(strip=True) if found_el else str(len(docs))
        return {"docs": docs, "found": found_text, "formInput": query}

    def _fetch_doc_public(self, docid: int) -> dict[str, Any]:
        url = f"{PUBLIC_HOST}/doc/{docid}/"
        html = self._request(url)
        soup = BeautifulSoup(html, "html.parser")
        title_el = soup.select_one("h2.doc_title, title")
        court_el = soup.select_one("h3.docsource_main")
        bench_el = soup.select_one("h3.doc_bench")
        maindoc = soup.select_one("div.maindoc")

        title = unescape(title_el.get_text(strip=True)) if title_el else f"Document {docid}"
        court = unescape(court_el.get_text(strip=True)) if court_el else ""
        bench = ""
        if bench_el:
            bench = re.sub(r"^Bench:\s*", "", bench_el.get_text(" ", strip=True), flags=re.I)

        doc_html = str(maindoc) if maindoc else html
        text = maindoc.get_text("\n", strip=True) if maindoc else ""

        return {
            "tid": docid,
            "title": title,
            "docsource": court,
            "bench": bench,
            "doc": doc_html,
            "text": text,
        }


def build_query(
    query: str = "",
    court: str = "",
    fromdate: str = "",
    todate: str = "",
    sortby: str = "",
) -> str:
    parts: list[str] = []
    if query:
        parts.append(query)
    if court:
        parts.append(f"doctypes:{court}")
    if fromdate:
        parts.append(f"fromdate: {fromdate}")
    if todate:
        parts.append(f"todate: {todate}")
    if sortby:
        parts.append(f"sortby: {sortby}")
    return " ".join(parts).strip()


def _extract_citation_from_text(text: str) -> str:
    match = re.search(
        r"Equivalent citations?:\s*([^|\n]+)",
        text,
        re.I,
    )
    if match:
        return match.group(1).strip()
    scc = re.search(r"\(\d{4}\)\s*\d+\s*SCC\s*\d+", text)
    if scc:
        return scc.group(0)
    air = re.search(r"AIR\s+\d{4}\s+\w+\s+\d+", text)
    if air:
        return air.group(0)
    return ""


def parse_date_from_title(title: str) -> tuple[str, int]:
    match = re.search(
        r"\bon\s+(\d{1,2})\s+([A-Za-z]+),?\s+(\d{4})\b",
        title,
        re.I,
    )
    if not match:
        return "", 0
    day, month_name, year = match.groups()
    month = MONTHS.get(month_name.lower(), 0)
    if not month:
        return "", int(year)
    return f"{year}-{month:02d}-{int(day):02d}", int(year)


def split_parties(title: str) -> tuple[str, str]:
    cleaned = re.sub(r"\s+on\s+\d{1,2}\s+[A-Za-z]+,?\s+\d{4}.*$", "", title, flags=re.I)
    for sep in (" vs ", " v. ", " v "):
        if sep in cleaned.lower():
            idx = cleaned.lower().index(sep.strip())
            left = cleaned[:idx].strip()
            right = cleaned[idx + len(sep) :].strip()
            return left, right
    return cleaned.strip(), ""


def extract_citations_from_html(doc_html: str, citing_id: str) -> list[dict]:
    soup = BeautifulSoup(doc_html, "html.parser")
    citations: list[dict] = []
    seen: set[tuple[str, str]] = set()

    for link in soup.select('a[href*="/doc/"]'):
        href = link.get("href", "")
        match = re.search(r"/doc/(\d+)/", href)
        if not match:
            continue
        cited_id = f"ik-{match.group(1)}"
        if cited_id == citing_id:
            continue
        parent = link.find_parent(class_="citetext")
        treatment = None
        if parent and parent.get("data-sentiment"):
            treatment = parent["data-sentiment"]
        context = link.get_text(" ", strip=True)[:200]
        key = (citing_id, cited_id)
        if key in seen:
            continue
        seen.add(key)
        citations.append(
            {
                "citing_id": citing_id,
                "cited_id": cited_id,
                "treatment": treatment,
                "context": context or None,
            }
        )
    return citations


def normalize_court(name: str) -> str:
    if not name:
        return "Indian Courts"
    for doctype, court in COURT_DOCTYPES.items():
        if doctype.replace("_", " ") in name.lower():
            return court
    if "supreme court" in name.lower():
        return "Supreme Court of India"
    if "high court" not in name.lower() and name.endswith(" Court"):
        return f"{name} High Court" if "High Court" not in name else name
    return name


def kanoon_to_judgment(
    docid: int,
    *,
    search_hit: dict | None = None,
    doc_payload: dict | None = None,
) -> dict:
    payload = doc_payload or {}
    search_hit = search_hit or {}

    title = payload.get("title") or search_hit.get("title") or f"Document {docid}"
    court = normalize_court(payload.get("docsource") or search_hit.get("docsource", ""))
    date, year = parse_date_from_title(title)
    if not year and search_hit.get("publishdate"):
        date = search_hit["publishdate"]
        parts = re.findall(r"\d+", date)
        if len(parts) >= 3:
            year = int(parts[0])

    text = payload.get("text") or ""
    if not text and payload.get("doc"):
        text = BeautifulSoup(payload["doc"], "html.parser").get_text("\n", strip=True)

    headline = search_hit.get("headline") or ""
    summary = headline
    if not summary and text:
        summary = text[:500] + ("..." if len(text) > 500 else "")

    citation = (
        search_hit.get("citation")
        or _extract_citation_from_text(headline)
        or f"Indian Kanoon Doc {docid}"
    )

    petitioner, respondent = split_parties(title)
    judgment_id = f"ik-{docid}"

    return {
        "id": judgment_id,
        "title": title,
        "citation": citation,
        "court": court,
        "bench": payload.get("bench"),
        "judges": payload.get("bench"),
        "date": date or "unknown",
        "year": year or 0,
        "case_number": None,
        "petitioner": petitioner,
        "respondent": respondent,
        "subject": "Indian Law",
        "summary": summary or "Imported from Indian Kanoon.",
        "full_text": text[:12000] if text else None,
        "keywords": ["indiankanoon", court.lower().replace(" ", "-") if court else "india"],
    }