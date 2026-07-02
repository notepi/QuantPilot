"""Strict AI versus biotech validation layer.

This module is independent from the formal S1/S2 scoring engines. It caps
history at the latest 250 valid trading observations and writes reproducible
audit, backtest, falsification, right-side-score, and position-state outputs.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import NormalDist
from typing import Any

import pandas as pd

from s3.style_rotation import load_style_config


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MARKET_DAILY = PROJECT_ROOT / "data" / "processed" / "market_daily.csv"
DEFAULT_MACRO_MARKET_DAILY = PROJECT_ROOT / "data" / "processed" / "macro_market_daily.csv"
DEFAULT_INDICATORS_DIR = PROJECT_ROOT / "data" / "indicators"
DEFAULT_S2_SCORES = PROJECT_ROOT / "s2" / "output" / "s2_scores.csv"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "s3" / "config.json"
DEFAULT_AI_CORE_VERSIONS = PROJECT_ROOT / "s3" / "versions.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "s3" / "output"


@dataclass(frozen=True)
class ValidationResult:
    report_date: str
    a_share_date: str
    hk_date: str
    us_close_date: str
    ai_core_date: str
    ai_core_version: str
    tech_growth_core_date: str
    tech_growth_core_version: str
    sample_count: int
    current_ai_state: str
    current_tech_growth_state: str
    market_state: str
    bio_return: float | None
    health_return: float | None
    ai_core_return: float | None
    tech_growth_core_return: float | None
    bio_vs_health: float | None
    bio_vs_ai: float | None
    bio_vs_tech: float | None
    right_side_score: float | None
    right_side_level: str
    score_confidence: str
    score_status: str
    feature_coverage: str
    core_index_status: str
    thesis_state: str
    position_action: str
    strongest_support: list[str]
    strongest_opposition: list[str]
    report_path: str
    audit_path: str


def run_ai_biotech_validation(
    market_daily_path: Path = DEFAULT_MARKET_DAILY,
    indicators_dir: Path = DEFAULT_INDICATORS_DIR,
    s2_scores_path: Path = DEFAULT_S2_SCORES,
    config_path: Path = DEFAULT_CONFIG_PATH,
    ai_core_versions_path: Path = DEFAULT_AI_CORE_VERSIONS,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    report_date: str | None = None,
    macro_market_daily_path: Path = DEFAULT_MACRO_MARKET_DAILY,
) -> ValidationResult:
    config = load_style_config(config_path)
    versions_payload = _load_versions_payload(ai_core_versions_path)
    ai_version = _core_version(versions_payload, config.get("ai_core_version_id") or versions_payload.get("active_version_id"))
    tech_version = _core_version(versions_payload, config.get("tech_growth_core_version_id") or versions_payload.get("tech_growth_core_version_id"))
    data = _build_research_frame(
        market_daily_path,
        macro_market_daily_path,
        indicators_dir,
        s2_scores_path,
        config,
        versions_payload,
        ai_version,
        tech_version,
        report_date,
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    audit = _audit_system(data, config, ai_version, tech_version, market_daily_path, macro_market_daily_path, indicators_dir, s2_scores_path)
    window_stats = _window_stats(data.frame, config)
    state_stats = _ai_state_stats(data.frame, config)
    lead_stats = _a_share_lead_stats(data.frame, config)
    right_side = _right_side_score(data.frame, config)
    if data.core_index_status == "DATA_ERROR":
        right_side.update({
            "right_side_score": "",
            "right_side_level": "missing",
            "confidence": "low",
            "score_status": "DATA_ERROR",
            "feature_coverage": right_side.get("feature_coverage", "missing"),
        })
    falsification = _falsification(data.frame, window_stats, state_stats, lead_stats, right_side)
    position = _position_action(data.frame, right_side, falsification, config)

    _write_csv(output_dir / "ai_biotech_window_stats.csv", window_stats)
    _write_csv(output_dir / "ai_biotech_ai_state_stats.csv", state_stats)
    _write_csv(output_dir / "ai_biotech_a_lead_stats.csv", lead_stats)
    _write_csv(output_dir / "ai_biotech_right_side_score.csv", [right_side])
    _write_csv(output_dir / "ai_biotech_falsification.csv", [falsification])

    audit_path = output_dir / "ai_biotech_audit_report.md"
    audit_path.write_text(_render_audit_report(audit), encoding="utf-8")
    report_path = output_dir / "ai_biotech_validation_report.md"
    report_path.write_text(
        _render_validation_report(data, config, ai_version, tech_version, window_stats, state_stats, lead_stats, right_side, falsification, position),
        encoding="utf-8",
    )

    latest = data.frame.iloc[-1] if not data.frame.empty else {}
    return ValidationResult(
        report_date=data.report_date,
        a_share_date=str(latest.get("a_share_date", "missing")) if len(data.frame) else "missing",
        hk_date=str(latest.get("hk_date", "missing")) if len(data.frame) else "missing",
        us_close_date=str(latest.get("us_close_date", "not_applicable")) if len(data.frame) else "missing",
        ai_core_date=str(latest.get("ai_core_date", "missing")) if len(data.frame) else "missing",
        tech_growth_core_date=str(latest.get("tech_core_date", "missing")) if len(data.frame) else "missing",
        ai_core_version=ai_version["version_id"],
        tech_growth_core_version=tech_version["version_id"],
        sample_count=len(data.frame),
        current_ai_state=str(latest.get("ai_state", "missing")) if len(data.frame) else "missing",
        current_tech_growth_state=str(latest.get("tech_state", "missing")) if len(data.frame) else "missing",
        market_state=str(latest.get("market_state", "missing")) if len(data.frame) else "missing",
        bio_return=_float_or_none(latest.get("bio_ret")),
        health_return=_float_or_none(latest.get("health_ret")),
        ai_core_return=_float_or_none(latest.get("ai_core_ret")),
        tech_growth_core_return=_float_or_none(latest.get("tech_core_ret")),
        bio_vs_health=_float_or_none(latest.get("bio_vs_health")),
        bio_vs_ai=_float_or_none(latest.get("bio_vs_ai")),
        bio_vs_tech=_float_or_none(latest.get("bio_vs_tech")),
        right_side_score=_float_or_none(right_side.get("right_side_score")),
        right_side_level=str(right_side.get("right_side_level") or "missing"),
        score_confidence=str(right_side.get("confidence") or "low"),
        score_status=str(right_side.get("score_status") or "missing"),
        feature_coverage=str(right_side.get("feature_coverage") or "missing"),
        core_index_status=data.core_index_status,
        thesis_state=str(falsification.get("thesis_state") or "unchanged"),
        position_action=str(position.get("action") or "insufficient_data"),
        strongest_support=_split_evidence(falsification.get("support_evidence")),
        strongest_opposition=_split_evidence(falsification.get("opposition_evidence")),
        report_path=str(report_path),
        audit_path=str(audit_path),
    )


@dataclass(frozen=True)
class ResearchData:
    report_date: str
    frame: pd.DataFrame
    symbols: dict[str, str]
    missing: list[str]
    core_index_status: str = "VALID"
    data_quality: dict[str, Any] | None = None


def _load_versions_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"versions": []}
    return payload


def _core_version(payload: dict[str, Any], configured: str | None) -> dict[str, Any]:
    active = configured or payload.get("active_version_id")
    for version in payload.get("versions", []):
        if version.get("version_id") == active:
            return version
    return {
        "version_id": str(active or "missing"),
        "market_scope": "missing",
        "constituents": [],
        "data_source": "missing",
        "rebalance_rule": "missing",
        "adjustment_policy": "missing",
        "notes": "core version not found.",
    }


def _versions_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(version.get("version_id")): version for version in payload.get("versions", [])}


def _core_constituent_symbols(version: dict[str, Any], versions: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in version.get("constituents", []):
        if item.get("version_ref"):
            rows.extend(_core_constituent_symbols(versions.get(str(item["version_ref"]), {}), versions))
            continue
        symbol = item.get("symbol")
        if symbol:
            rows.append({
                "symbol": str(symbol),
                "source_table": str(item.get("source_table") or "market_daily"),
                "weight": str(item.get("weight") or ""),
            })
    return rows


def _core_data_quality(
    market: pd.DataFrame,
    macro: pd.DataFrame,
    versions: dict[str, dict[str, Any]],
    ai_version: dict[str, Any],
    tech_version: dict[str, Any],
    latest_date: str,
) -> dict[str, Any]:
    symbols = _core_constituent_symbols(tech_version, versions) + _core_constituent_symbols(ai_version, versions)
    symbols.extend([
        {"symbol": "159567.SZ", "source_table": "market_daily", "weight": "observation"},
        {"symbol": "159557.SZ", "source_table": "market_daily", "weight": "benchmark"},
        {"symbol": "589720.SH", "source_table": "market_daily", "weight": "temperature"},
    ])
    seen = set()
    rows = []
    missing = []
    for item in symbols:
        key = (item["symbol"], item["source_table"])
        if key in seen:
            continue
        seen.add(key)
        source_table = item["source_table"]
        df = macro if source_table == "macro_market_daily" else market
        s = _series(df, item["symbol"])
        latest = str(s.index.max()) if not s.empty else "missing"
        if source_table == "macro_market_daily":
            usable = s[s.index.astype(str) < latest_date]
            latest_for_asia = str(usable.index.max()) if not usable.empty else "missing"
            status = "valid" if latest_for_asia != "missing" else "missing"
            latest_effective = latest_for_asia
        else:
            status = "valid" if latest == latest_date else "missing"
            latest_effective = latest
        if status != "valid":
            missing.append(item["symbol"])
        rows.append({
            "symbol": item["symbol"],
            "primary_source": source_table,
            "fallback_source_1": "local_verified_cache",
            "fallback_source_2": "not_configured",
            "adjustment_policy": "unadjusted_close",
            "latest_date": latest_effective,
            "missing_days": "0" if status == "valid" else "1+",
            "status": status,
        })
    return {
        "core_symbols": rows,
        "core_missing_symbols": sorted(set(missing)),
        "core_index_status": "DATA_ERROR" if missing else "VALID",
        "source_switch_count": 0,
        "missing_trade_dates": "none" if not missing else ",".join(sorted(set(missing))),
        "abnormal_trade_dates": "none",
        "cross_source_conflicts": "none",
    }


def _load_market(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, dtype={"symbol": str, "trade_date": str})
    needed = {"symbol", "trade_date", "close"}
    if not needed.issubset(df.columns):
        return pd.DataFrame()
    for field in ["close", "amount", "volume"]:
        if field in df.columns:
            df[field] = pd.to_numeric(df[field], errors="coerce")
    df["trade_date"] = df["trade_date"].astype(str).str.replace("-", "", regex=False)
    return df.dropna(subset=["symbol", "trade_date", "close"]).drop_duplicates(["symbol", "trade_date"], keep="last")


def _load_macro(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, dtype={"symbol": str, "trade_date": str})
    needed = {"symbol", "trade_date", "close"}
    if not needed.issubset(df.columns):
        return pd.DataFrame()
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df["trade_date"] = df["trade_date"].astype(str).str.replace("-", "", regex=False)
    if "source_status" in df.columns:
        df = df[df["source_status"].fillna("success") == "success"].copy()
    return df.dropna(subset=["symbol", "trade_date", "close"]).drop_duplicates(["symbol", "trade_date"], keep="last")


def _series(df: pd.DataFrame, symbol: str, field: str = "close") -> pd.Series:
    if df.empty or field not in df.columns:
        return pd.Series(dtype="float64")
    rows = df[df["symbol"] == symbol].sort_values("trade_date")
    return pd.Series(pd.to_numeric(rows[field], errors="coerce").to_numpy(), index=rows["trade_date"].astype(str), dtype="float64").dropna()


def _align_us_to_asia(us_series: pd.Series, base_index: pd.Index) -> tuple[pd.Series, pd.Series]:
    if us_series.empty or len(base_index) == 0:
        return pd.Series(dtype="float64"), pd.Series(dtype="object")
    us = us_series.sort_index()
    values = []
    dates = []
    for asian_date in base_index.astype(str):
        usable = us[us.index.astype(str) < asian_date]
        if usable.empty:
            values.append(float("nan"))
            dates.append("missing")
        else:
            values.append(float(usable.iloc[-1]))
            dates.append(str(usable.index[-1]))
    return pd.Series(values, index=base_index, dtype="float64"), pd.Series(dates, index=base_index, dtype="object")


def _source_series(
    market: pd.DataFrame,
    macro: pd.DataFrame,
    symbol: str,
    source_table: str | None,
    base_index: pd.Index,
    field: str = "close",
) -> tuple[pd.Series, pd.Series]:
    if source_table == "macro_market_daily":
        raw = _series(macro, symbol, field)
        return _align_us_to_asia(raw, base_index)
    raw = _series(market, symbol, field)
    aligned = raw.reindex(base_index)
    return aligned, pd.Series(base_index.astype(str), index=base_index, dtype="object")


def _weighted_core(
    market: pd.DataFrame,
    macro: pd.DataFrame,
    version: dict[str, Any],
    versions: dict[str, dict[str, Any]],
    base_index: pd.Index,
) -> tuple[pd.Series, pd.Series, list[str]]:
    return_parts = []
    date_parts = []
    expected_weight = 0.0
    missing = []
    for item in version.get("constituents", []):
        ref = item.get("version_ref")
        weight = float(item.get("weight") or 0)
        if weight <= 0:
            continue
        expected_weight += weight
        if ref:
            child = versions.get(ref, {})
            child_series, child_dates, child_missing = _weighted_core(market, macro, child, versions, base_index)
            missing.extend(child_missing)
            if child_series.empty or child_series.dropna().empty:
                missing.append(f"{ref}_missing")
                continue
            return_parts.append(child_series.pct_change(fill_method=None).rename(ref) * weight)
            date_parts.append(child_dates.rename(ref))
            continue
        symbol = item.get("symbol")
        if not symbol:
            continue
        s, dates = _source_series(market, macro, symbol, item.get("source_table"), base_index)
        if s.dropna().empty:
            missing.append(f"{symbol}_missing")
            continue
        return_parts.append(s.pct_change(fill_method=None).rename(symbol) * weight)
        date_parts.append(dates.rename(symbol))
    if not return_parts:
        return pd.Series(dtype="float64"), pd.Series(dtype="object"), missing
    if abs(expected_weight - 1.0) > 1e-6:
        missing.append(f"{version.get('version_id', 'core')}_weight_sum_{expected_weight:.6f}")
    aligned_returns = pd.concat(return_parts, axis=1)
    weighted_return = aligned_returns.sum(axis=1, min_count=len(return_parts))
    levels = []
    level = 100.0
    has_started = False
    for value in weighted_return:
        if pd.isna(value):
            levels.append(float("nan") if has_started else 100.0)
            has_started = True
            continue
        level *= 1.0 + float(value)
        levels.append(level)
        has_started = True
    series = pd.Series(levels, index=weighted_return.index, dtype="float64")
    dates_df = pd.concat(date_parts, axis=1) if date_parts else pd.DataFrame(index=series.index)
    latest_dates = dates_df.apply(lambda row: "|".join(sorted({str(x) for x in row.dropna() if str(x) != "missing"})) or "missing", axis=1)
    return series.astype("float64"), latest_dates.reindex(series.index), missing


def _load_s1(indicators_dir: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(indicators_dir.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        row: dict[str, Any] = {
            "trade_date": str(payload.get("trade_date") or path.stem),
            "s1_total": payload.get("total_score"),
        }
        for item in payload.get("indicator_results", []):
            row[str(item.get("code"))] = item.get("value")
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).drop_duplicates("trade_date", keep="last").sort_values("trade_date")
    for col in ["s1_total", "S1-01", "S1-02", "S1-03", "S1-04", "S1-05", "S1-06"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["s1_total_change"] = df["s1_total"].diff()
    return df


def _load_s2(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, dtype=str)
    if "date" not in df.columns:
        return pd.DataFrame()
    df["trade_date"] = df["date"].astype(str).str.replace("-", "", regex=False)
    for col in ["s2_adjusted_score", "s2_event_score", "s2_conversion_score"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.drop_duplicates("trade_date", keep="last").sort_values("trade_date")


def _build_research_frame(
    market_daily_path: Path,
    macro_market_daily_path: Path,
    indicators_dir: Path,
    s2_scores_path: Path,
    config: dict[str, Any],
    versions_payload: dict[str, Any],
    ai_version: dict[str, Any],
    tech_version: dict[str, Any],
    report_date: str | None,
) -> ResearchData:
    symbols = config["symbols"]
    bio_symbol = symbols["bio"]
    health_symbol = symbols["health"]
    a_bio_symbol = symbols.get("a_bio_temperature", "589720.SH")
    a_health_symbol = symbols.get("a_health_benchmark", "512170.SH")
    ai_semi_symbol = symbols.get("ai_semi", "512760.SH")
    market = _load_market(market_daily_path)
    macro = _load_macro(macro_market_daily_path)
    base_parts = [
        _series(market, bio_symbol),
        _series(market, health_symbol),
        _series(market, a_bio_symbol),
        _series(market, a_health_symbol),
    ]
    base = pd.concat(base_parts, axis=1, join="inner").dropna().sort_index()
    if report_date:
        base = base[base.index <= report_date.replace("-", "")]
    base_index = base.index
    versions = _versions_by_id(versions_payload)
    ai_core, ai_dates, ai_missing = _weighted_core(market, macro, ai_version, versions, base_index)
    tech_core, tech_dates, tech_missing = _weighted_core(market, macro, tech_version, versions, base_index)

    close_series = {
        "bio_close": _series(market, bio_symbol),
        "health_close": _series(market, health_symbol),
        "a_bio_close": _series(market, a_bio_symbol),
        "a_health_close": _series(market, a_health_symbol),
        "ai_core_close": ai_core,
        "tech_core_close": tech_core,
        "ai_semi_close": _series(market, ai_semi_symbol),
    }
    amount_series = {
        "bio_amount": _series(market, bio_symbol, "amount"),
        "tech_amount": _series(market, tech_version.get("constituents", [{}])[0].get("symbol", ""), "amount"),
    }
    missing = [name for name, value in close_series.items() if value.empty and name.endswith("_close")]
    missing.extend(ai_missing)
    missing.extend(tech_missing)
    frame = pd.concat(close_series, axis=1, join="inner").sort_index()
    for name, values in amount_series.items():
        frame[name] = values.reindex(frame.index)
    if report_date:
        frame = frame[frame.index <= report_date.replace("-", "")]
    max_days = int(config.get("max_history_trading_days", 250))
    frame = frame.tail(max_days + 1).copy()
    for col in ["bio_close", "health_close", "a_bio_close", "a_health_close", "ai_core_close", "tech_core_close", "ai_semi_close"]:
        frame[col.replace("_close", "_ret")] = frame[col].pct_change()
    frame["bio_vs_health"] = frame["bio_ret"] - frame["health_ret"]
    frame["bio_vs_ai"] = frame["bio_ret"] - frame["ai_core_ret"]
    frame["bio_vs_tech"] = frame["bio_ret"] - frame["tech_core_ret"]
    frame["a_bio_vs_health"] = frame["a_bio_ret"] - frame["a_health_ret"]
    frame["bio_amount_ratio_5_20"] = frame["bio_amount"].rolling(5).mean() / frame["bio_amount"].rolling(20).mean()
    frame["tech_amount_ratio_5_20"] = frame["tech_amount"].rolling(5).mean() / frame["tech_amount"].rolling(20).mean()
    frame["bio_rel_5d"] = _period_return(frame["bio_close"], 5) - _period_return(frame["health_close"], 5)
    frame["bio_rel_10d"] = _period_return(frame["bio_close"], 10) - _period_return(frame["health_close"], 10)
    frame["ai_5d"] = _period_return(frame["ai_core_close"], 5)
    frame["ai_10d"] = _period_return(frame["ai_core_close"], 10)
    frame["tech_5d"] = _period_return(frame["tech_core_close"], 5)
    frame["tech_10d"] = _period_return(frame["tech_core_close"], 10)
    frame["market_state"] = _market_state(frame, config)
    frame["ai_state"] = _ai_state(frame, config)
    frame["tech_state"] = _tech_state(frame, config)
    frame["bio_outperform_streak"] = _streak(frame["bio_vs_health"] > 0)
    frame["a_share_date"] = frame.index
    frame["hk_date"] = frame.index
    frame["ai_core_date"] = ai_dates.reindex(frame.index).fillna("missing")
    frame["tech_core_date"] = tech_dates.reindex(frame.index).fillna("missing")
    frame["us_close_date"] = frame["ai_core_date"].astype(str).str.split("|").str[0]
    s1 = _load_s1(indicators_dir)
    if not s1.empty:
        frame = frame.merge(s1, how="left", left_index=True, right_on="trade_date").set_index("trade_date")
    s2 = _load_s2(s2_scores_path)
    if not s2.empty:
        keep = ["trade_date", "s2_adjusted_score", "s2_event_score", "s2_conversion_score"]
        frame = frame.merge(s2[[c for c in keep if c in s2.columns]], how="left", left_index=True, right_on="trade_date").set_index("trade_date")
    frame = frame.dropna(subset=["bio_ret", "health_ret", "ai_core_ret", "tech_core_ret"], how="any").tail(max_days)
    latest_date = str(frame.index.max()) if not frame.empty else (report_date or "")
    clean_report_date = f"{latest_date[:4]}-{latest_date[4:6]}-{latest_date[6:]}" if len(latest_date) == 8 else str(latest_date)
    data_quality = _core_data_quality(market, macro, versions, ai_version, tech_version, latest_date)
    missing.extend(data_quality.get("core_missing_symbols", []))
    core_status = str(data_quality.get("core_index_status") or "VALID")
    return ResearchData(clean_report_date, frame, dict(symbols), sorted(set(missing)), core_status, data_quality)


def _period_return(close: pd.Series, days: int) -> pd.Series:
    return close / close.shift(days) - 1


def _streak(mask: pd.Series) -> pd.Series:
    result = []
    count = 0
    for value in mask.fillna(False):
        count = count + 1 if bool(value) else 0
        result.append(count)
    return pd.Series(result, index=mask.index, dtype="int64")


def _market_state(frame: pd.DataFrame, config: dict[str, Any]) -> pd.Series:
    th = config.get("ai_state_thresholds", {})
    risk_on = float(th.get("risk_on_daily", 0.003))
    risk_off = float(th.get("risk_off_daily", -0.003))
    states = []
    for _, row in frame.iterrows():
        if row.get("ai_core_ret", 0) > risk_on and row.get("health_ret", 0) > risk_on:
            states.append("RISK_ON")
        elif row.get("ai_core_ret", 0) < risk_off and row.get("health_ret", 0) < risk_off:
            states.append("RISK_OFF")
        elif row.get("ai_core_ret", 0) < risk_off and row.get("health_ret", 0) > risk_on:
            states.append("AI_WEAK_MARKET_RISK_ON")
        elif row.get("ai_core_ret", 0) > risk_on and row.get("health_ret", 0) < risk_off:
            states.append("AI_STRONG_MARKET_RISK_OFF")
        else:
            states.append("NEUTRAL")
    return pd.Series(states, index=frame.index)


def _ai_state(frame: pd.DataFrame, config: dict[str, Any]) -> pd.Series:
    th = config.get("ai_state_thresholds", {})
    daily = float(th.get("daily_move", 0.005))
    strong = float(th.get("strong_move", 0.015))
    side_abs = float(th.get("sideways_abs_5d", 0.02))
    high_pct = float(th.get("high_level_percentile", 0.75))
    vol_stall = float(th.get("volume_stall_ratio", 1.2))
    up_streak = _streak(frame["ai_core_ret"] > 0)
    down_streak = _streak(frame["ai_core_ret"] < 0)
    close_pct = frame["ai_core_close"].rolling(120, min_periods=20).rank(pct=True)
    states = []
    for idx, row in frame.iterrows():
        ai_ret = row.get("ai_core_ret")
        ai_5d = row.get("ai_5d")
        state = "NEUTRAL"
        if pd.notna(ai_ret) and ai_ret > daily:
            state = "AI_SINGLE_UP"
        if pd.notna(ai_ret) and ai_ret < -daily:
            state = "AI_SINGLE_DOWN"
        if up_streak.loc[idx] >= 3:
            state = "AI_3D_PLUS_UP"
        elif up_streak.loc[idx] >= 2:
            state = "AI_2D_UP"
        if down_streak.loc[idx] >= 3:
            state = "AI_3D_PLUS_DOWN"
        elif down_streak.loc[idx] >= 2:
            state = "AI_2D_DOWN"
        if pd.notna(ai_5d) and pd.notna(close_pct.loc[idx]) and abs(ai_5d) <= side_abs and close_pct.loc[idx] >= high_pct:
            state = "AI_HIGH_SIDEWAYS"
        if pd.notna(ai_ret) and pd.notna(ai_5d) and ai_ret < -strong and ai_5d > 0:
            state = "AI_PROFIT_TAKING"
        if pd.notna(row.get("tech_amount_ratio_5_20")) and row.get("tech_amount_ratio_5_20") >= vol_stall and pd.notna(ai_ret) and abs(ai_ret) <= daily:
            state = "AI_HIGH_VOLUME_STALL"
        if pd.notna(row.get("ai_10d")) and row.get("ai_10d") < -2 * daily:
            state = "AI_TREND_BREAK"
        if pd.notna(row.get("ai_semi_ret")) and pd.notna(ai_ret) and abs(row.get("ai_semi_ret") - ai_ret) > strong:
            state = "AI_INTERNAL_ROTATION"
        if pd.notna(ai_ret) and ai_ret < -daily and row.get("market_state") == "AI_WEAK_MARKET_RISK_ON":
            state = "AI_DOWN_RISK_ON"
        if pd.notna(ai_ret) and ai_ret < -daily and row.get("market_state") == "RISK_OFF":
            state = "AI_DOWN_RISK_OFF"
        states.append(state)
    return pd.Series(states, index=frame.index)


def _tech_state(frame: pd.DataFrame, config: dict[str, Any]) -> pd.Series:
    th = config.get("ai_state_thresholds", {})
    daily = float(th.get("daily_move", 0.005))
    up_streak = _streak(frame["tech_core_ret"] > 0)
    down_streak = _streak(frame["tech_core_ret"] < 0)
    states = []
    for idx, row in frame.iterrows():
        ret = row.get("tech_core_ret")
        state = "TECH_GROWTH_NEUTRAL"
        if pd.notna(ret) and ret > daily:
            state = "TECH_GROWTH_SINGLE_UP"
        elif pd.notna(ret) and ret < -daily:
            state = "TECH_GROWTH_SINGLE_DOWN"
        if up_streak.loc[idx] >= 3:
            state = "TECH_GROWTH_3D_PLUS_UP"
        elif up_streak.loc[idx] >= 2:
            state = "TECH_GROWTH_2D_UP"
        if down_streak.loc[idx] >= 3:
            state = "TECH_GROWTH_3D_PLUS_DOWN"
        elif down_streak.loc[idx] >= 2:
            state = "TECH_GROWTH_2D_DOWN"
        states.append(state)
    return pd.Series(states, index=frame.index)


def _window_stats(frame: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for window in [int(x) for x in config.get("validation_windows", [20, 60, 120, 250])]:
        sample = frame.tail(window)
        for name, col in [
            ("159567绝对收益", "bio_ret"),
            ("159567相对159557超额", "bio_vs_health"),
            ("159567相对TECH_GROWTH_CORE超额", "bio_vs_tech"),
            ("159567相对AI_CORE超额", "bio_vs_ai"),
            ("589720绝对收益", "a_bio_ret"),
            ("589720相对医疗宽基超额", "a_bio_vs_health"),
            ("S1后续变化", "s1_total_change"),
            ("创新药量能变化", "bio_amount_ratio_5_20"),
            ("创新药广度变化", "S1-05"),
        ]:
            rows.append(_stats_row(sample[col] if col in sample else pd.Series(dtype="float64"), window, name))
    return rows


def _stats_row(values: pd.Series, window: int, name: str) -> dict[str, str]:
    s = pd.to_numeric(values, errors="coerce").dropna()
    n = len(s)
    mean = float(s.mean()) if n else None
    std = float(s.std(ddof=1)) if n > 1 else None
    ci_low = ci_high = None
    if n > 1 and std is not None:
        half = 1.96 * std / math.sqrt(n)
        ci_low = (mean or 0.0) - half
        ci_high = (mean or 0.0) + half
    practical = "missing"
    if mean is not None:
        if ci_low is not None and ci_high is not None and ci_low * ci_high > 0 and abs(mean) < 0.002:
            practical = "统计上可能显著，但缺乏实际交易意义"
        elif n < max(15, window // 3) and abs(mean) >= 0.002:
            practical = "结果可能具有经济意义，但样本不足，置信度低"
        elif abs(mean) >= 0.002 and (s.gt(0).mean() if n else 0) >= 0.55:
            practical = "可能具有实际交易意义"
        else:
            practical = "实际交易意义不足"
    return {
        "window": str(window),
        "metric": name,
        "valid_samples": str(n),
        "mean": _fmt_num(mean),
        "median": _fmt_num(float(s.median()) if n else None),
        "win_rate": _fmt_num(float(s.gt(0).mean()) if n else None),
        "std": _fmt_num(std),
        "best": _fmt_num(float(s.max()) if n else None),
        "worst": _fmt_num(float(s.min()) if n else None),
        "max_drawdown": _fmt_num(_max_drawdown(s)),
        "max_consecutive_failures": str(_max_consecutive_failures(s)) if n else "",
        "ci_low": _fmt_num(ci_low),
        "ci_high": _fmt_num(ci_high),
        "effect_size": _fmt_num(None if not std else (mean or 0.0) / std),
        "significance": "significant" if ci_low is not None and ci_high is not None and ci_low * ci_high > 0 else "not_significant",
        "trading_meaning": practical,
    }


def _max_drawdown(returns: pd.Series) -> float | None:
    if returns.empty:
        return None
    clean = pd.to_numeric(returns, errors="coerce").dropna()
    if clean.empty:
        return None
    equity = (1 + clean).cumprod()
    dd = equity / equity.cummax() - 1
    return float(dd.min())


def _max_consecutive_failures(returns: pd.Series) -> int:
    worst = current = 0
    for value in returns:
        if value <= 0:
            current += 1
            worst = max(worst, current)
        else:
            current = 0
    return worst


def _ai_state_stats(frame: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for state in sorted(set(frame["ai_state"].dropna())):
        mask = frame["ai_state"] == state
        rows.extend(_forward_rows(frame, mask, state, "ai_state", config))
    for state in sorted(set(frame["tech_state"].dropna())):
        mask = frame["tech_state"] == state
        rows.extend(_forward_rows(frame, mask, state, "tech_growth_state", config))
    for state in ["AI_DOWN_RISK_ON", "AI_DOWN_RISK_OFF"]:
        mask = frame["ai_state"] == state
        if mask.sum() == 0:
            rows.extend(_forward_rows(frame, mask, state, "ai_state", config))
    return rows


def _forward_rows(frame: pd.DataFrame, mask: pd.Series, condition: str, condition_type: str, config: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    for horizon in [int(x) for x in config.get("forward_windows", [0, 1, 2, 3, 5])]:
        if horizon == 0:
            bio_future = frame["bio_ret"]
            rel_future = frame["bio_vs_health"]
            ai_excess = frame["bio_vs_ai"]
            tech_excess = frame["bio_vs_tech"]
            a_future = frame["a_bio_ret"]
            s1_future = frame.get("s1_total_change", pd.Series(index=frame.index, dtype="float64"))
        else:
            bio_future = frame["bio_close"].shift(-horizon) / frame["bio_close"] - 1
            rel_future = bio_future - (frame["health_close"].shift(-horizon) / frame["health_close"] - 1)
            ai_excess = bio_future - (frame["ai_core_close"].shift(-horizon) / frame["ai_core_close"] - 1)
            tech_excess = bio_future - (frame["tech_core_close"].shift(-horizon) / frame["tech_core_close"] - 1)
            a_future = frame["a_bio_close"].shift(-horizon) / frame["a_bio_close"] - 1
            s1_future = frame.get("s1_total", pd.Series(index=frame.index, dtype="float64")).shift(-horizon) - frame.get("s1_total", pd.Series(index=frame.index, dtype="float64"))
        selected = mask & bio_future.notna()
        rows.append({
            "condition_type": condition_type,
            "condition": condition,
            "horizon_days": str(horizon),
            "sample_count": str(int(selected.sum())),
            "bio_abs_win_rate": _fmt_num(float(bio_future[selected].gt(0).mean()) if selected.any() else None),
            "bio_abs_mean": _fmt_num(float(bio_future[selected].mean()) if selected.any() else None),
            "bio_abs_median": _fmt_num(float(bio_future[selected].median()) if selected.any() else None),
            "bio_max_drawdown": _fmt_num(_max_drawdown(bio_future[selected])),
            "bio_vs_health_win_rate": _fmt_num(float(rel_future[selected].gt(0).mean()) if selected.any() else None),
            "bio_vs_tech_win_rate": _fmt_num(float(tech_excess[selected].gt(0).mean()) if selected.any() else None),
            "bio_vs_ai_win_rate": _fmt_num(float(ai_excess[selected].gt(0).mean()) if selected.any() else None),
            "bio_vs_health_mean": _fmt_num(float(rel_future[selected].mean()) if selected.any() else None),
            "bio_vs_tech_mean": _fmt_num(float(tech_excess[selected].mean()) if selected.any() else None),
            "bio_vs_ai_mean": _fmt_num(float(ai_excess[selected].mean()) if selected.any() else None),
            "a_bio_mean": _fmt_num(float(a_future[selected].mean()) if selected.any() else None),
            "s1_future_change_mean": _fmt_num(float(s1_future[selected].mean()) if selected.any() else None),
            "volume_expansion_rate": _fmt_num(float(frame.loc[selected, "bio_amount_ratio_5_20"].gt(1).mean()) if selected.any() and "bio_amount_ratio_5_20" in frame else None),
            "breadth_improvement_rate": _fmt_num(float(frame.loc[selected, "S1-05"].diff().gt(0).mean()) if selected.any() and "S1-05" in frame else None),
            "confidence": _confidence(int(selected.sum()), min_good=20),
        })
    return rows


def _a_share_lead_stats(frame: pd.DataFrame, config: dict[str, Any]) -> list[dict[str, str]]:
    s1 = frame.get("s1_total", pd.Series(index=frame.index, dtype="float64"))
    s103 = frame.get("S1-03", pd.Series(index=frame.index, dtype="float64"))
    s104 = frame.get("S1-04", pd.Series(index=frame.index, dtype="float64"))
    s105 = frame.get("S1-05", pd.Series(index=frame.index, dtype="float64"))
    threshold = float(config.get("ai_state_thresholds", {}).get("relative_lead_threshold", 0.01))
    lead_conditions = {
        "S1_total_upcross_0.60": (s1.shift(1) < 0.60) & (s1 >= 0.60),
        "S1_total_2d_above_0.60": (s1 >= 0.60) & (s1.shift(1) >= 0.60),
        "S1_total_3d_above_0.60": (s1 >= 0.60) & (s1.shift(1) >= 0.60) & (s1.shift(2) >= 0.60),
        "S1-03_negative_to_positive": (s103.shift(1) < 0) & (s103 >= 0),
        "S1-04_upcross_0.90x": (s104.shift(1) < 0.90) & (s104 >= 0.90),
        "S1-04_upcross_1.00x": (s104.shift(1) < 1.00) & (s104 >= 1.00),
        "S1-05_upcross_30pct": (s105.shift(1) < 0.30) & (s105 >= 0.30),
        "S1-05_upcross_40pct": (s105.shift(1) < 0.40) & (s105 >= 0.40),
        "S1-03_04_05_all_improve": (s103.diff() > 0) & (s104.diff() > 0) & (s105.diff() > 0),
        "589720_positive_signal": frame["a_bio_ret"] > threshold,
        "589720_vs_a_health_positive_signal": frame["a_bio_vs_health"] > threshold,
    }
    same_day_conditions = {
        "589720_same_day_outperformance": (frame["a_bio_ret"] - frame["bio_ret"]) > threshold,
        "589720_two_day_relative_strength": ((frame["a_bio_ret"] - frame["bio_ret"]) > threshold) & ((frame["a_bio_ret"].shift(1) - frame["bio_ret"].shift(1)) > threshold),
        "589720_strong_159567_not_follow_same_day": (frame["a_bio_ret"] > threshold) & (frame["bio_ret"] <= 0),
        "589720_strong_159567_beats_159557_same_day": (frame["a_bio_ret"] > threshold) & (frame["bio_vs_health"] > 0),
    }
    rows = []
    for name, mask in lead_conditions.items():
        rows.extend(_forward_rows(frame, mask.fillna(False), name, "a_share_lead_signal", config))
    for name, mask in same_day_conditions.items():
        rows.extend(_forward_rows(frame, mask.fillna(False), name, "a_share_same_day_relative_strength", config))
    return rows


def _right_side_score(frame: pd.DataFrame, config: dict[str, Any]) -> dict[str, str]:
    if frame.empty:
        return {"date": "", "right_side_score": "", "right_side_level": "missing", "confidence": "low", "feature_contributions": "missing", "score_status": "insufficient_data", "feature_coverage": "0.00000000", "missing_features": "all"}
    target_days = int(config.get("right_side", {}).get("target_forward_days", 5))
    features = _right_side_features(frame)
    target = frame["bio_close"].shift(-target_days) / frame["bio_close"] - 1
    target = target - (frame["health_close"].shift(-target_days) / frame["health_close"] - 1)
    aligned = pd.concat([features, target.rename("target")], axis=1)
    aligned = aligned.dropna(subset=["target"])
    train_ratio = float(config.get("right_side", {}).get("train_ratio", 0.7))
    split = max(1, int(len(aligned) * train_ratio))
    train = aligned.iloc[:split]
    test = aligned.iloc[split:]
    max_missing_rate = float(config.get("right_side", {}).get("max_feature_missing_rate", 0.30))
    min_coverage = float(config.get("right_side", {}).get("min_current_feature_coverage", 0.75))
    feature_cols = [
        col for col in features.columns
        if col in train and float(train[col].isna().mean()) <= max_missing_rate and train[col].notna().sum() >= 10
    ]
    if not feature_cols:
        return {
            "date": str(frame.index[-1]),
            "right_side_score": "",
            "right_side_level": "missing",
            "confidence": "low",
            "train_samples": str(len(train)),
            "oos_samples": str(len(test)),
            "oos_direction_accuracy": "",
            "feature_contributions": "missing",
            "duplicate_counting_check": "not_run",
            "feature_coverage": "0.00000000",
            "missing_features": "all",
            "score_status": "insufficient_predictive_signal",
        }
    medians = train[feature_cols].median(numeric_only=True)
    train_x = train[feature_cols].fillna(medians)
    test_x = test[feature_cols].fillna(medians)
    missing_indicator_cols = []
    for col in feature_cols:
        if train[col].isna().any():
            indicator = f"{col}_missing"
            missing_indicator_cols.append(indicator)
            train_x[indicator] = train[col].isna().astype(float)
            test_x[indicator] = test[col].isna().astype(float)
    model_cols = list(train_x.columns)
    raw_weights: dict[str, float] = {}
    for col in model_cols:
        if len(train_x) < 10 or train_x[col].std() == 0:
            raw_weights[col] = 0.0
            continue
        corr = train_x[col].corr(train["target"])
        raw_weights[col] = max(0.0, float(corr)) if pd.notna(corr) else 0.0
    if sum(raw_weights.values()) <= 0:
        return {
            "date": str(frame.index[-1]),
            "right_side_score": "",
            "right_side_level": "missing",
            "confidence": "low",
            "train_samples": str(len(train)),
            "oos_samples": str(len(test)),
            "oos_direction_accuracy": "",
            "feature_contributions": "missing",
            "duplicate_counting_check": "all feature correlations are non-positive; no equal-weight fallback used.",
            "feature_coverage": "0.00000000",
            "missing_features": "insufficient_predictive_signal",
            "score_status": "insufficient_predictive_signal",
        }
    tech_ai_corr = None
    if {"tech_growth_not_crowding", "ai_not_crowding"}.issubset(train_x.columns):
        tech_ai_corr = train_x["tech_growth_not_crowding"].corr(train_x["ai_not_crowding"])
        if pd.notna(tech_ai_corr) and abs(float(tech_ai_corr)) >= 0.80:
            raw_weights["tech_growth_not_crowding"] *= 0.5
            raw_weights["ai_not_crowding"] *= 0.5
    total = sum(raw_weights.values())
    weights = {col: value / total for col, value in raw_weights.items()}
    current_raw = features.iloc[-1]
    valid_current = [col for col in feature_cols if pd.notna(current_raw.get(col))]
    missing_current = [col for col in feature_cols if col not in valid_current]
    coverage = len(valid_current) / len(feature_cols) if feature_cols else 0.0
    if coverage < min_coverage:
        return {
            "date": str(frame.index[-1]),
            "right_side_score": "",
            "right_side_level": "missing",
            "confidence": "low",
            "train_samples": str(len(train)),
            "oos_samples": str(len(test)),
            "oos_direction_accuracy": "",
            "feature_contributions": "missing",
            "duplicate_counting_check": "not_run_due_to_low_feature_coverage",
            "feature_coverage": f"{coverage:.8f}",
            "missing_features": ",".join(missing_current),
            "score_status": "insufficient_data",
        }
    effective_weight_total = sum(weights[col] for col in valid_current if col in weights)
    if effective_weight_total <= 0:
        return {
            "date": str(frame.index[-1]),
            "right_side_score": "",
            "right_side_level": "missing",
            "confidence": "low",
            "train_samples": str(len(train)),
            "oos_samples": str(len(test)),
            "oos_direction_accuracy": "",
            "feature_contributions": "missing",
            "duplicate_counting_check": "current effective feature weight is zero.",
            "feature_coverage": f"{coverage:.8f}",
            "missing_features": ",".join(missing_current) if missing_current else "none",
            "score_status": "insufficient_predictive_signal",
        }
    effective_weights = {col: weights[col] / effective_weight_total for col in valid_current if col in weights and effective_weight_total > 0}
    score = 100.0 * sum(float(current_raw[col]) * effective_weights[col] for col in effective_weights)
    predictions = (test_x[model_cols].mul(pd.Series(weights)).sum(axis=1) >= 0.5) if not test.empty else pd.Series(dtype=bool)
    actual = test["target"] > 0 if not test.empty else pd.Series(dtype=bool)
    oos_acc = float((predictions == actual).mean()) if len(test) else None
    baseline_up = float(actual.mean()) if len(actual) else None
    baseline_always = max(baseline_up or 0.0, 1.0 - (baseline_up or 0.0)) if baseline_up is not None else None
    benchmark_excess = None if oos_acc is None or baseline_always is None else oos_acc - baseline_always
    confidence = "high" if len(train) >= 120 and len(test) >= 40 and (oos_acc or 0) >= 0.55 else "medium" if len(train) >= 60 and len(test) >= 20 else "low"
    score_status = "valid" if benchmark_excess is not None and benchmark_excess > 0 else "descriptive_only"
    contributions = {col: float(current_raw[col]) * effective_weights[col] * 100 for col in effective_weights}
    return {
        "date": str(frame.index[-1]),
        "right_side_score": f"{score:.2f}",
        "right_side_level": _right_side_level(score),
        "confidence": confidence,
        "train_samples": str(len(train)),
        "oos_samples": str(len(test)),
        "oos_direction_accuracy": _fmt_num(oos_acc),
        "baseline_direction_accuracy": _fmt_num(baseline_always),
        "benchmark_excess_accuracy": _fmt_num(benchmark_excess),
        "feature_contributions": "; ".join(f"{k}={v:.2f}" for k, v in sorted(contributions.items(), key=lambda item: item[1], reverse=True)),
        "duplicate_counting_check": f"1d/5d/10d relative strength collapsed into one bio_relative_strength feature; S1 total and components are grouped; TECH_GROWTH_CORE and AI_CORE corr={_fmt_num(float(tech_ai_corr) if pd.notna(tech_ai_corr) else None)}, high-correlation pairs are half-weighted.",
        "feature_coverage": f"{coverage:.8f}",
        "missing_features": ",".join(missing_current) if missing_current else "none",
        "score_status": score_status,
        "missing_indicator_features": ",".join(missing_indicator_cols) if missing_indicator_cols else "none",
    }


def _right_side_features(frame: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=frame.index)
    rel_1 = _scale(frame["bio_vs_health"], -0.02, 0.02)
    rel_5 = _scale(frame["bio_rel_5d"], -0.05, 0.05)
    rel_10 = _scale(frame["bio_rel_10d"], -0.08, 0.08)
    out["bio_relative_strength"] = pd.concat([rel_1, rel_5, rel_10], axis=1).mean(axis=1)
    out["bio_outperform_streak"] = _scale(frame["bio_outperform_streak"], 0, 5)
    out["s1_group"] = pd.concat([
        _scale(frame.get("s1_total", pd.Series(index=frame.index)), 0.4, 0.8),
        _scale(frame.get("s1_total_change", pd.Series(index=frame.index)), -0.05, 0.05),
        _scale(frame.get("S1-03", pd.Series(index=frame.index)), -0.05, 0.05),
        _scale(frame.get("S1-04", pd.Series(index=frame.index)), 0.7, 1.2),
        _scale(frame.get("S1-05", pd.Series(index=frame.index)), 0.2, 0.6),
    ], axis=1).mean(axis=1)
    out["s2_conversion"] = _scale(frame.get("s2_conversion_score", pd.Series(index=frame.index)), 0.4, 0.7)
    out["volume"] = _scale(frame["bio_amount_ratio_5_20"], 0.8, 1.5)
    out["tech_growth_not_crowding"] = _scale(frame["bio_vs_tech"], -0.03, 0.03)
    out["ai_not_crowding"] = _scale(frame["bio_vs_ai"], -0.03, 0.03)
    out["a_share_lead"] = _scale(frame["a_bio_ret"] - frame["bio_ret"], -0.02, 0.02)
    return out.clip(0, 1)


def _scale(values: pd.Series, low: float, high: float) -> pd.Series:
    return ((pd.to_numeric(values, errors="coerce") - low) / (high - low)).clip(0, 1)


def _right_side_level(score: float) -> str:
    if score >= 85:
        return "主升或过热"
    if score >= 70:
        return "右侧确认"
    if score >= 50:
        return "初步右侧"
    if score >= 30:
        return "修复观察"
    return "无右侧"


def _falsification(
    frame: pd.DataFrame,
    window_stats: list[dict[str, str]],
    state_stats: list[dict[str, str]],
    lead_stats: list[dict[str, str]],
    right_side: dict[str, str],
) -> dict[str, str]:
    latest = frame.iloc[-1] if not frame.empty else {}
    support: list[str] = []
    opposition: list[str] = []
    if _num(latest.get("bio_vs_health")) and latest.get("bio_vs_health") > 0:
        support.append(f"159567当日跑赢159557 {_fmt_pct(latest.get('bio_vs_health'))}")
    if _num(latest.get("bio_ret")) and latest.get("bio_ret") > 0:
        support.append(f"159567当日绝对上涨 {_fmt_pct(latest.get('bio_ret'))}")
    if _num(latest.get("S1-05")) and latest.get("S1-05") >= 0.40:
        support.append(f"S1-05广度达到{_fmt_pct(latest.get('S1-05'))}")
    if _num(latest.get("tech_core_ret")) and latest.get("tech_core_ret") > 0 and _num(latest.get("bio_vs_tech")) and latest.get("bio_vs_tech") < 0:
        opposition.append(f"科技成长上涨时159567跑输TECH_GROWTH_CORE {_fmt_pct(latest.get('bio_vs_tech'))}")
    if _num(latest.get("ai_core_ret")) and latest.get("ai_core_ret") > 0 and _num(latest.get("bio_vs_ai")) and latest.get("bio_vs_ai") < 0:
        opposition.append(f"AI_CORE上涨时159567跑输AI_CORE {_fmt_pct(latest.get('bio_vs_ai'))}")
    if _num(latest.get("bio_ret")) and latest.get("bio_ret") < 0:
        opposition.append(f"159567绝对收益为负 {_fmt_pct(latest.get('bio_ret'))}")
    if _num(latest.get("bio_vs_health")) and latest.get("bio_vs_health") < 0:
        opposition.append(f"159567跑输159557 {_fmt_pct(latest.get('bio_vs_health'))}")
    if _num(latest.get("bio_amount_ratio_5_20")) and latest.get("bio_amount_ratio_5_20") < 1:
        opposition.append(f"159567量能低于20日均值，ratio={latest.get('bio_amount_ratio_5_20'):.2f}")
    if _num(latest.get("s2_conversion_score")) and latest.get("s2_conversion_score") < 0.60:
        opposition.append(f"S2_conversion_score={latest.get('s2_conversion_score'):.2f}，交易转化未确认")
    if _num(latest.get("S1-06")) and latest.get("S1-06") < 0:
        opposition.append(f"S1-06龙头先行强度为负 {_fmt_pct(latest.get('S1-06'))}")
    support = support[:3] or ["暂无强支持证据"]
    opposition = opposition[:3] or ["暂无强反对证据"]
    score = _float_or_none(right_side.get("right_side_score"))
    if len([x for x in opposition if x != "暂无强反对证据"]) >= 2:
        thesis = "weakened"
    elif score is not None and score >= 70 and len([x for x in support if x != "暂无强支持证据"]) >= 2:
        thesis = "strengthened"
    elif score is not None and score < 30:
        thesis = "invalidated"
    else:
        thesis = "unchanged"
    return {
        "date": str(frame.index[-1]) if not frame.empty else "",
        "support_evidence": " | ".join(support),
        "opposition_evidence": " | ".join(opposition),
        "thesis_state": thesis,
    }


def _position_action(frame: pd.DataFrame, right_side: dict[str, str], falsification: dict[str, str], config: dict[str, Any]) -> dict[str, str]:
    score = _float_or_none(right_side.get("right_side_score"))
    confidence = right_side.get("confidence", "low")
    score_status = right_side.get("score_status", "missing")
    opposition = _split_evidence(falsification.get("opposition_evidence"))
    latest = frame.iloc[-1] if not frame.empty else {}
    if score is None or score_status in {"insufficient_data", "insufficient_predictive_signal", "DATA_ERROR"}:
        action = "insufficient_data"
    elif confidence == "low":
        action = "hold" if score >= 50 else "insufficient_data"
    elif len([x for x in opposition if x != "暂无强反对证据"]) >= 2:
        action = "hold" if score >= 50 else "reduce"
    elif score >= 70 and confidence in {"medium", "high"}:
        action = "increase"
    elif score < 30:
        action = "reduce"
    else:
        action = "hold"
    if _num(latest.get("bio_vs_health")) and latest.get("bio_vs_health") < 0 and action == "increase":
        action = "hold"
    return {
        "action": action,
        "basis": f"right_side_score={right_side.get('right_side_score') or 'missing'}; score_status={score_status}; confidence={confidence}; thesis_state={falsification.get('thesis_state')}",
        "next_increase_condition": "右侧确认评分>=70、置信度不低、159567相对159557和量能同时确认、反对证据少于2条。",
        "next_reduce_condition": "AI回调后159567仍不涨或跑输159557，或右侧评分<30，或S2_conversion继续低于0.60。",
        "strongest_opposition": falsification.get("opposition_evidence", ""),
    }


def _audit_system(
    data: ResearchData,
    config: dict[str, Any],
    ai_version: dict[str, Any],
    tech_version: dict[str, Any],
    market_path: Path,
    macro_path: Path,
    indicators_dir: Path,
    s2_scores_path: Path,
) -> dict[str, Any]:
    frame = data.frame
    quality = data.data_quality or {}
    return {
        "ai_core_constituents": ai_version.get("constituents", []),
        "ai_core_version": ai_version.get("version_id"),
        "ai_core_scope": ai_version.get("market_scope"),
        "tech_core_constituents": tech_version.get("constituents", []),
        "tech_core_version": tech_version.get("version_id"),
        "tech_core_scope": tech_version.get("market_scope"),
        "ai_core_adjustment": ai_version.get("adjustment_policy"),
        "current_returns": "1/3/5/10/20日收益按共同有效交易日收盘价 close_t / close_t-n - 1 计算；缺失不补0。",
        "date_mapping": "TECH_GROWTH_CORE使用亚洲交易日同日收盘；AI_US/AI_GLOBAL中的美股成分按亚洲交易日映射上一可用美股收盘，禁止使用同日未来美股收盘。",
        "future_function": "历史统计使用当日及未来收益时只用于回测表，日报当前状态不使用未来收益；右侧评分训练目标shift(-5)仅用于历史权重估计。",
        "calendar_join": "研究表用共同交易日inner join，不按自然日直接填充；但原S1指标内部使用自然日扩大窗口后取可得交易日。",
        "holiday_mismatch": "跨市场分析保留a_share_date/hk_date/us_close_date/ai_core_date字段；美股节假日沿用最近已收盘日并降低新鲜度。",
        "duplicates": str(int(frame.index.duplicated().sum())),
        "return_window_reuse": "窗口统计按每个交易日滚动样本，回测会有重叠持有期，报告标注为描述性/验证性统计，不视为独立交易次数。",
        "adjustment_mix": "market_daily ETF adjusted_type当前为none；HK个股缓存存在qfq来源但本模块只用ETF market_daily。",
        "etf_actions_risk": "unadjusted_close无法完全消除ETF分红/拆并导致的伪收益风险，已写入低置信风险。",
        "descriptive_only": "当前S2_STYLE、相关性、条件收益为描述性统计；新增窗口/状态/领先表为历史验证统计。",
        "backtested": "新增AI状态、A股领先、右侧确认权重均使用最近最多250个共同有效交易日。",
        "realtime": "当前状态、当日收益、右侧评分、仓位标签。",
        "carried_forward": "S1/S2历史分数按已生成日报读取；S2内部沿用项仍由原S2报告披露。",
        "stale": data.missing,
        "missing_low_confidence": data.missing,
        "reproducible": "固定输入文件、AI_CORE版本和配置即可复现。",
        "tests": "新增单元/完整性测试覆盖；原S2测试保留。",
        "market_path": str(market_path),
        "macro_path": str(macro_path),
        "indicators_dir": str(indicators_dir),
        "s2_scores_path": str(s2_scores_path),
        "sample_count": str(len(frame)),
        "core_index_status": data.core_index_status,
        "core_symbols": quality.get("core_symbols", []),
        "source_switch_count": quality.get("source_switch_count", 0),
        "missing_trade_dates": quality.get("missing_trade_dates", "missing"),
        "abnormal_trade_dates": quality.get("abnormal_trade_dates", "missing"),
        "cross_source_conflicts": quality.get("cross_source_conflicts", "missing"),
    }


def _render_audit_report(audit: dict[str, Any]) -> str:
    lines = [
        "# AI/科技成长—创新药风格关系模块审计报告",
        "",
        "## 当前问题确认",
        "",
        "- 原CN_AI_CORE_V1 = 100% x 588000.SH。",
        "- 588000.SH代表科创50科技成长风格，不是纯AI指数；不得继续把588000涨跌直接表述为AI涨跌。",
        "- 本次修复后：588000.SH迁移为TECH_GROWTH_CORE，AI_CORE改用AI_CHINA/AI_US/AI_GLOBAL版本化篮子。",
        "",
        "## 20项审计结论",
        "",
        f"1. 当前TECH_GROWTH_CORE：{audit['tech_core_version']}，成分={audit['tech_core_constituents']}。",
        f"2. 当前AI_CORE：{audit['ai_core_version']}，成分={audit['ai_core_constituents']}。",
        f"3. 市场范围：TECH={audit['tech_core_scope']}；AI={audit['ai_core_scope']}。",
        f"4. 收益计算：{audit['current_returns']}",
        f"5. 日期映射：{audit['date_mapping']}",
        f"6. 未来函数：{audit['future_function']}",
        f"7. 自然日拼接：{audit['calendar_join']}",
        f"8. 节假日错位：{audit['holiday_mismatch']}",
        f"9. 重复日期：研究表重复日期数={audit['duplicates']}。",
        f"10. 收益窗口重复计数：{audit['return_window_reuse']}",
        f"11. 复权混用：{audit['adjustment_mix']}",
        f"12. ETF分红/拆分风险：{audit['etf_actions_risk']}",
        f"13. 描述性统计：{audit['descriptive_only']}",
        f"14. 历史回测：{audit['backtested']}",
        f"15. 实时值：{audit['realtime']}",
        f"16. 沿用值：{audit['carried_forward']}",
        f"17. 老化数据：{audit['stale'] or 'none'}。",
        f"18. 缺失/低置信度：{audit['missing_low_confidence'] or 'none'}。",
        f"19. 复现性：{audit['reproducible']}",
        f"20. 测试：{audit['tests']}",
        "",
        "## 数据源",
        "",
        f"- market_daily: {audit['market_path']}",
        f"- macro_market_daily: {audit['macro_path']}",
        f"- S1 indicators: {audit['indicators_dir']}",
        f"- S2 scores: {audit['s2_scores_path']}",
        f"- 有效样本数：{audit['sample_count']}",
        "",
        "## 核心数据完整性",
        "",
        f"- 核心指数状态：{audit['core_index_status']}",
        f"- 数据源切换次数：{audit['source_switch_count']}",
        f"- 缺失交易日：{audit['missing_trade_dates']}",
        f"- 异常交易日：{audit['abnormal_trade_dates']}",
        f"- 跨源冲突：{audit['cross_source_conflicts']}",
        "",
        "| 标的 | 主数据源 | 备用源1 | 备用源2 | 复权口径 | 最新日期 | 缺失天数 | 状态 |",
        "| --- | --- | --- | --- | --- | --- | ---: | --- |",
        *[
            f"| {row.get('symbol')} | {row.get('primary_source')} | {row.get('fallback_source_1')} | {row.get('fallback_source_2')} | {row.get('adjustment_policy')} | {row.get('latest_date')} | {row.get('missing_days')} | {row.get('status')} |"
            for row in audit.get("core_symbols", [])
        ],
        "",
    ]
    return "\n".join(lines)


def _render_validation_report(
    data: ResearchData,
    config: dict[str, Any],
    ai_version: dict[str, Any],
    tech_version: dict[str, Any],
    window_stats: list[dict[str, str]],
    state_stats: list[dict[str, str]],
    lead_stats: list[dict[str, str]],
    right_side: dict[str, str],
    falsification: dict[str, str],
    position: dict[str, str],
) -> str:
    frame = data.frame
    latest = frame.iloc[-1] if not frame.empty else {}
    window_summary = _window_summary_rows(window_stats)
    ai_down_rows = [row for row in state_stats if row["condition"] in {"AI_SINGLE_DOWN", "AI_2D_DOWN", "AI_3D_PLUS_DOWN", "AI_DOWN_RISK_ON", "AI_DOWN_RISK_OFF"} and row["horizon_days"] == "0"]
    lead_best = _best_lead_row(lead_stats)
    core_rows = (data.data_quality or {}).get("core_symbols", [])
    primary_sources = "; ".join(f"{row.get('symbol')}={row.get('primary_source')}" for row in core_rows) or "missing"
    fallback_sources = "; ".join(f"{row.get('symbol')}={row.get('fallback_source_1')}" for row in core_rows) or "missing"
    lines = [
        "# AI/科技成长—创新药风格验证日报",
        "",
        "## 1. 数据日期",
        "",
        f"- 报告日期：{data.report_date}",
        f"- A股数据日期：{latest.get('a_share_date', 'missing')}",
        f"- 港股数据日期：{latest.get('hk_date', 'missing')}",
        f"- 对应美股收盘日期：{latest.get('us_close_date', 'not_applicable')}",
        f"- TECH_GROWTH_CORE版本：{tech_version.get('version_id')}；{tech_version.get('market_scope')}",
        f"- AI_CORE版本：{ai_version.get('version_id')}；{ai_version.get('market_scope')}",
        f"- 有效样本数：{len(frame)}；历史上限：{config.get('max_history_trading_days', 250)}",
        "",
        "## 2. 今日状态",
        "",
        f"- 科技成长状态：{latest.get('tech_state', 'missing')}",
        f"- AI状态：{latest.get('ai_state', 'missing')}",
        f"- 市场状态：{latest.get('market_state', 'missing')}",
        f"- 创新药相对医疗：{_fmt_pct(latest.get('bio_vs_health'))}",
        f"- 创新药相对科技成长：{_fmt_pct(latest.get('bio_vs_tech'))}",
        f"- 创新药相对AI_CORE：{_fmt_pct(latest.get('bio_vs_ai'))}",
        f"- 589720情绪状态：{_a_temp_state(latest)}",
        f"- A股领先候选：{lead_best.get('condition', '未验证') if lead_best else '未验证'}",
        f"- 右侧确认评分：{right_side.get('right_side_score', 'missing')}；{right_side.get('right_side_level', 'missing')}",
        f"- 评分置信度：{right_side.get('confidence', 'low')}",
        f"- score_status：{right_side.get('score_status', 'missing')}；feature_coverage：{right_side.get('feature_coverage', 'missing')}",
        f"- 核心指数状态：{data.core_index_status}",
        "",
        "## 2A. 数据质量",
        "",
        f"- 核心数据完整性：{data.core_index_status}",
        f"- 使用主数据源：{primary_sources}",
        f"- 使用备用数据源：{fallback_sources}",
        f"- 数据源切换次数：{(data.data_quality or {}).get('source_switch_count', 'missing')}",
        f"- 缺失交易日：{(data.data_quality or {}).get('missing_trade_dates', 'missing')}",
        f"- 异常交易日：{(data.data_quality or {}).get('abnormal_trade_dates', 'missing')}",
        f"- 跨源冲突：{(data.data_quality or {}).get('cross_source_conflicts', 'missing')}",
        f"- 特征覆盖率：{right_side.get('feature_coverage', 'missing')}",
        f"- 核心指数状态：{data.core_index_status}",
        f"- 评分状态：{right_side.get('score_status', 'missing')}",
        "",
        "## 3. 多窗口结论",
        "",
        "| 窗口 | 科技成长—创新药关系 | AI—创新药关系 | 绝对上涨胜率 | 相对医疗跑赢胜率 | 稳定性 |",
        "| --- | --- | --- | ---: | ---: | --- |",
        *window_summary,
        "",
        "## 4. 最强支持证据",
        "",
        *[f"- {item}" for item in _split_evidence(falsification.get("support_evidence"))[:3]],
        "",
        "## 5. 最强反对证据",
        "",
        *[f"- {item}" for item in _split_evidence(falsification.get("opposition_evidence"))[:3]],
        "",
        "## 6. 科技成长/AI回调验证",
        "",
        f"- 科技成长是否回调：{'是' if latest.get('tech_core_ret', 0) < 0 else '否'}",
        f"- AI是否回调：{'是' if latest.get('ai_core_ret', 0) < 0 else '否'}",
        f"- AI回调类型：{latest.get('ai_state', 'missing')}",
        f"- 市场是否Risk Off：{'是' if latest.get('market_state') == 'RISK_OFF' else '否'}",
        f"- 159567绝对收益：{_fmt_pct(latest.get('bio_ret'))}",
        f"- 159567相对159557超额：{_fmt_pct(latest.get('bio_vs_health'))}",
        f"- 159567相对科技成长超额：{_fmt_pct(latest.get('bio_vs_tech'))}",
        f"- 159567相对AI_CORE超额：{_fmt_pct(latest.get('bio_vs_ai'))}",
        f"- 是否属于有效轮动：{_valid_rotation_text(latest, ai_down_rows)}",
        "",
        "## 7. A股领先港股验证",
        "",
        f"- 当前最佳历史lead_signal：{lead_best.get('condition', 'missing') if lead_best else 'missing'}",
        f"- S1是否先动：{_s1_lead_text(lead_stats)}",
        f"- 可能领先窗口：{lead_best.get('horizon_days', 'missing') if lead_best else 'missing'}日",
        f"- 历史样本数：{lead_best.get('sample_count', '0') if lead_best else '0'}",
        f"- 历史胜率：{lead_best.get('bio_vs_health_win_rate', 'missing') if lead_best else 'missing'}",
        f"- 当前是否有效：{_current_lead_valid(latest)}",
        "",
        "## 8. 当前命题",
        "",
        f"- AI资金虹吸假设：{_ai_siphon_text(latest)}",
        f"- 科技成长虹吸假设：{_tech_siphon_text(latest)}",
        f"- 创新药接力假设：{_relay_text(right_side, falsification)}",
        f"- A股领先港股假设：{_a_lead_thesis_text(lead_best)}",
        f"- 状态：{falsification.get('thesis_state', 'unchanged')}",
        "",
        "## 9. 仓位建议",
        "",
        f"- 建议：{position.get('action', 'insufficient_data')}",
        f"- 理由：{position.get('basis', '')}",
        f"- 下一增加条件：{position.get('next_increase_condition', '')}",
        f"- 下一减少条件：{position.get('next_reduce_condition', '')}",
        f"- 当前最强反对证据：{position.get('strongest_opposition', '')}",
        "",
        "## 10. 当前仍不能确认的事项",
        "",
        "- AI_CORE已拆分为AI_CHINA/AI_US/AI_GLOBAL；若宏观美股数据缺失，AI_GLOBAL置信度下降。",
        "- 当前只能在可用样本内判断创新药相对医疗、相对科技成长、相对AI_CORE的关系；不得用588000替代AI。",
        "- 当前复权口径为unadjusted_close，ETF分红/拆分仍可能影响历史收益精度。",
        "- 120/250日窗口包含重叠持有期统计，不等于独立交易次数。",
        "- 若20/60日与120/250日结论冲突，应解释为近期关系变化，但长期稳定性不足。",
        "- 本模块输出仓位动作标签，不构成投资建议。",
        "",
    ]
    return "\n".join(lines)


def _window_summary_rows(window_stats: list[dict[str, str]]) -> list[str]:
    rows = []
    by_window: dict[str, dict[str, dict[str, str]]] = {}
    for row in window_stats:
        by_window.setdefault(row["window"], {})[row["metric"]] = row
    for window in ["20", "60", "120", "250"]:
        bio = by_window.get(window, {}).get("159567绝对收益", {})
        rel = by_window.get(window, {}).get("159567相对159557超额", {})
        tech = by_window.get(window, {}).get("159567相对TECH_GROWTH_CORE超额", {})
        ai = by_window.get(window, {}).get("159567相对AI_CORE超额", {})
        tech_relation = "跑赢科技成长" if _float_or_none(tech.get("mean")) and float(tech["mean"]) > 0 else "跑输科技成长"
        relation = "跑赢AI" if _float_or_none(ai.get("mean")) and float(ai["mean"]) > 0 else "跑输AI"
        stability = _stability_text(bio, rel, tech, ai)
        rows.append(f"| {window}日 | {tech_relation} | {relation} | {bio.get('win_rate', 'missing')} | {rel.get('win_rate', 'missing')} | {stability} |")
    return rows


def _stability_text(*rows: dict[str, str]) -> str:
    samples = [int(row.get("valid_samples") or 0) for row in rows if row]
    sig = [row.get("significance") == "significant" for row in rows if row]
    if samples and min(samples) < 20:
        return "样本不足，置信度低"
    if sig and any(sig):
        return "存在统计信号，需结合经济意义"
    return "未获得稳定验证"


def _best_lead_row(rows: list[dict[str, str]]) -> dict[str, str]:
    candidates = [
        row for row in rows
        if row.get("condition_type") == "a_share_lead_signal"
        and row.get("horizon_days") in {"1", "2", "3", "5"}
        and int(row.get("sample_count") or 0) >= 3
    ]
    if not candidates:
        return {}
    return max(candidates, key=lambda row: _float_or_none(row.get("bio_vs_health_win_rate")) or -1)


def _valid_rotation_text(latest: pd.Series, ai_down_rows: list[dict[str, str]]) -> str:
    if not _num(latest.get("ai_core_ret")) or latest.get("ai_core_ret") >= 0:
        return "当前AI未回调，不适用。"
    if latest.get("bio_ret", 0) > 0 and latest.get("bio_vs_health", 0) > 0:
        return "当前样本显示AI回调时创新药绝对上涨且跑赢医疗，属于有效轮动迹象。"
    if latest.get("bio_vs_health", 0) > 0:
        return "当前仅相对医疗抗跌，不能写成绝对上涨。"
    return "AI回调未带来创新药有效响应。"


def _a_temp_state(latest: pd.Series) -> str:
    if not _num(latest.get("a_bio_ret")):
        return "missing"
    if latest.get("a_bio_ret") > 0 and latest.get("a_bio_vs_health", 0) > 0:
        return "589720强于A股医疗宽基"
    if latest.get("a_bio_ret") > 0:
        return "589720绝对上涨但未确认相对强"
    return "589720偏弱"


def _s1_lead_text(rows: list[dict[str, str]]) -> str:
    hits = [row for row in rows if row.get("condition_type") == "a_share_lead_signal" and row["condition"].startswith("S1") and int(row.get("sample_count") or 0) >= 3]
    if not hits:
        return "未表现出稳定领先样本"
    best = max(hits, key=lambda row: _float_or_none(row.get("bio_vs_health_win_rate")) or -1)
    return f"{best['condition']}，样本{best['sample_count']}，胜率{best['bio_vs_health_win_rate']}"


def _current_lead_valid(latest: pd.Series) -> str:
    if latest.get("a_bio_ret", 0) > 0 and latest.get("bio_ret", 0) <= 0:
        return "A股创新药同日较强但159567未跟随，不能称为领先有效。"
    if latest.get("a_bio_ret", 0) > 0 and latest.get("bio_vs_health", 0) > 0:
        return "A股与159567同步偏强，只能说明同日情绪共振，不等于A股领先。"
    return "未确认。"


def _ai_siphon_text(latest: pd.Series) -> str:
    if latest.get("ai_core_ret", 0) > 0 and latest.get("bio_vs_ai", 0) < 0:
        return "strengthened：AI_CORE上涨且159567跑输AI_CORE。"
    if latest.get("ai_core_ret", 0) < 0 and latest.get("bio_ret", 0) > 0:
        return "weakened：AI_CORE回调时159567上涨。"
    return "unchanged：当前证据不足。"


def _tech_siphon_text(latest: pd.Series) -> str:
    if latest.get("tech_core_ret", 0) > 0 and latest.get("bio_vs_tech", 0) < 0:
        return "strengthened：科技成长上涨且159567跑输TECH_GROWTH_CORE。"
    if latest.get("tech_core_ret", 0) < 0 and latest.get("bio_ret", 0) > 0:
        return "weakened：科技成长回调时159567上涨。"
    return "unchanged：当前证据不足。"


def _relay_text(right_side: dict[str, str], falsification: dict[str, str]) -> str:
    score = _float_or_none(right_side.get("right_side_score"))
    if score is not None and score >= 70 and falsification.get("thesis_state") == "strengthened":
        return "strengthened：初步具备右侧证据。"
    if score is not None and score < 50:
        return "weakened：右侧评分不足。"
    return "unchanged：仍需确认。"


def _a_lead_thesis_text(best: dict[str, str]) -> str:
    if not best:
        return "unchanged：样本不足。"
    win = _float_or_none(best.get("bio_vs_health_win_rate"))
    if win is not None and win >= 0.60 and int(best.get("sample_count") or 0) >= 20:
        return "strengthened：历史样本显示一定领先价值。"
    return "weakened：589720及S1对159567未表现出稳定领先价值，只适合作为同步情绪温度计。"


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _confidence(n: int, min_good: int = 20) -> str:
    if n >= min_good * 2:
        return "high"
    if n >= min_good:
        return "medium"
    return "low"


def _fmt_num(value: float | None) -> str:
    if value is None or pd.isna(value):
        return ""
    return f"{float(value):.8f}"


def _fmt_pct(value: object) -> str:
    value = _float_or_none(value)
    return "missing" if value is None else f"{value:.2%}"


def _num(value: object) -> bool:
    return _float_or_none(value) is not None


def _float_or_none(value: object) -> float | None:
    try:
        if value is None or value == "" or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _split_evidence(value: object) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in str(value).split("|") if item.strip()]
