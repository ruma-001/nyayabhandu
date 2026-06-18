# NyayaSetu

India's legal research and practice platform — search court judgments, trace citations, download proformas, and get state-wise filing guides.

## Features

- **Judgment Database** — Search Supreme Court and High Court judgments by name, citation, court, year, and subject
- **Citation Finder** — Look up cases by citation and explore citation graphs (cited by / cites)
- **Legal Proformas** — Ready-to-use document templates by state and case type
- **Filing Guides** — Step-by-step outlines with documents, court fees, limitation periods, and tips

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

Open [http://localhost:8080](http://localhost:8080)

## Tech Stack

- FastAPI
- SQLite
- Jinja2 + Tailwind CSS

## Adding Cases & Proformas

The site starts with **sample data only** (15 landmark judgments, 8 proformas). Dropdowns list all Indian courts/states from `data/catalog.json`, but search results only show what you've imported.

### Bulk import from JSON

1. Copy `data/import_format.json` as a template
2. Add your judgments, proformas, or filing guides
3. Run:

```bash
python import_data.py data/your_file.json          # add to existing data
python import_data.py data/seed.json --reset       # wipe and reimport everything
python import_data.py data/cases.json --type judgments
```

### JSON file structure

Each file can contain any of these top-level keys:

| Key | Description |
|-----|-------------|
| `judgments` | Court cases with citation, court, summary |
| `citations` | Links between cases (`citing_id` → `cited_id`) |
| `proformas` | Document templates by state and case type |
| `filing_outlines` | Step-by-step filing guides |

### Import from Indian Kanoon (automated)

NyayaSetu includes a built-in Indian Kanoon importer.

1. **Get an API token** (recommended for bulk): https://api.indiankanoon.org/
2. Set the token:

```bash
export INDIANKANOON_TOKEN=your_token_here
```

3. Import judgments:

```bash
# Search and import (public fallback works without token for small imports)
python import_kanoon.py --query "right to privacy" --pages 2

# Import from a specific court
python import_kanoon.py --query "bail" --court karnataka --pages 3

# Import recent Supreme Court judgments
python import_kanoon.py --court supremecourt --fromdate 1-1-2024 --pages 5

# Import one known case (Kesavananda Bharati = doc 257876)
python import_kanoon.py --docid 257876 --citations

# Save backup JSON while importing
python import_kanoon.py --query "consumer complaint" --backup data/imported.json
```

**Court codes** for `--court`: `supremecourt`, `delhi`, `bombay`, `karnataka`, `chennai`, `kolkata`, `allahabad`, `kerala`, `rajasthan`, `highcourts`, `judgments`, and more (see `kanoon_client.py`).

Without a token, the importer uses the public website (rate-limited, best for demos). With a token, it uses the official API for faster, larger imports.

### Scaling to all Indian cases

| Source | What it provides |
|--------|------------------|
| [Indian Kanoon API](https://api.indiankanoon.org/) | 3+ crore orders — use `import_kanoon.py` |
| [eCourts](https://ecourts.gov.in/) | District & High Court case status |
| [Supreme Court](https://main.sci.gov.in/) | SC judgments and daily orders |
| SCC Online / Manupatra | Commercial legal databases (licensed) |

## API

| Endpoint | Description |
|----------|-------------|
| `GET /api/judgments` | Search judgments |
| `GET /api/judgments/{id}` | Get judgment details |
| `GET /api/judgments/{id}/citations` | Citation graph |
| `GET /api/citations/search` | Search by citation |
| `GET /api/proformas` | List proformas |
| `GET /api/filing-guides` | List filing guides |
| `GET /api/stats` | Platform statistics |