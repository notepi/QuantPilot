"""CSV-backed event store for S2 industry-validation events."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


COMMON_FIELDS = [
    "event_id",
    "event_type",
    "event_subtype",
    "date",
    "published_at",
    "effective_trade_date",
    "discovered_at",
    "company",
    "ticker",
    "asset",
    "event_relevance_to_159567",
]
BD_FIELDS = [
    *COMMON_FIELDS,
    "partner",
    "upfront_usd",
    "near_term_milestone_usd",
    "long_term_milestone_usd",
    "total_value_usd",
    "rights_scope",
    "is_major_bd",
    "materiality_reason",
    "source_url",
    "source_urls",
    "source_tier",
    "importance",
    "status",
    "verification_status",
    "market_validation_status",
    "related_event_id",
    "is_duplicate",
    "duplicate_of",
    "event_stage",
    "note",
]
CLINICAL_FIELDS = [
    *COMMON_FIELDS,
    "conference",
    "phase",
    "data_type",
    "data_judgement",
    "market_reaction",
    "source_url",
    "source_urls",
    "source_tier",
    "importance",
    "status",
    "verification_status",
    "market_validation_status",
    "related_event_id",
    "is_duplicate",
    "duplicate_of",
    "event_stage",
    "note",
]
EARNINGS_FIELDS = [
    *COMMON_FIELDS,
    "period",
    "revenue_actual",
    "revenue_consensus",
    "revenue_yoy",
    "profit_actual",
    "profit_consensus",
    "profit_yoy",
    "product_revenue",
    "product_revenue_yoy",
    "has_consensus",
    "beat",
    "business_improved",
    "loss_narrowed",
    "turned_profitable",
    "guidance_raised",
    "consensus_source_url",
    "source_url",
    "source_urls",
    "source_tier",
    "importance",
    "status",
    "verification_status",
    "market_validation_status",
    "related_event_id",
    "is_duplicate",
    "duplicate_of",
    "event_stage",
    "note",
]
REGULATORY_FIELDS = [
    *COMMON_FIELDS,
    "approval_type",
    "market",
    "source_url",
    "source_urls",
    "source_tier",
    "importance",
    "status",
    "verification_status",
    "market_validation_status",
    "related_event_id",
    "is_duplicate",
    "duplicate_of",
    "event_stage",
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


def _event_type(path: Path) -> str:
    return path.stem.removesuffix("_events")


def _event_id(row: dict[str, str], event_type: str) -> str:
    parts = [
        event_type,
        row.get("event_subtype", ""),
        row.get("date", ""),
        row.get("company", ""),
        row.get("asset", "") or row.get("period", "") or row.get("approval_type", ""),
        row.get("source_url", ""),
    ]
    raw = "|".join(part.strip().lower() for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _source_urls(row: dict[str, str]) -> str:
    values: list[str] = []
    raw = row.get("source_urls", "")
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                values.extend(str(value) for value in parsed if value)
        except json.JSONDecodeError:
            values.extend(value for value in raw.split("|") if value)
    if row.get("source_url") and row["source_url"] not in values:
        values.append(row["source_url"])
    return json.dumps(values, ensure_ascii=False)


def _normalise_event(path: Path, row: dict[str, str]) -> dict[str, str]:
    event_type = row.get("event_type") or _event_type(path)
    normalised = {field: str(row.get(field, "") or "") for field in STORE_FILES[path.name]}
    normalised["event_type"] = event_type
    event_stage = row.get("event_stage") or ""
    event_subtype = row.get("event_subtype") or event_stage
    if not event_subtype or event_subtype == event_type:
        if event_type == "clinical":
            event_subtype = "clinical_readout"
        elif event_type == "regulatory":
            approval_type = row.get("approval_type", "").lower()
            event_subtype = "approval" if "approval" in approval_type or event_stage == "approval" else "regulatory_acceptance"
        elif event_type == "bd":
            event_subtype = "BD"
        elif event_type == "earnings":
            event_subtype = "earnings"
        else:
            event_subtype = event_type
    normalised["event_subtype"] = event_subtype
    normalised["event_id"] = row.get("event_id") or _event_id(row, event_type)
    normalised["published_at"] = row.get("published_at") or row.get("date", "")
    normalised["effective_trade_date"] = row.get("effective_trade_date") or row.get("date", "")
    normalised["discovered_at"] = row.get("discovered_at") or row.get("date", "")
    normalised["source_urls"] = _source_urls(row)
    normalised["status"] = row.get("status") or "active"
    normalised["verification_status"] = row.get("verification_status") or "confirmed"
    normalised["market_validation_status"] = row.get("market_validation_status") or "pending"
    normalised["is_duplicate"] = row.get("is_duplicate") or "false"
    normalised["duplicate_of"] = row.get("duplicate_of") or ""
    normalised["event_stage"] = row.get("event_stage") or ""
    normalised["event_relevance_to_159567"] = row.get("event_relevance_to_159567") or "medium"
    if path.name == "bd_events.csv":
        normalised["is_major_bd"] = row.get("is_major_bd") or "true"
    return normalised


def _write_rows(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def ensure_event_store(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for filename, fields in STORE_FILES.items():
        path = data_dir / filename
        if not path.exists():
            _write_rows(path, fields, [])
            continue
        if filename.endswith("_events.csv"):
            with path.open(newline="", encoding="utf-8") as fh:
                reader = csv.DictReader(fh)
                rows = list(reader)
                current_fields = list(reader.fieldnames or [])
            normalised_rows = [_normalise_event(path, row) for row in rows]
            if current_fields != fields or rows != normalised_rows:
                _write_rows(path, fields, normalised_rows)


def load_events(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def append_events(path: Path, events: list[dict[str, object]]) -> int:
    ensure_event_store(path.parent)
    existing = load_events(path)
    fields = STORE_FILES.get(path.name)
    if fields is None:
        raise ValueError(f"未知事件库文件: {path.name}")
    rows = [_normalise_event(path, row) for row in existing]
    by_id = {row["event_id"]: row for row in rows}
    by_semantic_key = {
        (
            row.get("event_type", ""),
            row.get("event_subtype", ""),
            row.get("date", ""),
            row.get("company", "").strip().lower(),
            row.get("asset", "").strip().lower() or row.get("period", "").strip().lower() or row.get("approval_type", "").strip().lower(),
        ): row
        for row in rows
    }
    added = 0
    for event in events:
        row = _normalise_event(path, {field: str(event.get(field, "") or "") for field in fields})
        semantic_key = (
            row.get("event_type", ""),
            row.get("event_subtype", ""),
            row.get("date", ""),
            row.get("company", "").strip().lower(),
            row.get("asset", "").strip().lower() or row.get("period", "").strip().lower() or row.get("approval_type", "").strip().lower(),
        )
        previous = by_id.get(row["event_id"]) or by_semantic_key.get(semantic_key)
        if previous:
            previous_sources = json.loads(_source_urls(previous))
            for source in json.loads(_source_urls(row)):
                if source not in previous_sources:
                    previous_sources.append(source)
            previous["source_urls"] = json.dumps(previous_sources, ensure_ascii=False)
            if previous.get("verification_status") != "confirmed" and row.get("verification_status") == "confirmed":
                previous["verification_status"] = "confirmed"
            if not previous.get("source_url") and row.get("source_url"):
                previous["source_url"] = row["source_url"]
            continue
        rows.append(row)
        by_id[row["event_id"]] = row
        by_semantic_key[semantic_key] = row
        added += 1
    _write_rows(path, fields, rows)
    return added
