import json
from pathlib import Path

import pandas as pd
import pytest

from s3.style_rotation import calculate_style_analysis


def _write_market(path: Path, closes: dict[str, list[float]]) -> None:
    rows = []
    dates = [f"202601{day:02d}" for day in range(1, len(next(iter(closes.values()))) + 1)]
    for symbol, values in closes.items():
        for trade_date, close in zip(dates, values, strict=True):
            rows.append({
                "symbol": symbol,
                "trade_date": trade_date,
                "open": close,
                "high": close,
                "low": close,
                "close": close,
            })
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "module": "AI_BIOTECH_ROTATION",
                "symbols": {"bio": "159567.SZ", "health": "159557.SZ", "ai_core": "588000.SH"},
                "periods": [1, 3, 5, 10, 20],
                "flat_thresholds": {"1": 0.005, "3": 0.01, "5": 0.015, "10": 0.02, "20": 0.03},
                "period_weights": {"1": 0.1, "3": 0.15, "5": 0.25, "10": 0.3, "20": 0.2},
                "total_weights": {"industry": 0.75, "style": 0.25},
                "correlation_windows": [10, 20, 60],
                "conditional_windows": [20, 60],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_style_rotation_identifies_independent_biotech(tmp_path):
    market = tmp_path / "market_daily.csv"
    config = tmp_path / "style_config.json"
    _write_config(config)
    _write_market(
        market,
        {
            "159567.SZ": [100 * (1.006 ** idx) for idx in range(30)],
            "588000.SH": [100 * (1.002 ** idx) for idx in range(30)],
            "159557.SZ": [100 * (1.001 ** idx) for idx in range(30)],
        },
    )

    result = calculate_style_analysis(market, config, tmp_path / "output", report_date="2026-01-30")

    assert result.style_score == pytest.approx(0.925)
    assert result.style_regime == "INDEPENDENT_BIOTECH"
    assert result.total_score(0.6) == pytest.approx(0.68125)
    assert Path(result.chart_cumulative_path).exists()
    assert Path(result.chart_excess_path).exists()


def test_style_rotation_scores_ai_down_bio_up_as_seesaw_period(tmp_path):
    market = tmp_path / "market_daily.csv"
    config = tmp_path / "style_config.json"
    _write_config(config)
    _write_market(
        market,
        {
            "159567.SZ": [100 * (1.004 ** idx) for idx in range(30)],
            "588000.SH": [100 * (0.996 ** idx) for idx in range(30)],
            "159557.SZ": [100 * (1.001 ** idx) for idx in range(30)],
        },
    )

    result = calculate_style_analysis(market, config, tmp_path / "output", report_date="2026-01-30")
    period_5d = next(item for item in result.periods if item.period == 5)

    assert period_5d.state == "AI_DOWN_BIO_UP_SEESAW"
    assert period_5d.independence == pytest.approx(0.55)
    assert result.style_score == pytest.approx(0.58)
    assert result.style_regime in {"ACTIVE_ROTATION", "AI_BIOTECH_SEESAW"}
