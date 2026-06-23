"""Read local S1 indicator JSON files without recalculating S1."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class S1Record:
    trade_date: str
    total_score: float
    expectation_level: str
    indicators: dict[str, dict[str, Any]]
    summary: str = ""


def _normalise(raw: dict[str, Any]) -> S1Record:
    indicators = {
        item.get("code", ""): {
            "name": item.get("name", ""),
            "value": float(item.get("value", 0.0) or 0.0),
            "weight": float(item.get("weight", 0.0) or 0.0),
            "expectation": item.get("expectation", "数据缺失"),
        }
        for item in raw.get("indicator_results", [])
        if item.get("code")
    }
    return S1Record(
        trade_date=str(raw.get("trade_date", "")),
        total_score=float(raw.get("total_score", 0.0) or 0.0),
        expectation_level=str(raw.get("expectation_level", "数据缺失")),
        indicators=indicators,
        summary=str(raw.get("summary", "")),
    )


def load_s1_records(indicators_dir: Path) -> list[S1Record]:
    records: list[S1Record] = []
    for path in sorted(indicators_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        record = _normalise(raw)
        if record.trade_date:
            records.append(record)
    return sorted(records, key=lambda item: item.trade_date)


def load_latest_s1(indicators_dir: Path, limit: int = 10) -> tuple[S1Record, list[S1Record]]:
    records = load_s1_records(indicators_dir)
    if not records:
        raise FileNotFoundError(f"未找到S1指标JSON: {indicators_dir}")
    return records[-1], records[-limit:]
