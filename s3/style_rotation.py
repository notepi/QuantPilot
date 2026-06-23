"""Technology-growth versus biotech style-rotation analysis for S3.

The module is intentionally separate from the formal S1/S2 scoring engines. It only
uses market prices to answer whether biotech strength is independent from
technology/growth style.
"""

from __future__ import annotations

import csv
import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MARKET_DAILY = PROJECT_ROOT / "data" / "processed" / "market_daily.csv"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "s3" / "config.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "s3" / "output"
LOGGER = logging.getLogger(__name__)

DEFAULT_CONFIG: dict[str, Any] = {
    "module": "TECH_GROWTH_BIOTECH_ROTATION",
    "symbols": {
        "bio": "159567.SZ",
        "health": "159557.SZ",
        "tech_growth_core": "588000.SH",
        "ai_core": "512760.SH",
        "ai_semi": "512760.SH",
    },
    "periods": [1, 3, 5, 10, 20],
    "flat_thresholds": {"1": 0.005, "3": 0.01, "5": 0.015, "10": 0.02, "20": 0.03},
    "period_weights": {"1": 0.10, "3": 0.15, "5": 0.25, "10": 0.30, "20": 0.20},
    "total_weights": {"industry": 0.75, "style": 0.25},
    "correlation_windows": [10, 20, 60],
    "conditional_windows": [20, 60],
}


@dataclass(frozen=True)
class StylePeriod:
    period: int
    bio_ret: float | None
    ai_ret: float | None
    health_ret: float | None
    bio_vs_ai: float | None
    bio_vs_health: float | None
    independence: float | None
    state: str
    data_status: str


@dataclass(frozen=True)
class ConditionalStats:
    window: int
    bio_avg_ret_when_ai_up: float | None
    bio_avg_ret_when_ai_down: float | None
    bio_excess_when_ai_up: float | None
    bio_excess_when_ai_down: float | None
    sample_ai_up: int
    sample_ai_down: int


@dataclass(frozen=True)
class StyleAnalysis:
    report_date: str
    module: str
    bio_symbol: str
    ai_core_symbol: str
    health_symbol: str
    style_score: float | None
    style_level: str
    style_regime: str
    data_status: str
    missing_reason: str
    total_weight_industry: float
    total_weight_style: float
    periods: list[StylePeriod] = field(default_factory=list)
    correlations: dict[int, float | None] = field(default_factory=dict)
    conditional: dict[int, ConditionalStats] = field(default_factory=dict)
    negative_rotation_flag: bool = False
    chart_cumulative_path: str = ""
    chart_excess_path: str = ""

    def total_score(self, industry_score: float) -> float | None:
        if self.style_score is None:
            return None
        return industry_score * self.total_weight_industry + self.style_score * self.total_weight_style


def load_style_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if not path.exists():
        return config
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return config
    for key, value in payload.items():
        if isinstance(value, dict) and isinstance(config.get(key), dict):
            config[key].update(value)
        else:
            config[key] = value
    return config


def _load_market(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["symbol", "trade_date", "close"])
    df = pd.read_csv(path, dtype={"symbol": str, "trade_date": str})
    if df.empty:
        return pd.DataFrame(columns=["symbol", "trade_date", "close"])
    df = df[["symbol", "trade_date", "close"]].copy()
    df["trade_date"] = df["trade_date"].astype(str).str.replace("-", "", regex=False)
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    df = df.dropna(subset=["symbol", "trade_date", "close"])
    return df.drop_duplicates(["symbol", "trade_date"], keep="last").sort_values(["symbol", "trade_date"])


def _symbol_series(df: pd.DataFrame, symbol: str, report_date: str | None) -> pd.Series:
    rows = df[df["symbol"] == symbol].copy()
    if report_date:
        rows = rows[rows["trade_date"] <= report_date.replace("-", "")]
    rows = rows.sort_values("trade_date").drop_duplicates("trade_date", keep="last")
    return pd.Series(rows["close"].to_numpy(), index=rows["trade_date"].astype(str), dtype="float64")


def _period_return(series: pd.Series, period: int) -> float | None:
    if len(series) <= period:
        return None
    base = float(series.iloc[-period - 1])
    latest = float(series.iloc[-1])
    if base == 0 or math.isnan(base) or math.isnan(latest):
        return None
    return latest / base - 1


def _classify_period(ai_ret: float, bio_ret: float, threshold: float) -> tuple[float, str]:
    bio_vs_ai = bio_ret - ai_ret
    if abs(ai_ret) <= threshold:
        if bio_ret > 0:
            return 0.85, "AI_FLAT_BIO_UP"
        return 0.35, "AI_FLAT_BIO_NOT_UP"
    if ai_ret > threshold:
        if bio_ret > 0 and bio_vs_ai > 0:
            return 1.00, "AI_UP_BIO_UP_BEATS_AI"
        if bio_ret > 0:
            return 0.70, "AI_UP_BIO_UP_LAGS_AI"
        return 0.15, "AI_UP_BIO_DOWN"
    if bio_ret > 0:
        return 0.55, "AI_DOWN_BIO_UP_SEESAW"
    if bio_vs_ai >= 0:
        return 0.35, "AI_DOWN_BIO_DOWN_DEFENSIVE"
    return 0.00, "AI_DOWN_BIO_DOWN_WORSE"


def _style_level(score: float | None) -> str:
    if score is None:
        return "missing"
    if score >= 0.80:
        return "独立主线"
    if score >= 0.60:
        return "主动轮动"
    if score >= 0.40:
        return "跷跷板反弹"
    if score >= 0.20:
        return "被动承接"
    return "AI抽血 / 风险偏好恶化"


def _aligned_returns(left: pd.Series, right: pd.Series) -> pd.DataFrame:
    frame = pd.DataFrame({"left": left.pct_change(), "right": right.pct_change()}).dropna()
    return frame


def _correlation(frame: pd.DataFrame, window: int) -> float | None:
    if len(frame) < max(5, window // 2):
        return None
    sample = frame.tail(window)
    if len(sample) < 2:
        return None
    value = sample["left"].corr(sample["right"])
    return None if pd.isna(value) else float(value)


def _conditional_stats(frame: pd.DataFrame, window: int) -> ConditionalStats:
    sample = frame.tail(window).copy()
    if sample.empty:
        return ConditionalStats(window, None, None, None, None, 0, 0)
    sample["excess"] = sample["left"] - sample["right"]
    ai_up = sample[sample["right"] > 0]
    ai_down = sample[sample["right"] < 0]
    return ConditionalStats(
        window=window,
        bio_avg_ret_when_ai_up=None if ai_up.empty else float(ai_up["left"].mean()),
        bio_avg_ret_when_ai_down=None if ai_down.empty else float(ai_down["left"].mean()),
        bio_excess_when_ai_up=None if ai_up.empty else float(ai_up["excess"].mean()),
        bio_excess_when_ai_down=None if ai_down.empty else float(ai_down["excess"].mean()),
        sample_ai_up=len(ai_up),
        sample_ai_down=len(ai_down),
    )


def _period_by_value(periods: list[StylePeriod], period: int) -> StylePeriod | None:
    for item in periods:
        if item.period == period:
            return item
    return None


def _is_ai_not_weak(item: StylePeriod, thresholds: dict[str, float]) -> bool:
    if item.ai_ret is None:
        return False
    return item.ai_ret >= -float(thresholds.get(str(item.period), 0.0))


def _determine_regime(
    periods: list[StylePeriod],
    thresholds: dict[str, float],
    negative_rotation_flag: bool,
) -> str:
    p5 = _period_by_value(periods, 5)
    p10 = _period_by_value(periods, 10)
    if not p5 or not p10 or p5.data_status != "valid" or p10.data_status != "valid":
        return "NEUTRAL"

    bio_strong = (p5.bio_ret or 0) > 0 and (p10.bio_ret or 0) > 0
    beats_ai = (p5.bio_vs_ai or 0) > 0 and (p10.bio_vs_ai or 0) > 0
    beats_health = (p5.bio_vs_health or 0) > 0 and (p10.bio_vs_health or 0) > 0
    ai_not_weak = _is_ai_not_weak(p5, thresholds) and _is_ai_not_weak(p10, thresholds)
    ai_weak = (p5.ai_ret or 0) < -thresholds.get("5", 0.0) or (p10.ai_ret or 0) < -thresholds.get("10", 0.0)
    ai_strong = (p5.ai_ret or 0) > thresholds.get("5", 0.0) and (p10.ai_ret or 0) > thresholds.get("10", 0.0)

    if ai_not_weak and bio_strong and beats_ai and beats_health:
        return "INDEPENDENT_BIOTECH"
    if ai_weak and bio_strong and beats_health and negative_rotation_flag:
        return "AI_BIOTECH_SEESAW"
    if ai_weak and bio_strong and beats_health:
        return "ACTIVE_ROTATION"
    if ai_strong and ((p5.bio_vs_ai or 0) < 0 and (p10.bio_vs_ai or 0) < 0) and not beats_health:
        return "AI_CROWDING_OUT"
    if ai_weak and (p5.bio_ret or 0) < 0 and (p10.bio_ret or 0) < 0:
        return "GROWTH_RISK_OFF"
    if negative_rotation_flag:
        return "AI_BIOTECH_SEESAW"
    return "NEUTRAL"


def _line_points(values: list[float], width: int, height: int, pad: int, y_min: float, y_max: float) -> str:
    if not values:
        return ""
    if y_max == y_min:
        y_max = y_min + 0.01
    points = []
    span = max(1, len(values) - 1)
    for idx, value in enumerate(values):
        x = pad + idx * (width - 2 * pad) / span
        y = height - pad - (value - y_min) * (height - 2 * pad) / (y_max - y_min)
        points.append(f"{x:.1f},{y:.1f}")
    return " ".join(points)


def _write_svg_chart(path: Path, title: str, series: dict[str, pd.Series]) -> None:
    colors = ["#1f77b4", "#2ca02c", "#d62728", "#9467bd"]
    aligned = pd.concat(series.values(), axis=1, join="inner").dropna()
    aligned.columns = list(series)
    aligned = aligned.tail(60)
    path.parent.mkdir(parents=True, exist_ok=True)
    if aligned.empty:
        path.write_text("<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"760\" height=\"360\"><text x=\"24\" y=\"40\">missing data</text></svg>\n", encoding="utf-8")
        return
    values = [float(v) for v in aligned.to_numpy().flatten()]
    y_min = min(values)
    y_max = max(values)
    if y_min > 0:
        y_min = 0.0
    if y_max < 0:
        y_max = 0.0
    width, height, pad = 760, 360, 54
    zero_y = height - pad - (0 - y_min) * (height - 2 * pad) / (y_max - y_min if y_max != y_min else 0.01)
    parts = [
        f"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width}\" height=\"{height}\" viewBox=\"0 0 {width} {height}\">",
        "<rect width=\"100%\" height=\"100%\" fill=\"white\"/>",
        f"<text x=\"{pad}\" y=\"28\" font-family=\"Arial\" font-size=\"16\" fill=\"#111\">{title}</text>",
        f"<line x1=\"{pad}\" y1=\"{zero_y:.1f}\" x2=\"{width - pad}\" y2=\"{zero_y:.1f}\" stroke=\"#999\" stroke-width=\"1\"/>",
    ]
    for idx, (name, values_series) in enumerate(aligned.items()):
        points = _line_points([float(v) for v in values_series], width, height, pad, y_min, y_max)
        color = colors[idx % len(colors)]
        parts.append(f"<polyline fill=\"none\" stroke=\"{color}\" stroke-width=\"2\" points=\"{points}\"/>")
        parts.append(f"<text x=\"{pad + idx * 150}\" y=\"{height - 14}\" font-family=\"Arial\" font-size=\"12\" fill=\"{color}\">{name}</text>")
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _make_charts(
    output_dir: Path,
    report_date: str,
    bio: pd.Series,
    ai: pd.Series,
    health: pd.Series,
    bio_symbol: str,
    ai_symbol: str,
    health_symbol: str,
) -> tuple[str, str]:
    aligned = pd.concat({bio_symbol: bio, ai_symbol: ai, health_symbol: health}, axis=1, join="inner").dropna().tail(60)
    if aligned.empty:
        return "", ""
    cumulative = aligned / aligned.iloc[0] - 1
    excess = pd.DataFrame({
        f"{bio_symbol}-{ai_symbol}": cumulative[bio_symbol] - cumulative[ai_symbol],
        f"{bio_symbol}-{health_symbol}": cumulative[bio_symbol] - cumulative[health_symbol],
    }, index=cumulative.index)
    chart_dir = output_dir / "charts"
    cumulative_path = chart_dir / f"style_cumulative_{report_date}.svg"
    excess_path = chart_dir / f"style_excess_{report_date}.svg"
    _write_svg_chart(cumulative_path, "60 trading days cumulative returns", {column: cumulative[column] for column in cumulative.columns})
    _write_svg_chart(excess_path, "60 trading days cumulative excess", {column: excess[column] for column in excess.columns})
    return str(cumulative_path), str(excess_path)


def calculate_style_analysis(
    market_daily_path: Path = DEFAULT_MARKET_DAILY,
    config_path: Path = DEFAULT_CONFIG_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    report_date: str | None = None,
) -> StyleAnalysis:
    config = load_style_config(config_path)
    symbols = config["symbols"]
    bio_symbol = str(symbols["bio"])
    ai_symbol = str(symbols.get("tech_growth_core") or symbols["ai_core"])
    health_symbol = str(symbols["health"])
    clean_report_date = (report_date or "").replace("-", "")

    df = _load_market(market_daily_path)
    bio = _symbol_series(df, bio_symbol, clean_report_date or None)
    ai = _symbol_series(df, ai_symbol, clean_report_date or None)
    health = _symbol_series(df, health_symbol, clean_report_date or None)
    latest_dates = [series.index[-1] for series in [bio, ai, health] if not series.empty]
    effective_report_date = report_date or (max(latest_dates) if latest_dates else "")

    if bio.empty or ai.empty or health.empty:
        missing = []
        if bio.empty:
            missing.append(bio_symbol)
        if ai.empty:
            missing.append(ai_symbol)
        if health.empty:
            missing.append(health_symbol)
        LOGGER.warning("S2_STYLE missing required symbols: %s", ",".join(missing))
        return StyleAnalysis(
            report_date=effective_report_date,
            module=str(config.get("module") or "TECH_GROWTH_BIOTECH_ROTATION"),
            bio_symbol=bio_symbol,
            ai_core_symbol=ai_symbol,
            health_symbol=health_symbol,
            style_score=None,
            style_level="missing",
            style_regime="NEUTRAL",
            data_status="missing",
            missing_reason="missing symbols: " + ",".join(missing),
            total_weight_industry=float(config["total_weights"]["industry"]),
            total_weight_style=float(config["total_weights"]["style"]),
        )

    periods: list[StylePeriod] = []
    thresholds = {str(k): float(v) for k, v in config["flat_thresholds"].items()}
    weights = {str(k): float(v) for k, v in config["period_weights"].items()}
    for period in [int(item) for item in config["periods"]]:
        bio_ret = _period_return(bio, period)
        ai_ret = _period_return(ai, period)
        health_ret = _period_return(health, period)
        if bio_ret is None or ai_ret is None or health_ret is None:
            periods.append(StylePeriod(period, bio_ret, ai_ret, health_ret, None, None, None, "MISSING", "missing"))
            continue
        bio_vs_ai = bio_ret - ai_ret
        bio_vs_health = bio_ret - health_ret
        score, state = _classify_period(ai_ret, bio_ret, thresholds[str(period)])
        periods.append(StylePeriod(period, bio_ret, ai_ret, health_ret, bio_vs_ai, bio_vs_health, score, state, "valid"))

    weighted = [(item.independence, weights.get(str(item.period), 0.0)) for item in periods if item.independence is not None]
    available_weight = sum(weight for _, weight in weighted)
    style_score = None if available_weight <= 0 else sum((score or 0.0) * weight for score, weight in weighted) / available_weight

    returns = _aligned_returns(bio, ai)
    correlations = {int(window): _correlation(returns, int(window)) for window in config["correlation_windows"]}
    conditional = {int(window): _conditional_stats(returns, int(window)) for window in config["conditional_windows"]}
    c20 = conditional.get(20)
    corr20 = correlations.get(20)
    negative_rotation_flag = bool(
        corr20 is not None
        and corr20 < -0.3
        and c20 is not None
        and c20.bio_avg_ret_when_ai_up is not None
        and c20.bio_avg_ret_when_ai_down is not None
        and c20.bio_avg_ret_when_ai_up < c20.bio_avg_ret_when_ai_down
    )
    regime = _determine_regime(periods, thresholds, negative_rotation_flag)
    cumulative_path, excess_path = _make_charts(output_dir, effective_report_date, bio, ai, health, bio_symbol, ai_symbol, health_symbol)
    missing_periods = [str(item.period) for item in periods if item.data_status != "valid"]
    LOGGER.info(
        "S2_STYLE calculated: report_date=%s score=%s regime=%s data_status=%s",
        effective_report_date,
        f"{style_score:.4f}" if style_score is not None else "missing",
        regime,
        "valid" if not missing_periods else "partial",
    )
    return StyleAnalysis(
        report_date=effective_report_date,
        module=str(config.get("module") or "TECH_GROWTH_BIOTECH_ROTATION"),
        bio_symbol=bio_symbol,
        ai_core_symbol=ai_symbol,
        health_symbol=health_symbol,
        style_score=style_score,
        style_level=_style_level(style_score),
        style_regime=regime,
        data_status="valid" if not missing_periods else "partial",
        missing_reason="" if not missing_periods else "missing periods: " + ",".join(missing_periods),
        total_weight_industry=float(config["total_weights"]["industry"]),
        total_weight_style=float(config["total_weights"]["style"]),
        periods=periods,
        correlations=correlations,
        conditional=conditional,
        negative_rotation_flag=negative_rotation_flag,
        chart_cumulative_path=cumulative_path,
        chart_excess_path=excess_path,
    )


def upsert_style_outputs(output_dir: Path, report_date: str, analysis: StyleAnalysis, industry_score: float) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    score_path = output_dir / "s2_style_scores.csv"
    score_fields = [
        "date", "module", "bio_symbol", "ai_core_symbol", "health_symbol", "s2_industry",
        "s2_style", "s2_total", "style_level", "style_regime", "data_status", "missing_reason",
        "corr_10d", "corr_20d", "corr_60d", "negative_rotation_flag",
        "bio_avg_ret_when_ai_up_20d", "bio_avg_ret_when_ai_down_20d",
        "bio_excess_when_ai_up_20d", "bio_excess_when_ai_down_20d",
        "bio_avg_ret_when_ai_up_60d", "bio_avg_ret_when_ai_down_60d",
        "bio_excess_when_ai_up_60d", "bio_excess_when_ai_down_60d",
        "chart_cumulative_path", "chart_excess_path",
    ]
    rows: list[dict[str, str]] = []
    if score_path.exists():
        with score_path.open(newline="", encoding="utf-8") as fh:
            rows = [row for row in csv.DictReader(fh) if row.get("date") != report_date]
    c20 = analysis.conditional.get(20) or ConditionalStats(20, None, None, None, None, 0, 0)
    c60 = analysis.conditional.get(60) or ConditionalStats(60, None, None, None, None, 0, 0)
    rows.append({
        "date": report_date,
        "module": analysis.module,
        "bio_symbol": analysis.bio_symbol,
        "ai_core_symbol": analysis.ai_core_symbol,
        "health_symbol": analysis.health_symbol,
        "s2_industry": f"{industry_score:.8f}",
        "s2_style": _float_csv(analysis.style_score),
        "s2_total": _float_csv(analysis.total_score(industry_score)),
        "style_level": analysis.style_level,
        "style_regime": analysis.style_regime,
        "data_status": analysis.data_status,
        "missing_reason": analysis.missing_reason,
        "corr_10d": _float_csv(analysis.correlations.get(10)),
        "corr_20d": _float_csv(analysis.correlations.get(20)),
        "corr_60d": _float_csv(analysis.correlations.get(60)),
        "negative_rotation_flag": str(analysis.negative_rotation_flag).lower(),
        "bio_avg_ret_when_ai_up_20d": _float_csv(c20.bio_avg_ret_when_ai_up),
        "bio_avg_ret_when_ai_down_20d": _float_csv(c20.bio_avg_ret_when_ai_down),
        "bio_excess_when_ai_up_20d": _float_csv(c20.bio_excess_when_ai_up),
        "bio_excess_when_ai_down_20d": _float_csv(c20.bio_excess_when_ai_down),
        "bio_avg_ret_when_ai_up_60d": _float_csv(c60.bio_avg_ret_when_ai_up),
        "bio_avg_ret_when_ai_down_60d": _float_csv(c60.bio_avg_ret_when_ai_down),
        "bio_excess_when_ai_up_60d": _float_csv(c60.bio_excess_when_ai_up),
        "bio_excess_when_ai_down_60d": _float_csv(c60.bio_excess_when_ai_down),
        "chart_cumulative_path": analysis.chart_cumulative_path,
        "chart_excess_path": analysis.chart_excess_path,
    })
    with score_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=score_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in score_fields} for row in sorted(rows, key=lambda row: row["date"]))

    period_path = output_dir / "s2_style_period_scores.csv"
    period_fields = [
        "date", "period", "bio_ret", "ai_ret", "health_ret", "bio_vs_ai",
        "bio_vs_health", "independence", "state", "data_status",
    ]
    period_rows: list[dict[str, str]] = []
    if period_path.exists():
        with period_path.open(newline="", encoding="utf-8") as fh:
            period_rows = [row for row in csv.DictReader(fh) if row.get("date") != report_date]
    for item in analysis.periods:
        period_rows.append({
            "date": report_date,
            "period": str(item.period),
            "bio_ret": _float_csv(item.bio_ret),
            "ai_ret": _float_csv(item.ai_ret),
            "health_ret": _float_csv(item.health_ret),
            "bio_vs_ai": _float_csv(item.bio_vs_ai),
            "bio_vs_health": _float_csv(item.bio_vs_health),
            "independence": _float_csv(item.independence),
            "state": item.state,
            "data_status": item.data_status,
        })
    with period_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=period_fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in period_fields} for row in sorted(period_rows, key=lambda row: (row["date"], int(row["period"]))))


def _float_csv(value: float | None) -> str:
    return "" if value is None else f"{value:.8f}"
