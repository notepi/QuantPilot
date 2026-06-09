"""Market data audit gate for S2.

This module intentionally runs before report generation. It does not calculate
S2 scores; it only answers whether a quote source is auditable enough for
latest-signal language.
"""

from __future__ import annotations

import csv
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from s2.event_store import load_events
from s2.update_market_data import _fetch_citydata_fund_daily, _fetch_tencent_etf_daily


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
S2_DATA_DIR = PROJECT_ROOT / "s2" / "data"
S2_OUTPUT_DIR = PROJECT_ROOT / "s2" / "output"
AUDIT_DIR = S2_OUTPUT_DIR / "data_audit"
AUDIT_PATH = AUDIT_DIR / "market_data_audit.csv"

AUDIT_FIELDS = [
    "symbol",
    "expected_report_date",
    "raw_latest_date",
    "cache_latest_date",
    "processed_latest_date",
    "final_latest_date",
    "calendar_lag_days",
    "trading_lag_days",
    "raw_status",
    "cache_status",
    "processed_status",
    "primary_source",
    "primary_status",
    "fallback_source",
    "fallback_status",
    "final_source",
    "final_source_reason",
    "fetched_at",
    "source_conflict",
    "stability_check_status",
    "data_quality",
    "can_use_for_latest_signal",
    "reason",
]

KEY_SYMBOLS = ["159567.SZ", "159557.SZ", "589720.SH"]
CLOSE_TOLERANCE = 0.001
PCT_TOLERANCE = 0.0015


@dataclass(frozen=True)
class SourceState:
    latest_date: str = ""
    source: str = ""
    fetched_at: str = ""
    status: str = "missing"
    close: float | None = None
    pct_chg: float | None = None


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype={"trade_date": str, "date": str, "ts_code": str, "ticker": str})


def _date_key(value: str) -> str:
    return str(value or "").replace("-", "")


def _normalise_symbol(symbol: str) -> str:
    raw = str(symbol or "").strip()
    if raw.endswith(".HK"):
        return f"{raw.removesuffix('.HK').zfill(5)}.HK"
    return raw


def _calendar_lag(latest: str, expected: str) -> int:
    if not latest or not expected:
        return 999
    try:
        return max(0, (datetime.strptime(expected, "%Y%m%d") - datetime.strptime(latest, "%Y%m%d")).days)
    except ValueError:
        return 999


def _source_status_from_schema(row: pd.Series, has_source: bool, has_fetched_at: bool, latest: str, expected: str) -> str:
    if not latest:
        return "missing"
    if latest < expected:
        return "stale"
    if not has_source or not has_fetched_at:
        return "unverified_raw_schema"
    source = str(row.get("source_name") or row.get("source") or "").strip()
    fetched_at = str(row.get("fetched_at") or "").strip()
    if not source or not fetched_at:
        return "unverified_source_fields"
    return "latest_available"


def _state_from_table(path: Path, symbol: str, expected: str, *, date_col: str = "trade_date", symbol_col: str = "ts_code") -> SourceState:
    df = _load_csv(path)
    if df.empty or symbol_col not in df.columns or date_col not in df.columns or "close" not in df.columns:
        return SourceState()
    rows = df[df[symbol_col].astype(str) == symbol].copy()
    if rows.empty:
        return SourceState()
    rows[date_col] = rows[date_col].astype(str).str.replace("-", "", regex=False)
    rows = rows.sort_values(date_col)
    row = rows.iloc[-1]
    latest = str(row[date_col])
    has_source = "source_name" in rows.columns or "source" in rows.columns
    has_fetched_at = "fetched_at" in rows.columns
    source = str(row.get("source_name") or row.get("source") or "").strip()
    fetched_at = str(row.get("fetched_at") or "").strip()
    status = _source_status_from_schema(row, has_source, has_fetched_at, latest, expected)
    close = _float_or_none(row.get("close"))
    pct_chg = _float_or_none(row.get("pct_chg"))
    return SourceState(latest, source, fetched_at, status, close, pct_chg)


def _state_from_cache(symbol: str, expected: str) -> SourceState:
    short = symbol.split(".")[0]
    path = S2_OUTPUT_DIR / "hk_cache" / f"{short}.csv"
    return _state_from_table(path, symbol, expected, date_col="date", symbol_col="ticker")


def _state_from_hk_daily(symbol: str, expected: str) -> SourceState:
    return _state_from_table(S2_DATA_DIR / "hk_daily.csv", symbol, expected)


def _state_from_processed_market(symbol: str, expected: str) -> SourceState:
    return _state_from_table(PROCESSED_DIR / "market_daily.csv", symbol, expected, symbol_col="symbol")


def _float_or_none(value: object) -> float | None:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct_from_two(rows: pd.DataFrame, date_col: str) -> float | None:
    if len(rows) < 2:
        return None
    ordered = rows.copy()
    ordered[date_col] = ordered[date_col].astype(str).str.replace("-", "", regex=False)
    ordered = ordered.sort_values(date_col).drop_duplicates(date_col, keep="last")
    close = pd.to_numeric(ordered["close"], errors="coerce").dropna()
    if len(close) < 2 or close.iloc[-2] == 0:
        return None
    return float(close.iloc[-1] / close.iloc[-2] - 1)


def _pct_from_row_or_two(row: pd.Series, rows: pd.DataFrame, date_col: str) -> float | None:
    pct = _float_or_none(row.get("pct_chg"))
    if pct is not None:
        return pct / 100
    return _pct_from_two(rows, date_col)


def _fetch_key_symbol(symbol: str) -> SourceState:
    short = symbol.split(".")[0]
    if symbol in {"159567.SZ", "159557.SZ"}:
        df = _fetch_tencent_etf_daily(short, limit=5)
        source = "tencent_fqkline"
        date_col = "date"
    elif symbol == "589720.SH":
        df = _fetch_citydata_fund_daily(symbol, start_date="20260601")
        source = "citydata_fund_daily"
        date_col = "trade_date"
    else:
        return SourceState()
    if df.empty or date_col not in df.columns or "close" not in df.columns:
        return SourceState(source=source, status="source_failed")
    df = df.copy().sort_values(date_col)
    row = df.iloc[-1]
    latest = str(row[date_col]).replace("-", "")
    return SourceState(
        latest_date=latest,
        source=source,
        fetched_at=datetime.now().isoformat(timespec="seconds"),
        status="success",
        close=_float_or_none(row.get("close")),
        pct_chg=_pct_from_row_or_two(row, df, date_col),
    )


def _stability_check(symbol: str) -> tuple[str, str, str, str]:
    if symbol not in KEY_SYMBOLS:
        return "not_required", "", "", ""
    try:
        first = _fetch_key_symbol(symbol)
        time.sleep(1)
        second = _fetch_key_symbol(symbol)
    except Exception as exc:  # noqa: BLE001 - audit must stay non-blocking
        return "source_failed", "", "", f"{type(exc).__name__}: {str(exc)[:160]}"
    if first.status != "success" or second.status != "success":
        return "source_failed", first.source or second.source, first.fetched_at or second.fetched_at, "double_fetch_failed"
    if first.latest_date != second.latest_date:
        return "unstable_source", second.source, second.fetched_at, f"trade_date mismatch: {first.latest_date}!={second.latest_date}"
    close_diff = abs((first.close or 0) - (second.close or 0))
    pct_1 = first.pct_chg
    pct_2 = second.pct_chg
    pct_diff = 0.0 if pct_1 is None or pct_2 is None else abs(pct_1 - pct_2)
    if close_diff > CLOSE_TOLERANCE or pct_diff > PCT_TOLERANCE:
        return "unstable_source", second.source, second.fetched_at, f"close_diff={close_diff:.6f};pct_diff={pct_diff:.6f}"
    return "stable", second.source, second.fetched_at, f"close={second.close};pct_chg={pct_2}"


def _symbols_to_audit() -> list[str]:
    symbols = set(KEY_SYMBOLS)
    for filename in ["clinical_events.csv", "leader_pool.csv"]:
        for row in load_events(S2_DATA_DIR / filename):
            ticker = row.get("ticker")
            if ticker:
                symbols.add(_normalise_symbol(ticker))
    hk = _load_csv(S2_DATA_DIR / "hk_daily.csv")
    if not hk.empty and "ts_code" in hk.columns:
        symbols.update(_normalise_symbol(str(value)) for value in hk["ts_code"].dropna().unique())
    processed = _load_csv(PROCESSED_DIR / "market_daily.csv")
    if not processed.empty and "symbol" in processed.columns:
        symbols.update(_normalise_symbol(str(value)) for value in processed["symbol"].dropna().unique())
    return sorted(symbols)


def _choose_final(symbol: str, expected: str, raw: SourceState, cache: SourceState, processed: SourceState) -> tuple[SourceState, str, str]:
    candidates: list[tuple[str, SourceState, str]] = []
    if processed.latest_date:
        candidates.append(("processed", processed, "processed table has latest symbol row"))
    if cache.latest_date:
        candidates.append(("cache", cache, "HK cache has symbol row"))
    if raw.latest_date:
        candidates.append(("raw", raw, "raw table has symbol row"))
    latest_candidates = [item for item in candidates if item[1].latest_date >= expected]
    if latest_candidates:
        verified = [item for item in latest_candidates if item[1].status in {"latest_available"}]
        if verified:
            name, state, reason = verified[0]
            return state, name, reason
        name, state, reason = latest_candidates[0]
        return state, name, reason
    if candidates:
        name, state, reason = sorted(candidates, key=lambda item: item[1].latest_date, reverse=True)[0]
        return state, name, f"{reason}; no source reached expected date"
    return SourceState(), "missing", "no local market data"


def _audit_symbol(symbol: str, expected_report_date: str) -> dict[str, str]:
    symbol = _normalise_symbol(symbol)
    expected = _date_key(expected_report_date)

    # ETF 标的不再检查 raw/fund_daily.csv（该文件已废弃，不再更新）
    # 数据流设计：ETF 行情直接从腾讯/citydata 实时抓取写入 processed
    if symbol in {"159567.SZ", "159557.SZ", "589720.SH"}:
        raw = SourceState()  # 跳过已废弃的 raw 检查
        cache = _state_from_cache(symbol, expected) if symbol in {"159567.SZ", "159557.SZ"} else SourceState()
    else:
        raw_path = RAW_DIR / "daily.csv"
        raw = _state_from_table(raw_path, symbol, expected)
        cache = SourceState()

    processed = _state_from_processed_market(symbol, expected)
    if not processed.latest_date and symbol.endswith(".HK"):
        processed = _state_from_hk_daily(symbol, expected)
    final_state, final_source, final_reason = _choose_final(symbol, expected, raw, cache, processed)
    stability_status, stability_source, stability_fetched_at, stability_reason = _stability_check(symbol)
    fetched_at = final_state.fetched_at or stability_fetched_at

    # source_conflict 只比较实际使用的源（cache/processed），不包含已废弃的 raw
    source_conflict = "false"
    active_sources = [state.latest_date for state in [cache, processed] if state.latest_date]
    if len(set(active_sources)) > 1:
        source_conflict = "true"

    reasons: list[str] = []
    if final_state.latest_date < expected:
        reasons.append("latest_trade_date < report_trade_date")
    if final_state.status in {"unverified_raw_schema", "unverified_source_fields"}:
        reasons.append(final_state.status)
    if stability_status in {"unstable_source", "source_failed"}:
        reasons.append(f"stability_check={stability_status}")
    if source_conflict == "true":
        reasons.append("raw/cache/processed latest_date mismatch")

    can_use = (
        final_state.latest_date >= expected
        and final_state.status not in {"missing", "stale", "unverified_raw_schema", "unverified_source_fields"}
        and stability_status not in {"unstable_source", "source_failed"}
        and source_conflict != "true"
    )
    if symbol not in KEY_SYMBOLS:
        can_use = (
            final_state.latest_date >= expected
            and final_state.status not in {"missing", "stale", "unverified_raw_schema", "unverified_source_fields"}
            and source_conflict != "true"
        )

    if not final_state.latest_date:
        quality = "missing"
    elif final_state.latest_date < expected:
        quality = "stale"
    elif stability_status == "unstable_source":
        quality = "unstable_source"
    elif final_state.status in {"unverified_raw_schema", "unverified_source_fields"}:
        quality = "latest_unverified"
    elif source_conflict == "true":
        quality = "source_conflict"
    else:
        quality = "latest_valid"

    return {
        "symbol": symbol,
        "expected_report_date": expected,
        "raw_latest_date": raw.latest_date,
        "cache_latest_date": cache.latest_date,
        "processed_latest_date": processed.latest_date,
        "final_latest_date": final_state.latest_date,
        "calendar_lag_days": str(_calendar_lag(final_state.latest_date, expected)),
        "trading_lag_days": str(_calendar_lag(final_state.latest_date, expected)),
        "raw_status": raw.status,
        "cache_status": cache.status,
        "processed_status": processed.status,
        "primary_source": raw.source or "missing",
        "primary_status": raw.status,
        "fallback_source": cache.source or processed.source or stability_source or "missing",
        "fallback_status": cache.status if cache.latest_date else processed.status,
        "final_source": final_source,
        "final_source_reason": final_reason,
        "fetched_at": fetched_at,
        "source_conflict": source_conflict,
        "stability_check_status": stability_status,
        "data_quality": quality,
        "can_use_for_latest_signal": str(can_use).lower(),
        "reason": "；".join(reasons + ([stability_reason] if stability_reason and stability_status != "stable" else [])),
    }


def refresh_market_data_audit(report_date: str | None = None) -> Path:
    report_date = report_date or datetime.now().strftime("%Y-%m-%d")
    rows = [_audit_symbol(symbol, report_date) for symbol in _symbols_to_audit()]
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    with AUDIT_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=AUDIT_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return AUDIT_PATH


def main() -> None:
    path = refresh_market_data_audit()
    rows = load_events(path)
    blocked = [row["symbol"] for row in rows if row.get("can_use_for_latest_signal") != "true"]
    unstable = [row["symbol"] for row in rows if row.get("data_quality") == "unstable_source"]
    print(f"market_data_audit updated: {path}")
    print(f"audited_symbols={len(rows)} blocked={len(blocked)} unstable={len(unstable)}")
    if blocked:
        print("blocked_symbols=" + ",".join(blocked[:30]))
    if unstable:
        print("unstable_symbols=" + ",".join(unstable[:30]))


if __name__ == "__main__":
    main()
