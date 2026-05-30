"""Market conversion metrics used by S2 scoring."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import median

import pandas as pd


LOCAL_LEADER_STOCKS = [
    "688235.SH",
    "688578.SH",
    "688506.SH",
    "688180.SH",
    "688266.SH",
]


@dataclass(frozen=True)
class MarketResult:
    value: float | None
    basis: str
    missing: list[str]
    sample_count: int = 0
    replacement_count: int = 0


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "trade_date" in df.columns:
        df["trade_date"] = df["trade_date"].astype(str)
    return df


def _prices(market_data_dir: Path, ticker: str) -> pd.DataFrame:
    source = "fund_daily.csv" if ticker in {"589720.SH", "159557.SZ", "159567.SZ"} else "daily.csv"
    df = _load_csv(market_data_dir / source)
    if df.empty or "ts_code" not in df.columns:
        return pd.DataFrame()
    return df[df["ts_code"].astype(str) == ticker].sort_values("trade_date")


def event_return(market_data_dir: Path, ticker: str, event_date: str, days: int = 5) -> float | None:
    df = _prices(market_data_dir, ticker)
    if df.empty or "close" not in df.columns:
        return None
    event_key = event_date.replace("-", "")
    window = df[df["trade_date"] >= event_key]
    if len(window) < 2:
        return None
    actual_days = min(days, len(window) - 1)
    start = float(window["close"].iloc[0])
    end = float(window["close"].iloc[actual_days])
    if start == 0:
        return None
    return (end - start) / start


def clinical_conversion_rate(
    events: list[dict[str, str]],
    market_data_dir: Path,
    etf: str = "589720.SH",
    benchmark: str = "159557.SZ",
) -> MarketResult:
    wins = 0
    usable = 0
    missing: list[str] = []
    fallback_used = 0
    for event in events:
        if event.get("status", "active") != "active":
            continue
        ticker = event.get("ticker", "")
        date = event.get("date", "")
        if not ticker or not date:
            missing.append(f"{event.get('company', '未知事件')}缺少ticker/date")
            continue
        stock_ret = event_return(market_data_dir, ticker, date)
        etf_ret = event_return(market_data_dir, etf, date)
        if stock_ret is None:
            benchmark_ret = event_return(market_data_dir, benchmark, date)
            if etf_ret is None or benchmark_ret is None:
                missing.append(f"{ticker}行情缺失，且{etf}/{benchmark}事件后行情不足")
                continue
            fallback_used += 1
            stock_ret = etf_ret
            etf_ret = benchmark_ret
        elif etf_ret is None:
            missing.append(f"{etf}事件后行情数据缺失")
            continue
        usable += 1
        wins += int(stock_ret > etf_ret)
    if usable == 0:
        return MarketResult(None, "无可计算临床事件后5日交易样本", missing or ["临床事件或行情数据缺失"])
    basis = f"{wins}/{usable} 个临床事件交易样本跑赢参照"
    if fallback_used:
        basis += f"；其中 {fallback_used} 个因标的行情缺失，使用 {etf} 跑赢 {benchmark} 作为ETF承接替代口径"
    return MarketResult(wins / usable, basis, missing, usable, fallback_used)


def leader_excess_median(
    events: list[dict[str, str]],
    market_data_dir: Path,
    etf: str = "589720.SH",
    local_leaders: list[str] | None = None,
) -> MarketResult:
    excess_values: list[float] = []
    missing: list[str] = []
    fallback_used = 0
    local_leaders = local_leaders or LOCAL_LEADER_STOCKS
    for event in events:
        if event.get("status", "active") != "active":
            continue
        ticker = event.get("ticker", "")
        date = event.get("date", "")
        if not ticker or not date:
            continue
        stock_ret = event_return(market_data_dir, ticker, date)
        etf_ret = event_return(market_data_dir, etf, date)
        if etf_ret is None:
            missing.append(f"{etf}事件后行情数据缺失")
            continue
        if stock_ret is not None:
            excess_values.append(stock_ret - etf_ret)
            continue

        leader_returns = [
            leader_ret
            for code in local_leaders
            if (leader_ret := event_return(market_data_dir, code, date)) is not None
        ]
        if not leader_returns:
            missing.append(f"{ticker}行情缺失，且本地A股龙头池事件后行情不足")
            continue
        fallback_used += 1
        excess_values.append(median(leader_returns) - etf_ret)
    if not excess_values:
        return MarketResult(None, "无可计算核心催化后5日超额收益样本", missing or ["核心催化事件或行情数据缺失"])
    basis = f"核心催化后5日超额收益中位数 {median(excess_values):.2%}"
    if fallback_used:
        basis += f"；其中 {fallback_used} 个事件因标的行情缺失，使用本地A股龙头池相对 {etf} 的中位超额收益"
    return MarketResult(median(excess_values), basis, missing, len(excess_values), fallback_used)
