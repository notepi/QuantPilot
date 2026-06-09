import csv
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from s2.event_store import append_events, ensure_event_store, load_events
from s2.citydata_client import _frame_from_payload
from s2.generate_s2_report import _s2_conversion_score, _s2_event_score, generate_report
from s2.hk_observation import read_hk_observation, update_hk_observation
from s2.market_metrics import clinical_conversion_rate, event_return
from s2.s1_reader import load_latest_s1
from s2.scoring import S2Item, S2Score, _carry_forward, _expire_carry, score_s2
import s2.update_market_data as s2_market_update


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


def test_s2_citydata_client_unwraps_fields_items_payload():
    payload = {
        "code": 0,
        "data": {
            "fields": ["ts_code", "trade_date", "close"],
            "items": [["159567.SZ", "20260605", 1.23]],
        },
    }

    df = _frame_from_payload(payload)

    assert list(df.columns) == ["ts_code", "trade_date", "close"]
    assert df.iloc[0]["trade_date"] == "20260605"


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


def test_event_store_merges_sources_for_same_event(tmp_path):
    data_dir = tmp_path / "data"
    ensure_event_store(data_dir)
    base = {
        "date": "2026-05-29",
        "company": "信达生物",
        "ticker": "01801.HK",
        "asset": "IBI363",
        "partner": "Pfizer",
        "source_url": "https://example.com/company-release",
    }
    append_events(data_dir / "bd_events.csv", [base])
    append_events(data_dir / "bd_events.csv", [{**base, "source_url": "https://example.com/exchange-filing"}])
    rows = load_events(data_dir / "bd_events.csv")

    assert len(rows) == 1
    assert json.loads(rows[0]["source_urls"]) == [
        "https://example.com/company-release",
        "https://example.com/exchange-filing",
    ]


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
    assert result.items["S2-01"].value is None
    assert result.items["S2-01"].rating == "数据缺失"
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
                "date": "2026-02-01",
                "company": "基准公司",
                "ticker": "600000.SH",
                "asset": "baseline",
                "partner": "Partner",
                "source_url": "https://example.com/baseline",
                "source_tier": "1",
                "importance": "high",
                "status": "active",
                "note": "历史重大BD",
            },
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
                "date": "2026-05-20",
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
    assert result.items["S2-04"].replacement_count == 0
    assert result.items["S2-04"].proxy_sample_count == 0
    assert result.items["S2-04"].hk_pending_count == 0
    assert result.items["S2-04"].true_sample_count == 1


def test_s1_inputs_do_not_rewrite_s2_score(tmp_path):
    data_dir = tmp_path / "data"
    ensure_event_store(data_dir)
    common = {
        "trade_date": "20260529",
        "data_dir": data_dir,
        "output_dir": tmp_path / "output",
        "market_data_dir": Path("data/raw"),
        "excel_path": Path("docs/创新药_第一阶段_v2_claude.xlsx"),
    }

    without_s1 = score_s2(**common)
    with_weak_s1 = score_s2(**common, s1_total=0.10, s1_share_change=-0.20)

    assert with_weak_s1.adjusted_score == without_s1.adjusted_score


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
                "date": "2026-05-20",
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
    assert result.items["S2-04"].true_sample_count == 1
    assert result.items["S2-04"].proxy_sample_count == 0
    assert result.items["S2-04"].hk_pending_count == 0
    assert result.items["S2-04"].adjusted_score <= 0.60
    assert result.items["S2-04"].proxy_type == ""
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
    assert (output_dir / "hk_observation_scores.csv").exists()
    assert daily_report.read_text(encoding="utf-8") == "OLD S1 REPORT"

    with (output_dir / "s2_scores.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows[0]["date"] == "2026-05-30"
    assert "s2_raw_score" in rows[0]
    assert "s2_adjusted_score" in rows[0]
    assert "s2_raw_total" in rows[0]
    assert "s2_adjusted_total" in rows[0]
    assert "formal_rating" in rows[0]
    assert "explanation_status" in rows[0]
    assert "final_view" in rows[0]
    assert "s2_event_score" in rows[0]
    assert "s2_conversion_score" in rows[0]
    assert "s2_event_rating" in rows[0]
    assert "s2_conversion_rating" in rows[0]
    assert "final_view_code" in rows[0]
    assert "industry_event_state" in rows[0]
    assert "conversion_state" in rows[0]
    assert "a_share_temperature_state" in rows[0]
    assert "hk_observation_state" in rows[0]

    with (output_dir / "s2_item_scores.csv").open(encoding="utf-8") as fh:
        item_rows = list(csv.DictReader(fh))
    assert len(item_rows) == 7
    assert {row["code"] for row in item_rows} == {"S2-01", "S2-02", "S2-03a", "S2-03b", "S2-04", "S2-05", "S2-06"}
    assert "adjusted_score" in item_rows[0]
    assert "event_db_maturity" in item_rows[0]
    assert "raw_bd_amount" in item_rows[0]
    assert "quality_bd_amount" in item_rows[0]
    assert "true_sample_count" in item_rows[0]
    assert "proxy_sample_count" in item_rows[0]
    assert "indicator_status" in item_rows[0]
    assert "official_sample_count" in item_rows[0]
    assert "pending_sample_count" in item_rows[0]
    assert "missing_reason" in item_rows[0]
    assert "last_valid_observation_date" in item_rows[0]
    assert "s2_04_official_status" in item_rows[0]
    assert "s2_04_official_sample_count" in item_rows[0]
    assert "s2_04_hk_event_pending_count" in item_rows[0]
    assert "hk_observation_status" in item_rows[0]
    assert "hk_observation_available" in item_rows[0]
    assert "is_carry_forward" in item_rows[0]
    assert "raw_mature_event_count" in item_rows[0]
    assert "deduped_trade_sample_count" in item_rows[0]
    assert "success_count" in item_rows[0]
    assert "success_rate" in item_rows[0]

    report = report_path.read_text(encoding="utf-8")
    assert "港股观察标的**: 159567.SZ 港股创新药ETF" in report
    assert "正式量化温度计**: 589720.SH 科创创新药ETF" in report
    assert "589720.SH 弱，只表示 A 股科创创新药资金状态偏弱" in report
    assert "S2产业事件侧得分：S2_event_score=" in report
    assert "S2交易转化侧得分：S2_conversion_score=" in report
    assert "S2-04_official_status" in report
    assert "S2-04_hk_event_pending_count" in report
    assert "HK_observation_status" in report
    assert "S2-04 待成熟事件日历" in report
    assert "数据质量摘要" in report
    assert "今日变化" in report
    assert "### 不可判定" in report
    assert "S2-03a / S2-03b 业绩验证层" in report
    assert "S2-06 商业化兑现质量" in report
    assert "Policy_Risk_Layer 政策风险层" in report
    assert "Macro_Risk_Layer 宏观资金层" in report
    assert "final_view_code_dict" in report


def test_s2_explanation_scores_do_not_change_official_total():
    items = {
        "S2-01": S2Item("S2-01", "BD落地频率", 1.0, 0.7, 0.7, 0.75, "符合预期", "", ""),
        "S2-02": S2Item("S2-02", "BD金额质量", 1.0, 0.7, 0.7, 0.75, "符合预期", "", ""),
        "S2-03a": S2Item("S2-03a", "财报客观改善", 1.0, 1.0, 0.65, 0.60, "超预期", "", ""),
        "S2-03b": S2Item("S2-03b", "一致预期验证", None, 0.5, 0.5, 0.45, "数据缺失", "", ""),
        "S2-04": S2Item("S2-04", "数据催化转化率", None, 0.5, 0.5, 0.45, "待验证", "", ""),
        "S2-05": S2Item("S2-05", "龙头接力强度", -0.01, 0.4, 0.4, 0.60, "低于预期", "", ""),
    }
    result = S2Score(
        trade_date="20260602",
        raw_score=0.56,
        adjusted_score=0.56,
        items=items,
        missing_data="",
        level="低于预期",
        available_weight=0.60,
        missing_indicator_count=1,
        pending_indicator_count=1,
        proxy_indicator_count=0,
        stale_indicator_count=0,
    )

    assert _s2_event_score(result) == pytest.approx((0.7 + 0.7 + 0.65 + 0.5) / 4)
    assert _s2_conversion_score(result) == pytest.approx((0.5 + 0.4) / 2)
    assert result.adjusted_score == pytest.approx(0.56)


def test_event_return_requires_full_five_trade_day_window():
    market_dir = Path("data/raw")

    assert event_return(market_dir, "589720.SH", "2026-05-26", as_of_trade_date="20260529") is None
    assert event_return(market_dir, "589720.SH", "2026-05-20", as_of_trade_date="20260529") is not None


def test_clinical_conversion_uses_hk_stock_and_hk_benchmark_without_159567(tmp_path):
    market_dir = tmp_path / "raw"
    market_dir.mkdir()
    dates = ["20260520", "20260521", "20260522", "20260525", "20260526", "20260527"]
    with (market_dir / "fund_daily.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["ts_code", "trade_date", "close"])
        writer.writeheader()
        for ticker, closes in [("589720.SH", [1, 1, 1, 1, 1, 1.02]), ("159557.SZ", [1, 1, 1, 1, 1, 1.01])]:
            for date, close in zip(dates, closes):
                writer.writerow({"ts_code": ticker, "trade_date": date, "close": close})
    with (market_dir / "hk_daily.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["ts_code", "trade_date", "close"])
        writer.writeheader()
        for date, close in zip(dates, [1, 1, 1, 1, 1, 1.10]):
            writer.writerow({"ts_code": "09926.HK", "trade_date": date, "close": close})

    result = clinical_conversion_rate(
        [{"date": "2026-05-20", "company": "康方生物", "ticker": "9926.HK", "asset": "ivonescimab"}],
        market_dir,
        as_of_trade_date="20260527",
    )

    assert result.value == pytest.approx(1.0)
    assert result.true_sample_count == 1
    assert result.proxy_sample_count == 0
    assert result.hk_pending_count == 0
    assert result.clinical_event_statuses[0].trading_status == "mature_calculable"
    assert result.clinical_event_statuses[0].included_in_official_score is True
    assert result.clinical_event_statuses[0].excess_vs_159557_5d == pytest.approx(0.09)
    assert result.clinical_event_statuses[0].excess_vs_159567_5d is None


def test_clinical_conversion_includes_hk_events_when_prices_exist(tmp_path):
    market_dir = tmp_path / "raw"
    market_dir.mkdir()
    dates = ["20260520", "20260521", "20260522", "20260525", "20260526", "20260527"]
    with (market_dir / "fund_daily.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["ts_code", "trade_date", "close"])
        writer.writeheader()
        for ticker, closes in [
            ("589720.SH", [1, 1, 1, 1, 1, 1.02]),
            ("159567.SZ", [1, 1, 1, 1, 1, 1.03]),
            ("159557.SZ", [1, 1, 1, 1, 1, 1.01]),
        ]:
            for date, close in zip(dates, closes):
                writer.writerow({"ts_code": ticker, "trade_date": date, "close": close})
    with (market_dir / "hk_daily.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["ts_code", "trade_date", "close"])
        writer.writeheader()
        for date, close in zip(dates, [1, 1, 1, 1, 1, 1.10]):
            writer.writerow({"ts_code": "09926.HK", "trade_date": date, "close": close})

    result = clinical_conversion_rate(
        [{"date": "2026-05-20", "company": "康方生物", "ticker": "9926.HK", "asset": "ivonescimab"}],
        market_dir,
        as_of_trade_date="20260527",
    )

    assert result.value == pytest.approx(1.0)
    assert result.true_sample_count == 1
    assert result.hk_pending_count == 0
    assert result.clinical_event_statuses[0].trading_status == "mature_calculable"
    assert result.clinical_event_statuses[0].included_in_official_score is True
    assert result.clinical_event_statuses[0].excess_vs_159567_5d == pytest.approx(0.07)


def test_clinical_conversion_dedupes_same_stock_date_benchmark_window(tmp_path):
    market_dir = tmp_path / "raw"
    market_dir.mkdir()
    dates = ["20260529", "20260602", "20260603", "20260604", "20260605", "20260606"]
    with (market_dir / "fund_daily.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["ts_code", "trade_date", "close"])
        writer.writeheader()
        for ticker, closes in [
            ("159567.SZ", [1, 1, 1, 1, 1, 0.95]),
            ("159557.SZ", [1, 1, 1, 1, 1, 0.98]),
        ]:
            for date, close in zip(dates, closes):
                writer.writerow({"ts_code": ticker, "trade_date": date, "close": close})
    with (market_dir / "hk_daily.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["ts_code", "trade_date", "close"])
        writer.writeheader()
        for date, close in zip(dates, [1, 1, 1, 1, 1, 0.90]):
            writer.writerow({"ts_code": "06990.HK", "trade_date": date, "close": close})

    result = clinical_conversion_rate(
        [
            {"date": "2026-05-29", "company": "科伦博泰", "ticker": "6990.HK", "asset": "sac-TMT"},
            {"date": "2026-05-29", "company": "科伦博泰", "ticker": "6990.HK", "asset": "A400"},
        ],
        market_dir,
        as_of_trade_date="20260606",
    )

    statuses = result.clinical_event_statuses
    assert result.raw_mature_event_count == 2
    assert result.deduped_trade_sample_count == 1
    assert result.sample_count == 1
    assert result.success_count == 0
    assert result.success_rate == pytest.approx(0.0)
    assert statuses[0].trade_sample_id == statuses[1].trade_sample_id
    assert statuses[0].included_in_deduped_trade_sample is True
    assert statuses[1].trading_status == "mature_deduped_duplicate"
    assert statuses[1].included_in_deduped_trade_sample is False


def test_clinical_conversion_marks_mature_hk_event_missing_price(tmp_path):
    market_dir = tmp_path / "raw"
    market_dir.mkdir()
    dates = ["20260520", "20260521", "20260522", "20260525", "20260526", "20260527", "20260528"]
    with (market_dir / "fund_daily.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["ts_code", "trade_date", "close"])
        writer.writeheader()
        for ticker in ["589720.SH", "159567.SZ", "159557.SZ"]:
            for date in dates:
                writer.writerow({"ts_code": ticker, "trade_date": date, "close": 1})

    result = clinical_conversion_rate(
        [{"date": "2026-05-20", "company": "测试公司", "ticker": "1234.HK", "asset": "missing asset"}],
        market_dir,
        as_of_trade_date="20260528",
    )

    status = result.clinical_event_statuses[0]
    assert status.trading_status == "missing_price"
    assert status.is_mature is True
    assert status.included_in_official_score is False
    assert "missing_price: 1234.HK本地行情缺失" in result.missing[0]


def test_clinical_events_roll_into_june_maturity_checks(tmp_path):
    market_dir = tmp_path / "raw"
    market_dir.mkdir()
    dates = ["20260601", "20260602", "20260603", "20260604", "20260605"]
    with (market_dir / "fund_daily.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["ts_code", "trade_date", "close"])
        writer.writeheader()
        for ticker in ["589720.SH", "159567.SZ", "159557.SZ"]:
            for date in dates:
                writer.writerow({"ts_code": ticker, "trade_date": date, "close": 1})

    events = [
        {"date": "2026-06-01", "company": "康宁杰瑞", "ticker": "9966.HK", "asset": "KN026"},
        {"date": "2026-06-02", "company": "先声再明", "ticker": "2096.HK", "asset": "SIM0505"},
        {"date": "2026-06-03", "company": "科伦博泰", "ticker": "6990.HK", "asset": "SKB500"},
        {"date": "2026-06-04", "company": "信达生物", "ticker": "01801.HK", "asset": "IBI343"},
    ]

    result = clinical_conversion_rate(events, market_dir, as_of_trade_date="20260605")
    maturity_dates = {status.company: status.next_maturity_date for status in result.clinical_event_statuses}

    assert maturity_dates["康宁杰瑞"] == "2026-06-08"
    assert maturity_dates["先声再明"] == "2026-06-09"
    assert maturity_dates["科伦博泰"] == "2026-06-10"
    assert maturity_dates["信达生物"] == "2026-06-11"


def test_update_hk_daily_writes_close_pct_chg_and_trade_date(tmp_path, monkeypatch):
    monkeypatch.setattr(s2_market_update, "S2_DATA_DIR", tmp_path)
    monkeypatch.setattr(s2_market_update, "HK_DAILY_PATH", tmp_path / "hk_daily.csv")

    def fake_fetch(ticker: str) -> pd.DataFrame:
        return s2_market_update._normalise_akshare_hk(
            pd.DataFrame({
                "日期": ["2026-06-01", "2026-06-02"],
                "收盘": [10.0, 11.0],
            }),
            ticker,
        )

    monkeypatch.setattr(s2_market_update, "_fetch_hk_stock", fake_fetch)

    result = s2_market_update.update_hk_daily(["9926.HK"])
    df = pd.read_csv(tmp_path / "hk_daily.csv", dtype={"trade_date": str, "ts_code": str})

    assert result["status"] == "success"
    assert list(df[["ts_code", "trade_date", "close"]].iloc[-1]) == ["09926.HK", "20260602", 11.0]
    assert "pct_chg" in df.columns
    assert df["pct_chg"].iloc[-1] == pytest.approx(10.0)


def test_superseded_event_remains_available_for_market_validation(tmp_path):
    data_dir = tmp_path / "data"
    ensure_event_store(data_dir)
    append_events(
        data_dir / "clinical_events.csv",
        [
            {
                "date": "2026-05-20",
                "company": "康方生物",
                "ticker": "9926.HK",
                "conference": "ASCO 2026",
                "asset": "ivonescimab preview",
                "source_url": "https://example.com/akeso-preview",
                "source_tier": "2",
                "importance": "high",
                "status": "superseded",
                "note": "已由正式数据替代",
            }
        ],
    )

    result = score_s2(
        trade_date="20260529",
        data_dir=data_dir,
        output_dir=tmp_path / "output",
        market_data_dir=Path("data/raw"),
        excel_path=Path("docs/创新药_第一阶段_v2_claude.xlsx"),
    )

    assert result.items["S2-04"].proxy_sample_count == 0
    assert result.items["S2-04"].hk_pending_count == 0
    assert result.items["S2-04"].true_sample_count == 1


def test_hk_observation_updates_cache_and_falls_back_when_fetch_fails(tmp_path):
    cache_dir = tmp_path / "hk_cache"
    dates = pd.date_range("2026-05-22", periods=6, freq="B")

    def fetcher(symbol: str) -> pd.DataFrame:
        scale = 1.02 if symbol == "159567" else 1.01
        return pd.DataFrame({"日期": dates, "收盘": [1, 1, 1, 1, 1, scale]})

    observation = update_hk_observation(cache_dir, today=datetime(2026, 5, 29), fetcher=fetcher)

    assert observation["status"] == "valid"
    assert observation["is_valid_for_judgement"] is True
    assert observation["excess_159567_vs_159557_5d"] == pytest.approx(0.01)
    assert observation["return_159557_5d"] == pytest.approx(0.01)
    assert (cache_dir / "159567.csv").exists()
    assert (cache_dir / "159557.csv").exists()

    def broken_fetcher(symbol: str) -> pd.DataFrame:
        raise RuntimeError(f"{symbol} unavailable")

    fallback = update_hk_observation(cache_dir, today=datetime(2026, 5, 29), fetcher=broken_fetcher, fallback_fetcher=broken_fetcher)

    assert fallback["status"] == "stale_valid"
    assert fallback["is_valid_for_judgement"] is True
    assert len(fallback["errors"]) == 4
    assert fallback["excess_159567_vs_159557_5d"] == pytest.approx(0.01)


def test_hk_observation_uses_eastmoney_fallback(tmp_path):
    cache_dir = tmp_path / "hk_cache"
    dates = pd.date_range("2026-05-22", periods=6, freq="B")

    def broken_fetcher(symbol: str) -> pd.DataFrame:
        raise RuntimeError(f"{symbol} akshare unavailable")

    def eastmoney_fetcher(symbol: str) -> pd.DataFrame:
        scale = 1.03 if symbol == "159567" else 1.01
        return pd.DataFrame({
            "date": dates.strftime("%Y-%m-%d"),
            "open": [1, 1, 1, 1, 1, scale],
            "high": [1, 1, 1, 1, 1, scale],
            "low": [1, 1, 1, 1, 1, scale],
            "close": [1, 1, 1, 1, 1, scale],
            "volume": [100] * 6,
            "amount": [1000] * 6,
        })

    observation = update_hk_observation(
        cache_dir,
        today=datetime(2026, 5, 29),
        fetcher=broken_fetcher,
        fallback_fetcher=eastmoney_fetcher,
    )

    assert observation["status"] == "valid"
    assert observation["data_source"] == "eastmoney"
    assert observation["excess_159567_vs_159557_5d"] == pytest.approx(0.02)
    cached = pd.read_csv(cache_dir / "159567.csv")
    assert {"date", "ticker", "open", "high", "low", "close", "volume", "amount", "source", "fetched_at"}.issubset(cached.columns)


def test_hk_observation_marks_old_cache_stale(tmp_path):
    cache_dir = tmp_path / "hk_cache"
    dates = pd.date_range("2026-05-11", periods=6, freq="B")
    cache_dir.mkdir()
    for symbol in ["159567", "159557"]:
        pd.DataFrame({"trade_date": dates.strftime("%Y%m%d"), "close": [1, 1, 1, 1, 1, 1.01]}).to_csv(
            cache_dir / f"{symbol}.csv",
            index=False,
        )

    observation = read_hk_observation(cache_dir, today=datetime(2026, 6, 1))

    assert observation["status"] == "stale"
    assert observation["is_valid_for_judgement"] is False
    assert observation["return_159567_1d"] is None
    assert observation["return_159567_5d"] is None
    assert observation["return_159557_5d"] is None
    assert observation["excess_159567_vs_159557_5d"] is None


def test_market_score_carry_forward_uses_two_and_five_day_limits():
    previous = S2Item("S2-05", "龙头接力强度", 0.08, 1.0, 0.75, 0.75, "超预期", "旧观测", "test", sample_count=3)
    current = S2Item("S2-05", "龙头接力强度", None, 0.5, 0.5, 0.45, "待验证", "等待新样本", "test", pending_count=2)

    recent = _carry_forward(current, previous, "2026-05-30", 2)
    aging = _carry_forward(current, previous, "2026-05-30", 3)
    stale = _expire_carry(current, "S2-05", 6)

    assert recent.carry_forward_type == "recent_carry_forward"
    assert recent.adjusted_score == pytest.approx(0.75)
    assert aging.carry_forward_type == "aging_carry_forward"
    assert aging.adjusted_score == pytest.approx(0.60)
    assert stale.carry_forward_type == "stale"
    assert stale.rating == "数据缺失"


def test_generate_report_carries_market_scores_when_only_pending_events_are_added(tmp_path):
    indicators = tmp_path / "indicators"
    data_dir = tmp_path / "s2_data"
    output_dir = tmp_path / "s2_output"
    indicators.mkdir()
    write_json(indicators / "20260529.json", s1_payload("20260529", 0.46))
    ensure_event_store(data_dir)
    append_events(
        data_dir / "clinical_events.csv",
        [
            {
                "date": "2026-05-20",
                "company": "百济神州",
                "ticker": "688235.SH",
                "conference": "ASCO 2026",
                "asset": "ivonescimab preview",
                "source_url": "https://example.com/akeso-preview",
                "source_tier": "2",
                "importance": "high",
                "status": "active",
                "note": "成熟催化",
            }
        ],
    )
    generate_report(
        indicators_dir=indicators,
        data_dir=data_dir,
        output_dir=output_dir,
        market_data_dir=Path("data/raw"),
        excel_path=Path("docs/创新药_第一阶段_v2_claude.xlsx"),
        report_date="2026-05-30",
    )
    append_events(
        data_dir / "clinical_events.csv",
        [
            {
                "date": "2026-05-31",
                "company": "康方生物",
                "ticker": "9926.HK",
                "conference": "ASCO 2026",
                "asset": "ivonescimab formal data",
                "source_url": "https://example.com/akeso-formal",
                "source_tier": "2",
                "importance": "high",
                "status": "active",
                "note": "待验证催化",
            }
        ],
    )

    generate_report(
        indicators_dir=indicators,
        data_dir=data_dir,
        output_dir=output_dir,
        market_data_dir=Path("data/raw"),
        excel_path=Path("docs/创新药_第一阶段_v2_claude.xlsx"),
        report_date="2026-05-31",
    )

    with (output_dir / "s2_item_scores.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    previous = {row["code"]: row for row in rows if row["date"] == "2026-05-30"}
    current = {row["code"]: row for row in rows if row["date"] == "2026-05-31"}
    for code in {"S2-04", "S2-05"}:
        assert current[code]["adjusted_score"] == previous[code]["adjusted_score"]
        assert current[code]["carried_forward_from"] == "2026-05-30"
        assert int(current[code]["pending_count"]) >= 1
