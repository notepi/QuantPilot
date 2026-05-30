"""Local S2 scoring based on Excel definitions, event CSVs, and market data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from openpyxl import load_workbook

from s2.event_store import ensure_event_store, load_events
from s2.market_metrics import clinical_conversion_rate, leader_excess_median


DEFAULT_DEFINITIONS = {
    "S2-01": ("BD落地频率", 0.2, ">=1.5x", "0.8x~1.5x", "<0.8x"),
    "S2-02": ("BD金额质量", 0.2, ">=150%", "80%~150%", "<80%"),
    "S2-03": ("龙头业绩兑现率", 0.2, ">=60%", "40%~60%", "<40%"),
    "S2-04": ("数据催化转化率", 0.2, ">=60%", "40%~60%", "<40%"),
    "S2-05": ("龙头接力强度", 0.2, ">=5%", "0%~5%", "<0%"),
}


@dataclass(frozen=True)
class S2Definition:
    code: str
    name: str
    weight: float
    exceed: str
    meet: str
    below: str


@dataclass(frozen=True)
class S2Item:
    code: str
    name: str
    value: float | None
    raw_score: float
    adjusted_score: float
    confidence: float
    rating: str
    basis: str
    source: str
    sample_count: int = 0
    replacement_count: int = 0
    missing: str = ""

    @property
    def score(self) -> float:
        """Backward-compatible official score alias."""
        return self.adjusted_score


@dataclass(frozen=True)
class S2Score:
    trade_date: str
    raw_score: float
    adjusted_score: float
    items: dict[str, S2Item]
    missing_data: str

    @property
    def total_score(self) -> float:
        """Backward-compatible official total score alias."""
        return self.adjusted_score


def load_definitions(excel_path: Path) -> dict[str, S2Definition]:
    if not excel_path.exists():
        return {
            code: S2Definition(code, name, weight, exceed, meet, below)
            for code, (name, weight, exceed, meet, below) in DEFAULT_DEFINITIONS.items()
        }
    wb = load_workbook(excel_path, read_only=True, data_only=True)
    ws = wb["第二阶段"]
    definitions: dict[str, S2Definition] = {}
    for row in ws.iter_rows(min_row=5, values_only=True):
        code = row[1]
        if not code or not str(code).startswith("S2-"):
            continue
        definitions[str(code)] = S2Definition(
            code=str(code),
            name=str(row[3]),
            weight=float(row[11] or 0.2),
            exceed=str(row[8]),
            meet=str(row[9]),
            below=str(row[10]),
        )
    return definitions or {
        code: S2Definition(code, name, weight, exceed, meet, below)
        for code, (name, weight, exceed, meet, below) in DEFAULT_DEFINITIONS.items()
    }


def _parse_date(value: str) -> datetime | None:
    raw = value.replace("-", "")
    try:
        return datetime.strptime(raw, "%Y%m%d")
    except ValueError:
        return None


def _active_since(events: list[dict[str, str]], trade_date: str, days: int) -> list[dict[str, str]]:
    end = _parse_date(trade_date)
    if end is None:
        return []
    start = end - timedelta(days=days)
    active = []
    for event in events:
        event_date = _parse_date(event.get("date", ""))
        if event_date and start <= event_date <= end and event.get("status", "active") == "active":
            active.append(event)
    return active


def _number(value: str) -> float:
    try:
        return float(value or 0)
    except ValueError:
        return 0.0


def _rate_score(value: float | None, exceed: float, meet: float) -> tuple[float, str]:
    if value is None:
        return 0.5, "数据缺失"
    if value >= exceed:
        return 1.0, "超预期"
    if value >= meet:
        return 0.7, "符合预期"
    return 0.4, "低于预期"


def _confidence(sample_count: int, replacement_count: int, missing: str = "") -> float:
    if sample_count <= 0:
        base = 0.45
    elif sample_count < 3:
        base = 0.60
    elif sample_count < 5:
        base = 0.75
    else:
        base = 0.90
    if replacement_count > 0:
        base = min(base, 0.65)
    if missing:
        base = min(base, 0.70)
    return base


def _adjust(raw_score: float, sample_count: int, replacement_count: int = 0, missing: str = "") -> tuple[float, float]:
    confidence = _confidence(sample_count, replacement_count, missing)
    cap = 1.0
    if sample_count < 3:
        cap = min(cap, 0.65)
    elif sample_count < 5:
        cap = min(cap, 0.75)
    if replacement_count > 0:
        cap = min(cap, 0.70)
    if missing and sample_count <= 0:
        cap = min(cap, 0.60)
    return min(raw_score, cap), confidence


def _bd_frequency(defn: S2Definition, bd_events: list[dict[str, str]], trade_date: str) -> S2Item:
    recent = _active_since(bd_events, trade_date, 90)
    last_year = _active_since(bd_events, trade_date, 365)
    if not recent:
        adjusted, confidence = _adjust(0.5, 0, missing="BD事件库为空或无90日事件")
        return S2Item(defn.code, defn.name, None, 0.5, adjusted, confidence, "数据缺失", "近90日事件库无重大BD记录", "bd_events.csv", 0, 0, "BD事件库为空或无90日事件")
    baseline = len(last_year) / 4 if last_year else 0
    if baseline <= 0:
        value = None
        raw_score, rating = 0.7, "符合预期"
        missing = "过去4季度单季平均笔数不足，暂按有重大BD但基准缺失处理"
    else:
        value = len(recent) / baseline
        raw_score, rating = _rate_score(value, 1.5, 0.8)
        missing = ""
    if len(last_year) == len(recent):
        missing = missing or "过去4季度基准不足，当前倍数仅基于事件库现有样本"
    basis = f"近90日重大BD {len(recent)} 笔；过去365日事件库记录 {len(last_year)} 笔"
    adjusted, confidence = _adjust(raw_score, len(recent), missing=missing)
    return S2Item(defn.code, defn.name, value, raw_score, adjusted, confidence, rating, basis, "bd_events.csv", len(recent), 0, missing)


def _bd_quality(defn: S2Definition, bd_events: list[dict[str, str]], trade_date: str) -> S2Item:
    recent = _active_since(bd_events, trade_date, 90)
    if not recent:
        adjusted, confidence = _adjust(0.5, 0, missing="BD金额事件缺失")
        return S2Item(defn.code, defn.name, None, 0.5, adjusted, confidence, "数据缺失", "近90日无可统计BD金额", "bd_events.csv", 0, 0, "BD金额事件缺失")
    amount = sum(_number(e.get("upfront_usd", "")) + _number(e.get("near_term_milestone_usd", "")) for e in recent)
    high_quality = any(e.get("source_tier") == "1" or e.get("importance") == "high" for e in recent)
    if amount <= 0:
        raw_score, rating = (0.7, "符合预期") if high_quality else (0.5, "数据缺失")
        missing = "首付款/近期里程碑金额缺失，无法计算同比"
    else:
        raw_score, rating = (1.0, "超预期") if amount >= 500_000_000 else (0.7, "符合预期")
        missing = "去年同期金额基准不足，V1以近90日金额绝对强度辅助评分"
    adjusted, confidence = _adjust(raw_score, len(recent), missing=missing)
    return S2Item(defn.code, defn.name, amount, raw_score, adjusted, confidence, rating, f"近90日首付款+近期里程碑合计 {amount:,.0f} USD", "bd_events.csv", len(recent), 0, missing)


def _earnings(defn: S2Definition, earnings_events: list[dict[str, str]]) -> S2Item:
    active = [e for e in earnings_events if e.get("status", "active") == "active"]
    if not active:
        adjusted, confidence = _adjust(0.5, 0, missing="业绩事件库为空")
        return S2Item(defn.code, defn.name, None, 0.5, adjusted, confidence, "数据缺失", "事件库无有效业绩/商业化兑现记录", "earnings_events.csv", 0, 0, "业绩事件库为空")
    beats = sum(1 for event in active if event.get("beat", "").lower() in {"true", "1", "yes", "y", "是"})
    value = beats / len(active)
    raw_score, rating = _rate_score(value, 0.60, 0.40)
    adjusted, confidence = _adjust(raw_score, len(active))
    return S2Item(defn.code, defn.name, value, raw_score, adjusted, confidence, rating, f"{beats}/{len(active)} 个已披露龙头事件标记为超预期", "earnings_events.csv", len(active))


def _clinical(defn: S2Definition, clinical_events: list[dict[str, str]], market_data_dir: Path) -> S2Item:
    result = clinical_conversion_rate(clinical_events, market_data_dir)
    raw_score, rating = _rate_score(result.value, 0.60, 0.40)
    adjusted, confidence = _adjust(raw_score, result.sample_count, result.replacement_count, "；".join(result.missing))
    return S2Item(defn.code, defn.name, result.value, raw_score, adjusted, confidence, rating, result.basis, "clinical_events.csv + 本地行情", result.sample_count, result.replacement_count, "；".join(result.missing))


def _leader(defn: S2Definition, catalyst_events: list[dict[str, str]], market_data_dir: Path) -> S2Item:
    result = leader_excess_median(catalyst_events, market_data_dir)
    raw_score, rating = _rate_score(result.value, 0.05, 0.0)
    adjusted, confidence = _adjust(raw_score, result.sample_count, result.replacement_count, "；".join(result.missing))
    return S2Item(defn.code, defn.name, result.value, raw_score, adjusted, confidence, rating, result.basis, "事件库 + 本地行情", result.sample_count, result.replacement_count, "；".join(result.missing))


def score_s2(
    trade_date: str,
    data_dir: Path,
    output_dir: Path,
    market_data_dir: Path,
    excel_path: Path,
    s1_total: float | None = None,
    s1_share_change: float | None = None,
) -> S2Score:
    del output_dir  # Reserved for future score artifacts; scoring itself is pure.
    ensure_event_store(data_dir)
    definitions = load_definitions(excel_path)
    bd_events = load_events(data_dir / "bd_events.csv")
    clinical_events = load_events(data_dir / "clinical_events.csv")
    earnings_events = load_events(data_dir / "earnings_events.csv")
    regulatory_events = load_events(data_dir / "regulatory_events.csv")
    catalyst_events = clinical_events + bd_events + regulatory_events

    items = {
        "S2-01": _bd_frequency(definitions["S2-01"], bd_events, trade_date),
        "S2-02": _bd_quality(definitions["S2-02"], bd_events, trade_date),
        "S2-03": _earnings(definitions["S2-03"], earnings_events),
        "S2-04": _clinical(definitions["S2-04"], clinical_events, market_data_dir),
        "S2-05": _leader(definitions["S2-05"], catalyst_events, market_data_dir),
    }
    total_weight = sum(definitions[code].weight for code in items)
    raw_score = sum(items[code].raw_score * definitions[code].weight for code in items) / total_weight
    adjusted_score = sum(items[code].adjusted_score * definitions[code].weight for code in items) / total_weight
    if s1_total is not None and s1_share_change is not None and s1_total < 0.50 and s1_share_change < 0:
        adjusted_score = min(adjusted_score, 0.75)
    missing = [item.missing for item in items.values() if item.missing]
    return S2Score(trade_date=trade_date, raw_score=raw_score, adjusted_score=adjusted_score, items=items, missing_data="；".join(missing))
