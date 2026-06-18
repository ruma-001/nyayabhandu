"""NyayaBhandu — India's Legal Research & Practice Platform."""

from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from database import init_db
from services import (
    get_citations_for,
    get_filter_options,
    get_judgment,
    get_outline,
    get_outline_filters,
    get_proforma,
    get_proforma_filters,
    get_stats,
    search_by_citation,
    search_judgments,
    search_outlines,
    search_proformas,
)

BASE_DIR = Path(__file__).parent

app = FastAPI(
    title="NyayaBhandu",
    description="India's comprehensive legal research and practice platform",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.on_event("startup")
def startup():
    init_db()


# ── Pages ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    stats = get_stats()
    featured = search_judgments(limit=6)
    return templates.TemplateResponse(
        request, "index.html", {"stats": stats, "featured": featured}
    )


@app.get("/judgments", response_class=HTMLResponse)
async def judgments_page(
    request: Request,
    q: str = "",
    court: str = "",
    year: int | None = None,
    subject: str = "",
):
    results = search_judgments(query=q, court=court, year=year, subject=subject)
    filters = get_filter_options()
    return templates.TemplateResponse(
        request,
        "judgments/index.html",
        {
            "results": results,
            "filters": filters,
            "q": q,
            "court": court,
            "year": year,
            "subject": subject,
        },
    )


@app.get("/judgments/{judgment_id}", response_class=HTMLResponse)
async def judgment_detail(request: Request, judgment_id: str):
    judgment = get_judgment(judgment_id)
    if not judgment:
        return templates.TemplateResponse(
            request, "404.html", status_code=404
        )
    citations = get_citations_for(judgment_id)
    return templates.TemplateResponse(
        request,
        "judgments/detail.html",
        {"judgment": judgment, "citations": citations},
    )


@app.get("/citations", response_class=HTMLResponse)
async def citations_page(request: Request, q: str = ""):
    results = search_by_citation(q) if q else []
    return templates.TemplateResponse(
        request, "citations/index.html", {"results": results, "q": q}
    )


@app.get("/proformas", response_class=HTMLResponse)
async def proformas_page(
    request: Request,
    case_type: str = "",
    state: str = "",
    q: str = "",
):
    results = search_proformas(case_type=case_type, state=state, query=q)
    filters = get_proforma_filters()
    return templates.TemplateResponse(
        request,
        "proformas/index.html",
        {
            "results": results,
            "filters": filters,
            "case_type": case_type,
            "state": state,
            "q": q,
        },
    )


@app.get("/proformas/{proforma_id}", response_class=HTMLResponse)
async def proforma_detail(request: Request, proforma_id: str):
    proforma = get_proforma(proforma_id)
    if not proforma:
        return templates.TemplateResponse(
            request, "404.html", status_code=404
        )
    return templates.TemplateResponse(
        request, "proformas/detail.html", {"proforma": proforma}
    )


@app.get("/filing-guides", response_class=HTMLResponse)
async def filing_guides_page(
    request: Request,
    case_type: str = "",
    state: str = "",
    q: str = "",
):
    results = search_outlines(case_type=case_type, state=state, query=q)
    filters = get_outline_filters()
    return templates.TemplateResponse(
        request,
        "filing/index.html",
        {
            "results": results,
            "filters": filters,
            "case_type": case_type,
            "state": state,
            "q": q,
        },
    )


@app.get("/filing-guides/{outline_id}", response_class=HTMLResponse)
async def filing_guide_detail(request: Request, outline_id: str):
    outline = get_outline(outline_id)
    if not outline:
        return templates.TemplateResponse(
            request, "404.html", status_code=404
        )
    return templates.TemplateResponse(
        request, "filing/detail.html", {"outline": outline}
    )


# ── API Endpoints ──────────────────────────────────────────────────────────

@app.get("/api/judgments")
async def api_judgments(
    q: str = "",
    court: str = "",
    year: int | None = None,
    subject: str = "",
    limit: int = Query(default=50, le=100),
):
    return search_judgments(query=q, court=court, year=year, subject=subject, limit=limit)


@app.get("/api/judgments/{judgment_id}")
async def api_judgment(judgment_id: str):
    judgment = get_judgment(judgment_id)
    if not judgment:
        return JSONResponse({"error": "Not found"}, status_code=404)
    return judgment


@app.get("/api/judgments/{judgment_id}/citations")
async def api_citations(judgment_id: str):
    return get_citations_for(judgment_id)


@app.get("/api/citations/search")
async def api_citation_search(q: str = ""):
    return search_by_citation(q)


@app.get("/api/proformas")
async def api_proformas(case_type: str = "", state: str = "", q: str = ""):
    return search_proformas(case_type=case_type, state=state, query=q)


@app.get("/api/filing-guides")
async def api_filing_guides(case_type: str = "", state: str = "", q: str = ""):
    return search_outlines(case_type=case_type, state=state, query=q)


@app.get("/api/stats")
async def api_stats():
    return get_stats()