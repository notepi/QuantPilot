"""Refresh optional S2 market data without blocking S2 scoring."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd

from s2.citydata_client import pro_api as citydata_pro_api
from s2.hk_observation import update_hk_observation


PROJECT_ROOT = Path(__file__).resolve().parent.parent
S2_DATA_DIR = PROJECT_ROOT / "s2" / "data"
HK_DAILY_PATH = S2_DATA_DIR / "hk_daily.csv"
HK_TICKERS = [
    "9926.HK",
    "01801.HK",
    "6990.HK",
    "9966.HK",
    "6855.HK",
    "02096.HK",
    "06160.HK",
    "01952.HK",
]
HK_DAILY_FIELDS = ["ts_code", "trade_date", "open", "high", "low", "close", "pct_chg", "vol", "amount", "source", "fetched_at"]


def _empty_hk_daily() -> pd.DataFrame:
    return pd.DataFrame(columns=HK_DAILY_FIELDS)


def _normalise_hk_ticker(ticker: str) -> str:
    return f"{ticker.removesuffix('.HK').zfill(5)}.HK"


def _load_hk_daily() -> pd.DataFrame:
    if not HK_DAILY_PATH.exists():
        return _empty_hk_daily()
    df = pd.read_csv(HK_DAILY_PATH, dtype={"ts_code": str, "trade_date": str})
    if df.empty:
        return _empty_hk_daily()
    for field in HK_DAILY_FIELDS:
        if field not in df.columns:
            df[field] = ""
    df["ts_code"] = df["ts_code"].astype(str).map(_normalise_hk_ticker)
    df["trade_date"] = df["trade_date"].astype(str).str.replace("-", "", regex=False)
    return _ensure_pct_chg(df[HK_DAILY_FIELDS])


def _ensure_pct_chg(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return _empty_hk_daily()
    result = df.copy()
    result["close"] = pd.to_numeric(result["close"], errors="coerce")
    result["pct_chg"] = pd.to_numeric(result.get("pct_chg", ""), errors="coerce")
    result = result.sort_values(["ts_code", "trade_date"])
    calculated = result.groupby("ts_code")["close"].pct_change() * 100
    result["pct_chg"] = result["pct_chg"].where(result["pct_chg"].notna(), calculated)
    return result[HK_DAILY_FIELDS]


def _normalise_akshare_hk(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if df.empty:
        return _empty_hk_daily()
    date_col = "日期" if "日期" in df.columns else "date" if "date" in df.columns else "trade_date"
    close_col = "收盘" if "收盘" in df.columns else "close"
    if date_col not in df.columns or close_col not in df.columns:
        return _empty_hk_daily()
    result = pd.DataFrame()
    result["trade_date"] = pd.to_datetime(df[date_col], errors="coerce").dt.strftime("%Y%m%d")
    result["ts_code"] = _normalise_hk_ticker(ticker)
    column_map = {
        "open": "开盘",
        "high": "最高",
        "low": "最低",
        "close": close_col,
        "pct_chg": "涨跌幅",
        "vol": "成交量",
        "amount": "成交额",
    }
    for field, cn_col in column_map.items():
        src = cn_col if cn_col in df.columns else field if field in df.columns else close_col if field in {"open", "high", "low", "close"} else None
        result[field] = pd.to_numeric(df[src], errors="coerce") if src else ""
    result["source"] = "akshare.stock_hk_hist"
    result["fetched_at"] = datetime.now().isoformat(timespec="seconds")
    return _ensure_pct_chg(result[HK_DAILY_FIELDS].dropna(subset=["trade_date", "close"]))


def _fetch_hk_stock(ticker: str) -> pd.DataFrame:
    import akshare as ak

    symbol = ticker.removesuffix(".HK").zfill(5)
    return _normalise_akshare_hk(ak.stock_hk_hist(symbol=symbol, period="daily", adjust=""), ticker)


def _fetch_tencent_hk_stock(ticker: str, limit: int = 260, timeout: int = 15) -> pd.DataFrame:
    normalised = _normalise_hk_ticker(ticker)
    symbol = f"hk{normalised.removesuffix('.HK')}"
    params = urllib.parse.urlencode({"param": f"{symbol},day,,,{limit},qfq"})
    url = f"https://web.ifzq.gtimg.cn/appstock/app/hkfqkline/get?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    symbol_payload = ((payload.get("data") or {}).get(symbol) or {})
    rows = symbol_payload.get("day") or symbol_payload.get("qfqday") or []
    if not rows:
        return _empty_hk_daily()
    result = pd.DataFrame()
    result["trade_date"] = pd.to_datetime([row[0] for row in rows], errors="coerce").strftime("%Y%m%d")
    result["ts_code"] = normalised
    result["open"] = pd.to_numeric([row[1] if len(row) > 1 else "" for row in rows], errors="coerce")
    result["close"] = pd.to_numeric([row[2] if len(row) > 2 else "" for row in rows], errors="coerce")
    result["high"] = pd.to_numeric([row[3] if len(row) > 3 else "" for row in rows], errors="coerce")
    result["low"] = pd.to_numeric([row[4] if len(row) > 4 else "" for row in rows], errors="coerce")
    result["vol"] = pd.to_numeric([row[5] if len(row) > 5 else "" for row in rows], errors="coerce")
    result["pct_chg"] = ""
    result["amount"] = pd.to_numeric([row[8] if len(row) > 8 else "" for row in rows], errors="coerce")
    result["source"] = "tencent.hkfqkline"
    result["fetched_at"] = datetime.now().isoformat(timespec="seconds")
    return _ensure_pct_chg(result[HK_DAILY_FIELDS].dropna(subset=["trade_date", "close"]))


def _fetch_tushare_fund_daily(symbol: str, start_date: str | None = None, end_date: str | None = None) -> pd.DataFrame:
    pro = citydata_pro_api()
    ts_code = symbol if symbol.endswith(".SZ") or symbol.endswith(".SH") else f"{symbol}.SZ"
    end = end_date or datetime.now().strftime("%Y%m%d")
    start = start_date or (datetime.now() - pd.Timedelta(days=220)).strftime("%Y%m%d")
    df = pro.fund_daily(ts_code=ts_code, start_date=start, end_date=end)
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.copy()
    df["ts_code"] = ts_code
    df["trade_date"] = df["trade_date"].astype(str)
    return df


def _fetch_tushare_fund_daily_checked(symbol: str, expected_trade_date: str | None = None) -> pd.DataFrame:
    df = _fetch_tushare_fund_daily(f"{symbol}.SZ")
    if df.empty:
        return df
    expected = expected_trade_date or datetime.now().strftime("%Y%m%d")
    latest = str(df["trade_date"].max())
    if latest < expected:
        raise ValueError(f"tushare stale for {symbol}: latest={latest}, expected={expected}")
    return df


def _fetch_tencent_etf_daily(symbol: str, limit: int = 260, timeout: int = 15) -> pd.DataFrame:
    params = urllib.parse.urlencode({"param": f"sz{symbol},day,,,{limit},qfq"})
    url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?{params}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    symbol_payload = ((payload.get("data") or {}).get(f"sz{symbol}") or {})
    rows = symbol_payload.get("qfqday") or symbol_payload.get("day") or []
    if not rows:
        return pd.DataFrame()
    result = pd.DataFrame()
    result["date"] = pd.to_datetime([row[0] for row in rows], errors="coerce").strftime("%Y%m%d")
    result["open"] = pd.to_numeric([row[1] if len(row) > 1 else "" for row in rows], errors="coerce")
    result["close"] = pd.to_numeric([row[2] if len(row) > 2 else "" for row in rows], errors="coerce")
    result["high"] = pd.to_numeric([row[3] if len(row) > 3 else "" for row in rows], errors="coerce")
    result["low"] = pd.to_numeric([row[4] if len(row) > 4 else "" for row in rows], errors="coerce")
    result["volume"] = pd.to_numeric([row[5] if len(row) > 5 else "" for row in rows], errors="coerce")
    result["amount"] = ""
    return result.dropna(subset=["date", "close"])


def update_position_etf_daily() -> dict[str, object]:
    """Deprecated: ETF prices for S2 are kept in HK_observation cache only."""
    return {
        "status": "skipped",
        "updated": [],
        "errors": [],
        "path": str(DEFAULT_OBSERVATION_CACHE_PATH()),
        "message": "S2不再写data/raw/fund_daily.csv；159567/159557仅刷新HK_observation缓存。",
    }


def DEFAULT_OBSERVATION_CACHE_PATH() -> Path:
    return PROJECT_ROOT / "s2" / "output" / "hk_cache"


def update_hk_daily(tickers: list[str] | None = None) -> dict[str, object]:
    """Refresh HK individual stock daily prices used by S2-04."""
    tickers = tickers or HK_TICKERS
    existing = _load_hk_daily()
    frames = [existing] if not existing.empty else []
    errors: list[str] = []
    updated: list[str] = []
    for ticker in tickers:
        normalised = _normalise_hk_ticker(ticker)
        try:
            fresh = _fetch_hk_stock(normalised)
            if fresh.empty:
                raise ValueError("empty HK history")
            frames.append(fresh)
            updated.append(normalised)
        except Exception as exc:  # noqa: BLE001 - optional S2 data must not block
            try:
                fresh = _fetch_tencent_hk_stock(normalised)
                if fresh.empty:
                    raise ValueError("empty Tencent HK history")
                frames.append(fresh)
                updated.append(normalised)
                errors.append(f"{normalised}: akshare_failed_then_tencent_success: {type(exc).__name__}: {str(exc)[:120]}")
            except Exception as fallback_exc:  # noqa: BLE001 - optional S2 data must not block
                errors.append(
                    f"{normalised}: akshare {type(exc).__name__}: {str(exc)[:100]}；"
                    f"tencent {type(fallback_exc).__name__}: {str(fallback_exc)[:100]}"
                )
    merged = pd.concat(frames, ignore_index=True) if frames else _empty_hk_daily()
    S2_DATA_DIR.mkdir(parents=True, exist_ok=True)
    if merged.empty:
        _empty_hk_daily().to_csv(HK_DAILY_PATH, index=False)
    else:
        merged["ts_code"] = merged["ts_code"].astype(str).map(_normalise_hk_ticker)
        merged["trade_date"] = merged["trade_date"].astype(str).str.replace("-", "", regex=False)
        merged = merged.drop_duplicates(["ts_code", "trade_date"], keep="last").sort_values(["ts_code", "trade_date"])
        merged = _ensure_pct_chg(merged)
        merged[HK_DAILY_FIELDS].to_csv(HK_DAILY_PATH, index=False)
    return {
        "status": "success" if updated and not errors else "partial" if updated else "failed",
        "updated": updated,
        "errors": errors,
        "latest_dates": {
            ticker: str(merged[merged["ts_code"] == ticker]["trade_date"].max())
            for ticker in sorted(set(merged["ts_code"])) if not merged.empty
        },
        "path": str(HK_DAILY_PATH),
    }


def update_s2_market_data() -> dict[str, object]:
    """Backward-compatible entry point for the S2 observation updater."""
    expected_trade_date = datetime.now().strftime("%Y%m%d")
    observation = update_hk_observation(
        fetcher=lambda symbol: _fetch_tushare_fund_daily_checked(symbol, expected_trade_date),
        fallback_fetcher=_fetch_tencent_etf_daily,
        primary_source_name="tushare_fund_daily",
        fallback_source_name="tencent_fqkline",
    )
    hk_daily = update_hk_daily()
    etf_daily = update_position_etf_daily()
    return {"hk_observation": observation, "hk_daily": hk_daily, "etf_daily": etf_daily}


def main() -> None:
    result = update_s2_market_data()
    etf_daily = result["etf_daily"]
    print(f"ETF_daily 状态: {etf_daily['status']}；更新 {len(etf_daily['updated'])} 个标的；文件: {etf_daily['path']}")
    for error in etf_daily.get("errors", []):
        print(f"- {error}")
    observation = result["hk_observation"]
    print(f"HK_observation 状态: {observation['status']}")
    print(observation["comment"])
    for error in observation.get("errors", []):
        print(f"- {error}")
    hk_daily = result["hk_daily"]
    print(f"HK_daily 状态: {hk_daily['status']}；更新 {len(hk_daily['updated'])} 个标的；文件: {hk_daily['path']}")
    for error in hk_daily.get("errors", []):
        print(f"- {error}")


if __name__ == "__main__":
    main()
