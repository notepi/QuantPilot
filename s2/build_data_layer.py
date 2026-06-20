"""Build the first-stage S2 data layer.

This script deliberately separates automatic market-data collection from
fact/meaning datasets that require human or agent verification.
"""

from __future__ import annotations

import csv
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from s2.audit_market_data import refresh_market_data_audit
from s2.event_store import load_events
from s2.market_metrics import clinical_conversion_rate
from s2.update_market_data import _fetch_citydata_fund_daily, _fetch_tencent_etf_daily, _fetch_tencent_hk_stock
from wb.tushare_proxy import pro_api as citydata_pro_api


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
INDICATORS_DIR = DATA_DIR / "indicators"
PROCESSED_DIR = DATA_DIR / "processed"
S2_DATA_DIR = PROJECT_ROOT / "s2" / "data"
S2_OUTPUT_DIR = PROJECT_ROOT / "s2" / "output"
REPORTS_DIR = PROJECT_ROOT / "reports"
CORE_SOURCE_AUDIT_PATH = S2_OUTPUT_DIR / "data_audit" / "core_market_source_audit.csv"

A_STOCKS = [
    "600276.SH", "603259.SH", "688192.SH", "688235.SH", "688506.SH",
    "688331.SH", "688578.SH", "688180.SH", "688266.SH",
    "300558.SZ", "002422.SZ", "000963.SZ",
]
ETF_SYMBOLS = [
    "159567.SZ", "159557.SZ", "589720.SH", "512010.SH", "512170.SH",
    "588000.SH", "512760.SH",
]
HK_STOCKS = [
    "09926.HK", "01801.HK", "06160.HK", "06990.HK", "09966.HK",
    "06855.HK", "02096.HK", "03692.HK", "01093.HK", "01177.HK", "02269.HK",
]
MACRO_SYMBOLS = {
    "QQQ": "QQQ",
    "SOXX": "SOXX",
    "SMH": "SMH",
    "XBI": "XBI",
    "IBB": "IBB",
    "XLV": "XLV",
    "XLP": "XLP",
    "XLU": "XLU",
    "US10Y": "^TNX",
    "DXY": "DX-Y.NYB",
    "HSTECH": "^HSTECH",
}
STOOQ_SYMBOLS = {
    "QQQ": "qqq.us",
    "SOXX": "soxx.us",
    "SMH": "smh.us",
    "XBI": "xbi.us",
    "IBB": "ibb.us",
    "XLV": "xlv.us",
    "XLP": "xlp.us",
    "XLU": "xlu.us",
}
CORE_MARKET_SYMBOLS = {"588000.SH", "512760.SH", "SMH", "SOXX", "QQQ"}

MARKET_FIELDS = [
    "symbol", "trade_date", "open", "high", "low", "close", "pct_chg",
    "volume", "amount", "source_name", "source_api", "source_url",
    "adjusted_type", "fetched_at", "source_status", "error_message",
    "retry_count", "data_version", "asset_type",
]


def _today() -> str:
    return datetime.now().strftime("%Y%m%d")


def _report_trade_date() -> str:
    indicator_files = sorted(INDICATORS_DIR.glob("*.json"))
    if not indicator_files:
        return _today()
    latest = indicator_files[-1]
    try:
        payload = json.loads(latest.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return latest.stem
    return str(payload.get("trade_date") or latest.stem)


def _start_date(months: int = 24) -> str:
    return (datetime.now() - timedelta(days=months * 31)).strftime("%Y%m%d")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _empty_market(symbol: str, source_api: str, error: str, asset_type: str) -> pd.DataFrame:
    return pd.DataFrame([{
        "symbol": symbol,
        "trade_date": "",
        "open": "",
        "high": "",
        "low": "",
        "close": "",
        "pct_chg": "",
        "volume": "",
        "amount": "",
        "source_name": "",
        "source_api": source_api,
        "source_url": "",
        "adjusted_type": "none",
        "fetched_at": _now(),
        "source_status": "failed",
        "error_message": error,
        "retry_count": "0",
        "data_version": "v1",
        "asset_type": asset_type,
    }])


def _normalise_akshare_cn(df: pd.DataFrame, symbol: str, source_api: str, source_url: str, asset_type: str) -> pd.DataFrame:
    if df.empty:
        return _empty_market(symbol, source_api, "empty", asset_type)
    result = pd.DataFrame()
    result["trade_date"] = pd.to_datetime(df["日期"], errors="coerce").dt.strftime("%Y%m%d")
    result["symbol"] = symbol
    result["open"] = pd.to_numeric(df["开盘"], errors="coerce")
    result["high"] = pd.to_numeric(df["最高"], errors="coerce")
    result["low"] = pd.to_numeric(df["最低"], errors="coerce")
    result["close"] = pd.to_numeric(df["收盘"], errors="coerce")
    result["pct_chg"] = pd.to_numeric(df.get("涨跌幅", ""), errors="coerce")
    result["volume"] = pd.to_numeric(df.get("成交量", ""), errors="coerce")
    result["amount"] = pd.to_numeric(df.get("成交额", ""), errors="coerce")
    result["source_name"] = "akshare"
    result["source_api"] = source_api
    result["source_url"] = source_url
    result["adjusted_type"] = "none"
    result["fetched_at"] = _now()
    result["source_status"] = "success"
    result["error_message"] = ""
    result["retry_count"] = "0"
    result["data_version"] = "v1"
    result["asset_type"] = asset_type
    return result.dropna(subset=["trade_date", "close"])[MARKET_FIELDS]


def _normalise_citydata(df: pd.DataFrame, symbol: str, source_api: str, asset_type: str, error: str = "") -> pd.DataFrame:
    if df.empty:
        return _empty_market(symbol, source_api, error or "empty", asset_type)
    result = pd.DataFrame()
    result["trade_date"] = df["trade_date"].astype(str)
    result["symbol"] = symbol
    for dst, src in [("open", "open"), ("high", "high"), ("low", "low"), ("close", "close"), ("pct_chg", "pct_chg"), ("volume", "vol"), ("amount", "amount")]:
        result[dst] = pd.to_numeric(df[src], errors="coerce") if src in df.columns else ""
    result["source_name"] = "citydata"
    result["source_api"] = source_api
    result["source_url"] = "https://tushare.citydata.club"
    result["adjusted_type"] = "none"
    result["fetched_at"] = _now()
    result["source_status"] = "success"
    result["error_message"] = ""
    result["retry_count"] = "1" if error else "0"
    result["data_version"] = "v1"
    result["asset_type"] = asset_type
    return result.dropna(subset=["trade_date", "close"])[MARKET_FIELDS]


def _latest_trade_date(df: pd.DataFrame) -> str:
    if df.empty or "trade_date" not in df.columns:
        return ""
    return str(df["trade_date"].astype(str).str.replace("-", "", regex=False).max())


def _fetch_citydata_a_stock_with_trade_date_supplement(symbol: str, start: str, end: str, error: str = "") -> pd.DataFrame:
    pro = citydata_pro_api()
    range_df = pro.daily(ts_code=symbol, start_date=start, end_date=end)
    if range_df.empty or _latest_trade_date(range_df) < end:
        day_df = pro.daily(ts_code=symbol, trade_date=end)
        if not day_df.empty:
            range_df = pd.concat([range_df, day_df], ignore_index=True) if not range_df.empty else day_df
    return _normalise_citydata(range_df, symbol, "daily", "a_share_stock", error)


def _fetch_a_stock(symbol: str) -> pd.DataFrame:
    start = _start_date()
    end = _today()
    try:
        import akshare as ak

        df = ak.stock_zh_a_hist(symbol=symbol.split(".")[0], period="daily", start_date=start, end_date=end, adjust="")
        normalised = _normalise_akshare_cn(df, symbol, "stock_zh_a_hist", "akshare://stock_zh_a_hist", "a_share_stock")
        if _latest_trade_date(normalised) >= end:
            return normalised
        return _fetch_citydata_a_stock_with_trade_date_supplement(symbol, start, end, "akshare_stale")
    except Exception as exc:  # noqa: BLE001
        try:
            return _fetch_citydata_a_stock_with_trade_date_supplement(symbol, start, end, f"akshare_failed: {type(exc).__name__}: {str(exc)[:120]}")
        except Exception as fallback_exc:  # noqa: BLE001
            return _empty_market(symbol, "stock_zh_a_hist|citydata.daily", f"akshare {type(exc).__name__}: {str(exc)[:100]}; citydata {type(fallback_exc).__name__}: {str(fallback_exc)[:100]}", "a_share_stock")


def _fetch_etf(symbol: str) -> pd.DataFrame:
    start = _start_date()
    end = _today()
    short = symbol.split(".")[0]
    try:
        import akshare as ak

        df = ak.fund_etf_hist_em(symbol=short, period="daily", start_date=start, end_date=end, adjust="")
        return _normalise_akshare_cn(df, symbol, "fund_etf_hist_em", "akshare://fund_etf_hist_em", "exchange_traded_fund")
    except Exception as exc:  # noqa: BLE001
        if symbol in {"159567.SZ", "159557.SZ", "512010.SH", "512170.SH", "588000.SH", "512760.SH"}:
            try:
                df = _fetch_tencent_etf_daily(short, limit=520).rename(columns={"date": "trade_date", "volume": "vol"})
                normalised = _normalise_citydata(df, symbol, "tencent_fqkline", "exchange_traded_fund", f"akshare_failed: {type(exc).__name__}: {str(exc)[:120]}")
                normalised["source_name"] = "tencent"
                normalised["source_url"] = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz{short},day,,,520,qfq"
                return normalised
            except Exception as tencent_exc:  # noqa: BLE001
                exc = tencent_exc
        try:
            df = _fetch_citydata_fund_daily(symbol, start_date=start, end_date=end)
            return _normalise_citydata(df, symbol, "fund_daily", "exchange_traded_fund", "akshare_failed")
        except Exception as fallback_exc:  # noqa: BLE001
            return _empty_market(symbol, "fund_etf_hist_em|fallback", f"{type(exc).__name__}: {str(exc)[:100]}; fallback {type(fallback_exc).__name__}: {str(fallback_exc)[:100]}", "exchange_traded_fund")


def _fetch_hk(symbol: str) -> pd.DataFrame:
    try:
        df = _fetch_tencent_hk_stock(symbol, limit=520)
        if df.empty:
            raise ValueError("empty Tencent HK history")
        result = pd.DataFrame()
        result["symbol"] = df["ts_code"]
        result["trade_date"] = df["trade_date"]
        for dst, src in [("open", "open"), ("high", "high"), ("low", "low"), ("close", "close"), ("pct_chg", "pct_chg"), ("volume", "vol"), ("amount", "amount")]:
            result[dst] = df[src] if src in df.columns else ""
        result["source_name"] = "tencent"
        result["source_api"] = "hkfqkline"
        result["source_url"] = f"https://web.ifzq.gtimg.cn/appstock/app/hkfqkline/get?param=hk{symbol.removesuffix('.HK').zfill(5)},day,,,520,qfq"
        result["adjusted_type"] = "qfq"
        result["fetched_at"] = _now()
        result["source_status"] = "success"
        result["error_message"] = ""
        result["retry_count"] = "0"
        result["data_version"] = "v1"
        result["asset_type"] = "hk_stock"
        return result[MARKET_FIELDS]
    except Exception as exc:  # noqa: BLE001
        return _empty_market(symbol, "tencent.hkfqkline", f"{type(exc).__name__}: {str(exc)[:120]}", "hk_stock")


def build_market_daily() -> Path:
    frames = []
    for symbol in A_STOCKS:
        frames.append(_fetch_a_stock(symbol))
    for symbol in ETF_SYMBOLS:
        frames.append(_fetch_etf(symbol))
    for symbol in HK_STOCKS:
        frames.append(_fetch_hk(symbol))
    df = pd.concat(frames, ignore_index=True)
    df = df[df["trade_date"].astype(str) != ""].copy()
    df["symbol"] = df["symbol"].astype(str)
    df["trade_date"] = df["trade_date"].astype(str)
    df = df.drop_duplicates(["symbol", "trade_date"], keep="last").sort_values(["symbol", "trade_date"])
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    path = PROCESSED_DIR / "market_daily.csv"
    df[MARKET_FIELDS].to_csv(path, index=False)
    return path


def _fetch_yahoo_daily(symbol: str, label: str) -> pd.DataFrame:
    params = urllib.parse.urlencode({"range": "2y", "interval": "1d"})
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?{params}"
    fetched_at = _now()
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))
        result = ((payload.get("chart") or {}).get("result") or [None])[0]
        if not result:
            raise ValueError("empty yahoo result")
        timestamps = result.get("timestamp") or []
        quote = (((result.get("indicators") or {}).get("quote") or [{}])[0])
        rows = []
        for idx, ts in enumerate(timestamps):
            close_values = quote.get("close") or []
            if idx >= len(close_values) or close_values[idx] is None:
                continue
            rows.append({
                "symbol": label,
                "trade_date": datetime.fromtimestamp(ts).strftime("%Y%m%d"),
                "close": close_values[idx],
                "source_name": "yahoo",
                "source_api": "chart",
                "source_url": url,
                "fetched_at": fetched_at,
                "source_status": "success",
                "error_message": "",
            })
        return pd.DataFrame(rows)
    except Exception as exc:  # noqa: BLE001
        return pd.DataFrame([{
            "symbol": label,
            "trade_date": "",
            "close": "",
            "source_name": "yahoo",
            "source_api": "chart",
            "source_url": url,
            "fetched_at": fetched_at,
            "source_status": "failed",
            "error_message": f"{type(exc).__name__}: {str(exc)[:160]}",
        }])


def _fetch_stooq_daily(label: str) -> pd.DataFrame:
    stooq_symbol = STOOQ_SYMBOLS.get(label)
    fetched_at = _now()
    if not stooq_symbol:
        return pd.DataFrame([{
            "symbol": label,
            "trade_date": "",
            "close": "",
            "source_name": "stooq",
            "source_api": "daily_csv",
            "source_url": "",
            "fetched_at": fetched_at,
            "source_status": "failed",
            "error_message": "no_stooq_symbol_mapping",
        }])
    url = f"https://stooq.com/q/d/l/?s={urllib.parse.quote(stooq_symbol)}&i=d"
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=15) as response:
            df = pd.read_csv(response)
        if df.empty or "Date" not in df.columns or "Close" not in df.columns:
            raise ValueError("empty stooq result")
        out = pd.DataFrame()
        out["symbol"] = label
        out["trade_date"] = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%Y%m%d")
        out["close"] = pd.to_numeric(df["Close"], errors="coerce")
        out["source_name"] = "stooq"
        out["source_api"] = "daily_csv"
        out["source_url"] = url
        out["fetched_at"] = fetched_at
        out["source_status"] = "success"
        out["error_message"] = ""
        return out.dropna(subset=["trade_date", "close"])
    except Exception as exc:  # noqa: BLE001
        return pd.DataFrame([{
            "symbol": label,
            "trade_date": "",
            "close": "",
            "source_name": "stooq",
            "source_api": "daily_csv",
            "source_url": url,
            "fetched_at": fetched_at,
            "source_status": "failed",
            "error_message": f"{type(exc).__name__}: {str(exc)[:160]}",
        }])


def _fresh_cache_rows(path: Path, label: str, max_calendar_lag: int = 7) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path, dtype={"symbol": str, "trade_date": str})
    rows = df[df["symbol"].astype(str) == label].copy()
    rows = rows[rows["trade_date"].astype(str) != ""]
    if rows.empty:
        return pd.DataFrame()
    latest = str(rows["trade_date"].max())
    try:
        lag = (datetime.now() - datetime.strptime(latest, "%Y%m%d")).days
    except ValueError:
        return pd.DataFrame()
    if lag > max_calendar_lag:
        return pd.DataFrame()
    rows["source_name"] = "local_verified_cache"
    rows["source_api"] = rows.get("source_api", "cache")
    rows["source_status"] = "success"
    rows["error_message"] = f"cache_lag_days={lag}"
    rows["fetched_at"] = _now()
    return rows


def _fetch_macro_with_fallback(symbol: str, label: str, cache_path: Path) -> tuple[pd.DataFrame, dict[str, str]]:
    primary = _fetch_yahoo_daily(symbol, label)
    primary_ok = not primary.empty and (primary["trade_date"].astype(str) != "").sum() >= 200
    if primary_ok:
        return primary, {
            "symbol": label,
            "requested_date_range": "2y",
            "primary_source": "yahoo",
            "fallback_source": "",
            "failure_reason": "",
            "rows_received": str(len(primary[primary["trade_date"].astype(str) != ""])),
            "latest_trade_date": str(primary["trade_date"].max()),
            "missing_dates": "",
            "validation_result": "primary_success",
        }
    fallback = _fetch_stooq_daily(label)
    fallback_ok = not fallback.empty and (fallback["trade_date"].astype(str) != "").sum() >= 200
    if fallback_ok:
        return fallback, {
            "symbol": label,
            "requested_date_range": "all_available",
            "primary_source": "yahoo",
            "fallback_source": "stooq",
            "failure_reason": str(primary.get("error_message", pd.Series(["primary_insufficient"])).iloc[0])[:160],
            "rows_received": str(len(fallback[fallback["trade_date"].astype(str) != ""])),
            "latest_trade_date": str(fallback["trade_date"].max()),
            "missing_dates": "",
            "validation_result": "fallback_success",
        }
    cache = _fresh_cache_rows(cache_path, label)
    cache_ok = not cache.empty
    if cache_ok:
        return cache, {
            "symbol": label,
            "requested_date_range": "cache",
            "primary_source": "yahoo",
            "fallback_source": "stooq|local_verified_cache",
            "failure_reason": "network_sources_failed_or_insufficient",
            "rows_received": str(len(cache)),
            "latest_trade_date": str(cache["trade_date"].max()),
            "missing_dates": "",
            "validation_result": "cache_success",
        }
    return fallback if not fallback.empty else primary, {
        "symbol": label,
        "requested_date_range": "2y",
        "primary_source": "yahoo",
        "fallback_source": "stooq|local_verified_cache",
        "failure_reason": "all_sources_failed_or_insufficient",
        "rows_received": "0",
        "latest_trade_date": "",
        "missing_dates": "unknown",
        "validation_result": "failed",
    }


def build_macro_market_daily() -> Path:
    path = PROCESSED_DIR / "macro_market_daily.csv"
    frames = []
    audit_rows = []
    for label, symbol in MACRO_SYMBOLS.items():
        if label in {"SMH", "SOXX", "QQQ"}:
            frame, audit = _fetch_macro_with_fallback(symbol, label, path)
            frames.append(frame)
            audit_rows.append(audit)
        else:
            frames.append(_fetch_yahoo_daily(symbol, label))
    df = pd.concat(frames, ignore_index=True)
    if not df.empty:
        df = df.sort_values(["symbol", "trade_date"])
        df["pct_1d"] = pd.to_numeric(df["close"], errors="coerce").groupby(df["symbol"]).pct_change(fill_method=None)
        df["pct_5d"] = pd.to_numeric(df["close"], errors="coerce").groupby(df["symbol"]).pct_change(5, fill_method=None)
        df["pct_10d"] = pd.to_numeric(df["close"], errors="coerce").groupby(df["symbol"]).pct_change(10, fill_method=None)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    if audit_rows:
        CORE_SOURCE_AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(audit_rows).to_csv(CORE_SOURCE_AUDIT_PATH, index=False)
    return path


def _truthy_source(row: dict[str, str]) -> bool:
    return bool(row.get("source_url") or row.get("source_urls"))


def _copy_events(src: Path, dst: Path, event_kind: str) -> Path:
    rows = load_events(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    out_rows = []
    for row in rows:
        source_url = row.get("source_url") or row.get("source_urls") or ""
        out = dict(row)
        out.update({
            "source_name": row.get("source_type") or row.get("source_tier") or "existing_event_store",
            "source_type": row.get("source_type") or "not_reverified_this_run",
            "source_date": row.get("published_at") or row.get("date") or "missing",
            "fetched_at": "",
            "source_status": "present_not_reverified" if _truthy_source(row) else "missing_source_url",
            "error_message": "",
            "confidence": row.get("confidence") or ("medium" if _truthy_source(row) else "low"),
            "raw_text_excerpt": row.get("note") or "",
            "data_category": event_kind,
            "requires_human_verification": "true",
        })
        if not source_url:
            out["source_url"] = "missing"
        out_rows.append(out)
    if out_rows:
        fields = sorted({key for row in out_rows for key in row})
        with dst.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(out_rows)
    else:
        dst.write_text("source_status,requires_human_verification\nmissing,true\n", encoding="utf-8")
    return dst


def build_company_financials() -> Path:
    rows = load_events(S2_DATA_DIR / "commercialization_metrics.csv")
    out = []
    for row in rows:
        out.append({
            "company_name": row.get("company_name") or "missing",
            "symbol": row.get("symbol") or "missing",
            "report_period": row.get("report_period") or "missing",
            "report_type": "missing",
            "total_revenue": "missing",
            "total_revenue_yoy": row.get("total_revenue_yoy") or "missing",
            "product_revenue": "missing",
            "product_revenue_yoy": row.get("product_revenue_yoy") or "missing",
            "innovation_drug_revenue": "missing",
            "innovation_drug_revenue_yoy": row.get("innovation_drug_revenue_yoy") or "missing",
            "adjusted_profit": "missing",
            "adjusted_profit_yoy": row.get("adjusted_profit_yoy") or "missing",
            "net_profit": "missing",
            "net_profit_yoy": "missing",
            "operating_cash_flow": row.get("operating_cash_flow") or "missing",
            "cash_balance": row.get("cash_balance") or "missing",
            "gross_margin": "missing",
            "r_and_d_expense": "missing",
            "selling_expense": "missing",
            "source_url": row.get("source_url") or "missing",
            "source_type": row.get("source_type") or "missing",
            "source_date": row.get("source_date") or "missing",
            "confidence": "medium" if row.get("source_url") else "low",
            "fetched_at": "",
            "source_status": "present_not_reverified",
            "raw_text_excerpt": row.get("note") or "",
            "requires_human_verification": "true",
        })
    path = PROCESSED_DIR / "company_financials.csv"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    fields = list(out[0]) if out else ["source_status", "requires_human_verification"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(out)
    return path


def build_clinical_trade_returns() -> Path:
    clinical_events = load_events(S2_DATA_DIR / "clinical_events.csv")
    audit_path = S2_OUTPUT_DIR / "data_audit" / "market_data_audit.csv"
    result = clinical_conversion_rate(
        clinical_events,
        DATA_DIR / "raw",
        as_of_trade_date=_report_trade_date(),
        audit_path=audit_path if audit_path.exists() else None,
    )
    rows = []
    audit = {row["symbol"]: row for row in load_events(audit_path)} if audit_path.exists() else {}
    for status in result.clinical_event_statuses:
        stock_audit = audit.get(status.ticker) or audit.get(f"{status.ticker.removesuffix('.HK').zfill(5)}.HK", {})
        benchmark_audit = audit.get(status.benchmark_code, {})
        rows.append({
            "trade_sample_id": status.trade_sample_id,
            "stock_code": status.ticker,
            "event_date": status.event_date,
            "benchmark_code": status.benchmark_code,
            "window_days": status.window_days,
            "trading_status": status.trading_status,
            "included_in_official_score": str(status.included_in_official_score).lower(),
            "included_in_deduped_trade_sample": str(status.included_in_deduped_trade_sample).lower(),
            "stock_return_5d": status.stock_return_5d,
            "benchmark_return_5d": status.etf_159557_return_5d if status.is_hk_event else "",
            "excess_return_5d": status.excess_vs_159557_5d if status.is_hk_event else "",
            "stock_source": stock_audit.get("final_source", "missing"),
            "benchmark_source": benchmark_audit.get("final_source", "missing"),
            "stock_fetched_at": stock_audit.get("fetched_at", "missing"),
            "benchmark_fetched_at": benchmark_audit.get("fetched_at", "missing"),
            "stock_source_status": stock_audit.get("data_quality", "missing"),
            "benchmark_source_status": benchmark_audit.get("data_quality", "missing"),
            "data_quality": "valid" if status.included_in_official_score else status.trading_status,
            "missing_reason": status.dedupe_note or "",
        })
    path = S2_DATA_DIR / "clinical_trade_returns.csv"
    fields = list(rows[0]) if rows else [
        "trade_sample_id", "stock_code", "event_date", "benchmark_code", "window_days",
        "trading_status", "data_quality", "missing_reason",
    ]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def _table_quality(path: Path) -> dict[str, object]:
    rows = load_events(path)
    if not rows:
        return {"rows": 0, "missing_ratio": 1.0, "source_status": "missing", "fetched_at_coverage": 0.0}
    total = sum(len(row) for row in rows)
    missing = sum(1 for row in rows for value in row.values() if str(value or "").strip().lower() in {"", "missing"})
    fetched = sum(1 for row in rows if str(row.get("fetched_at") or "").strip())
    statuses: dict[str, int] = {}
    for row in rows:
        status = row.get("source_status") or "missing"
        statuses[status] = statuses.get(status, 0) + 1
    return {
        "rows": len(rows),
        "missing_ratio": missing / total if total else 1.0,
        "source_status": "；".join(f"{key}:{value}" for key, value in sorted(statuses.items())),
        "fetched_at_coverage": fetched / len(rows),
    }


def build_data_quality_report(paths: list[Path]) -> Path:
    audit_rows = load_events(S2_OUTPUT_DIR / "data_audit" / "market_data_audit.csv")
    blocked = [row for row in audit_rows if row.get("can_use_for_latest_signal") != "true"]
    unstable = [row for row in audit_rows if row.get("data_quality") == "unstable_source"]
    lines = [
        "# S2 数据质量报告",
        "",
        f"**生成时间**: {_now()}",
        "",
        "## 数据分工",
        "",
        "- 代码自动抓取：A股股票、ETF、港股个股、海外ETF/指数/宏观行情、事件后收益计算、market_data_audit。",
        "- 需要人工/智能体查证：BD事件、临床事件、审批事件、公司财务字段、商业化兑现、一致预期、政策风险事件。",
        "- 本阶段不生成日报；未过审计的数据不得进入 latest 判断、S2-04、Macro_Risk_Layer 或 final_view。",
        "",
        "## 行情审计",
        "",
        f"- audited_symbols={len(audit_rows)}",
        f"- can_use_for_latest_signal=false：{len(blocked)}",
        f"- unstable_source：{len(unstable)}",
        f"- blocked_symbols：{', '.join(row['symbol'] for row in blocked) or 'none'}",
        f"- unstable_symbols：{', '.join(row['symbol'] for row in unstable) or 'none'}",
        "",
        "## 表级质量",
        "",
        "| 文件 | 行数 | missing_ratio | source_status分布 | fetched_at覆盖率 |",
        "| --- | ---: | ---: | --- | ---: |",
    ]
    for path in paths:
        q = _table_quality(path)
        lines.append(f"| {path.relative_to(PROJECT_ROOT)} | {q['rows']} | {q['missing_ratio']:.2%} | {q['source_status']} | {q['fetched_at_coverage']:.2%} |")
    lines.extend([
        "",
        "## 暂不能生成的结论",
        "",
        "- 任何 `can_use_for_latest_signal=false` 的标的不得进入 latest_valid。",
        "- 需要人工核验的事件/财务/政策表，本阶段只做结构化和 source_status 标注，不新增未经查证事实。",
    ])
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / "data_quality_report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def build_data_layer() -> list[Path]:
    report_trade_date = _report_trade_date()
    paths = [
        build_market_daily(),
        build_macro_market_daily(),
    ]
    paths.append(refresh_market_data_audit(report_trade_date))
    paths.extend([
        build_clinical_trade_returns(),
        build_company_financials(),
        _copy_events(S2_DATA_DIR / "bd_events.csv", PROCESSED_DIR / "bd_events.csv", "bd"),
        _copy_events(S2_DATA_DIR / "clinical_events.csv", PROCESSED_DIR / "clinical_events.csv", "clinical"),
        _copy_events(S2_DATA_DIR / "regulatory_events.csv", PROCESSED_DIR / "approval_events.csv", "approval"),
        _copy_events(S2_DATA_DIR / "policy_risk_events.csv", PROCESSED_DIR / "policy_risk_events.csv", "policy_risk"),
    ])
    paths.append(build_data_quality_report(paths))
    return paths


def main() -> None:
    paths = build_data_layer()
    print("S2 data layer built:")
    for path in paths:
        print(f"- {path}")


if __name__ == "__main__":
    main()
