"""Static reference catalogs for courts, states, and case types."""

import json
from pathlib import Path

CATALOG_PATH = Path(__file__).parent / "data" / "catalog.json"

_catalog: dict | None = None


def load_catalog() -> dict:
    global _catalog
    if _catalog is None:
        with open(CATALOG_PATH, encoding="utf-8") as f:
            _catalog = json.load(f)
    return _catalog


def _merge_unique(primary: list[str], secondary: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for item in primary + secondary:
        if item and item not in seen:
            seen.add(item)
            merged.append(item)
    return merged