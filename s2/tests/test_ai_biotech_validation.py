import json
from pathlib import Path

import pandas as pd

from s2.ai_biotech_validation import run_ai_biotech_validation


def _write_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "enabled": True,
                "max_history_trading_days": 250,
                "ai_core_version_id": "CN_AI_CORE_TEST",
                "adjustment_policy": "unadjusted_close",
                "symbols": {
                    "bio": "159567.SZ",
                    "health": "159557.SZ",
                    "ai_core": "588000.SH",
                    "ai_semi": "512760.SH",
                    "a_bio_temperature": "589720.SH",
                    "a_health_benchmark": "512170.SH",
                },
                "validation_windows": [20, 60, 120, 250],
                "forward_windows": [0, 1, 2, 3, 5],
                "right_side": {"target_forward_days": 5, "train_ratio": 0.7},
                "ai_state_thresholds": {
                    "daily_move": 0.005,
                    "strong_move": 0.015,
                    "sideways_abs_5d": 0.02,
                    "high_level_percentile": 0.75,
                    "volume_stall_ratio": 1.2,
                    "risk_on_daily": 0.003,
                    "risk_off_daily": -0.003,
                    "relative_lead_threshold": 0.01,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _write_ai_versions(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "active_version_id": "CN_AI_CORE_TEST",
                "versions": [
                    {
                        "version_id": "CN_AI_CORE_TEST",
                        "effective_date": "2026-01-01",
                        "market_scope": "China A-share technology proxy",
                        "constituents": [{"symbol": "588000.SH", "weight": 1.0}],
                        "data_source": "test",
                        "rebalance_rule": "fixed",
                        "adjustment_policy": "unadjusted_close",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _write_market(path: Path, days: int = 280) -> None:
    dates = pd.bdate_range("2025-01-01", periods=days).strftime("%Y%m%d").tolist()
    rows = []
    symbols = {
        "159567.SZ": 1.001,
        "159557.SZ": 1.0005,
        "588000.SH": 1.002,
        "512760.SH": 1.0015,
        "589720.SH": 1.0008,
        "512170.SH": 1.0004,
    }
    for symbol, drift in symbols.items():
        for idx, trade_date in enumerate(dates):
            close = 100 * (drift ** idx)
            rows.append({
                "symbol": symbol,
                "trade_date": trade_date,
                "close": close,
                "amount": 1000 + idx,
                "volume": 100 + idx,
                "adjusted_type": "none",
                "source_name": "test",
            })
    rows.append(dict(rows[-1]))
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_s1(indicators: Path, days: int = 280) -> None:
    indicators.mkdir()
    dates = pd.bdate_range("2025-01-01", periods=days).strftime("%Y%m%d").tolist()
    for idx, trade_date in enumerate(dates):
        payload = {
            "trade_date": trade_date,
            "total_score": 0.55 + (0.1 if idx % 20 > 10 else 0),
            "indicator_results": [
                {"code": "S1-01", "value": 0.5},
                {"code": "S1-02", "value": 0.02},
                {"code": "S1-03", "value": 0.01 if idx % 10 else -0.01},
                {"code": "S1-04", "value": 0.95},
                {"code": "S1-05", "value": 0.35 + (idx % 5) / 100},
                {"code": "S1-06", "value": 0.01},
            ],
        }
        (indicators / f"{trade_date}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_ai_biotech_validation_caps_history_and_writes_outputs(tmp_path):
    market = tmp_path / "market_daily.csv"
    indicators = tmp_path / "indicators"
    s2_scores = tmp_path / "s2_scores.csv"
    config = tmp_path / "style_config.json"
    versions = tmp_path / "ai_core_versions.json"
    output = tmp_path / "output"
    _write_market(market)
    _write_s1(indicators)
    _write_config(config)
    _write_ai_versions(versions)
    pd.DataFrame(
        [{"date": "2026-01-01", "s2_adjusted_score": 0.6, "s2_event_score": 0.6, "s2_conversion_score": 0.5}]
    ).to_csv(s2_scores, index=False)

    result = run_ai_biotech_validation(market, indicators, s2_scores, config, versions, output)

    assert result.ai_core_version == "CN_AI_CORE_TEST"
    assert result.sample_count == 250
    assert (output / "ai_biotech_validation_report.md").exists()
    assert (output / "ai_biotech_audit_report.md").exists()
    period_rows = pd.read_csv(output / "ai_biotech_window_stats.csv")
    assert set(period_rows["window"].astype(str)) == {"20", "60", "120", "250"}
    audit = (output / "ai_biotech_audit_report.md").read_text(encoding="utf-8")
    assert "重复日期" in audit


def test_ai_biotech_validation_keeps_missing_out_of_samples(tmp_path):
    market = tmp_path / "market_daily.csv"
    indicators = tmp_path / "indicators"
    s2_scores = tmp_path / "s2_scores.csv"
    config = tmp_path / "style_config.json"
    versions = tmp_path / "ai_core_versions.json"
    output = tmp_path / "output"
    _write_market(market, days=80)
    df = pd.read_csv(market)
    df.loc[(df["symbol"] == "159567.SZ") & (df.index % 17 == 0), "close"] = ""
    df.to_csv(market, index=False)
    _write_s1(indicators, days=80)
    _write_config(config)
    _write_ai_versions(versions)
    pd.DataFrame(columns=["date", "s2_adjusted_score", "s2_event_score", "s2_conversion_score"]).to_csv(s2_scores, index=False)

    result = run_ai_biotech_validation(market, indicators, s2_scores, config, versions, output)
    period_rows = pd.read_csv(output / "ai_biotech_window_stats.csv")
    bio_60 = period_rows[(period_rows["window"] == 60) & (period_rows["metric"] == "159567绝对收益")].iloc[0]

    assert result.sample_count < 80
    assert bio_60["valid_samples"] <= min(60, result.sample_count)
