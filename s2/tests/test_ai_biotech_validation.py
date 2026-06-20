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
                "tech_growth_core_version_id": "TECH_GROWTH_CORE_TEST",
                "ai_core_version_id": "AI_GLOBAL_TEST",
                "adjustment_policy": "unadjusted_close",
                "symbols": {
                    "bio": "159567.SZ",
                    "health": "159557.SZ",
                    "tech_growth_core": "588000.SH",
                    "ai_core": "512760.SH",
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
                "active_version_id": "AI_GLOBAL_TEST",
                "tech_growth_core_version_id": "TECH_GROWTH_CORE_TEST",
                "versions": [
                    {
                        "version_id": "TECH_GROWTH_CORE_TEST",
                        "effective_date": "2026-01-01",
                        "market_scope": "China A-share technology proxy",
                        "core_type": "TECH_GROWTH_CORE",
                        "constituents": [{"symbol": "588000.SH", "weight": 1.0, "source_table": "market_daily"}],
                        "data_source": "test",
                        "rebalance_rule": "fixed",
                        "adjustment_policy": "unadjusted_close",
                    },
                    {
                        "version_id": "AI_CHINA_TEST",
                        "effective_date": "2026-01-01",
                        "market_scope": "China AI hardware proxy",
                        "core_type": "AI_CORE",
                        "constituents": [{"symbol": "512760.SH", "weight": 1.0, "source_table": "market_daily"}],
                        "data_source": "test",
                        "rebalance_rule": "fixed",
                        "adjustment_policy": "unadjusted_close",
                    },
                    {
                        "version_id": "AI_US_TEST",
                        "effective_date": "2026-01-01",
                        "market_scope": "US AI proxy",
                        "core_type": "AI_CORE",
                        "constituents": [
                            {"symbol": "SMH", "weight": 0.45, "source_table": "macro_market_daily"},
                            {"symbol": "SOXX", "weight": 0.35, "source_table": "macro_market_daily"},
                            {"symbol": "QQQ", "weight": 0.20, "source_table": "macro_market_daily"}
                        ],
                        "data_source": "test",
                        "rebalance_rule": "fixed",
                        "adjustment_policy": "unadjusted_close",
                    },
                    {
                        "version_id": "AI_GLOBAL_TEST",
                        "effective_date": "2026-01-01",
                        "market_scope": "Global AI proxy",
                        "core_type": "AI_CORE",
                        "constituents": [
                            {"version_ref": "AI_CHINA_TEST", "weight": 0.45},
                            {"version_ref": "AI_US_TEST", "weight": 0.55}
                        ],
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


def _write_macro(path: Path, days: int = 280) -> None:
    dates = pd.bdate_range("2024-12-31", periods=days).strftime("%Y%m%d").tolist()
    rows = []
    symbols = {"SMH": 1.003, "SOXX": 1.0025, "QQQ": 1.0015}
    for symbol, drift in symbols.items():
        for idx, trade_date in enumerate(dates):
            rows.append({
                "symbol": symbol,
                "trade_date": trade_date,
                "close": 100 * (drift ** idx),
                "source_status": "success",
            })
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
    macro = tmp_path / "macro_market_daily.csv"
    indicators = tmp_path / "indicators"
    s2_scores = tmp_path / "s2_scores.csv"
    config = tmp_path / "style_config.json"
    versions = tmp_path / "ai_core_versions.json"
    output = tmp_path / "output"
    _write_market(market)
    _write_macro(macro)
    _write_s1(indicators)
    _write_config(config)
    _write_ai_versions(versions)
    pd.DataFrame(
        [{"date": "2026-01-01", "s2_adjusted_score": 0.6, "s2_event_score": 0.6, "s2_conversion_score": 0.5}]
    ).to_csv(s2_scores, index=False)

    result = run_ai_biotech_validation(market, indicators, s2_scores, config, versions, output, macro_market_daily_path=macro)

    assert result.ai_core_version == "AI_GLOBAL_TEST"
    assert result.tech_growth_core_version == "TECH_GROWTH_CORE_TEST"
    assert result.sample_count == 250
    assert (output / "ai_biotech_validation_report.md").exists()
    assert (output / "ai_biotech_audit_report.md").exists()
    period_rows = pd.read_csv(output / "ai_biotech_window_stats.csv")
    assert set(period_rows["window"].astype(str)) == {"20", "60", "120", "250"}
    assert "159567相对TECH_GROWTH_CORE超额" in set(period_rows["metric"])
    assert "159567相对AI_CORE超额" in set(period_rows["metric"])
    audit = (output / "ai_biotech_audit_report.md").read_text(encoding="utf-8")
    assert "重复日期" in audit
    assert "588000.SH代表科创50科技成长风格，不是纯AI指数" in audit


def test_ai_biotech_validation_keeps_missing_out_of_samples(tmp_path):
    market = tmp_path / "market_daily.csv"
    macro = tmp_path / "macro_market_daily.csv"
    indicators = tmp_path / "indicators"
    s2_scores = tmp_path / "s2_scores.csv"
    config = tmp_path / "style_config.json"
    versions = tmp_path / "ai_core_versions.json"
    output = tmp_path / "output"
    _write_market(market, days=80)
    _write_macro(macro, days=80)
    df = pd.read_csv(market)
    df.loc[(df["symbol"] == "159567.SZ") & (df.index % 17 == 0), "close"] = ""
    df.to_csv(market, index=False)
    _write_s1(indicators, days=80)
    _write_config(config)
    _write_ai_versions(versions)
    pd.DataFrame(columns=["date", "s2_adjusted_score", "s2_event_score", "s2_conversion_score"]).to_csv(s2_scores, index=False)

    result = run_ai_biotech_validation(market, indicators, s2_scores, config, versions, output, macro_market_daily_path=macro)
    period_rows = pd.read_csv(output / "ai_biotech_window_stats.csv")
    bio_60 = period_rows[(period_rows["window"] == 60) & (period_rows["metric"] == "159567绝对收益")].iloc[0]

    assert result.sample_count < 80
    assert bio_60["valid_samples"] <= min(60, result.sample_count)


def test_ai_core_is_not_single_588000_and_us_mapping_has_no_future_function(tmp_path):
    market = tmp_path / "market_daily.csv"
    macro = tmp_path / "macro_market_daily.csv"
    indicators = tmp_path / "indicators"
    s2_scores = tmp_path / "s2_scores.csv"
    config = tmp_path / "style_config.json"
    versions = tmp_path / "ai_core_versions.json"
    output = tmp_path / "output"
    _write_market(market, days=80)
    _write_macro(macro, days=80)
    _write_s1(indicators, days=80)
    _write_config(config)
    _write_ai_versions(versions)
    pd.DataFrame(columns=["date", "s2_adjusted_score", "s2_event_score", "s2_conversion_score"]).to_csv(s2_scores, index=False)

    result = run_ai_biotech_validation(market, indicators, s2_scores, config, versions, output, macro_market_daily_path=macro)
    report = (output / "ai_biotech_validation_report.md").read_text(encoding="utf-8")
    right_side = pd.read_csv(output / "ai_biotech_right_side_score.csv").iloc[0]

    assert result.ai_core_version == "AI_GLOBAL_TEST"
    assert result.ai_core_version != "TECH_GROWTH_CORE_TEST"
    assert "AI_CORE版本：AI_GLOBAL_TEST" in report
    assert "TECH_GROWTH_CORE版本：TECH_GROWTH_CORE_TEST" in report
    assert "AI_CORE版本：CN_AI_CORE_TEST" not in report
    assert str(result.us_close_date) < str(result.a_share_date)
    assert "TECH_GROWTH_CORE and AI_CORE" in right_side["duplicate_counting_check"]


def test_real_ai_core_versions_split_tech_growth_from_ai_core():
    payload = json.loads(Path("s2/ai_core_versions.json").read_text(encoding="utf-8"))
    versions = {item["version_id"]: item for item in payload["versions"]}

    assert payload["active_version_id"] == "AI_GLOBAL_V1"
    assert "TECH_GROWTH_CORE_V1" in versions
    assert "AI_GLOBAL_V1" in versions
    assert versions["TECH_GROWTH_CORE_V1"]["constituents"][0]["symbol"] == "588000.SH"
    assert versions["AI_GLOBAL_V1"]["constituents"] != [{"symbol": "588000.SH", "name": "科创50ETF", "weight": 1.0}]

    for version_id in ["TECH_GROWTH_CORE_V1", "AI_CHINA_V1", "AI_US_V1", "AI_GLOBAL_V1"]:
        total_weight = sum(float(item.get("weight") or 0) for item in versions[version_id]["constituents"])
        assert total_weight == 1.0
