import csv
import json
from pathlib import Path

import pytest

from s2.event_store import append_events, ensure_event_store, load_events
from s2.generate_s2_report import generate_report
from s2.s1_reader import load_latest_s1
from s2.scoring import score_s2


def write_json(path: Path, data: dict):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def s1_payload(trade_date: str, score: float):
    return {
        "phase": "第一阶段",
        "trade_date": trade_date,
        "total_score": score,
        "expectation_level": "低于预期" if score < 0.6 else "符合预期",
        "indicator_results": [
            {"code": "S1-01", "name": "资金回流连续性", "value": 0.0, "expectation": "低于预期"},
            {"code": "S1-02", "name": "ETF份额变化", "value": -0.02, "expectation": "低于预期"},
        ],
    }


def test_load_latest_s1_reads_recent_records(tmp_path):
    indicators = tmp_path / "indicators"
    indicators.mkdir()
    write_json(indicators / "20260528.json", s1_payload("20260528", 0.63))
    write_json(indicators / "20260529.json", s1_payload("20260529", 0.46))

    latest, recent = load_latest_s1(indicators, limit=2)

    assert latest.trade_date == "20260529"
    assert latest.total_score == pytest.approx(0.46)
    assert [record.trade_date for record in recent] == ["20260528", "20260529"]


def test_event_store_deduplicates_by_stable_key(tmp_path):
    data_dir = tmp_path / "data"
    ensure_event_store(data_dir)
    event = {
        "date": "2026-05-29",
        "company": "信达生物",
        "ticker": "01801.HK",
        "asset": "IBI363",
        "partner": "Pfizer",
        "upfront_usd": "650000000",
        "total_value_usd": "10500000000",
        "source_url": "https://example.com/innovent-pfizer",
        "source_tier": "1",
        "importance": "high",
        "status": "active",
        "note": "重大BD",
    }

    append_events(data_dir / "bd_events.csv", [event])
    append_events(data_dir / "bd_events.csv", [event])
    rows = load_events(data_dir / "bd_events.csv")

    assert len(rows) == 1
    assert rows[0]["company"] == "信达生物"


def test_score_s2_uses_events_and_marks_missing_market_data(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    ensure_event_store(data_dir)
    append_events(
        data_dir / "bd_events.csv",
        [
            {
                "date": "2026-05-01",
                "company": "恒瑞医药",
                "ticker": "600276.SH",
                "asset": "portfolio",
                "partner": "BMS",
                "upfront_usd": "600000000",
                "total_value_usd": "15200000000",
                "source_url": "https://example.com/hengrui-bms",
                "source_tier": "1",
                "importance": "high",
                "status": "active",
                "note": "重大BD",
            }
        ],
    )

    result = score_s2(
        trade_date="20260529",
        data_dir=data_dir,
        output_dir=output_dir,
        market_data_dir=tmp_path / "raw",
        excel_path=Path("docs/创新药_第一阶段_v2_claude.xlsx"),
    )

    assert result.adjusted_score > 0
    assert result.items["S2-01"].value is not None
    assert result.items["S2-01"].raw_score >= result.items["S2-01"].adjusted_score
    assert "数据缺失" in result.missing_data


def test_adjusted_score_caps_small_samples_and_replacements(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    market_dir = Path("data/raw")
    ensure_event_store(data_dir)
    append_events(
        data_dir / "bd_events.csv",
        [
            {
                "date": "2026-05-28",
                "company": "信达生物",
                "ticker": "01801.HK",
                "asset": "oncology programs",
                "partner": "Pfizer",
                "upfront_usd": "650000000",
                "total_value_usd": "10500000000",
                "source_url": "https://example.com/innovent",
                "source_tier": "1",
                "importance": "high",
                "status": "active",
                "note": "重大BD",
            },
            {
                "date": "2026-05-12",
                "company": "恒瑞医药",
                "ticker": "600276.SH",
                "asset": "portfolio",
                "partner": "BMS",
                "upfront_usd": "600000000",
                "near_term_milestone_usd": "350000000",
                "total_value_usd": "15200000000",
                "source_url": "https://example.com/hengrui",
                "source_tier": "1",
                "importance": "high",
                "status": "active",
                "note": "重大BD",
            },
        ],
    )
    append_events(
        data_dir / "clinical_events.csv",
        [
            {
                "date": "2026-05-26",
                "company": "康方生物",
                "ticker": "9926.HK",
                "conference": "ASCO 2026",
                "asset": "ivonescimab",
                "source_url": "https://example.com/akeso",
                "source_tier": "2",
                "importance": "high",
                "status": "active",
                "note": "ASCO plenary",
            }
        ],
    )

    result = score_s2(
        trade_date="20260529",
        data_dir=data_dir,
        output_dir=output_dir,
        market_data_dir=market_dir,
        excel_path=Path("docs/创新药_第一阶段_v2_claude.xlsx"),
        s1_total=0.46,
        s1_share_change=-0.02,
    )

    assert result.items["S2-01"].raw_score == pytest.approx(1.0)
    assert result.items["S2-01"].adjusted_score <= 0.65
    assert result.items["S2-04"].replacement_count >= 1
    assert result.items["S2-04"].adjusted_score <= 0.70
    assert result.adjusted_score <= 0.75


def test_s2_v1_quality_controls_and_proxy_breakdown(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "output"
    market_dir = Path("data/raw")
    ensure_event_store(data_dir)
    append_events(
        data_dir / "bd_events.csv",
        [
            {
                "date": "2026-05-28",
                "company": "信达生物",
                "ticker": "01801.HK",
                "asset": "oncology programs",
                "partner": "Pfizer",
                "upfront_usd": "650000000",
                "near_term_milestone_usd": "100000000",
                "total_value_usd": "10500000000",
                "source_url": "https://example.com/innovent",
                "source_tier": "1",
                "importance": "high",
                "status": "active",
                "note": "重大BD",
            },
            {
                "date": "2026-05-12",
                "company": "恒瑞医药",
                "ticker": "600276.SH",
                "asset": "portfolio",
                "partner": "BMS",
                "upfront_usd": "600000000",
                "near_term_milestone_usd": "350000000",
                "total_value_usd": "15200000000",
                "source_url": "https://example.com/hengrui",
                "source_tier": "1",
                "importance": "high",
                "status": "active",
                "note": "重大BD",
            },
        ],
    )
    append_events(
        data_dir / "clinical_events.csv",
        [
            {
                "date": "2026-05-26",
                "company": "康方生物",
                "ticker": "9926.HK",
                "conference": "ASCO 2026",
                "asset": "ivonescimab",
                "source_url": "https://example.com/akeso",
                "source_tier": "2",
                "importance": "high",
                "status": "active",
                "note": "ASCO plenary",
            }
        ],
    )

    result = score_s2(
        trade_date="20260529",
        data_dir=data_dir,
        output_dir=output_dir,
        market_data_dir=market_dir,
        excel_path=Path("docs/创新药_第一阶段_v2_claude.xlsx"),
    )

    assert result.items["S2-01"].event_db_maturity == "low"
    assert result.items["S2-01"].adjusted_score <= 0.70
    assert result.items["S2-02"].raw_bd_amount == pytest.approx(1_700_000_000)
    assert result.items["S2-02"].quality_bd_amount == pytest.approx(1_475_000_000)
    assert result.items["S2-04"].true_sample_count == 0
    assert result.items["S2-04"].proxy_sample_count == 1
    assert result.items["S2-04"].adjusted_score <= 0.60
    assert result.items["S2-04"].proxy_type == "ETF承接替代"
    assert result.items["S2-05"].leader_excess_median_5d is not None
    assert result.items["S2-05"].leader_win_rate_5d is not None
    assert result.items["S2-05"].leader_excess_median_10d is not None
    assert result.items["S2-05"].leader_breadth_20d is not None


def test_generate_report_writes_independent_outputs_without_daily_report(tmp_path):
    indicators = tmp_path / "indicators"
    data_dir = tmp_path / "s2_data"
    output_dir = tmp_path / "s2_output"
    market_dir = tmp_path / "raw"
    docs_dir = tmp_path / "docs"
    indicators.mkdir()
    docs_dir.mkdir()
    daily_report = docs_dir / "daily_report.md"
    daily_report.write_text("OLD S1 REPORT", encoding="utf-8")
    write_json(indicators / "20260529.json", s1_payload("20260529", 0.46))

    report_path = generate_report(
        indicators_dir=indicators,
        data_dir=data_dir,
        output_dir=output_dir,
        market_data_dir=market_dir,
        excel_path=Path("docs/创新药_第一阶段_v2_claude.xlsx"),
        report_date="2026-05-30",
    )

    assert report_path == output_dir / "reports" / "2026-05-30.md"
    assert report_path.exists()
    assert (output_dir / "s2_daily_report.md").exists()
    assert (output_dir / "s2_scores.csv").exists()
    assert (output_dir / "s2_item_scores.csv").exists()
    assert (output_dir / "s2_indicator_history.md").exists()
    assert daily_report.read_text(encoding="utf-8") == "OLD S1 REPORT"

    with (output_dir / "s2_scores.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["date"] == "2026-05-30"
    assert "s2_raw_score" in rows[0]
    assert "s2_adjusted_score" in rows[0]

    with (output_dir / "s2_item_scores.csv").open(encoding="utf-8") as fh:
        item_rows = list(csv.DictReader(fh))
    assert len(item_rows) == 5
    assert {row["code"] for row in item_rows} == {"S2-01", "S2-02", "S2-03", "S2-04", "S2-05"}
    assert "adjusted_score" in item_rows[0]
    assert "event_db_maturity" in item_rows[0]
    assert "raw_bd_amount" in item_rows[0]
    assert "quality_bd_amount" in item_rows[0]
    assert "true_sample_count" in item_rows[0]
    assert "proxy_sample_count" in item_rows[0]
