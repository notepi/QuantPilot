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
    true_value: float | None = None
    proxy_value: float | None = None
    true_sample_count: int = 0
    proxy_sample_count: int = 0
    proxy_type: str = ""
    leader_excess_median_5d: float | None = None
    leader_win_rate_5d: float | None = None
    leader_excess_median_10d: float | None = None
    leader_breadth_20d: float | None = None


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


def _ma_breadth(market_data_dir: Path, tickers: list[str], trade_date: str, window: int = 20) -> float | None:
    above = 0
    usable = 0
    date_key = trade_date.replace("-", "")
    for ticker in tickers:
        df = _prices(market_data_dir, ticker)
        if df.empty or "close" not in df.columns:
            continue
        history = df[df["trade_date"] <= date_key].tail(window)
        if len(history) < window:
            continue
        usable += 1
        above += int(float(history["close"].iloc[-1]) > float(history["close"].mean()))
    if usable == 0:
        return None
    return above / usable


def clinical_conversion_rate(
    events: list[dict[str, str]],
    market_data_dir: Path,
    etf: str = "589720.SH",
    benchmark: str = "159557.SZ",
) -> MarketResult:
    true_wins = 0
    true_usable = 0
    proxy_wins = 0
    proxy_usable = 0
    missing: list[str] = []
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
            proxy_usable += 1
            proxy_wins += int(etf_ret > benchmark_ret)
            continue
        elif etf_ret is None:
            missing.append(f"{etf}事件后行情数据缺失")
            continue
        true_usable += 1
        true_wins += int(stock_ret > etf_ret)
    usable = true_usable + proxy_usable
    if usable == 0:
        return MarketResult(None, "无可计算临床事件后5日交易样本", missing or ["临床事件或行情数据缺失"])
    true_value = true_wins / true_usable if true_usable else None
    proxy_value = (true_wins + proxy_wins) / usable
    value = 0.7 * true_value + 0.3 * proxy_value if true_value is not None else proxy_value
    basis = f"真实标的样本 {true_wins}/{true_usable}；含替代口径样本 {true_wins + proxy_wins}/{usable}"
    if proxy_usable:
        basis += f"；其中 {proxy_usable} 个因标的行情缺失，使用 {etf} 跑赢 {benchmark} 作为ETF承接替代口径"
    return MarketResult(
        value,
        basis,
        missing,
        usable,
        proxy_usable,
        true_value,
        proxy_value,
        true_usable,
        proxy_usable,
        "ETF承接替代" if proxy_usable else "",
    )


def leader_excess_median(
    events: list[dict[str, str]],
    market_data_dir: Path,
    etf: str = "589720.SH",
    local_leaders: list[str] | None = None,
) -> MarketResult:
    excess_values: list[float] = []
    excess_values_10d: list[float] = []
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
        etf_ret_10d = event_return(market_data_dir, etf, date, days=10)
        if etf_ret is None:
            missing.append(f"{etf}事件后行情数据缺失")
            continue
        if stock_ret is not None:
            excess_values.append(stock_ret - etf_ret)
            stock_ret_10d = event_return(market_data_dir, ticker, date, days=10)
            if stock_ret_10d is not None and etf_ret_10d is not None:
                excess_values_10d.append(stock_ret_10d - etf_ret_10d)
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
        leader_returns_10d = [
            leader_ret
            for code in local_leaders
            if (leader_ret := event_return(market_data_dir, code, date, days=10)) is not None
        ]
        if leader_returns_10d and etf_ret_10d is not None:
            excess_values_10d.append(median(leader_returns_10d) - etf_ret_10d)
    if not excess_values:
        return MarketResult(None, "无可计算核心催化后5日超额收益样本", missing or ["核心催化事件或行情数据缺失"])
    win_rate = sum(1 for value in excess_values if value > 0) / len(excess_values)
    breadth = _ma_breadth(market_data_dir, local_leaders, max((event.get("date", "") for event in events), default=""))
    basis = f"核心催化后5日超额收益中位数 {median(excess_values):.2%}"
    if fallback_used:
        basis += f"；其中 {fallback_used} 个事件因标的行情缺失，使用本地A股龙头池相对 {etf} 的中位超额收益"
    return MarketResult(
        median(excess_values),
        basis,
        missing,
        len(excess_values),
        fallback_used,
        leader_excess_median_5d=median(excess_values),
        leader_win_rate_5d=win_rate,
        leader_excess_median_10d=median(excess_values_10d) if excess_values_10d else None,
        leader_breadth_20d=breadth,
    )
