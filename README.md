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