"""CSV-backed event store for S2 industry-validation events."""

from __future__ import annotations

import csv
from pathlib import Path


BD_FIELDS = [
    "date",
    "company",
    "ticker",
    "asset",
    "partner",
    "upfront_usd",
    "near_term_milestone_usd",
    "total_value_usd",
    "rights_scope",
    "source_url",
    "source_tier",
    "importance",
    "status",
    "note",
]
CLINICAL_FIELDS = [
    "date",
    "company",
    "ticker",
    "conference",
    "asset",
    "phase",
    "data_type",
    "data_judgement",
    "market_reaction",
    "source_url",
    "source_tier",
    "importance",
    "status",
    "note",
]
EARNINGS_FIELDS = [
    "date",
    "company",
    "ticker",
    "period",
    "revenue_yoy",
    "profit_yoy",
    "product_revenue",
    "beat",
    "source_url",
    "source_tier",
    "importance",
    "status",
    "note",
]
REGULATORY_FIELDS = [
    "date",
    "company",
    "ticker",
    "asset",
    "approval_type",
    "market",
    "source_url",
    "source_tier",
    "importance",
    "status",
    "note",
]
LEADER_FIELDS = ["ticker", "company", "market", "weight", "source", "note"]

STORE_FILES = {
    "bd_events.csv": BD_FIELDS,
    "clinical_events.csv": CLINICAL_FIELDS,
    "earnings_events.csv": EARNINGS_FIELDS,
    "regulatory_events.csv": REGULATORY_FIELDS,
    "leader_pool.csv": LEADER_FIELDS,
}


def ensure_event_store(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for filename, fields in STORE_FILES.items():
        path = data_dir / filename
        if not path.exists():
            with path.open("w", newline="", encoding="utf-8") as fh:
                csv.DictWriter(fh, fieldnames=fields).writeheader()


def load_events(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _event_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        row.get("date", ""),
        row.get("company", ""),
        row.get("asset", ""),
        row.get("source_url", ""),
    )


def append_events(path: Path, events: list[dict[str, object]]) -> int:
    existing = load_events(path)
    if existing:
        fields = list(existing[0].keys())
    else:
        fields = STORE_FILES.get(path.name)
        if fields is None:
            raise ValueError(f"未知事件库文件: {path.name}")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            csv.DictWriter(fh, fieldnames=fields).writeheader()

    seen = {_event_key(row) for row in existing}
    new_rows: list[dict[str, str]] = []
    for event in events:
        row = {field: str(event.get(field, "")) for field in fields}
        row.setdefault("status", "active")
        key = _event_key(row)
        if key in seen:
            continue
        seen.add(key)
        new_rows.append(row)

    if new_rows:
        with path.open("a", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writerows(new_rows)
    return len(new_rows)

