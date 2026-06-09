"""Refresh the minimal Macro_Risk_Layer market snapshot."""

from __future__ import annotations

import csv
import json
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "s2" / "data"
HK_CACHE_DIR = PROJECT_ROOT / "s2" / "output" / "hk_cache"
MACRO_PATH = DATA_DIR / "macro_market_snapshot.csv"

FIELDS = [
    "snapshot_date",
    "QQQ_pct",
    "SOXX_pct",
    "SMH_pct",
    "XBI_pct",
    "IBB_pct",
    "XLV_pct",
    "XLP_pct",
    "XLU_pct",
    "US10Y_change",
    "DXY_pct",
    "HSTECH_pct",
    "ETF_159557_pct",
    "ETF_159567_pct",
    "data_source",
    "source_status",
]

YAHOO_SYMBOLS = {
    "QQQ_pct": "QQQ",
    "SOXX_pct": "SOXX",
    "SMH_pct": "SMH",
    "XBI_pct": "XBI",
    "IBB_pct": "IBB",
    "XLV_pct": "XLV",
    "XLP_pct": "XLP",
    "XLU_pct": "XLU",
    "US10Y_change": "^TNX",
    "DXY_pct": "DX-Y.NYB",
    "HSTECH_pct": "^HSTECH",
}


def _fmt_pct(value: float | None) -> str:
    return "missing" if value is None else f"{value:.2%}"


def _fetch_yahoo_daily_pct(symbol: str) -> tuple[float | None, str]:
    params = urllib.parse.urlencode({"range": "5d", "interval": "1d"})
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        return None, "empty"
    closes = (((result.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or []
    clean = [float(value) for value in closes if value is not None]
    if len(clean) < 2:
        return None, "insufficient"
    return clean[-1] / clean[-2] - 1, "success"


def _hk_cache_daily_pct(symbol: str) -> tuple[float | None, str]:
    path = HK_CACHE_DIR / f"{symbol}.csv"
    if not path.exists():
        return None, "missing_cache"
    df = pd.read_csv(path, dtype={"date": str})
    if len(df) < 2 or "close" not in df:
        return None, "insufficient_cache"
    df = df.sort_values("date")
    close = pd.to_numeric(df["close"], errors="coerce").dropna()
    if len(close) < 2:
        return None, "insufficient_cache"
    return float(close.iloc[-1] / close.iloc[-2] - 1), "success"


def refresh_macro_snapshot(snapshot_date: str | None = None) -> dict[str, str]:
    snapshot_date = snapshot_date or datetime.now().strftime("%Y-%m-%d")
    row = {field: "missing" for field in FIELDS}
    row["snapshot_date"] = snapshot_date
    statuses: list[str] = []
    sources: list[str] = []
    for field, symbol in YAHOO_SYMBOLS.items():
        try:
            value, status = _fetch_yahoo_daily_pct(symbol)
        except Exception as exc:  # noqa: BLE001 - macro layer must stay non-blocking
            value, status = None, f"{type(exc).__name__}: {str(exc)[:80]}"
        row[field] = _fmt_pct(value)
        statuses.append(f"{field}:{status}")
        if value is not None:
            sources.append("yahoo_chart")
    for field, symbol in [("ETF_159557_pct", "159557"), ("ETF_159567_pct", "159567")]:
        value, status = _hk_cache_daily_pct(symbol)
        row[field] = _fmt_pct(value)
        statuses.append(f"{field}:{status}")
        if value is not None:
            sources.append("hk_cache")
    row["data_source"] = "+".join(sorted(set(sources))) if sources else "missing"
    row["source_status"] = "；".join(statuses)

    rows: list[dict[str, str]] = []
    if MACRO_PATH.exists():
        with MACRO_PATH.open(newline="", encoding="utf-8") as fh:
            rows = [old for old in csv.DictReader(fh) if old.get("snapshot_date") != snapshot_date and old.get("date") != snapshot_date]
    rows.append(row)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with MACRO_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: old.get(field, "") for field in FIELDS} for old in sorted(rows, key=lambda item: item["snapshot_date"]))
    return row


def main() -> None:
    row = refresh_macro_snapshot()
    print(f"Macro snapshot updated: {row['snapshot_date']} source={row['data_source']}")
    print(row["source_status"])


if __name__ == "__main__":
    main()
