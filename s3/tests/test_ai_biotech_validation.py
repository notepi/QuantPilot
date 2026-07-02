import json
from pathlib import Path

import pandas as pd
import pytest

from s3.validation import ValidationResult, _a_share_lead_stats, _right_side_score, _versions_by_id, _weighted_core, run_ai_biotech_validation
from s3.generate_report import generate_ai_style_report, render_ai_style_report
from s3.style_rotation import StyleAnalysis


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
    payload = json.loads(Path("s3/versions.json").read_text(encoding="utf-8"))
    versions = {item["version_id"]: item for item in payload["versions"]}

    assert payload["active_version_id"] == "AI_GLOBAL_V1"
    assert "TECH_GROWTH_CORE_V1" in versions
    assert "AI_GLOBAL_V1" in versions
    assert versions["TECH_GROWTH_CORE_V1"]["constituents"][0]["symbol"] == "588000.SH"
    assert versions["AI_GLOBAL_V1"]["constituents"] != [{"symbol": "588000.SH", "name": "科创50ETF", "weight": 1.0}]

    for version_id in ["TECH_GROWTH_CORE_V1", "AI_CHINA_V1", "AI_US_V1", "AI_GLOBAL_V1"]:
        total_weight = sum(float(item.get("weight") or 0) for item in versions[version_id]["constituents"])
        assert total_weight == 1.0


def test_weighted_core_uses_fixed_return_weights_and_price_level_does_not_matter():
    dates = ["20260101", "20260102", "20260105"]
    market = pd.DataFrame({
        "symbol": ["A"] * 3 + ["B"] * 3,
        "trade_date": dates + dates,
        "close": [10, 11, 12.1, 1000, 990, 980.1],
    })
    version = {
        "version_id": "TEST_CORE",
        "constituents": [
            {"symbol": "A", "weight": 0.5, "source_table": "market_daily"},
            {"symbol": "B", "weight": 0.5, "source_table": "market_daily"},
        ],
    }

    index, _, missing = _weighted_core(market, pd.DataFrame(), version, {}, pd.Index(dates))

    assert missing == []
    assert index.loc["20260101"] == 100.0
    assert index.loc["20260102"] == 104.5
    assert index.loc["20260105"] == pytest.approx(109.2025)


def test_weighted_core_does_not_reweight_when_core_constituent_missing():
    dates = ["20260101", "20260102", "20260105"]
    market = pd.DataFrame({
        "symbol": ["A"] * 3 + ["B"] * 2,
        "trade_date": dates + ["20260101", "20260105"],
        "close": [10, 11, 12.1, 100, 121],
    })
    version = {
        "version_id": "TEST_CORE",
        "constituents": [
            {"symbol": "A", "weight": 0.5, "source_table": "market_daily"},
            {"symbol": "B", "weight": 0.5, "source_table": "market_daily"},
        ],
    }

    index, _, _ = _weighted_core(market, pd.DataFrame(), version, {}, pd.Index(dates))

    assert pd.isna(index.loc["20260102"])
    assert pd.isna(index.loc["20260105"])


def test_right_side_score_reports_insufficient_data_when_current_feature_coverage_low():
    dates = pd.bdate_range("2026-01-01", periods=80).strftime("%Y%m%d")
    frame = pd.DataFrame(index=dates)
    frame["bio_close"] = [100 * (1.001 ** idx) for idx in range(80)]
    frame["health_close"] = [100 * (1.0005 ** idx) for idx in range(80)]
    frame["bio_vs_health"] = 0.001
    frame["bio_rel_5d"] = 0.005
    frame["bio_rel_10d"] = 0.01
    frame["bio_outperform_streak"] = 1
    frame["s1_total"] = 0.6
    frame["s1_total_change"] = 0.01
    frame["S1-03"] = 0.01
    frame["S1-04"] = 1.0
    frame["S1-05"] = 0.4
    frame["s2_conversion_score"] = 0.55
    frame["bio_amount_ratio_5_20"] = 1.1
    frame["bio_vs_tech"] = 0.002
    frame["bio_vs_ai"] = 0.002
    frame["a_bio_ret"] = 0.001
    frame["bio_ret"] = 0.001
    frame.iloc[-1, frame.columns.get_loc("bio_vs_health")] = pd.NA
    frame.iloc[-1, frame.columns.get_loc("bio_rel_5d")] = pd.NA
    frame.iloc[-1, frame.columns.get_loc("bio_rel_10d")] = pd.NA
    frame.iloc[-1, frame.columns.get_loc("bio_amount_ratio_5_20")] = pd.NA
    frame.iloc[-1, frame.columns.get_loc("bio_vs_tech")] = pd.NA
    frame.iloc[-1, frame.columns.get_loc("bio_vs_ai")] = pd.NA

    result = _right_side_score(frame, {"right_side": {"target_forward_days": 5, "train_ratio": 0.7, "min_current_feature_coverage": 0.75}})

    assert result["score_status"] == "insufficient_data"
    assert result["right_side_score"] == ""
    assert float(result["feature_coverage"]) < 0.75


def test_a_share_same_day_strength_is_not_named_as_lead():
    dates = pd.bdate_range("2026-01-01", periods=20).strftime("%Y%m%d")
    frame = pd.DataFrame(index=dates)
    frame["a_bio_ret"] = 0.02
    frame["bio_ret"] = 0.0
    frame["a_bio_vs_health"] = 0.02
    frame["bio_close"] = [100 + idx for idx in range(20)]
    frame["health_close"] = [100 for _ in range(20)]
    frame["a_bio_close"] = [100 + idx for idx in range(20)]
    frame["ai_core_close"] = [100 + idx for idx in range(20)]
    frame["tech_core_close"] = [100 + idx for idx in range(20)]
    frame["bio_vs_health"] = 0.0
    frame["bio_vs_ai"] = 0.0
    frame["bio_vs_tech"] = 0.0
    frame["bio_amount_ratio_5_20"] = 1.0
    frame["s1_total"] = 0.5

    rows = _a_share_lead_stats(frame, {"forward_windows": [0, 1], "ai_state_thresholds": {"relative_lead_threshold": 0.01}})
    same_day = {row["condition"] for row in rows if row["condition_type"] == "a_share_same_day_relative_strength"}
    lead = {row["condition"] for row in rows if row["condition_type"] == "a_share_lead_signal"}

    assert "589720_same_day_outperformance" in same_day
    assert all("leads" not in condition for condition in same_day)
    assert "589720_positive_signal" in lead


def test_ai_style_report_generates_independently_without_formal_position_action(tmp_path):
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

    report = generate_ai_style_report(market, macro, indicators, s2_scores, config, versions, output)

    text = report.read_text(encoding="utf-8")
    assert report == output / "ai_style_daily_report.md"
    assert "# AI与科技成长风格日报" in text
    assert "20日" in text
    assert "60日" in text
    assert "120日" in text
    assert "250日" in text
    assert "核心指数状态" in text
    assert "context_action_hint" in text
    assert "正式position_action" not in text
    assert "建议：reduce" not in text
    assert "建议：increase" not in text


def test_ai_style_report_uses_structured_relative_values_even_when_not_evidence(tmp_path):
    output = tmp_path / "output"
    output.mkdir()
    pd.DataFrame([{
        "right_side_score": "51.61",
        "score_status": "descriptive_only",
        "feature_coverage": "1.00000000",
    }]).to_csv(output / "ai_biotech_right_side_score.csv", index=False)
    pd.DataFrame([{
        "window": "20",
        "metric": "159567相对AI_CORE超额",
        "mean": "0.01",
        "trading_meaning": "实际交易意义不足",
    }]).to_csv(output / "ai_biotech_window_stats.csv", index=False)
    pd.DataFrame([{
        "condition_type": "a_share_lead_signal",
        "condition": "589720_positive_signal",
        "horizon_days": "1",
        "sample_count": "10",
        "bio_vs_health_win_rate": "0.50",
    }]).to_csv(output / "ai_biotech_a_lead_stats.csv", index=False)

    style = StyleAnalysis(
        report_date="2026-06-24",
        module="TECH_GROWTH_BIOTECH_ROTATION",
        bio_symbol="159567.SZ",
        ai_core_symbol="AI_CORE",
        health_symbol="159557.SZ",
        style_score=0.5,
        style_level="neutral",
        style_regime="same_day_strength",
        data_status="valid",
        missing_reason="",
        total_weight_industry=0.75,
        total_weight_style=0.25,
    )
    validation = ValidationResult(
        report_date="2026-06-24",
        a_share_date="20260624",
        hk_date="20260624",
        us_close_date="20260623",
        ai_core_date="20260623",
        ai_core_version="AI_GLOBAL_TEST",
        tech_growth_core_date="20260624",
        tech_growth_core_version="TECH_GROWTH_CORE_TEST",
        sample_count=120,
        current_ai_state="AI_SINGLE_DOWN",
        current_tech_growth_state="TECH_UP",
        market_state="RISK_ON",
        bio_return=0.0275,
        health_return=0.0292,
        ai_core_return=-0.0108,
        tech_growth_core_return=0.0361,
        bio_vs_health=-0.0017,
        bio_vs_ai=0.0383,
        bio_vs_tech=-0.0086,
        right_side_score=51.61,
        right_side_level="初步右侧",
        score_confidence="high",
        score_status="descriptive_only",
        feature_coverage="1.00000000",
        core_index_status="VALID",
        thesis_state="unchanged",
        position_action="hold",
        strongest_support=["159567当日绝对上涨 2.75%"],
        strongest_opposition=["159567跑输159557 -0.17%", "159567量能低于20日均值，ratio=0.94"],
        report_path=str(output / "ai_biotech_validation_report.md"),
        audit_path=str(output / "ai_biotech_audit_report.md"),
    )

    text = render_ai_style_report(style, validation, output)

    assert "biotech_vs_ai: 159567跑赢AI_CORE 3.83%" in text
    assert "biotech_vs_ai: 未确认" not in text
