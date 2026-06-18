# Data Ingestion Guide — NyayaBhandu

## Two Different Types of Legal Data

| Data | What it is | Best source | In NyayaBhandu |
|------|-----------|-------------|----------------|
| **Judgments** | Published court orders (final decisions) | Indian Kanoon | `import_kanoon.py`, `bulk_import.py` |
| **Cases filed** | Pending/disposed matters, filings, hearings | eCourts | Not yet — requires separate pipeline |

You cannot get "all cases filed" from Indian Kanoon — it indexes **judgments and orders**, not every filing in every district court.

---

## Part 1: Importing All Judgments (Recommended Path)

### Step 1 — Get Indian Kanoon API token

1. Register at https://api.indiankanoon.org/
2. Generate a shared API token
3. Set it:

```bash
export INDIANKANOON_TOKEN=your_token_here
```

Indian Kanoon has **3+ crore** documents. API access is paid for high volume but is the only realistic way to bulk-import judgments legally and reliably.

### Step 2 — Small test import

```bash
cd /home/ruchitha/Projects/nyayabhandu
source .venv/bin/activate

# 10 cases — works even without token (public fallback)
python import_kanoon.py --query "bail" --court karnataka --pages 1

# Single landmark case
python import_kanoon.py --docid 257876 --citations
```

### Step 3 — Bulk import by court and year

```bash
# Supreme Court 2020–2024 (~thousands of cases)
python bulk_import.py --courts supremecourt --years 2020-2024 --pages-per-year 20

# Three High Courts, one year
python bulk_import.py --courts delhi,bombay,karnataka --years 2024 --pages-per-year 30

# All High Courts + SC for 2023 (run overnight)
python bulk_import.py --courts all --years 2023 --pages-per-year 15
```

Progress is saved to `data/import_progress.json`. If interrupted:

```bash
python bulk_import.py --courts all --years 2020-2024 --resume
```

### Step 4 — Scale to millions

Run in batches by **court × year**. Example cron job:

```bash
# Import one court-year per night
0 2 * * * cd /path/to/nyayabhandu && .venv/bin/python bulk_import.py \
  --courts karnataka --years 2010-2024 --pages-per-year 50 --resume
```

For production at national scale:
- Move from SQLite to **PostgreSQL**
- Add **Elasticsearch/Meilisearch** for full-text search
- Run imports on a background worker (Celery, cron, or cloud function)
- Store raw HTML/JSON from Kanoon in S3 before normalizing

### Court codes reference

| Code | Court |
|------|-------|
| `supremecourt` | Supreme Court of India |
| `delhi` | Delhi High Court |
| `bombay` | Bombay High Court |
| `karnataka` | Karnataka High Court |
| `chennai` | Madras High Court |
| `kolkata` | Calcutta High Court |
| `allahabad` | Allahabad High Court |
| `highcourts` | All High Courts (search filter) |
| `judgments` | SC + HC + District Courts (search filter) |
| `delhidc` | Delhi District Courts |

Full list in `kanoon_client.py` → `COURT_DOCTYPES`.

---

## Part 2: Cases Filed (eCourts) — Harder Problem

**Cases filed** means: case number, parties, filing date, next hearing, status (pending/disposed), orders — often **before** a final judgment exists.

### Sources

| Source | URL | Coverage |
|--------|-----|----------|
| eCourts Services | https://services.ecourts.gov.in/ | District courts, many HCs |
| eCourts India API | https://ecourtsindia.com/api/ | Third-party CNR lookup |
| SurePass / LegalKart APIs | Commercial | CNR search, case tracking |
| Individual HC websites | e.g. delhihighcourt.nic.in | State-specific |

### Why it's different from judgments

- eCourts uses **CNR numbers** (16-digit unique case IDs)
- No single free API gives "all cases ever filed in India"
- Data is fragmented across ~3,000 court establishments
- Scraping eCourts directly violates their terms and uses CAPTCHA

### Recommended approach for case filings

1. **CNR lookup API** — User enters CNR → you fetch case status via licensed API (SurePass, ecourtsindia.com)
2. **Court-specific crawlers** — Some High Courts publish cause lists and orders as PDFs/HTML
3. **Incremental sync** — Track cases your users search for, cache results locally

### Future schema (not yet implemented)

```sql
CREATE TABLE cases (
    id TEXT PRIMARY KEY,          -- CNR or court case number
    court TEXT,
    case_type TEXT,
    filing_date TEXT,
    status TEXT,                  -- pending / disposed
    petitioner TEXT,
    respondent TEXT,
    next_hearing TEXT,
    judgment_id TEXT,             -- links to judgments table when disposed
    raw_json TEXT
);
```

---

## Part 3: Other Judgment Sources

| Source | Method |
|--------|--------|
| Supreme Court | https://main.sci.gov.in/ — scrape judgment PDFs |
| High Court sites | Each HC has its own format — custom parsers per court |
| SCC Online / Manupatra | Licensed commercial databases |
| AWS Open Data | Some legal datasets on data.gov.in |

---

## Legal & Ethical Notes

- **Indian Kanoon API** — Use their official API with a token; respect rate limits and pricing
- **eCourts scraping** — Their terms prohibit automated scraping; use licensed APIs
- **Attribution** — Credit Indian Kanoon / eCourts as data sources on your site
- **Copyright** — Court judgments are generally not copyrighted in India, but databases may have restrictions

---

## Quick Reference

```bash
# Judgments — single search
python import_kanoon.py --query "consumer complaint" --pages 5

# Judgments — bulk by court/year
python bulk_import.py --courts supremecourt --years 2020-2024 --pages-per-year 20 --resume

# Manual JSON import (proformas, custom data)
python import_data.py data/my_file.json

# Check what's in the database
python -c "from services import get_stats; print(get_stats())"
```