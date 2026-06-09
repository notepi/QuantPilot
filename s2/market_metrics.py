"""Market conversion metrics used by S2 scoring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
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

HK_DAILY_FILE = "hk_daily.csv"
S2_HK_DAILY_PATH = Path(__file__).resolve().parent / "data" / "hk_daily.csv"
HK_POSITION_ETF = "159567.SZ"
HK_BENCHMARK_ETF = "159557.SZ"


@dataclass(frozen=True)
class ClinicalEventStatus:
    event_id: str
    company: str
    ticker: str
    asset: str
    event_date: str
    trading_status: str
    days_elapsed: int
    required_days: int
    is_mature: bool
    has_local_price: bool
    is_hk_event: bool
    included_in_official_score: bool
    included_in_hk_observation: bool
    benchmark_code: str = ""
    window_days: int = 5
    trade_sample_id: str = ""
    included_in_deduped_trade_sample: bool = False
    dedupe_note: str = ""
    next_maturity_date: str = ""
    stock_return_5d: float | None = None
    excess_vs_159567_5d: float | None = None
    excess_vs_159557_5d: float | None = None
    etf_159567_return_5d: float | None = None
    etf_159557_return_5d: float | None = None
    etf_159567_vs_159557_5d: float | None = None
    event_relevance_to_159567: str = ""


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
    pending_count: int = 0
    hk_pending_count: int = 0
    price_missing_count: int = 0
    raw_mature_event_count: int = 0
    deduped_trade_sample_count: int = 0
    success_count: int = 0
    success_rate: float | None = None
    mature_event_keys: tuple[str, ...] = ()
    proxy_event_keys: tuple[str, ...] = ()
    clinical_event_statuses: tuple[ClinicalEventStatus, ...] = ()


def _load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if "trade_date" in df.columns:
        df["trade_date"] = df["trade_date"].astype(str)
    return df


def _normalise_hk_ticker(ticker: str) -> str:
    if not ticker.endswith(".HK"):
        return ticker
    code = ticker.removesuffix(".HK").zfill(5)
    return f"{code}.HK"


def _normalise_symbol(ticker: str) -> str:
    return _normalise_hk_ticker(str(ticker or ""))


def _load_market_audit(path: Path | None) -> dict[str, dict[str, str]]:
    if not path or not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str).fillna("")
    if "symbol" not in df.columns:
        return {}
    return {_normalise_symbol(row["symbol"]): dict(row) for _, row in df.iterrows()}


def _audit_allows_latest(audit: dict[str, dict[str, str]], ticker: str) -> bool:
    if not audit:
        return True
    row = audit.get(_normalise_symbol(ticker))
    if row is None:
        return False
    return str(row.get("can_use_for_latest_signal", "")).lower() == "true"


def _audit_block_reason(audit: dict[str, dict[str, str]], ticker: str) -> str:
    row = audit.get(_normalise_symbol(ticker))
    if row is None:
        return f"{ticker} not_in_market_data_audit"
    return f"{ticker} data_quality={row.get('data_quality')}; reason={row.get('reason') or 'missing'}"


def _prices(market_data_dir: Path, ticker: str) -> pd.DataFrame:
    if ticker.endswith(".HK"):
        df = _load_csv(market_data_dir / HK_DAILY_FILE)
        if df.empty:
            df = _load_csv(S2_HK_DAILY_PATH)
        if df.empty or "ts_code" not in df.columns:
            return pd.DataFrame()
        df = df.copy()
        df["ts_code"] = df["ts_code"].astype(str).map(_normalise_hk_ticker)
        return df[df["ts_code"] == _normalise_hk_ticker(ticker)].sort_values("trade_date")
    source = "fund_daily.csv" if ticker in {"589720.SH", "159557.SZ", "159567.SZ"} else "daily.csv"
    df = _load_csv(market_data_dir / source)
    if df.empty or "ts_code" not in df.columns:
        return pd.DataFrame()
    return df[df["ts_code"].astype(str) == ticker].sort_values("trade_date")


def _is_market_validation_event(event: dict[str, str]) -> bool:
    return (
        event.get("status", "active") in {"active", "superseded"}
        and event.get("verification_status", "confirmed") == "confirmed"
        and event.get("is_duplicate", "false").lower() not in {"true", "1", "yes", "y", "是"}
    )


def _event_key(event: dict[str, str]) -> str:
    return event.get("event_id") or "|".join(
        [
            event.get("date", ""),
            event.get("company", ""),
            event.get("asset", ""),
            event.get("source_url", ""),
        ]
    )


def _trade_sample_id(ticker: str, event_date: str, benchmark_code: str, window_days: int = 5) -> str:
    stock_code = _normalise_hk_ticker(ticker)
    return f"{stock_code}|{event_date.replace('-', '')}|{benchmark_code}|{window_days}"


def event_return(
    market_data_dir: Path,
    ticker: str,
    event_date: str,
    days: int = 5,
    as_of_trade_date: str | None = None,
) -> float | None:
    df = _prices(market_data_dir, ticker)
    if df.empty or "close" not in df.columns:
        return None
    event_key = event_date.replace("-", "")
    window = df[df["trade_date"] >= event_key]
    if as_of_trade_date:
        window = window[window["trade_date"] <= as_of_trade_date.replace("-", "")]
    if len(window) < days + 1:
        return None
    start = float(window["close"].iloc[0])
    end = float(window["close"].iloc[days])
    if start == 0:
        return None
    return (end - start) / start


def _event_returns_bundle(
    market_data_dir: Path,
    ticker: str,
    event_date: str,
    as_of_trade_date: str | None,
) -> dict[str, float | None]:
    stock_ret = event_return(market_data_dir, ticker, event_date, as_of_trade_date=as_of_trade_date)
    position_ret = event_return(market_data_dir, HK_POSITION_ETF, event_date, as_of_trade_date=as_of_trade_date)
    benchmark_ret = event_return(market_data_dir, HK_BENCHMARK_ETF, event_date, as_of_trade_date=as_of_trade_date)
    return {
        "stock_return_5d": stock_ret,
        "etf_159567_return_5d": position_ret,
        "etf_159557_return_5d": benchmark_ret,
        "excess_vs_159567_5d": None if stock_ret is None or position_ret is None else stock_ret - position_ret,
        "excess_vs_159557_5d": None if stock_ret is None or benchmark_ret is None else stock_ret - benchmark_ret,
        "etf_159567_vs_159557_5d": None if position_ret is None or benchmark_ret is None else position_ret - benchmark_ret,
    }


def _event_relevance(event: dict[str, str]) -> str:
    explicit = event.get("event_relevance_to_159567", "").lower()
    ticker = _normalise_hk_ticker(event.get("ticker", ""))
    if ticker in {"09926.HK", "01801.HK", "06990.HK", "09966.HK", "06855.HK", "02096.HK", "06160.HK", "01952.HK"}:
        return "high"
    if explicit in {"high", "medium", "low"}:
        return explicit
    if ticker.endswith(".HK"):
        return "medium"
    return "medium" if ticker else "low"


def _trading_days_elapsed(
    market_data_dir: Path,
    event_date: str,
    as_of_trade_date: str | None,
    etf: str,
) -> int:
    df = _prices(market_data_dir, etf)
    if df.empty and etf != "589720.SH":
        df = _prices(market_data_dir, "589720.SH")
    if df.empty:
        return 0
    window = df[df["trade_date"] >= event_date.replace("-", "")]
    if as_of_trade_date:
        window = window[window["trade_date"] <= as_of_trade_date.replace("-", "")]
    return max(0, len(window) - 1)


def _next_maturity_date(as_of_trade_date: str | None, days_elapsed: int, required_days: int = 5) -> str:
    if not as_of_trade_date or days_elapsed >= required_days:
        return ""
    date = datetime.strptime(as_of_trade_date.replace("-", ""), "%Y%m%d")
    return (date + pd.offsets.BDay(required_days - days_elapsed)).strftime("%Y-%m-%d")


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
    as_of_trade_date: str | None = None,
    audit_path: Path | None = None,
) -> MarketResult:
    true_wins = 0
    true_usable = 0
    missing: list[str] = []
    pending_count = 0
    hk_pending_count = 0
    price_missing_count = 0
    raw_mature_event_count = 0
    seen_trade_samples: set[str] = set()
    mature_event_keys: list[str] = []
    event_statuses: list[ClinicalEventStatus] = []
    market_audit = _load_market_audit(audit_path)
    for event in events:
        if not _is_market_validation_event(event):
            continue
        ticker = event.get("ticker", "")
        date = event.get("effective_trade_date") or event.get("date", "")
        if not ticker or not date:
            missing.append(f"{event.get('company', '未知事件')}缺少ticker/date")
            continue
        event_key = _event_key(event)
        is_hk_event = ticker.endswith(".HK")
        benchmark_code = benchmark if is_hk_event else etf
        trade_sample_id = _trade_sample_id(ticker, date, benchmark_code, 5)
        relevance = _event_relevance(event)
        maturity_clock = ticker if is_hk_event else etf
        days_elapsed = _trading_days_elapsed(market_data_dir, date, as_of_trade_date, maturity_clock)
        is_mature = days_elapsed >= 5
        next_maturity_date = _next_maturity_date(as_of_trade_date, days_elapsed)
        if not is_mature:
            pending_count += 1
            if is_hk_event:
                hk_pending_count += 1
            event_statuses.append(
                ClinicalEventStatus(
                    event_key,
                    event.get("company", ""),
                    ticker,
                    event.get("asset", ""),
                    date,
                    "pending_not_enough_days",
                    days_elapsed,
                    5,
                    False,
                    False,
                    is_hk_event,
                    False,
                    is_hk_event,
                    benchmark_code,
                    5,
                    trade_sample_id,
                    False,
                    "事件未满5个完整交易日，尚未形成交易样本",
                    next_maturity_date,
                    event_relevance_to_159567=relevance,
                )
            )
            missing.append(f"{ticker}待满5个交易日验证")
            continue
        if market_audit and (not _audit_allows_latest(market_audit, ticker) or not _audit_allows_latest(market_audit, benchmark_code)):
            price_missing_count += 1
            if is_hk_event:
                hk_pending_count += 1
            audit_reason = "；".join(
                reason for reason in [
                    "" if _audit_allows_latest(market_audit, ticker) else _audit_block_reason(market_audit, ticker),
                    "" if _audit_allows_latest(market_audit, benchmark_code) else _audit_block_reason(market_audit, benchmark_code),
                ]
                if reason
            )
            event_statuses.append(
                ClinicalEventStatus(
                    event_key,
                    event.get("company", ""),
                    ticker,
                    event.get("asset", ""),
                    date,
                    "market_data_audit_blocked",
                    days_elapsed,
                    5,
                    True,
                    False,
                    is_hk_event,
                    False,
                    is_hk_event,
                    benchmark_code,
                    5,
                    trade_sample_id,
                    False,
                    audit_reason,
                    event_relevance_to_159567=relevance,
                )
            )
            missing.append(f"market_data_audit_blocked: {audit_reason}")
            continue
        stock_ret = event_return(market_data_dir, ticker, date, as_of_trade_date=as_of_trade_date)
        etf_ret = event_return(market_data_dir, benchmark if is_hk_event else etf, date, as_of_trade_date=as_of_trade_date)
        returns = _event_returns_bundle(market_data_dir, ticker, date, as_of_trade_date)
        if stock_ret is None or etf_ret is None:
            price_missing_count += 1
            if is_hk_event:
                hk_pending_count += 1
            event_statuses.append(
                ClinicalEventStatus(
                    event_key,
                    event.get("company", ""),
                    ticker,
                    event.get("asset", ""),
                    date,
                    "missing_price",
                    days_elapsed,
                    5,
                    True,
                    False,
                    is_hk_event,
                    False,
                    is_hk_event,
                    benchmark_code,
                    5,
                    trade_sample_id,
                    False,
                    "成熟但行情缺失，未进入正式交易样本",
                    stock_return_5d=returns["stock_return_5d"],
                    excess_vs_159567_5d=returns["excess_vs_159567_5d"],
                    excess_vs_159557_5d=returns["excess_vs_159557_5d"],
                    etf_159567_return_5d=returns["etf_159567_return_5d"],
                    etf_159557_return_5d=returns["etf_159557_return_5d"],
                    etf_159567_vs_159557_5d=returns["etf_159567_vs_159557_5d"],
                    event_relevance_to_159567=relevance,
                )
            )
            missing_parts: list[str] = []
            if stock_ret is None:
                missing_parts.append(ticker)
            if etf_ret is None:
                missing_parts.append(benchmark if is_hk_event else etf)
            required = "、".join(missing_parts) if missing_parts else (benchmark if is_hk_event else etf)
            missing.append(f"missing_price: {required}本地行情缺失，成熟样本暂不进入S2-04正式得分")
            continue
        raw_mature_event_count += 1
        if trade_sample_id in seen_trade_samples:
            event_statuses.append(
                ClinicalEventStatus(
                    event_key,
                    event.get("company", ""),
                    ticker,
                    event.get("asset", ""),
                    date,
                    "mature_deduped_duplicate",
                    days_elapsed,
                    5,
                    True,
                    True,
                    is_hk_event,
                    False,
                    is_hk_event,
                    benchmark_code,
                    5,
                    trade_sample_id,
                    False,
                    "同一 stock_code + event_date + benchmark_code + window_days 已有正式交易样本，本项目仅保留明细",
                    stock_return_5d=returns["stock_return_5d"],
                    excess_vs_159567_5d=returns["excess_vs_159567_5d"],
                    excess_vs_159557_5d=returns["excess_vs_159557_5d"],
                    etf_159567_return_5d=returns["etf_159567_return_5d"],
                    etf_159557_return_5d=returns["etf_159557_return_5d"],
                    etf_159567_vs_159557_5d=returns["etf_159567_vs_159557_5d"],
                    event_relevance_to_159567=relevance,
                )
            )
            continue
        seen_trade_samples.add(trade_sample_id)
        true_usable += 1
        true_wins += int(stock_ret > etf_ret)
        mature_event_keys.append(trade_sample_id)
        event_statuses.append(
            ClinicalEventStatus(
                event_key,
                event.get("company", ""),
                ticker,
                event.get("asset", ""),
                date,
                "mature_calculable",
                days_elapsed,
                5,
                True,
                True,
                is_hk_event,
                True,
                is_hk_event,
                benchmark_code,
                5,
                trade_sample_id,
                True,
                "进入去重后的正式交易样本",
                stock_return_5d=returns["stock_return_5d"],
                excess_vs_159567_5d=returns["excess_vs_159567_5d"],
                excess_vs_159557_5d=returns["excess_vs_159557_5d"],
                etf_159567_return_5d=returns["etf_159567_return_5d"],
                etf_159557_return_5d=returns["etf_159557_return_5d"],
                etf_159567_vs_159557_5d=returns["etf_159567_vs_159557_5d"],
                event_relevance_to_159567=relevance,
            )
        )
    if true_usable == 0:
        return MarketResult(
            None,
            "无成熟可计算临床事件后5日交易样本",
            missing or ["临床事件或行情数据缺失"],
            pending_count=pending_count,
            hk_pending_count=hk_pending_count,
            price_missing_count=price_missing_count,
            raw_mature_event_count=raw_mature_event_count,
            deduped_trade_sample_count=0,
            success_count=0,
            success_rate=None,
            mature_event_keys=tuple(mature_event_keys),
            clinical_event_statuses=tuple(event_statuses),
        )
    true_value = true_wins / true_usable if true_usable else None
    value = true_value
    basis = (
        f"正式口径：raw_mature_event_count={raw_mature_event_count}；"
        f"deduped_trade_sample_count={true_usable}；success_count={true_wins}；"
        f"success_rate={true_value:.2%}；港股事件使用{benchmark}作宽基对照，A股事件使用{etf}作温度计对照"
    )
    return MarketResult(
        value,
        basis,
        missing,
        true_usable,
        0,
        true_value,
        None,
        true_usable,
        0,
        "",
        pending_count=pending_count,
        hk_pending_count=hk_pending_count,
        price_missing_count=price_missing_count,
        raw_mature_event_count=raw_mature_event_count,
        deduped_trade_sample_count=true_usable,
        success_count=true_wins,
        success_rate=true_value,
        mature_event_keys=tuple(mature_event_keys),
        clinical_event_statuses=tuple(event_statuses),
    )


def leader_excess_median(
    events: list[dict[str, str]],
    market_data_dir: Path,
    etf: str = "589720.SH",
    local_leaders: list[str] | None = None,
    as_of_trade_date: str | None = None,
) -> MarketResult:
    excess_values: list[float] = []
    excess_values_10d: list[float] = []
    missing: list[str] = []
    pending_count = 0
    mature_event_keys: list[str] = []
    local_leaders = local_leaders or LOCAL_LEADER_STOCKS
    for event in events:
        if not _is_market_validation_event(event):
            continue
        date = event.get("effective_trade_date") or event.get("date", "")
        if not date:
            continue
        event_key = _event_key(event)
        etf_ret = event_return(market_data_dir, etf, date, as_of_trade_date=as_of_trade_date)
        etf_ret_10d = event_return(market_data_dir, etf, date, days=10, as_of_trade_date=as_of_trade_date)
        if etf_ret is None:
            pending_count += 1
            missing.append(f"{etf}待满5个交易日验证")
            continue
        leader_returns = [
            leader_ret
            for code in local_leaders
            if (leader_ret := event_return(market_data_dir, code, date, as_of_trade_date=as_of_trade_date)) is not None
        ]
        if len(leader_returns) < 3:
            pending_count += 1
            missing.append(f"本地A股龙头池待满5个交易日验证或有效样本少于3只")
            continue
        excess_values.append(median(leader_returns) - etf_ret)
        mature_event_keys.append(event_key)
        leader_returns_10d = [
            leader_ret
            for code in local_leaders
            if (leader_ret := event_return(market_data_dir, code, date, days=10, as_of_trade_date=as_of_trade_date)) is not None
        ]
        if len(leader_returns_10d) >= 3 and etf_ret_10d is not None:
            excess_values_10d.append(median(leader_returns_10d) - etf_ret_10d)
    if not excess_values:
        return MarketResult(
            None,
            "无新增成熟核心催化后5日超额收益样本",
            missing or ["核心催化事件或行情数据缺失"],
            pending_count=pending_count,
            mature_event_keys=tuple(mature_event_keys),
        )
    win_rate = sum(1 for value in excess_values if value > 0) / len(excess_values)
    breadth = _ma_breadth(market_data_dir, local_leaders, as_of_trade_date or max((event.get("date", "") for event in events), default=""))
    basis = f"正式口径：核心催化后本地A股龙头池相对 {etf} 的5日中位超额收益 {median(excess_values):.2%}"
    return MarketResult(
        median(excess_values),
        basis,
        missing,
        len(excess_values),
        0,
        leader_excess_median_5d=median(excess_values),
        leader_win_rate_5d=win_rate,
        leader_excess_median_10d=median(excess_values_10d) if excess_values_10d else None,
        leader_breadth_20d=breadth,
        pending_count=pending_count,
        mature_event_keys=tuple(mature_event_keys),
    )
