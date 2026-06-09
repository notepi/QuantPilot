"""Minimal Hong Kong innovation-drug ETF observation layer."""

from __future__ import annotations

import csv
import json
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Callable

import pandas as pd
from pandas.tseries.offsets import BDay


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CACHE_DIR = PROJECT_ROOT / "s2" / "output" / "hk_cache"
DEFAULT_LEGACY_FUND_PATH = PROJECT_ROOT / "data" / "raw" / "fund_daily.csv"
ETF_SYMBOLS = ("159567", "159557")
EASTMONEY_SECIDS = {"159567": "0.159567", "159557": "0.159557"}
CACHE_FIELDS = ["date", "ticker", "open", "high", "low", "close", "volume", "amount", "source", "fetched_at"]


def _cache_path(cache_dir: Path, symbol: str) -> Path:
    return cache_dir / f"{symbol}.csv"


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=CACHE_FIELDS)


def _load_cache(cache_dir: Path, symbol: str) -> pd.DataFrame:
    path = _cache_path(cache_dir, symbol)
    if not path.exists():
        return _empty_frame()
    df = pd.read_csv(path, dtype={"date": str, "trade_date": str, "ticker": str})
    if "trade_date" in df.columns and "date" not in df.columns:
        df["date"] = df["trade_date"]
    if "date" not in df.columns or "close" not in df.columns:
        return _empty_frame()
    df["date"] = df["date"].astype(str).str.replace("-", "", regex=False)
    df["ticker"] = df.get("ticker", f"{symbol}.SZ")
    for field in ["open", "high", "low", "volume", "amount"]:
        if field not in df.columns:
            df[field] = df["close"] if field in {"open", "high", "low"} else ""
    if "source" not in df.columns:
        df["source"] = "legacy_cache"
    if "fetched_at" not in df.columns:
        df["fetched_at"] = ""
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df[CACHE_FIELDS].dropna(subset=["date", "close"]).drop_duplicates("date", keep="last").sort_values("date")


def _load_legacy_fund_cache(path: Path, symbol: str) -> pd.DataFrame:
    if not path.exists():
        return _empty_frame()
    df = pd.read_csv(path, dtype={"trade_date": str, "ts_code": str})
    if not {"ts_code", "trade_date", "close"}.issubset(df.columns):
        return _empty_frame()
    rows = df[df["ts_code"] == f"{symbol}.SZ"].copy()
    if rows.empty:
        return _empty_frame()
    rows["date"] = rows["trade_date"].astype(str)
    rows["ticker"] = f"{symbol}.SZ"
    rows["open"] = rows.get("open", rows["close"])
    rows["high"] = rows.get("high", rows["close"])
    rows["low"] = rows.get("low", rows["close"])
    rows["volume"] = rows.get("vol", rows.get("volume", ""))
    rows["amount"] = rows.get("amount", "")
    rows["source"] = "local_fund_daily"
    rows["fetched_at"] = ""
    return rows[CACHE_FIELDS].dropna(subset=["date", "close"]).drop_duplicates("date", keep="last").sort_values("date")


def _normalise_hist(df: pd.DataFrame, symbol: str, source: str) -> pd.DataFrame:
    if df.empty:
        return _empty_frame()
    date_col = "日期" if "日期" in df.columns else "date" if "date" in df.columns else "trade_date"
    close_col = "收盘" if "收盘" in df.columns else "close"
    if date_col not in df.columns or close_col not in df.columns:
        return _empty_frame()
    result = pd.DataFrame()
    result["date"] = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y%m%d")
    result["ticker"] = f"{symbol}.SZ"
    column_map = {
        "open": "开盘",
        "high": "最高",
        "low": "最低",
        "close": close_col,
        "volume": "成交量",
        "amount": "成交额",
    }
    for field, cn_col in column_map.items():
        src = cn_col if cn_col in df.columns else field if field in df.columns else close_col if field in {"open", "high", "low", "close"} else None
        result[field] = pd.to_numeric(df[src], errors="coerce") if src else ""
    result["source"] = source
    result["fetched_at"] = datetime.now().isoformat(timespec="seconds")
    return result[CACHE_FIELDS].dropna(subset=["date", "close"]).drop_duplicates("date", keep="last").sort_values("date")


def _fetch_akshare(symbol: str) -> pd.DataFrame:
    import akshare as ak

    return ak.fund_etf_hist_em(symbol=symbol, period="daily", adjust="")


def _fetch_eastmoney(symbol: str, limit: int = 120, timeout: int = 15) -> pd.DataFrame:
    secid = EASTMONEY_SECIDS[symbol]
    params = {
        "secid": secid,
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57",
        "klt": "101",
        "fqt": "0",
        "beg": "0",
        "end": "20500101",
        "lmt": str(limit),
    }
    url = "https://push2his.eastmoney.com/api/qt/stock/kline/get?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    klines = (payload.get("data") or {}).get("klines") or []
    rows: list[dict[str, object]] = []
    for line in klines:
        parts = str(line).split(",")
        if len(parts) < 7:
            continue
        rows.append({
            "date": parts[0],
            "open": parts[1],
            "close": parts[2],
            "high": parts[3],
            "low": parts[4],
            "volume": parts[5],
            "amount": parts[6],
        })
    return pd.DataFrame(rows)


def _write_cache(cache_dir: Path, symbol: str, df: pd.DataFrame) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    df[CACHE_FIELDS].to_csv(_cache_path(cache_dir, symbol), index=False)


def _write_update_status(cache_dir: Path, observation: dict[str, object]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        f"attempted_at={datetime.now().isoformat(timespec='seconds')}",
        f"status={observation['status']}",
        f"data_source={observation.get('data_source', '')}",
        f"primary_source={observation.get('primary_source', 'akshare')}",
        f"primary_source_status={observation.get('primary_source_status', '')}",
        f"primary_source_error={observation.get('primary_source_error', '')}",
        f"fallback_source={observation.get('fallback_source', 'eastmoney')}",
        f"fallback_source_status={observation.get('fallback_source_status', '')}",
        f"fallback_source_error={observation.get('fallback_source_error', '')}",
        f"final_data_source={observation.get('final_data_source', observation.get('data_source', ''))}",
    ]
    lines.extend(f"error={error}" for error in observation.get("errors", []))
    (cache_dir / "status.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _error_text(symbol: str, exc: Exception) -> str:
    message = str(exc)
    if "Failed to resolve" in message:
        detail = "DNS解析失败"
    elif "proxy" in message.lower():
        detail = "代理连接失败"
    elif "timed out" in message.lower():
        detail = "请求超时"
    else:
        detail = message[:160]
    return f"{symbol}: {type(exc).__name__}: {detail}"


def _source_from_frame(frame: pd.DataFrame) -> str:
    if frame.empty or "source" not in frame.columns:
        return ""
    values = [str(value) for value in frame["source"].dropna().unique() if str(value)]
    return values[-1] if values else ""


def read_hk_update_status(cache_dir: Path = DEFAULT_CACHE_DIR) -> dict[str, object]:
    """Read the latest simple refresh status, if the updater has run."""
    path = cache_dir / "status.txt"
    if not path.exists():
        return {}
    result: dict[str, object] = {"errors": []}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        if key == "error":
            result["errors"].append(value)
        elif key:
            result[key] = value
    return result


def _comment(status: str, excess: float | None) -> str:
    if status == "missing":
        return "HK_observation 数据缺失，不判断 159567 是否强于 159557。"
    if status == "stale":
        return "HK_observation 数据滞后，不判断 159567 是否强于 159557。"
    if status == "stale_valid":
        return "HK_observation 使用缓存且仍在1个交易日容忍期内，提示但可做低置信观察。"
    if status == "date_mismatch":
        return "159567 与 159557 最新日期不一致，只可回看共同交易日历史5日超额，不做最新强弱判断。"
    if status == "data_fetch_failed":
        return "报告日已有对照行情但本地未抓到159567同步行情，标记 data_fetch_failed，不做最新强弱判断。"
    if excess is None:
        return "HK_observation 共同交易日不足 6 个，不判断 159567 是否强于 159557。"
    direction = "强于" if excess > 0 else "弱于" if excess < 0 else "持平于"
    return f"港股创新药 ETF 最近 5 个交易日{direction}港股医疗宽基。"


def _business_day_lag(latest_date: str, today: datetime) -> int:
    if not latest_date:
        return 999
    latest = datetime.strptime(latest_date, "%Y%m%d")
    if latest.date() >= today.date():
        return 0
    return len(pd.bdate_range(latest + BDay(1), today))


def _calendar_day_lag(latest_date: str, today: datetime) -> int:
    if not latest_date:
        return 999
    latest = datetime.strptime(latest_date, "%Y%m%d")
    return max(0, (today.date() - latest.date()).days)


def _freeze_trend_status(status: str) -> bool:
    return status in {"date_mismatch", "data_fetch_failed", "valid_common_date"}


def _public_hk_status(status: str, is_valid: bool, has_common_date: bool) -> str:
    if is_valid:
        return "latest_valid"
    if status == "data_fetch_failed":
        return "data_fetch_failed"
    if has_common_date:
        return "valid_common_date"
    return "missing"


def _build_observation(
    frames: dict[str, pd.DataFrame],
    *,
    today: datetime,
    errors: list[str] | None = None,
) -> dict[str, object]:
    errors = errors or []
    latest = {
        symbol: str(frame["date"].max()) if not frame.empty else ""
        for symbol, frame in frames.items()
    }
    data_sources = sorted({_source_from_frame(frame) for frame in frames.values() if _source_from_frame(frame)})
    data_source = "+".join(data_sources)
    if any(not latest.get(symbol) for symbol in ETF_SYMBOLS):
        report_trade_date = today.strftime("%Y%m%d")
        return {
            "status": "missing",
            "hk_observation_status": "missing",
            "latest_date_159567": latest.get("159567", ""),
            "latest_date_159557": latest.get("159557", ""),
            "common_trade_date": "",
            "report_trade_date": report_trade_date,
            "lag_days_159567": _business_day_lag(latest.get("159567", ""), today),
            "lag_days_159557": _business_day_lag(latest.get("159557", ""), today),
            "calendar_lag_days": _calendar_day_lag(latest.get("159567", ""), today),
            "trading_lag_days": _business_day_lag(latest.get("159567", ""), today),
            "report_day_price_available_externally": False,
            "local_fetch_failed": False,
            "data_fetch_failed": False,
            "observation_trade_date": "",
            "return_159567_1d": None,
            "return_159567_5d": None,
            "return_159557_5d": None,
            "excess_159567_vs_159557_5d": None,
            "is_valid_for_judgement": False,
            "data_source": data_source,
            "comment": _comment("missing", None),
            "errors": errors,
        }

    report_trade_date = today.strftime("%Y%m%d")
    lag_159567 = _business_day_lag(latest["159567"], today)
    lag_159557 = _business_day_lag(latest["159557"], today)
    calendar_lag_159567 = _calendar_day_lag(latest["159567"], today)
    max_business_lag = max(lag_159567, lag_159557)
    date_mismatch = latest["159567"] != latest["159557"]
    data_fetch_failed = date_mismatch and (
        latest["159557"] >= report_trade_date
        or latest["159567"] >= report_trade_date
        or min(lag_159567, lag_159557) == 0
    )
    merged = frames["159567"].merge(frames["159557"], on="date", suffixes=("_159567", "_159557"))
    merged = merged.sort_values("date")
    observation_trade_date = str(merged["date"].max()) if not merged.empty else ""
    one_day = benchmark_one_day = excess_one_day = None
    five_day = benchmark_five_day = excess = None
    ten_day = benchmark_ten_day = excess_ten_day = None
    if len(merged) >= 6:
        one_day = float(merged["close_159567"].iloc[-1] / merged["close_159567"].iloc[-2] - 1)
        benchmark_one_day = float(merged["close_159557"].iloc[-1] / merged["close_159557"].iloc[-2] - 1)
        excess_one_day = one_day - benchmark_one_day
        five_day = float(merged["close_159567"].iloc[-1] / merged["close_159567"].iloc[-6] - 1)
        benchmark_five_day = float(merged["close_159557"].iloc[-1] / merged["close_159557"].iloc[-6] - 1)
        excess = five_day - benchmark_five_day
    if len(merged) >= 11:
        ten_day = float(merged["close_159567"].iloc[-1] / merged["close_159567"].iloc[-11] - 1)
        benchmark_ten_day = float(merged["close_159557"].iloc[-1] / merged["close_159557"].iloc[-11] - 1)
        excess_ten_day = ten_day - benchmark_ten_day
    if data_fetch_failed:
        status = "data_fetch_failed"
    elif date_mismatch:
        status = "date_mismatch"
    else:
        status = "stale" if max_business_lag > 1 else "valid"
    is_valid_for_judgement = status == "valid" and excess is not None
    hk_observation_status = _public_hk_status(status, is_valid_for_judgement, bool(observation_trade_date))
    return {
        "status": status,
        "hk_observation_status": hk_observation_status,
        "latest_date_159567": latest["159567"],
        "latest_date_159557": latest["159557"],
        "common_trade_date": observation_trade_date,
        "report_trade_date": report_trade_date,
        "lag_days_159567": lag_159567,
        "lag_days_159557": lag_159557,
        "calendar_lag_days": calendar_lag_159567,
        "trading_lag_days": lag_159567,
        "report_day_price_available_externally": False,
        "local_fetch_failed": False,
        "date_mismatch": date_mismatch,
        "data_fetch_failed": data_fetch_failed,
        "observation_trade_date": observation_trade_date,
        "return_159567_1d": one_day if is_valid_for_judgement else None,
        "return_159557_1d": benchmark_one_day if is_valid_for_judgement else None,
        "excess_159567_vs_159557_1d": excess_one_day if is_valid_for_judgement else None,
        "return_159567_5d": five_day if is_valid_for_judgement else None,
        "return_159557_5d": benchmark_five_day if is_valid_for_judgement else None,
        "excess_159567_vs_159557_5d": excess if is_valid_for_judgement else None,
        "return_159567_10d": ten_day if is_valid_for_judgement else None,
        "return_159557_10d": benchmark_ten_day if is_valid_for_judgement else None,
        "excess_159567_vs_159557_10d": excess_ten_day if is_valid_for_judgement else None,
        "common_trade_return_159567_1d": one_day,
        "common_trade_return_159557_1d": benchmark_one_day,
        "common_trade_excess_159567_vs_159557_1d": excess_one_day,
        "common_trade_return_159567_5d": five_day,
        "common_trade_return_159557_5d": benchmark_five_day,
        "common_trade_excess_159567_vs_159557_5d": excess,
        "common_trade_return_159567_10d": ten_day,
        "common_trade_return_159557_10d": benchmark_ten_day,
        "common_trade_excess_159567_vs_159557_10d": excess_ten_day,
        "is_valid_for_judgement": is_valid_for_judgement,
        "max_business_day_lag": max_business_lag,
        "data_source": data_source,
        "comment": _comment(status, excess),
        "errors": errors,
    }


def read_hk_observation(cache_dir: Path = DEFAULT_CACHE_DIR, *, today: datetime | None = None) -> dict[str, object]:
    """Read the latest cached observation without touching the network."""
    frames = {symbol: _load_cache(cache_dir, symbol) for symbol in ETF_SYMBOLS}
    return _build_observation(frames, today=today or datetime.now())


def update_hk_observation(
    cache_dir: Path = DEFAULT_CACHE_DIR,
    *,
    today: datetime | None = None,
    fetcher: Callable[[str], pd.DataFrame] | None = None,
    fallback_fetcher: Callable[[str], pd.DataFrame] | None = None,
    primary_source_name: str = "akshare",
    fallback_source_name: str = "eastmoney",
    legacy_fund_path: Path = DEFAULT_LEGACY_FUND_PATH,
) -> dict[str, object]:
    """Refresh the two ETF caches; use old cache and continue on fetch failure."""
    errors: list[str] = []
    primary_errors: list[str] = []
    fallback_errors: list[str] = []
    fallback_used = False
    fallback_success_symbols: set[str] = set()
    cache_used_symbols: set[str] = set()
    frames: dict[str, pd.DataFrame] = {}
    fetcher = fetcher or _fetch_akshare
    fallback_fetcher = fallback_fetcher or _fetch_eastmoney
    for symbol in ETF_SYMBOLS:
        try:
            fresh = _normalise_hist(fetcher(symbol), symbol, primary_source_name)
            if fresh.empty:
                raise ValueError("empty ETF history")
            _write_cache(cache_dir, symbol, fresh)
            frames[symbol] = fresh
        except Exception as exc:  # noqa: BLE001 - observation failures must stay non-blocking
            error = _error_text(symbol, exc)
            primary_errors.append(error)
            errors.append(f"{primary_source_name}/{error}")
            try:
                fallback_used = True
                fresh = _normalise_hist(fallback_fetcher(symbol), symbol, fallback_source_name)
                if fresh.empty:
                    raise ValueError("empty ETF history")
                _write_cache(cache_dir, symbol, fresh)
                frames[symbol] = fresh
                fallback_success_symbols.add(symbol)
            except Exception as fallback_exc:  # noqa: BLE001 - keep S2 non-blocking
                fallback_error = _error_text(symbol, fallback_exc)
                fallback_errors.append(fallback_error)
                errors.append(f"{fallback_source_name}/{fallback_error}")
                cached = _load_cache(cache_dir, symbol)
                if cached.empty:
                    cached = _load_legacy_fund_cache(legacy_fund_path, symbol)
                    if not cached.empty:
                        _write_cache(cache_dir, symbol, cached)
                if not cached.empty:
                    cache_used_symbols.add(symbol)
                frames[symbol] = cached
    observation = _build_observation(frames, today=today or datetime.now(), errors=errors)
    observation["primary_source"] = primary_source_name
    observation["primary_source_status"] = "failed" if primary_errors else "success"
    observation["primary_source_error"] = "；".join(primary_errors)
    observation["fallback_source"] = fallback_source_name
    if not fallback_used:
        fallback_status = "not_used"
    elif fallback_errors:
        fallback_status = "failed"
    else:
        fallback_status = "success"
    observation["fallback_source_status"] = fallback_status
    observation["fallback_source_error"] = "；".join(fallback_errors)
    if not primary_errors:
        final_data_source = primary_source_name
    elif fallback_success_symbols and not fallback_errors:
        final_data_source = fallback_source_name
    elif cache_used_symbols:
        final_data_source = "cache"
    else:
        final_data_source = "none"
    observation["final_data_source"] = final_data_source
    if final_data_source == "cache" and observation.get("status") == "valid":
        observation["status"] = "stale_valid"
        observation["comment"] = _comment("stale_valid", observation.get("excess_159567_vs_159557_5d"))
        observation["is_valid_for_judgement"] = observation.get("max_business_day_lag", 999) <= 1 and observation.get("excess_159567_vs_159557_5d") is not None
    _write_update_status(cache_dir, observation)
    return observation


def upsert_hk_observation_history(output_dir: Path, report_date: str, observation: dict[str, object]) -> None:
    """Persist the lightweight observation history for later review."""
    path = output_dir / "hk_observation_scores.csv"
    fields = [
        "date",
        "status",
        "hk_observation_status",
        "latest_date_159567",
        "latest_date_159557",
        "common_trade_date",
        "report_trade_date",
        "lag_days_159567",
        "lag_days_159557",
        "calendar_lag_days",
        "trading_lag_days",
        "report_day_price_available_externally",
        "local_fetch_failed",
        "data_fetch_failed",
        "observation_trade_date",
        "return_159567_1d",
        "return_159557_1d",
        "excess_159567_vs_159557_1d",
        "return_159567_5d",
        "return_159557_5d",
        "excess_159567_vs_159557_5d",
        "return_159567_10d",
        "return_159557_10d",
        "excess_159567_vs_159557_10d",
        "common_trade_return_159567_1d",
        "common_trade_return_159557_1d",
        "common_trade_excess_159567_vs_159557_1d",
        "common_trade_return_159567_5d",
        "common_trade_return_159557_5d",
        "common_trade_excess_159567_vs_159557_5d",
        "common_trade_return_159567_10d",
        "common_trade_return_159557_10d",
        "common_trade_excess_159567_vs_159557_10d",
        "excess_5d",
        "excess_5d_direction",
        "hk_underperform_streak_days",
        "hk_outperform_streak_days",
        "hk_relative_trend_state",
        "is_valid_for_judgement",
        "data_source",
        "primary_source",
        "primary_source_status",
        "primary_source_error",
        "fallback_source",
        "fallback_source_status",
        "fallback_source_error",
        "final_data_source",
        "max_business_day_lag",
        "comment",
    ]
    rows: list[dict[str, str]] = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            rows = [row for row in csv.DictReader(fh) if row.get("date") != report_date]
    row = {"date": report_date}
    for field in fields[1:]:
        value = observation.get(field)
        row[field] = "" if value is None else str(value).lower() if isinstance(value, bool) else str(value)
    row["excess_5d"] = row.get("excess_159567_vs_159557_5d", "")
    excess = observation.get("excess_159567_vs_159557_5d")
    if not observation.get("is_valid_for_judgement") or excess is None:
        row["excess_5d_direction"] = "unknown"
    elif float(excess) > 0:
        row["excess_5d_direction"] = "当日相对强"
    elif float(excess) < 0:
        row["excess_5d_direction"] = "当日相对弱"
    else:
        row["excess_5d_direction"] = "当日持平"
    rows.append(row)
    sorted_rows = sorted(rows, key=lambda item: item["date"])
    under_streak = 0
    out_streak = 0
    for item in sorted_rows:
        try:
            item_excess = float(item.get("excess_5d") or item.get("excess_159567_vs_159557_5d") or "")
        except ValueError:
            item_excess = 0.0
            valid = False
        else:
            valid = item.get("is_valid_for_judgement", "").lower() == "true"
        if _freeze_trend_status(item.get("status", "")):
            item["hk_underperform_streak_days"] = str(under_streak)
            item["hk_outperform_streak_days"] = str(out_streak)
            item["hk_relative_trend_state"] = "日期不一致，不更新连续强弱"
            continue
        if not valid:
            under_streak = 0
            out_streak = 0
        elif item_excess < 0:
            under_streak += 1
            out_streak = 0
        elif item_excess > 0:
            out_streak += 1
            under_streak = 0
        else:
            under_streak = 0
            out_streak = 0
        item["hk_underperform_streak_days"] = str(under_streak)
        item["hk_outperform_streak_days"] = str(out_streak)
        if under_streak >= 3:
            item["hk_relative_trend_state"] = "连续弱于港股医疗宽基"
        elif out_streak >= 3:
            item["hk_relative_trend_state"] = "连续强于港股医疗宽基"
        elif valid:
            item["hk_relative_trend_state"] = "相对强弱未形成连续趋势"
        else:
            item["hk_relative_trend_state"] = "不可判定"
    output_dir.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in sorted_rows)
