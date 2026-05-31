"""Daily S2 report generator.

This module is intentionally independent from the existing S1 workflow. It reads
S1 outputs, event stores, and local market data, then writes only under s2/output.
"""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from s2.event_store import ensure_event_store, load_events
from s2.s1_reader import S1Record, load_latest_s1
from s2.scoring import S2Score, score_s2


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDICATORS_DIR = PROJECT_ROOT / "data" / "indicators"
DEFAULT_MARKET_DATA_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_EXCEL_PATH = PROJECT_ROOT / "docs" / "创新药_第一阶段_v2_claude.xlsx"
DEFAULT_DATA_DIR = PROJECT_ROOT / "s2" / "data"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "s2" / "output"


def _fmt(value: float | None, percent: bool = False, money: bool = False) -> str:
    if value is None:
        return "数据缺失"
    if money:
        return f"{value:,.0f} USD"
    return f"{value:.2%}" if percent else f"{value:.2f}"


def _csv_float(value: float | None) -> str:
    return "" if value is None else f"{value:.8f}"


def _s1_line(record: S1Record) -> str:
    s102 = record.indicators.get("S1-02", {}).get("value")
    s105 = record.indicators.get("S1-05", {}).get("value")
    return f"S1最新日期 {record.trade_date}，综合得分 {record.total_score:.2f}，等级 {record.expectation_level}；S1-02={_fmt(s102, True)}，S1-05={_fmt(s105, True)}。"


def _stage(s1: S1Record, s2: S2Score) -> tuple[str, str]:
    if s1.total_score >= 0.60 and s2.adjusted_score >= 0.60:
        return "产业验证接力观察期", "持有"
    if s1.total_score < 0.60 and s2.adjusted_score >= 0.60:
        return "产业验证强、资金未确认", "小仓试探"
    if s1.total_score >= 0.60 and s2.adjusted_score < 0.60:
        return "预期修复强、产业待验证", "观察 / 等确认"
    return "交易和产业均待确认", "观察 / 等确认"


def render_report(s1: S1Record, recent_s1: list[S1Record], s2: S2Score, data_dir: Path, report_date: str) -> str:
    stage, action = _stage(s1, s2)
    bd_events = load_events(data_dir / "bd_events.csv")
    clinical_events = load_events(data_dir / "clinical_events.csv")
    earnings_events = load_events(data_dir / "earnings_events.csv")
    today_new = [
        event for event in bd_events + clinical_events + earnings_events
        if event.get("date", "").replace("-", "") == report_date.replace("-", "")
    ]
    new_text = "今日无新增重大产业事件，产业事件分沿用当前观察窗口。" if not today_new else f"今日新增 {len(today_new)} 条事件。"

    lines = [
        "# 创新药 S2 产业验证日报",
        "",
        f"**报告日期**: {report_date}",
        f"**S1交易日**: {s1.trade_date}",
        "**输出范围**: 独立 S2 模块，不修改 S1 日报",
        "",
        "## 一、今日结论",
        "",
        f"- 当前阶段：{stage}",
        f"- 操作倾向：{action}",
        f"- S2原始得分：{s2.raw_score:.2f}",
        f"- S2置信度调整后得分：{s2.adjusted_score:.2f}",
        f"- {_s1_line(s1)}",
        f"- {new_text}",
        "",
        "## 二、最近 10 个交易日 S1",
        "",
        "| 日期 | S1综合得分 | S1等级 |",
        "| --- | ---: | --- |",
    ]
    for record in recent_s1:
        lines.append(f"| {record.trade_date} | {record.total_score:.2f} | {record.expectation_level} |")

    lines.extend([
        "",
        "## 三、S2 本地计算结果",
        "",
        "| 指标 | 名称 | 指标值 | 原始得分 | 调整后得分 | 置信度 | 样本数 | 替代口径数 | 评级 | 来源 | 依据 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ])
    for item in s2.items.values():
        percent = item.code in {"S2-03", "S2-04", "S2-05"}
        money = item.code == "S2-02"
        lines.append(
            f"| {item.code} | {item.name} | {_fmt(item.value, percent, money)} | {item.raw_score:.2f} | {item.adjusted_score:.2f} | {item.confidence:.2f} | {item.sample_count} | {item.replacement_count} | {item.rating} | {item.source} | {item.basis} |"
        )

    lines.extend([
        "",
        "## 四、事件库状态",
        "",
        f"- BD事件库：{len(bd_events)} 条",
        f"- 临床事件库：{len(clinical_events)} 条",
        f"- 业绩事件库：{len(earnings_events)} 条",
        f"- {new_text}",
        "",
        "### 当前观察窗口内的重要事件",
        "",
    ])
    active_events = [
        event for event in bd_events + clinical_events + earnings_events
        if event.get("status", "active") == "active"
    ]
    if active_events:
        for event in active_events[:10]:
            title = " / ".join(
                part for part in [
                    event.get("date"),
                    event.get("company"),
                    event.get("asset") or event.get("period"),
                ]
                if part
            )
            lines.append(f"- {title}: {event.get('note', '')} 来源: {event.get('source_url') or '来源缺失'}")
    else:
        lines.append("- 暂无 active 事件。")

    lines.extend([
        "",
        "## 五、数据缺失与待验证事项",
        "",
    ])
    if s2.missing_data:
        seen_missing = set()
        for item in s2.missing_data.split("；"):
            if item:
                if item in seen_missing:
                    continue
                seen_missing.add(item)
                lines.append(f"- {item}")
    else:
        lines.append("- 暂无关键缺失项。")

    lines.extend([
        "",
        "## 六、复核清单",
        "",
        "- S2分数来自本地事件库和行情计算，不靠临场主观重打分。",
        "- 新事件必须由智能体联网查证后写入事件库。",
        "- 缺失数据保留为“数据缺失”，不编造。",
    ])
    return "\n".join(lines) + "\n"


def _upsert_score(output_dir: Path, report_date: str, s1: S1Record, s2: S2Score, stage: str, action: str) -> None:
    path = output_dir / "s2_scores.csv"
    fields = ["date", "s1_trade_date", "s1_total", "s2_raw_score", "s2_adjusted_score", "s2_total", "current_stage", "action_bias", "missing_data"]
    rows: list[dict[str, str]] = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            rows = [row for row in csv.DictReader(fh) if row.get("date") != report_date]
    rows.append({
        "date": report_date,
        "s1_trade_date": s1.trade_date,
        "s1_total": f"{s1.total_score:.4f}",
        "s2_raw_score": f"{s2.raw_score:.4f}",
        "s2_adjusted_score": f"{s2.adjusted_score:.4f}",
        "s2_total": f"{s2.adjusted_score:.4f}",
        "current_stage": stage,
        "action_bias": action,
        "missing_data": s2.missing_data,
    })
    output_dir.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: row["date"]))


def _upsert_item_scores(output_dir: Path, report_date: str, s1: S1Record, s2: S2Score) -> None:
    path = output_dir / "s2_item_scores.csv"
    fields = [
        "date",
        "s1_trade_date",
        "code",
        "name",
        "value",
        "raw_score",
        "adjusted_score",
        "confidence",
        "sample_count",
        "replacement_count",
        "rating",
        "source",
        "basis",
        "missing",
        "event_db_maturity",
        "raw_bd_amount",
        "quality_bd_amount",
        "true_value",
        "proxy_value",
        "true_sample_count",
        "proxy_sample_count",
        "proxy_type",
        "leader_excess_median_5d",
        "leader_win_rate_5d",
        "leader_excess_median_10d",
        "leader_breadth_20d",
    ]
    rows: list[dict[str, str]] = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            rows = [row for row in csv.DictReader(fh) if row.get("date") != report_date]

    for item in s2.items.values():
        rows.append({
            "date": report_date,
            "s1_trade_date": s1.trade_date,
            "code": item.code,
            "name": item.name,
            "value": _csv_float(item.value),
            "raw_score": f"{item.raw_score:.4f}",
            "adjusted_score": f"{item.adjusted_score:.4f}",
            "confidence": f"{item.confidence:.4f}",
            "sample_count": str(item.sample_count),
            "replacement_count": str(item.replacement_count),
            "rating": item.rating,
            "source": item.source,
            "basis": item.basis,
            "missing": item.missing,
            "event_db_maturity": item.event_db_maturity,
            "raw_bd_amount": _csv_float(item.raw_bd_amount),
            "quality_bd_amount": _csv_float(item.quality_bd_amount),
            "true_value": _csv_float(item.true_value),
            "proxy_value": _csv_float(item.proxy_value),
            "true_sample_count": str(item.true_sample_count),
            "proxy_sample_count": str(item.proxy_sample_count),
            "proxy_type": item.proxy_type,
            "leader_excess_median_5d": _csv_float(item.leader_excess_median_5d),
            "leader_win_rate_5d": _csv_float(item.leader_win_rate_5d),
            "leader_excess_median_10d": _csv_float(item.leader_excess_median_10d),
            "leader_breadth_20d": _csv_float(item.leader_breadth_20d),
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda row: (row["date"], row["code"])))


def _render_indicator_history(output_dir: Path) -> str:
    item_path = output_dir / "s2_item_scores.csv"
    if not item_path.exists():
        return "# 创新药 S2 指标历史\n\n暂无 S2 指标历史。\n"

    with item_path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    latest_dates = sorted({row["date"] for row in rows}, reverse=True)[:30]
    rows = [row for row in rows if row["date"] in latest_dates]

    lines = [
        "# 创新药 S2 指标历史",
        "",
        "该文件由 `python -m s2.generate_s2_report` 自动生成，记录 S2-01 到 S2-05 的每日底层计算结果。",
        "",
        "| 日期 | 指标 | 指标值 | 原始得分 | 调整后得分 | 置信度 | 样本数 | 替代口径数 | 真实样本 | 代理样本 | 成熟度 | 评级 | 缺失说明 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in sorted(rows, key=lambda item: (item["date"], item["code"]), reverse=True):
        value = row["value"] or "数据缺失"
        lines.append(
            f"| {row['date']} | {row['code']} {row['name']} | {value} | {float(row['raw_score']):.2f} | "
            f"{float(row['adjusted_score']):.2f} | {float(row['confidence']):.2f} | {row['sample_count']} | "
            f"{row['replacement_count']} | {row.get('true_sample_count', '0')} | {row.get('proxy_sample_count', '0')} | "
            f"{row.get('event_db_maturity', '') or '-'} | {row['rating']} | {row['missing'] or '-'} |"
        )
    return "\n".join(lines) + "\n"


def generate_report(
    indicators_dir: Path = DEFAULT_INDICATORS_DIR,
    data_dir: Path = DEFAULT_DATA_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    market_data_dir: Path = DEFAULT_MARKET_DATA_DIR,
    excel_path: Path = DEFAULT_EXCEL_PATH,
    report_date: str | None = None,
) -> Path:
    report_date = report_date or datetime.now().strftime("%Y-%m-%d")
    ensure_event_store(data_dir)
    latest_s1, recent_s1 = load_latest_s1(indicators_dir)
    s2 = score_s2(
        trade_date=latest_s1.trade_date,
        data_dir=data_dir,
        output_dir=output_dir,
        market_data_dir=market_data_dir,
        excel_path=excel_path,
        s1_total=latest_s1.total_score,
        s1_share_change=latest_s1.indicators.get("S1-02", {}).get("value"),
    )
    content = render_report(latest_s1, recent_s1, s2, data_dir, report_date)
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{report_date}.md"
    report_path.write_text(content, encoding="utf-8")
    (output_dir / "s2_daily_report.md").write_text(content, encoding="utf-8")
    stage, action = _stage(latest_s1, s2)
    _upsert_score(output_dir, report_date, latest_s1, s2, stage, action)
    _upsert_item_scores(output_dir, report_date, latest_s1, s2)
    (output_dir / "s2_indicator_history.md").write_text(_render_indicator_history(output_dir), encoding="utf-8")
    return report_path


def main() -> None:
    path = generate_report()
    print(f"S2日报已更新: {path}")


if __name__ == "__main__":
    main()
