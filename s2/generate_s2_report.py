"""Daily S2 report generator.

This module is intentionally independent from the existing S1 workflow. It reads
S1 outputs, event stores, and local market data, then writes only under s2/output.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta
from pathlib import Path

from s2.event_store import ensure_event_store, load_events
from s2.hk_observation import read_hk_observation, read_hk_update_status, upsert_hk_observation_history
from s2.s1_reader import S1Record, load_latest_s1
from s2.scoring import S2Score, score_s2


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDICATORS_DIR = PROJECT_ROOT / "data" / "indicators"
DEFAULT_MARKET_DATA_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_EXCEL_PATH = PROJECT_ROOT / "docs" / "创新药_第一阶段_v2_claude.xlsx"
DEFAULT_DATA_DIR = PROJECT_ROOT / "s2" / "data"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "s2" / "output"

EVENT_SCORE_CODES = ("S2-01", "S2-02", "S2-03a", "S2-03b")
FORMAL_ITEM_CODES = ("S2-01", "S2-02", "S2-03a", "S2-03b", "S2-04", "S2-05")

POLICY_RISK_FIELDS = [
    "event_name",
    "event_date",
    "region",
    "affected_chain",
    "risk_direction",
    "severity",
    "status",
    "affected_symbols",
    "source_url",
    "last_checked_date",
    "explanation",
]
MACRO_MARKET_FIELDS = [
    "snapshot_date",
    "QQQ_pct",
    "SOXX_pct",
    "SMH_pct",
    "XBI_pct",
    "IBB_pct",
    "XLV_pct",
    "XLP_pct",
    "XLU_pct",
    "US10Y_change",
    "DXY_pct",
    "HSTECH_pct",
    "ETF_159557_pct",
    "ETF_159567_pct",
    "data_source",
    "source_status",
]
HK_EXTERNAL_AVAILABILITY_FIELDS = [
    "date",
    "symbol",
    "price_available",
    "source_url",
    "last_checked_date",
    "note",
]
EARNINGS_CONSENSUS_FIELDS = [
    "company_name",
    "symbol",
    "report_period",
    "actual_revenue",
    "consensus_revenue",
    "revenue_beat",
    "actual_adjusted_profit",
    "consensus_adjusted_profit",
    "profit_beat",
    "actual_eps",
    "consensus_eps",
    "eps_beat",
    "consensus_source",
    "source_url",
    "source_date",
    "confidence",
    "note",
]


def _ensure_auxiliary_layers(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    policy_path = data_dir / "policy_risk_events.csv"
    if not policy_path.exists():
        with policy_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=POLICY_RISK_FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerow({
                "event_name": "BIOSECURE",
                "event_date": "2025-12-18",
                "region": "US",
                "affected_chain": "procurement_supply_chain_risk",
                "risk_direction": "risk_up",
                "severity": "high",
                "status": "effective",
                "affected_symbols": "603259.SH|02269.HK",
                "source_url": "https://www.bakermckenzie.com/en/insight/publications/2026/01/united-states-the-biosecure-act-becomes-law",
                "last_checked_date": datetime.now().strftime("%Y-%m-%d"),
                "explanation": "BIOSECURE 已成为法律，形成美国政府采购/供应链合规风险；仅进入政策风险观察层，不进入S2正式分",
            })
            writer.writerow({
                "event_name": "BINSA",
                "event_date": "2026-06-02",
                "region": "US",
                "affected_chain": "outbound_investment_BD_sentiment_risk",
                "risk_direction": "risk_up",
                "severity": "medium",
                "status": "proposed",
                "affected_symbols": "600276.SH|01801.HK|09926.HK",
                "source_url": "https://chinaselectcommittee.house.gov/media/press-releases/moolenaar-dingell-introduce-legislation-to-prevent-offshoring-biotech-industry-to-china",
                "last_checked_date": datetime.now().strftime("%Y-%m-%d"),
                "explanation": "BINSA 拟把生物技术纳入对外投资审查，压制BD出海情绪；仅进入政策风险观察层，不进入S2正式分",
            })
    macro_path = data_dir / "macro_market_snapshot.csv"
    if not macro_path.exists():
        with macro_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=MACRO_MARKET_FIELDS, lineterminator="\n")
            writer.writeheader()
    hk_external_path = data_dir / "hk_external_availability.csv"
    if not hk_external_path.exists():
        with hk_external_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=HK_EXTERNAL_AVAILABILITY_FIELDS, lineterminator="\n")
            writer.writeheader()
    consensus_path = data_dir / "earnings_consensus.csv"
    if not consensus_path.exists():
        with consensus_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=EARNINGS_CONSENSUS_FIELDS, lineterminator="\n")
            writer.writeheader()
            for symbol, company in [
                ("06160.HK", "百济神州"),
                ("01801.HK", "信达生物"),
                ("09926.HK", "康方生物"),
                ("600276.SH", "恒瑞医药"),
                ("603259.SH", "药明康德"),
                ("02269.HK", "药明生物"),
            ]:
                row = {field: "missing" for field in EARNINGS_CONSENSUS_FIELDS}
                row.update({
                    "company_name": company,
                    "symbol": symbol,
                    "note": "未接入可靠一致预期来源；不得用同比增长替代 beat/miss",
                })
                writer.writerow(row)


def _fmt(value: float | None, percent: bool = False, money: bool = False) -> str:
    if value is None:
        return "数据缺失"
    if money:
        return f"{value:,.0f} USD"
    return f"{value:.2%}" if percent else f"{value:.2f}"


def _cell(value: object) -> str:
    return str(value if value not in {None, ""} else "missing").replace("|", "\\|")


def _csv_float(value: float | None) -> str:
    return "" if value is None else f"{value:.8f}"


def _style_score_text(value: float | None) -> str:
    return "missing" if value is None else f"{value:.2f}"


def _style_percent(value: float | None) -> str:
    return "missing" if value is None else f"{value:.2%}"


def _style_total_text(style: StyleAnalysis | None, industry_score: float) -> str:
    if style is None:
        return "missing"
    total = style.total_score(industry_score)
    return _style_score_text(total)


def _style_conclusion(style: StyleAnalysis | None) -> str:
    if style is None:
        return "科技成长—创新药风格模块未运行。"
    if style.data_status == "missing":
        return f"科技成长—创新药风格不可判定：{style.missing_reason or '核心行情缺失'}。"
    if style.style_regime == "INDEPENDENT_BIOTECH":
        return "当前创新药开始脱离科技成长跷跷板：科技成长不弱时创新药仍保持正收益，并在5D、10D同时跑赢科技成长与医疗宽基。"
    if style.style_regime == "ACTIVE_ROTATION":
        return "当前创新药属于主动轮动：创新药跑赢医疗宽基，但尚未证明科技成长偏强时也能持续形成超额。"
    if style.style_regime == "AI_BIOTECH_SEESAW":
        return "当前属于科技成长—创新药跷跷板：创新药主要在科技成长走弱时获得资金轮动，尚未形成独立主线。"
    if style.style_regime == "AI_CROWDING_OUT":
        return "当前存在科技成长风格压制：科技成长持续偏强时，创新药跑输科技成长和医疗宽基。"
    if style.style_regime == "GROWTH_RISK_OFF":
        return "当前属于成长风险偏好恶化：科技成长和创新药同步走弱。"
    return "当前科技成长—创新药风格为中性：尚未形成稳定的独立主线或跷跷板证据。"


def _tech_growth_state_label(state: str) -> str:
    return (
        state.replace("AI_FLAT", "TECH_FLAT")
        .replace("AI_UP", "TECH_UP")
        .replace("AI_DOWN", "TECH_DOWN")
        .replace("BEATS_AI", "BEATS_TECH")
        .replace("LAGS_AI", "LAGS_TECH")
    )


def _style_rotation_section(style: StyleAnalysis | None, industry_score: float) -> list[str]:
    if style is None:
        return [
            "## 十、科技成长—创新药风格",
            "",
            "- S2_STYLE = missing；风格模块未运行。",
        ]
    c20 = style.conditional.get(20)
    c60 = style.conditional.get(60)
    lines = [
        "## 十、科技成长—创新药风格",
        "",
        "该模块独立于 S2 产业评分，只判断资金风格和独立性，不改 S2-01 至 S2-06 权重。",
        "",
        f"- TECH_GROWTH_CORE = {style.ai_core_symbol}；创新药主对象 = {style.bio_symbol}；医疗宽基对照 = {style.health_symbol}。",
        f"- S2_INDUSTRY = {industry_score:.2f}；S2_STYLE = {_style_score_text(style.style_score)}；S2_TOTAL = {_style_total_text(style, industry_score)}。",
        f"- style_level = {style.style_level}；style_regime = {style.style_regime}；data_status = {style.data_status}。",
        f"- negative_rotation_flag = {str(style.negative_rotation_flag).lower()}；missing_reason = {style.missing_reason or 'none'}。",
        f"- 结论：{_style_conclusion(style)}",
        "",
        "| 周期 | 159567收益 | TECH_GROWTH_CORE收益 | 159567 vs 科技成长 | 159567 vs 159557 | independence | 状态 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in style.periods:
        lines.append(
            f"| {item.period}D | {_style_percent(item.bio_ret)} | {_style_percent(item.ai_ret)} | "
            f"{_style_percent(item.bio_vs_ai)} | {_style_percent(item.bio_vs_health)} | "
            f"{_style_score_text(item.independence)} | {_tech_growth_state_label(item.state)} |"
        )
    lines.extend([
        "",
        "| 辅助指标 | 数值 |",
        "| --- | ---: |",
        f"| corr_10d | {_style_score_text(style.correlations.get(10))} |",
        f"| corr_20d | {_style_score_text(style.correlations.get(20))} |",
        f"| corr_60d | {_style_score_text(style.correlations.get(60))} |",
    ])
    if c20:
        lines.extend([
            f"| bio_avg_ret_when_tech_up_20d | {_style_percent(c20.bio_avg_ret_when_ai_up)} |",
            f"| bio_avg_ret_when_tech_down_20d | {_style_percent(c20.bio_avg_ret_when_ai_down)} |",
            f"| bio_excess_when_tech_up_20d | {_style_percent(c20.bio_excess_when_ai_up)} |",
            f"| bio_excess_when_tech_down_20d | {_style_percent(c20.bio_excess_when_ai_down)} |",
        ])
    if c60:
        lines.extend([
            f"| bio_avg_ret_when_tech_up_60d | {_style_percent(c60.bio_avg_ret_when_ai_up)} |",
            f"| bio_avg_ret_when_tech_down_60d | {_style_percent(c60.bio_avg_ret_when_ai_down)} |",
            f"| bio_excess_when_tech_up_60d | {_style_percent(c60.bio_excess_when_ai_up)} |",
            f"| bio_excess_when_tech_down_60d | {_style_percent(c60.bio_excess_when_ai_down)} |",
        ])
    lines.extend([
        "",
        f"- 60日累计收益图：{style.chart_cumulative_path or 'missing'}",
        f"- 60日超额曲线图：{style.chart_excess_path or 'missing'}",
    ])
    return lines


def _ai_biotech_validation_section(result: ValidationResult | None) -> list[str]:
    lines = [
        "## 十一、AI/科技成长—创新药严格验证",
        "",
        "该模块使用最近最多250个共同有效交易日，分别验证科技成长虹吸、AI虹吸、AI回调轮动、A股领先港股和右侧确认，不进入原S1/S2正式评分。",
        "",
    ]
    if result is None:
        lines.append("- validation_status = missing；验证模块未运行。")
        return lines
    lines.extend([
        f"- 报告日期：{result.report_date}；A股数据日期：{result.a_share_date}；港股数据日期：{result.hk_date}；对应美股收盘日期：{result.us_close_date}。",
        f"- TECH_GROWTH_CORE版本：{result.tech_growth_core_version}；数据日期：{result.tech_growth_core_date}。",
        f"- AI_CORE版本：{result.ai_core_version}；AI_CORE数据日期：{result.ai_core_date}；有效样本数：{result.sample_count}。",
        f"- 科技成长状态：{result.current_tech_growth_state}；AI状态：{result.current_ai_state}；市场状态：{result.market_state}。",
        f"- 右侧确认评分：{_style_score_text(result.right_side_score)}；等级：{result.right_side_level}；置信度：{result.score_confidence}；score_status={result.score_status}；feature_coverage={result.feature_coverage}。",
        f"- 核心指数状态：{result.core_index_status}。",
        f"- 当前命题状态：{result.thesis_state}；仓位动作标签：{result.position_action}。",
        f"- 最强支持证据：{'；'.join(result.strongest_support[:3]) or 'missing'}。",
        f"- 最强反对证据：{'；'.join(result.strongest_opposition[:3]) or 'missing'}。",
        f"- 验证日报：{result.report_path}",
        f"- 审计报告：{result.audit_path}",
    ])
    return lines


def _s1_line(record: S1Record) -> str:
    s102 = record.indicators.get("S1-02", {}).get("value")
    s105 = record.indicators.get("S1-05", {}).get("value")
    s106 = record.indicators.get("S1-06", {}).get("value")
    return f"S1最新日期 {record.trade_date}，综合得分 {record.total_score:.2f}，等级 {record.expectation_level}；S1-02={_fmt(s102, True)}，S1-05={_fmt(s105, True)}，S1-06={_fmt(s106, True)}。"


def _s1_market_state(record: S1Record) -> str:
    if record.total_score >= 0.80:
        return "强"
    if record.total_score >= 0.60:
        return "中性"
    return "弱"


def _expectation_score(expectation: str) -> float:
    return {
        "超预期": 1.0,
        "符合预期": 0.7,
        "低于预期": 0.4,
        "显著低于预期": 0.2,
    }.get(expectation, 0.5)


def _indicator_contribution(record: S1Record, code: str) -> float:
    item = record.indicators.get(code, {})
    return float(item.get("weight") or 0.0) * _expectation_score(str(item.get("expectation", "")))


def _s1_score_contribution(record: S1Record) -> dict[str, float]:
    return {
        "flow_score_contribution": _indicator_contribution(record, "S1-01") + _indicator_contribution(record, "S1-02"),
        "price_strength_contribution": _indicator_contribution(record, "S1-03"),
        "volume_contribution": _indicator_contribution(record, "S1-04"),
        "breadth_contribution": _indicator_contribution(record, "S1-05"),
        "leader_contribution": _indicator_contribution(record, "S1-06"),
    }


def _s1_structure_flags(record: S1Record) -> dict[str, str]:
    breadth = record.indicators.get("S1-05", {}).get("value")
    result = {
        "s1_structure_quality": "normal",
        "s1_breadth_state": "normal",
    }
    if breadth is None:
        return result
    if float(breadth) < 0.40:
        result["s1_breadth_state"] = "weak_breadth"
    if float(breadth) < 0.20:
        result["s1_structure_quality"] = "weak_breadth_repair"
    if float(breadth) < 0.10:
        result["s1_breadth_state"] = "breadth_collapse"
    return result


def _s1_contribution_sentence(record: S1Record) -> str:
    contributions = _s1_score_contribution(record)
    if contributions["flow_score_contribution"] >= max(contributions.values()):
        return "S1改善主要来自资金/份额流入，非价格强度和广度扩散。"
    return "S1贡献来源较分散，仍需拆分资金、价格强度和广度质量。"


def _truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes", "y", "是"}


def _apply_hk_external_availability(data_dir: Path, report_date: str, observation: dict[str, object]) -> None:
    rows = load_events(data_dir / "hk_external_availability.csv")
    report_trade_date = report_date.replace("-", "")
    matched = [
        row for row in rows
        if row.get("date", "").replace("-", "") == report_trade_date and row.get("symbol") == "159567"
    ]
    available = any(_truthy(row.get("price_available")) for row in matched)
    observation["report_day_price_available_externally"] = available
    latest_159567 = str(observation.get("latest_date_159567") or "")
    local_failed = available and latest_159567 != report_trade_date
    observation["local_fetch_failed"] = local_failed
    if local_failed:
        observation["data_fetch_failed"] = True
        observation["status"] = "data_fetch_failed"
        observation["hk_observation_status"] = "data_fetch_failed"
        observation["is_valid_for_judgement"] = False
        observation["comment"] = "外部确认报告日已有159567行情，但本地未抓到同步行情，local_fetch_failed=true；不做最新强弱判断。"
    elif observation.get("is_valid_for_judgement"):
        observation["hk_observation_status"] = "latest_valid"
    elif observation.get("common_trade_date") or observation.get("observation_trade_date"):
        observation["hk_observation_status"] = "valid_common_date"
    else:
        observation["hk_observation_status"] = "missing"


def _s1_trend(recent_s1: list[S1Record]) -> dict[str, object]:
    weak_streak = 0
    for record in reversed(recent_s1):
        if record.total_score < 0.50:
            weak_streak += 1
        else:
            break
    latest = recent_s1[-1]
    previous = recent_s1[-2] if len(recent_s1) >= 2 else None
    delta = latest.total_score - previous.total_score if previous else None
    if latest.total_score >= 0.60:
        trend_state = "温度计修复"
    elif weak_streak >= 3 and delta is not None and delta > 0:
        trend_state = "A股温度计连续弱势，但弱势中小幅修复，尚未确认"
    elif weak_streak >= 3:
        trend_state = "A股温度计连续弱势"
    elif delta is not None and delta > 0:
        trend_state = "弱势中小幅修复"
    else:
        trend_state = "弱势未修复"
    if delta is None:
        direction = "无昨日基准"
    elif delta > 0:
        direction = f"上升 {delta:+.2f}"
    elif delta < 0:
        direction = f"下降 {delta:+.2f}"
    else:
        direction = "持平"
    return {
        "s1_weak_streak_days": weak_streak,
        "s1_trend_state": trend_state,
        "s1_recent_direction": direction,
    }


def _hk_observation_line(observation: dict[str, object], update_status: dict[str, object]) -> str:
    chain = _hk_source_chain_text(observation, update_status)
    proxy = _hk_proxy_summary(observation)
    return f"港股观察层：状态={observation.get('hk_observation_status') or observation['status']}。{chain}。{proxy}该观察层不进入 S2_total，也不改变 adjusted_score。"


def _hk_source_chain_text(observation: dict[str, object], update_status: dict[str, object]) -> str:
    primary_status = str(update_status.get("primary_source_status") or observation.get("primary_source_status") or "unknown")
    fallback_status = str(update_status.get("fallback_source_status") or observation.get("fallback_source_status") or "unknown")
    final_source = str(update_status.get("final_data_source") or observation.get("final_data_source") or observation.get("data_source") or "none")
    primary_source = str(update_status.get("primary_source") or observation.get("primary_source") or "primary")
    fallback_source = str(update_status.get("fallback_source") or observation.get("fallback_source") or "fallback")
    if primary_status == "failed" and fallback_status == "success" and final_source == "eastmoney":
        if not observation.get("is_valid_for_judgement"):
            return f"{primary_source}抓取失败，{fallback_source}兜底部分成功，但159567与159557日期未同步，因此本日HK_observation不可作最新判断"
        return f"{primary_source}抓取失败，{fallback_source}兜底成功，因此本日HK_observation=latest_valid"
    if primary_status == "failed" and fallback_status == "failed" and final_source == "cache":
        if observation.get("is_valid_for_judgement"):
            return f"{primary_source}与{fallback_source}本次抓取均失败，使用已更新至报告日的本地缓存；latest_date_159567={observation.get('latest_date_159567') or 'missing'}，latest_date_159557={observation.get('latest_date_159557') or 'missing'}"
        return f"{primary_source}与{fallback_source}本次抓取均失败，使用缓存；缓存未形成同步最新行情，不按有效行情处理"
    if primary_status == "success":
        return f"{final_source}抓取成功"
    if fallback_status == "failed":
        return "akshare与eastmoney均失败，缓存不可用时标记缺失"
    return f"数据源链路：primary={primary_status}，fallback={fallback_status}，final={final_source}"


def _hk_proxy_state(observation: dict[str, object]) -> str:
    if not observation.get("is_valid_for_judgement"):
        return "不可判定"
    excess = observation.get("excess_159567_vs_159557_5d")
    if excess is None:
        return "不可判定"
    if excess > 0:
        return "港股创新药ETF强于港股医疗宽基"
    if excess < 0:
        return "港股创新药ETF弱于港股医疗宽基"
    return "港股创新药ETF与港股医疗宽基持平"


def _counter_evidence(s1: S1Record, s2: S2Score, observation: dict[str, object], output_dir: Path, report_date: str, policy_events: list[dict[str, str]] | None = None) -> list[str]:
    triggers: list[str] = []
    trend = _hk_relative_trend(output_dir, report_date, observation)
    try:
        under_streak = int(trend.get("hk_underperform_streak_days") or 0)
    except ValueError:
        under_streak = 0
    if observation.get("is_valid_for_judgement") and under_streak >= 3:
        triggers.append(f"159567 连续 {under_streak} 日跑输 159557：港股创新药承接弱")
    excess = observation.get("excess_159567_vs_159557_5d")
    if observation.get("is_valid_for_judgement") and excess is not None and float(excess) < -0.03:
        triggers.append(f"159567 5日相对159557超额 {_fmt(float(excess), True)}：港股创新药ETF明显弱于宽基")
    event_score = _s2_event_score(s2)
    conversion_score = _s2_conversion_score(s2)
    if event_score >= 0.60 and conversion_score < 0.50:
        triggers.append(f"S2_event_score={event_score:.2f} 但 S2_conversion_score={conversion_score:.2f}：产业热、交易冷")
    s105 = s1.indicators.get("S1-05", {}).get("value")
    if s1.total_score >= 0.60 and s105 is not None and float(s105) < 0.30:
        triggers.append(f"S1_total={s1.total_score:.2f} 但 S1-05={_fmt(float(s105), True)}：A股温度计可能虚修复")
    clinical = s2.items["S2-04"]
    if s2.adjusted_score >= 0.60 and clinical.success_rate == 0:
        triggers.append("S2总分改善但临床事件交易转化仍为0，不能视为事件催化确认")
    mature_statuses = [status for status in clinical.clinical_event_statuses if status.included_in_official_score]
    if len(mature_statuses) >= 3:
        failed = [
            status for status in mature_statuses
            if status.excess_vs_159567_5d is not None and status.excess_vs_159567_5d <= 0
        ]
        if len(failed) > len(mature_statuses) / 2:
            triggers.append(f"成熟临床事件多数跑输159567：ASCO/临床催化转化不足（{len(failed)}/{len(mature_statuses)}）")
    policy_state = _policy_risk_state(policy_events or [])
    if policy_state.get("counter_evidence"):
        triggers.extend(policy_state["counter_evidence"].split("；"))
    return triggers


def _position_explanation_section(s1: S1Record, s2: S2Score, observation: dict[str, object], output_dir: Path, report_date: str, policy_events: list[dict[str, str]] | None = None) -> list[str]:
    event_score = _s2_event_score(s2)
    conversion_score = _s2_conversion_score(s2)
    triggers = _counter_evidence(s1, s2, observation, output_dir, report_date, policy_events)
    if not observation.get("is_valid_for_judgement"):
        hk_strength = f"不可判定，原因：HK_observation 状态为 {observation.get('hk_observation_status') or observation.get('status')}"
    else:
        hk_strength = _hk_proxy_state(observation)
    lines = [
        "## 九、HK_observation反证层_159567",
        "",
        "- 本层只输出159567相对159557的客观状态、反证与待验证项，不输出买卖建议。",
        f"- 产业事件是否有效：{'是' if event_score >= 0.60 else '否'}，S2_event_score={event_score:.2f}。",
        f"- 交易转化是否确认：{'是' if conversion_score >= 0.60 else '否'}，S2_conversion_score={conversion_score:.2f}。",
        f"- 159567 是否强于 159557：{hk_strength}。",
        f"- 今日是否出现反证信号：{'是' if triggers else '否'}。",
    ]
    if triggers:
        lines.extend(f"  - {trigger}" for trigger in triggers)
    else:
        lines.append("  - 暂无已触发反证；继续等待成熟样本和港股行情刷新。")
    lines.extend([
        "",
        "| 临床事件 | 标的 | 相关性 | 成熟状态 | 个股5日 | 个股-159567 | 个股-159567_scope | 个股-159557 | 159567-159557 | 159567-159557_scope |",
        "| --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | --- |",
    ])
    statuses = s2.items["S2-04"].clinical_event_statuses
    for status in statuses[:12]:
        title = " / ".join(part for part in [status.company, status.asset] if part)
        lines.append(
            f"| {title} | {status.ticker} | {status.event_relevance_to_159567 or 'medium'} | {status.trading_status} | "
            f"{_fmt(status.stock_return_5d, True)} | {_fmt(status.excess_vs_159567_5d, True)} | {_relative_data_scope(observation, status.excess_vs_159567_5d)} | "
            f"{_fmt(status.excess_vs_159557_5d, True)} | {_fmt(status.etf_159567_vs_159557_5d, True)} | {_relative_data_scope(observation, status.etf_159567_vs_159557_5d)} |"
        )
    return lines


def _hk_proxy_summary(observation: dict[str, object]) -> str:
    if not observation.get("is_valid_for_judgement"):
        status = observation.get("hk_observation_status") or observation.get("status", "missing")
        common_date = observation.get("common_trade_date") or observation.get("observation_trade_date") or "missing"
        common_excess = observation.get("common_trade_excess_159567_vs_159557_5d")
        if common_excess is not None:
            return f"HK_observation未确认：状态={status}；仅可回看共同交易日 {common_date} 的历史5日超额 {_fmt(common_excess, True)}，不作为最新强弱判断。"
        return f"HK_observation未确认：状态={status}；数据不可判定。"
    excess = observation.get("excess_159567_vs_159557_5d")
    if excess is None:
        return "数据不可判定。"
    verb = "跑赢" if excess > 0 else "跑输" if excess < 0 else "持平"
    magnitude = abs(float(excess))
    return f"159567最近5个交易日{verb}159557 {magnitude:.2%}，说明{_hk_proxy_state(observation)}。"


def _s1_update_line(output_dir: Path) -> str:
    # Do not trust the historical status file alone. It is display metadata and
    # can lag behind the actual S1 indicator JSON after a manual rerun.
    try:
        latest_s1, _ = load_latest_s1(DEFAULT_INDICATORS_DIR)
    except Exception:  # noqa: BLE001 - report should disclose missing S1 state
        return "S1更新状态：无法读取最新S1指标文件。"

    fund_daily_latest = _latest_raw_trade_date("fund_daily.csv", "589720.SH")
    fund_share_latest = _latest_raw_trade_date("fund_share.csv", "589720.SH")
    parts = [
        f"S1指标已更新到 {latest_s1.trade_date}",
        f"本地 589720.SH 行情最新交易日为 {fund_daily_latest or 'missing'}",
        f"fund_share 最新披露日为 {fund_share_latest or 'missing'}",
    ]

    return "S1更新状态：" + "；".join(parts) + "。"


def _latest_raw_trade_date(filename: str, ts_code: str | None = None) -> str:
    path = DEFAULT_MARKET_DATA_DIR / filename
    if not path.exists():
        return ""
    try:
        rows = list(csv.DictReader(path.open(newline="", encoding="utf-8")))
    except OSError:
        return ""
    dates = []
    for row in rows:
        if ts_code and row.get("ts_code") != ts_code:
            continue
        trade_date = str(row.get("trade_date") or "").strip()
        if trade_date:
            dates.append(trade_date)
    return max(dates) if dates else ""


def _combination_observation(s1: S1Record, s2: S2Score) -> str:
    if s1.total_score >= 0.60 and s2.adjusted_score >= 0.60:
        return "S1/S2总分达到符合预期，但关键交易确认项仍未达标。"
    if s1.total_score < 0.60 and s2.adjusted_score >= 0.60:
        return "S2达到符合预期，S1尚未达到"
    if s1.total_score >= 0.60 and s2.adjusted_score < 0.60:
        return "S1达到符合预期，S2尚未达到"
    return "S1与S2均未达到符合预期"


def _industry_event_status(s2: S2Score, new_event_count: int) -> str:
    bd_signal = max(s2.items["S2-01"].adjusted_score, s2.items["S2-02"].adjusted_score)
    if new_event_count > 0 and bd_signal >= 0.60:
        return f"今日新增 {new_event_count} 条确认事件；BD 线索仍处于有效观察区间。"
    if new_event_count > 0:
        return f"今日新增 {new_event_count} 条确认事件；事件已入库，正式产业分仍需继续观察。"
    return "今日无新增重大产业事件，产业事件分沿用当前观察窗口。"


def _trading_conversion_status(s2: S2Score) -> str:
    clinical = s2.items["S2-04"]
    leader = s2.items["S2-05"]
    if clinical.sample_count == 0 and clinical.pending_count > 0:
        return f"S2-04 暂无成熟可计算样本，{clinical.pending_count} 个事件等待满 5 个交易日；S2-05 {leader.rating}。"
    suffix = ""
    if clinical.deduped_trade_sample_count >= 3 and clinical.success_rate == 0:
        suffix = "样本数量满足，但交易转化失败。"
    return f"S2-04 去重正式交易样本 {clinical.sample_count} 个，raw成熟事件 {clinical.raw_mature_event_count} 个，success_rate={_fmt(clinical.success_rate, True)}，评级 {clinical.rating}；S2-05 评级 {leader.rating}。{suffix}"


def _s2_event_score(s2: S2Score) -> float:
    if "S2-03" in s2.items and not all(code in s2.items for code in ("S2-03a", "S2-03b")):
        return sum(s2.items[code].adjusted_score for code in ("S2-01", "S2-02", "S2-03")) / 3
    return sum(s2.items[code].adjusted_score for code in EVENT_SCORE_CODES) / len(EVENT_SCORE_CODES)


def _previous_event_score(previous: dict[str, float]) -> float | None:
    if all(code in previous for code in EVENT_SCORE_CODES):
        return sum(previous[code] for code in EVENT_SCORE_CODES) / len(EVENT_SCORE_CODES)
    if all(code in previous for code in ("S2-01", "S2-02", "S2-03")):
        return sum(previous[code] for code in ("S2-01", "S2-02", "S2-03")) / 3
    return None


def _s2_conversion_score(s2: S2Score) -> float:
    return sum(s2.items[code].adjusted_score for code in ("S2-04", "S2-05")) / 2


def _event_score_state(score: float) -> str:
    if score >= 0.80:
        return "强"
    if score >= 0.60:
        return "符合预期"
    if score >= 0.40:
        return "中性偏弱"
    return "明显弱"


def _conversion_state_code(score: float) -> str:
    if score >= 0.70:
        return "strong_confirmed"
    if score >= 0.60:
        return "confirmed_improving"
    if score >= 0.45:
        return "recovering_not_confirmed"
    return "weak"


def _conversion_state_label(score: float) -> str:
    return {
        "strong_confirmed": "交易转化强确认",
        "confirmed_improving": "交易转化确认改善",
        "recovering_not_confirmed": "交易转化修复中，但未确认",
        "weak": "交易转化弱",
    }[_conversion_state_code(score)]


def _conversion_score_state(s2: S2Score) -> str:
    if s2.items["S2-04"].rating == "待验证":
        return "交易转化待验证"
    score = _s2_conversion_score(s2)
    return _conversion_state_label(score)


def _bd_linkage_explanation(s2: S2Score) -> str:
    frequency = s2.items["S2-01"]
    quality = s2.items["S2-02"]
    frequency_ok = frequency.adjusted_score >= 0.60
    quality_ok = quality.adjusted_score >= 0.60
    if frequency_ok and quality_ok:
        return "BD频率与金额质量均符合预期，说明产业事件侧较前期改善；但该改善尚未通过S2-04和S2-05转化为交易确认。"
    if not frequency_ok and quality_ok:
        return "BD数量频率未放大，但金额质量仍有支撑。"
    if frequency_ok and not quality_ok:
        return "BD数量改善，但金额质量不足，需警惕小额事件堆积。"
    return "BD频率与金额质量均未达到符合预期，产业事件侧仍需继续观察。"


def _hk_event_pending_count(s2: S2Score) -> int:
    return sum(
        status.is_hk_event and not status.included_in_official_score
        for status in s2.items["S2-04"].clinical_event_statuses
    )


def _hk_etf_proxy_status(observation: dict[str, object]) -> str:
    if not observation.get("is_valid_for_judgement"):
        return f"{observation.get('hk_observation_status') or observation['status']}，不可判断"
    excess = observation.get("excess_159567_vs_159557_5d")
    if excess is None:
        return "共同交易日不足，不可判断"
    if excess > 0:
        return "159567 强于 159557"
    if excess < 0:
        return "159567 弱于 159557"
    return "159567 与 159557 持平"


def _next_s204_validation(s2: S2Score, report_date: str) -> dict[str, str]:
    dates: dict[str, int] = {}
    for status in s2.items["S2-04"].clinical_event_statuses:
        if status.trading_status == "pending_not_enough_days" and status.next_maturity_date:
            dates[status.next_maturity_date] = dates.get(status.next_maturity_date, 0) + 1
    if not dates:
        return {"date": "", "days_to": "", "count": "0", "all_dates": ""}
    next_date = sorted(dates)[0]
    try:
        days_to = (datetime.strptime(next_date, "%Y-%m-%d") - datetime.strptime(report_date, "%Y-%m-%d")).days
    except ValueError:
        days_to = 0
    return {
        "date": next_date,
        "days_to": str(max(0, days_to)),
        "count": str(dates[next_date]),
        "all_dates": ", ".join(sorted(dates)),
    }


def _hk_relative_trend(output_dir: Path, report_date: str, observation: dict[str, object]) -> dict[str, str]:
    path = output_dir / "hk_observation_scores.csv"
    rows: list[dict[str, str]] = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            rows = [row for row in csv.DictReader(fh) if row.get("date", "") < report_date]
    current = {
        "date": report_date,
        "status": str(observation.get("status", "")),
        "hk_observation_status": str(observation.get("hk_observation_status", "")),
        "is_valid_for_judgement": str(bool(observation.get("is_valid_for_judgement"))).lower(),
        "excess_5d": _csv_float(observation.get("excess_159567_vs_159557_5d")),
    }
    rows.append(current)
    under_streak = 0
    out_streak = 0
    trend_state = "不可判定"
    direction = "unknown"
    for row in sorted(rows, key=lambda item: item["date"]):
        try:
            excess = float(row.get("excess_5d") or row.get("excess_159567_vs_159557_5d") or "")
        except ValueError:
            valid = False
            excess = 0.0
        else:
            valid = row.get("is_valid_for_judgement", "").lower() == "true"
        if row.get("status") in {"date_mismatch", "data_fetch_failed"} or row.get("hk_observation_status") in {"valid_common_date", "data_fetch_failed"}:
            trend_state = "日期不一致，不更新连续强弱"
            direction = "not_updated"
            continue
        if not valid:
            under_streak = 0
            out_streak = 0
            trend_state = "不可判定"
            direction = "unknown"
        elif excess < 0:
            under_streak += 1
            out_streak = 0
            trend_state = "连续弱于港股医疗宽基" if under_streak >= 3 else "相对强弱未形成连续趋势"
            direction = "当日相对弱"
        elif excess > 0:
            out_streak += 1
            under_streak = 0
            trend_state = "连续强于港股医疗宽基" if out_streak >= 3 else "相对强弱未形成连续趋势"
            direction = "当日相对强"
        else:
            under_streak = 0
            out_streak = 0
            trend_state = "相对强弱未形成连续趋势"
            direction = "当日持平"
    return {
        "excess_5d": _csv_float(observation.get("excess_159567_vs_159557_5d")),
        "excess_5d_direction": direction,
        "hk_underperform_streak_days": str(under_streak),
        "hk_outperform_streak_days": str(out_streak),
        "hk_relative_trend_state": trend_state,
    }


def _previous_item_scores(output_dir: Path, report_date: str) -> dict[str, float]:
    path = output_dir / "s2_item_scores.csv"
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as fh:
        rows = [row for row in csv.DictReader(fh) if row.get("date", "") < report_date]
    if not rows:
        return {}
    latest_date = max(row["date"] for row in rows)
    return {
        row["code"]: float(row["adjusted_score"])
        for row in rows
        if row["date"] == latest_date and row.get("adjusted_score")
    }


def _daily_change_summary(output_dir: Path, report_date: str, s2: S2Score) -> str:
    previous = _previous_item_scores(output_dir, report_date)
    if not all(code in previous for code in ("S2-01", "S2-02", "S2-04", "S2-05")):
        return "暂无完整前一日 S2 子指标，不做日间变化比较。"
    previous_event_score = _previous_event_score(previous)
    if previous_event_score is None:
        return "暂无完整前一日 S2 事件侧子指标，不做日间变化比较。"
    current_event_score = _s2_event_score(s2)
    if current_event_score > previous_event_score:
        event_change = "产业事件侧较前一日改善"
    elif current_event_score < previous_event_score:
        event_change = "产业事件侧较前一日回落"
    else:
        event_change = "产业事件侧与前一日持平"
    repaired = [
        s2.items[code].name
        for code in EVENT_SCORE_CODES
        if code in previous
        if previous[code] < 0.60 <= s2.items[code].adjusted_score
    ]
    repair_text = f"，主要来自{'、'.join(repaired)}修复" if repaired else ""
    clinical = s2.items["S2-04"]
    leader = s2.items["S2-05"]
    if clinical.rating == "待验证":
        conversion_text = f"；但交易转化侧仍未确认，S2-04 无成熟可计算样本，S2-05 {leader.rating}"
    else:
        conversion_text = f"；交易转化侧状态为{_conversion_score_state(s2)}"
    return f"{event_change}{repair_text}{conversion_text}。"


def _previous_score_row(output_dir: Path, report_date: str) -> dict[str, str] | None:
    path = output_dir / "s2_scores.csv"
    if not path.exists():
        return None
    with path.open(newline="", encoding="utf-8") as fh:
        rows = [row for row in csv.DictReader(fh) if row.get("date", "") < report_date]
    if not rows:
        return None
    return sorted(rows, key=lambda row: row["date"])[-1]


def _previous_hk_row(output_dir: Path, report_date: str) -> dict[str, str] | None:
    path = output_dir / "hk_observation_scores.csv"
    if not path.exists():
        return None
    with path.open(newline="", encoding="utf-8") as fh:
        rows = [row for row in csv.DictReader(fh) if row.get("date", "") < report_date]
    if not rows:
        return None
    return sorted(rows, key=lambda row: row["date"])[-1]


def _previous_item_row(output_dir: Path, report_date: str, code: str) -> dict[str, str] | None:
    path = output_dir / "s2_item_scores.csv"
    if not path.exists():
        return None
    with path.open(newline="", encoding="utf-8") as fh:
        rows = [row for row in csv.DictReader(fh) if row.get("date", "") < report_date and row.get("code") == code]
    if not rows:
        return None
    return sorted(rows, key=lambda row: row["date"])[-1]


def _delta_row(name: str, previous: str, current: str, explanation: str) -> str:
    try:
        prev_float = float(previous)
        curr_float = float(current)
        change = f"{curr_float - prev_float:+.2f}"
        prev_text = f"{prev_float:.2f}"
        curr_text = f"{curr_float:.2f}"
    except ValueError:
        change = "无改善" if previous == current else "变化"
        prev_text = previous or "无昨日基准"
        curr_text = current or "数据缺失"
    return f"| {name} | {prev_text} | {curr_text} | {change} | {explanation} |"


def _today_delta_section(s1: S1Record, recent_s1: list[S1Record], s2: S2Score, output_dir: Path, report_date: str, hk_observation: dict[str, object]) -> list[str]:
    previous_score = _previous_score_row(output_dir, report_date)
    previous_hk = _previous_hk_row(output_dir, report_date)
    previous_s204 = _previous_item_row(output_dir, report_date, "S2-04")
    lines = [
        "## 二、今日变化",
        "",
        "| 项目 | 昨日 | 今日 | 变化 | 解释 |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    previous_s1 = recent_s1[-2] if len(recent_s1) >= 2 else None
    if previous_s1:
        explanation = "弱势小幅修复" if s1.total_score > previous_s1.total_score and s1.total_score < 0.50 else _s1_trend(recent_s1)["s1_trend_state"]
        lines.append(_delta_row("S1_total", f"{previous_s1.total_score:.4f}", f"{s1.total_score:.4f}", str(explanation)))
    else:
        lines.append("| S1_total | 无昨日基准 | 数据缺失 | - | 无昨日基准 |")
    if previous_score:
        lines.append(_delta_row("S2_adjusted", previous_score.get("s2_adjusted_score", ""), f"{s2.adjusted_score:.4f}", _daily_change_summary(output_dir, report_date, s2)))
        prev_event = previous_score.get("s2_event_score") or ""
        prev_conversion = previous_score.get("s2_conversion_score") or ""
        lines.append(_delta_row("S2_event_score", prev_event, f"{_s2_event_score(s2):.4f}", f"产业事件侧{_event_score_state(_s2_event_score(s2))}"))
        lines.append(_delta_row("S2_conversion_score", prev_conversion, f"{_s2_conversion_score(s2):.4f}", _conversion_score_state(s2)))
    else:
        lines.append("| S2_adjusted | 无昨日基准 | 数据缺失 | - | 无昨日基准 |")
        lines.append("| S2_event_score | 无昨日基准 | 数据缺失 | - | 无昨日基准 |")
        lines.append("| S2_conversion_score | 无昨日基准 | 数据缺失 | - | 无昨日基准 |")
    previous_pending = previous_s204.get("pending_count", "") if previous_s204 else ""
    lines.append(_delta_row("S2-04 pending", previous_pending, str(s2.items["S2-04"].pending_count), "ASCO/临床事件等待满5个完整交易日"))
    previous_hk_status = previous_hk.get("status", "") if previous_hk else ""
    current_hk_status = str(hk_observation.get("hk_observation_status") or hk_observation.get("status", ""))
    hk_explanation = "仍无法判断159567强弱" if current_hk_status != "latest_valid" else "可判断159567相对159557强弱"
    lines.append(_delta_row("HK_observation", previous_hk_status, current_hk_status, hk_explanation))
    return lines


def _explanation_status(s2: S2Score) -> str:
    statuses: list[str] = []
    clinical = s2.items["S2-04"]
    if clinical.sample_count == 0 and clinical.pending_count > 0:
        statuses.append("事件密集但交易样本未成熟")
    if s2.items["S2-03b"].rating == "数据缺失":
        statuses.append("一致预期验证缺数据")
    if s2.items["S2-03a"].rating != "数据缺失" and s2.items["S2-03b"].rating == "数据缺失":
        statuses.append("财报客观改善有效，但不能冒充超一致预期")
    if s2.items["S2-05"].value is not None and s2.items["S2-05"].value < 0:
        statuses.append("A股龙头接力偏弱")
    if max(s2.items["S2-01"].adjusted_score, s2.items["S2-02"].adjusted_score) >= 0.60 and clinical.rating == "待验证":
        statuses.append("产业事件有效，交易转化待验证")
    return "；".join(statuses) or "正式指标未出现额外解释性状态"


def _main_positive_factors(s2: S2Score, observation: dict[str, object]) -> str:
    factors: list[str] = []
    if s2.items["S2-01"].adjusted_score >= 0.60:
        factors.append("BD频率符合预期")
    if s2.items["S2-02"].adjusted_score >= 0.60:
        factors.append("BD金额质量符合预期")
    factors.append(f"产业事件侧得分{_s2_event_score(s2):.2f}")
    if observation.get("is_valid_for_judgement"):
        factors.append("HK_observation=latest_valid")
    return "；".join(factors)


def _main_negative_factors(s1: S1Record, s2: S2Score, observation: dict[str, object]) -> str:
    factors: list[str] = []
    if s1.total_score < 0.60:
        factors.append(f"S1={s1.total_score:.2f}仍弱")
    if _s2_conversion_score(s2) < 0.60:
        factors.append(f"S2_conversion_score={_s2_conversion_score(s2):.2f}，修复但未确认")
    s105 = s1.indicators.get("S1-05", {}).get("value")
    if s105 is not None and float(s105) < 0.10:
        factors.append(f"S1-05={_fmt(float(s105), True)}，breadth_collapse")
    clinical = s2.items["S2-04"]
    if clinical.success_rate == 0:
        factors.append("S2-04 success_rate=0.00%")
    if observation.get("is_valid_for_judgement") and (observation.get("excess_159567_vs_159557_5d") or 0) < 0:
        factors.append("159567跑输159557")
    if s2.items["S2-05"].value is not None and s2.items["S2-05"].value < 0:
        factors.append("S2-05为负")
    if s2.items["S2-04"].sample_count == 0:
        factors.append("S2-04仍无成熟正式样本")
    return "；".join(factors)


def _final_view_fields(
    s1: S1Record,
    s2: S2Score,
    observation: dict[str, object],
    recent_s1: list[S1Record] | None = None,
    next_validation_dates: str = "",
    policy_events: list[dict[str, str]] | None = None,
    macro_rows: list[dict[str, str]] | None = None,
    report_date: str = "",
) -> dict[str, str]:
    clinical = s2.items["S2-04"]
    leader = s2.items["S2-05"]
    industry_event_score = _s2_event_score(s2)
    conversion_score = _s2_conversion_score(s2)
    industry_event_state = f"产业事件侧{_event_score_state(industry_event_score)}"
    if s2.items["S2-01"].adjusted_score >= 0.60 and s2.items["S2-02"].adjusted_score >= 0.60:
        industry_event_state += "，BD频率与金额质量均符合预期"
    if clinical.rating == "待验证":
        conversion_state = f"交易转化待验证，S2-04无成熟样本，S2-05{leader.rating}"
        final_view_code = "E"
    elif industry_event_score >= 0.60 and conversion_score >= 0.60:
        conversion_state = _conversion_state_label(conversion_score)
        final_view_code = "A"
    elif industry_event_score >= 0.40 and conversion_score >= 0.60:
        conversion_state = _conversion_state_label(conversion_score)
        final_view_code = "B"
    else:
        conversion_state = _conversion_state_label(conversion_score)
        final_view_code = "C" if industry_event_score >= 0.60 else "D"
    final_view_sub_code = ""
    if final_view_code == "C":
        if s2.adjusted_score >= 0.60 and clinical.success_rate == 0 and not observation.get("is_valid_for_judgement"):
            final_view_sub_code = "C3"
        elif _conversion_state_code(conversion_score) == "recovering_not_confirmed":
            final_view_sub_code = "C1"
        else:
            final_view_sub_code = "C2"
    s1_trend = _s1_trend(recent_s1) if recent_s1 else {"s1_trend_state": f"A股温度计{_s1_market_state(s1)}"}
    hk_relative_state = "不可判定"
    if observation.get("is_valid_for_judgement"):
        excess = observation.get("excess_159567_vs_159557_5d")
        if excess is not None and excess < 0:
            hk_relative_state = "159567近5日弱于159557"
        elif excess is not None and excess > 0:
            hk_relative_state = "159567近5日强于159557"
        else:
            hk_relative_state = "159567近5日与159557持平"
    policy_state = _policy_risk_state(policy_events or [])
    negative_factors = _main_negative_factors(s1, s2, observation)
    if policy_state["state"] == "政策风险升高":
        negative_factors = "；".join(part for part in [negative_factors, "Policy_Risk_Layer=risk_up"] if part)
    return {
        "final_view_code": final_view_code,
        "final_view_sub_code": final_view_sub_code,
        "industry_event_state": industry_event_state,
        "conversion_state": conversion_state,
        "a_share_temperature_state": f"A股温度计{_s1_market_state(s1)}，S1={s1.total_score:.2f}",
        "hk_observation_state": f"{observation.get('hk_observation_status') or observation['status']}，{observation['comment']}",
        "industry_event_state_machine": _event_score_state(industry_event_score),
        "a_share_temperature_state_machine": str(s1_trend["s1_trend_state"]),
        "hk_relative_state": hk_relative_state,
        "policy_risk_state": policy_state["state"],
        "macro_layer_status": "moved_to_ai_style_report",
        "macro_risk_state": "moved_to_ai_style_report",
        "conversion_state_machine": f"{_conversion_state_code(conversion_score)}；S2-04{clinical.rating}，S2-05{leader.rating}",
        "main_positive_factors": _main_positive_factors(s2, observation),
        "main_negative_factors": negative_factors,
        "next_validation_dates": next_validation_dates,
    }


def _final_view(s1: S1Record, s2: S2Score, observation: dict[str, object], policy_events: list[dict[str, str]] | None = None, macro_rows: list[dict[str, str]] | None = None, report_date: str = "") -> str:
    fields = _final_view_fields(s1, s2, observation, policy_events=policy_events, macro_rows=macro_rows, report_date=report_date)
    clinical = s2.items["S2-04"]
    s105 = s1.indicators.get("S1-05", {}).get("value")
    if (
        _s2_event_score(s2) >= 0.60
        and 0.45 <= _s2_conversion_score(s2) < 0.60
        and s1.total_score >= 0.60
        and s105 is not None
        and float(s105) < 0.10
        and clinical.deduped_trade_sample_count >= 3
        and clinical.success_rate == 0
        and not observation.get("is_valid_for_judgement")
    ):
        return "产业事件侧符合预期，但交易转化修复未确认；S1总分改善但广度坍缩；S2-04样本数量满足但成功率为0；159567同步行情缺失，因此159567是否右侧不可判定。"
    if (
        _s2_event_score(s2) >= 0.60
        and 0.45 <= _s2_conversion_score(s2) < 0.60
        and s1.total_score >= 0.60
        and s105 is not None
        and float(s105) < 0.10
        and clinical.deduped_trade_sample_count >= 3
        and clinical.success_rate == 0
        and observation.get("is_valid_for_judgement")
    ):
        excess = observation.get("excess_159567_vs_159557_5d")
        hk_phrase = "159567同步行情已恢复"
        if excess is not None and float(excess) < 0:
            hk_phrase += "，近5日相对159557仍偏弱"
        elif excess is not None and float(excess) > 0:
            hk_phrase += "，近5日相对159557转强"
        return f"产业事件侧符合预期，但交易转化修复未确认；S1总分改善但广度坍缩；S2-04样本数量满足但成功率为0；{hk_phrase}，因此159567是否右侧仍需继续验证。"
    return "；".join(part for part in [
        fields["final_view_code"],
        fields["final_view_sub_code"],
        fields["industry_event_state"],
        fields["conversion_state"],
        fields["a_share_temperature_state"],
        fields["hk_observation_state"],
        fields["policy_risk_state"],
    ] if part)


def _within_days(event: dict[str, str], report_date: str, days: int = 90) -> bool:
    try:
        end = datetime.strptime(report_date, "%Y-%m-%d")
        event_date = datetime.strptime(event.get("date", ""), "%Y-%m-%d")
    except ValueError:
        return False
    return end - timedelta(days=days) <= event_date <= end


def _data_quality_actions(s2: S2Score) -> list[str]:
    actions: list[str] = []
    if s2.items["S2-01"].rating == "数据缺失":
        actions.append("可修复缺口：S2-01 需要一次性回填前 4 个完整 90 日窗口的重大 BD 事件。")
    if s2.items["S2-02"].rating == "数据缺失":
        actions.append("可修复缺口：S2-02 需要一次性回填去年同期 90 日重大 BD 金额。")
    if s2.items["S2-03b"].rating == "数据缺失":
        actions.append("外部来源缺口：S2-03b 需要接入可靠一致预期来源；仅有同比增长不能替代 beat / miss。")
    if s2.items["S2-04"].rating == "待验证":
        actions.append(f"自然等待：S2-04 有 {s2.items['S2-04'].pending_count} 个临床事件尚未满 5 个完整交易日。")
    return actions


def _event_dedupe_status(events: list[dict[str, str]]) -> str:
    seen: dict[tuple[str, str, str, str], int] = {}
    for event in events:
        if event.get("is_duplicate", "false").lower() in {"true", "1", "yes", "y", "是"}:
            continue
        key = (
            event.get("company", ""),
            event.get("asset", ""),
            event.get("conference", "") or event.get("partner", ""),
            event.get("date", ""),
        )
        seen[key] = seen.get(key, 0) + 1
    return "有待复核" if any(count > 1 for count in seen.values()) else "通过"


def _policy_risk_state(policy_events: list[dict[str, str]]) -> dict[str, str]:
    active = [row for row in policy_events if row.get("status", "").lower() in {"active", "watch", "monitoring", "effective", "proposed"}]
    elevated = [
        row for row in active
        if row.get("risk_direction", "").lower() in {"risk_up", "up", "升高"}
        and row.get("severity", "").lower() in {"high", "medium", "中", "高"}
    ]
    if elevated:
        return {
            "state": "政策风险升高",
            "summary": "；".join(row.get("event_name", "") for row in elevated if row.get("event_name")),
            "counter_evidence": "BD出海估值折价风险；港股创新药风险偏好压制",
        }
    if active:
        return {
            "state": "政策风险观察",
            "summary": "；".join(row.get("event_name", "") for row in active if row.get("event_name")),
            "counter_evidence": "",
        }
    return {"state": "无有效政策风险记录", "summary": "missing", "counter_evidence": ""}


def _latest_macro_row(rows: list[dict[str, str]], report_date: str) -> dict[str, str] | None:
    eligible = [row for row in rows if (row.get("snapshot_date") or row.get("date", "")) <= report_date]
    if not eligible:
        return None
    return sorted(eligible, key=lambda row: row.get("snapshot_date") or row.get("date", ""))[-1]


def _pct_number(value: str) -> float | None:
    raw = (value or "").strip().replace("%", "")
    if not raw or raw.lower() == "missing":
        return None
    try:
        number = float(raw)
    except ValueError:
        return None
    return number / 100 if abs(number) > 1 else number


def _is_missing_text(value: object) -> bool:
    raw = str(value or "").strip().lower()
    return raw in {"", "missing", "数据缺失"}


def _market_audit_rows(output_dir: Path) -> dict[str, dict[str, str]]:
    rows = load_events(output_dir / "data_audit" / "market_data_audit.csv")
    return {str(row.get("symbol") or ""): row for row in rows}


def _audit_row_for_symbol(audit_rows: dict[str, dict[str, str]], symbol: str) -> dict[str, str]:
    raw = str(symbol or "")
    candidates = [raw]
    if raw.endswith(".HK"):
        candidates.append(f"{raw.removesuffix('.HK').zfill(5)}.HK")
    for candidate in candidates:
        if candidate in audit_rows:
            return audit_rows[candidate]
    return {}


def _audit_value(row: dict[str, str], field: str) -> str:
    return row.get(field) or "missing"


def _audit_status(row: dict[str, str]) -> str:
    if not row:
        return "missing"
    return "passed" if str(row.get("can_use_for_latest_signal") or "").lower() == "true" else "blocked"


def _commercialization_report_state(data_dir: Path) -> dict[str, object]:
    rows = load_events(data_dir / "commercialization_metrics.csv")
    key_fields = ["total_revenue_yoy", "product_revenue_yoy", "innovation_drug_revenue_yoy", "adjusted_profit_yoy", "operating_cash_flow", "cash_balance"]
    official_source_types = {"official_report", "company_announcement", "exchange_filing", "official_disclosure", "annual_report", "interim_report", "quarterly_report"}
    if not rows:
        return {
            "status": "insufficient_data",
            "score": "missing",
            "usable_count": 0,
            "core_count": 0,
            "coverage": 0.0,
            "field_completeness": 0.0,
            "note": "商业化核心公司指标覆盖不足：0/0；缺失字段保留missing",
        }
    usable = [row for row in rows if any(not _is_missing_text(row.get(field)) for field in key_fields)]
    filled_fields = sum(1 for row in rows for field in key_fields if not _is_missing_text(row.get(field)))
    total_fields = len(rows) * len(key_fields)
    coverage = len(usable) / len(rows)
    completeness = filled_fields / total_fields if total_fields else 0.0
    status = "scorable" if len(usable) >= 3 and completeness >= 0.50 else "insufficient_data"
    non_official_sources = [
        row for row in usable
        if str(row.get("source_type") or "").strip().lower() not in official_source_types
    ]
    if status == "scorable" and (completeness <= 0.50 or non_official_sources):
        status = "scorable_low_confidence"
    score = "scorable" if status == "scorable" else "missing"
    if status == "scorable":
        note_prefix = "商业化核心公司指标达到最低评分覆盖"
    elif status == "scorable_low_confidence":
        note_prefix = "商业化核心公司指标达到最低评分覆盖，但完整度或来源置信度偏低"
    else:
        note_prefix = "商业化核心公司指标覆盖不足"
    source_note = ""
    if non_official_sources:
        source_note = f"；非官方/媒体来源样本={len(non_official_sources)}"
    return {
        "status": status,
        "score": score,
        "usable_count": len(usable),
        "core_count": len(rows),
        "coverage": coverage,
        "field_completeness": completeness,
        "note": f"{note_prefix}：{len(usable)}/{len(rows)}；关键字段完整度={completeness:.0%}{source_note}；缺失字段保留missing",
    }


def _macro_layer_status(rows: list[dict[str, str]], report_date: str) -> dict[str, object]:
    row = _latest_macro_row(rows, report_date)
    core_fields = ["QQQ_pct", "SOXX_pct", "SMH_pct", "XBI_pct", "IBB_pct", "XLV_pct", "XLP_pct", "XLU_pct", "HSTECH_pct", "ETF_159557_pct", "ETF_159567_pct"]
    if row is None:
        return {"status": "insufficient_data", "missing_count": len(core_fields), "core_count": len(core_fields), "missing_ratio": 1.0}
    present = 0
    for field in core_fields:
        if field in {"SOXX_pct", "SMH_pct"}:
            continue
        if not _is_missing_text(row.get(field)):
            present += 1
    if not _is_missing_text(row.get("SOXX_pct")) or not _is_missing_text(row.get("SMH_pct")):
        present += 1
    core_count = 10
    missing_count = core_count - present
    missing_ratio = missing_count / core_count
    return {
        "status": "insufficient_data" if missing_ratio > 0.50 else "valid",
        "missing_count": missing_count,
        "core_count": core_count,
        "missing_ratio": missing_ratio,
    }


def _relative_data_scope(observation: dict[str, object], value: object | None = None) -> str:
    if _is_missing_text(value):
        return "missing"
    if observation.get("is_valid_for_judgement"):
        return "latest_valid"
    return "historical_common_date"


def _macro_states(rows: list[dict[str, str]], report_date: str) -> dict[str, str]:
    row = _latest_macro_row(rows, report_date)
    if row is None:
        return {
            "date": "missing",
            "risk_on_growth": "missing",
            "risk_off_defensive": "missing",
            "ai_crowding_unwind": "missing",
            "biotech_relative_strength": "missing",
            "hk_innovation_vs_health": "missing",
        }
    qqq = _pct_number(row.get("QQQ_pct") or row.get("QQQ", ""))
    soxx = _pct_number(row.get("SOXX_pct") or row.get("SOXX", "")) if (row.get("SOXX_pct") or row.get("SOXX")) else _pct_number(row.get("SMH_pct") or row.get("SMH", ""))
    xbi = _pct_number(row.get("XBI_pct") or row.get("XBI", ""))
    ibb = _pct_number(row.get("IBB_pct") or row.get("IBB", ""))
    xlv = _pct_number(row.get("XLV_pct") or row.get("XLV", ""))
    xlp = _pct_number(row.get("XLP_pct") or row.get("XLP", ""))
    xlu = _pct_number(row.get("XLU_pct") or row.get("XLU", ""))
    hk_inno = _pct_number(row.get("ETF_159567_pct") or row.get("159567", ""))
    hk_health = _pct_number(row.get("ETF_159557_pct") or row.get("159557", ""))
    defensive_values = [value for value in [xlv, xlp, xlu] if value is not None]
    defensive = sum(defensive_values) / len(defensive_values) if defensive_values else None
    biotech = xbi if xbi is not None else ibb
    return {
        "date": row.get("snapshot_date") or row.get("date", "missing") or "missing",
        "risk_on_growth": "true" if qqq is not None and qqq > 0 and (defensive is None or qqq > defensive) else "false" if qqq is not None else "missing",
        "risk_off_defensive": "true" if defensive is not None and qqq is not None and defensive > qqq else "false" if defensive is not None and qqq is not None else "missing",
        "ai_crowding_unwind": "true" if soxx is not None and qqq is not None and soxx < qqq < 0 else "false" if soxx is not None and qqq is not None else "missing",
        "biotech_relative_strength": "true" if biotech is not None and xlv is not None and biotech > xlv else "false" if biotech is not None and xlv is not None else "missing",
        "hk_innovation_vs_health": "positive" if hk_inno is not None and hk_health is not None and hk_inno > hk_health else "negative" if hk_inno is not None and hk_health is not None and hk_inno < hk_health else "missing",
    }


def _policy_risk_section(policy_events: list[dict[str, str]]) -> list[str]:
    state = _policy_risk_state(policy_events)
    lines = [
        "## 七、Policy_Risk_Layer 政策风险层",
        "",
        "- Policy_Risk_Layer 不进入 S2_event_score，不改变 S2_total，只进入 final_view 解释和反证层。",
        f"- 当前状态：{state['state']}。",
        "",
        "| event_name | event_date | region | affected_chain | risk_direction | severity | status | affected_symbols | source_url | last_checked_date | explanation |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not policy_events:
        lines.append("| missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing |")
    for row in policy_events:
        lines.append(
            f"| {_cell(row.get('event_name'))} | {_cell(row.get('event_date'))} | {_cell(row.get('region'))} | "
            f"{_cell(row.get('affected_chain'))} | {_cell(row.get('risk_direction'))} | {_cell(row.get('severity'))} | "
            f"{_cell(row.get('status'))} | {_cell(row.get('affected_symbols'))} | {_cell(row.get('source_url'))} | "
            f"{_cell(row.get('last_checked_date'))} | {_cell(row.get('explanation'))} |"
        )
    return lines


def _macro_risk_section(macro_rows: list[dict[str, str]], report_date: str) -> list[str]:
    states = _macro_states(macro_rows, report_date)
    layer = _macro_layer_status(macro_rows, report_date)
    latest = _latest_macro_row(macro_rows, report_date) or {}
    lines = [
        "## 八、Macro_Risk_Layer 宏观资金层",
        "",
        "- Macro_Risk_Layer 不进入 S2正式分，只用于解释交易转化强弱。",
        f"- macro_layer_status = {layer['status']}；核心字段缺失 {layer['missing_count']}/{layer['core_count']}（{layer['missing_ratio']:.0%}）。",
        f"- macro_risk_state = {'不可判定' if layer['status'] == 'insufficient_data' else 'valid'}。",
        "",
        "| 状态 | 数值 |",
        "| --- | ---: |",
        f"| snapshot_date | {states['date']} |",
        f"| macro_layer_status | {layer['status']} |",
        f"| risk_off_defensive | {states['risk_off_defensive']} |",
        f"| ai_crowding_unwind | {states['ai_crowding_unwind']} |",
        f"| biotech_relative_strength | {states['biotech_relative_strength']} |",
        f"| hk_innovation_vs_health | {states.get('hk_innovation_vs_health', 'missing')} |",
        "",
        "| 资产 | 日度/窗口变化 |",
        "| --- | ---: |",
    ]
    for field in MACRO_MARKET_FIELDS[1:]:
        lines.append(f"| {field} | {latest.get(field) or 'missing'} |")
    return lines


def _data_quality_section(s1: S1Record, s2: S2Score, today_new_count: int, hk_observation: dict[str, object], hk_update_status: dict[str, object], events: list[dict[str, str]], data_dir: Path) -> list[str]:
    clinical = s2.items["S2-04"]
    commercialization_state = _commercialization_report_state(data_dir)
    primary_status = hk_update_status.get("primary_source_status", "unknown")
    fallback_status = hk_update_status.get("fallback_source_status", "unknown")
    final_source = hk_update_status.get("final_data_source") or hk_observation.get("data_source") or "数据缺失"
    rows = [
        ("S1", "valid", f"589720行情和指标更新到{s1.trade_date}"),
        ("S2事件库", "valid", f"今日新增{today_new_count}条确认事件"),
        ("事件去重检查", _event_dedupe_status(events), "is_duplicate=true 的事件不进入正式统计"),
        ("S2-04交易转化", "pending" if clinical.pending_count else "valid", f"raw_mature_event_count={clinical.raw_mature_event_count}；deduped_trade_sample_count={clinical.deduped_trade_sample_count}；{clinical.pending_count}个事件未满5日"),
        ("HK_observation", str(hk_observation.get("hk_observation_status") or hk_observation.get("status", "missing")), f"source={final_source}；source_status={hk_observation.get('primary_source_status', primary_status)}->{hk_observation.get('fallback_source_status', fallback_status)}；primary_source_status={primary_status}；fallback_source_status={fallback_status}；latest_date_159567={hk_observation.get('latest_date_159567') or 'missing'}；latest_date_159557={hk_observation.get('latest_date_159557') or 'missing'}；common_trade_date={hk_observation.get('common_trade_date') or hk_observation.get('observation_trade_date') or 'missing'}；calendar_lag_days={hk_observation.get('calendar_lag_days', 'missing')}；trading_lag_days={hk_observation.get('trading_lag_days', 'missing')}；report_day_price_available_externally={str(bool(hk_observation.get('report_day_price_available_externally'))).lower()}；local_fetch_failed={str(bool(hk_observation.get('local_fetch_failed'))).lower()}；data_fetch_failed={str(bool(hk_observation.get('data_fetch_failed'))).lower()}"),
        ("S2-03a财报客观改善", "missing" if s2.items["S2-03a"].rating == "数据缺失" else s2.items["S2-03a"].rating, s2.items["S2-03a"].missing or "财报客观改善为正，但样本不足且没有一致预期验证，不得称为超预期"),
        ("S2-03b一致预期验证", "missing" if s2.items["S2-03b"].rating == "数据缺失" else "valid", s2.items["S2-03b"].missing or "具备一致预期样本"),
        ("S2-06商业化兑现质量", str(commercialization_state["status"]), commercialization_state["note"] if commercialization_state["status"] != "scorable" else s2.explanation_items["S2-06"].missing or "商业化指标样本有效"),
    ]
    lines = [
        "## 三、数据质量摘要",
        "",
        "| 模块 | 状态 | 说明 |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| {module} | {status} | {note} |" for module, status, note in rows)
    return lines


def _hk_observation_section(observation: dict[str, object], output_dir: Path, report_date: str) -> list[str]:
    trend = _hk_relative_trend(output_dir, report_date, observation)
    audit_rows = _market_audit_rows(output_dir)
    audit_159567 = _audit_row_for_symbol(audit_rows, "159567.SZ")
    audit_159557 = _audit_row_for_symbol(audit_rows, "159557.SZ")
    lines = [
        "## 六、第三层：HK_observation_159567观察层",
        "",
        "| 项目 | 数值 |",
        "| --- | ---: |",
        f"| 底层数据状态 | {observation['status']} |",
        f"| hk_observation_status | {observation.get('hk_observation_status') or observation['status']} |",
        f"| latest_date_159567 | {observation.get('latest_date_159567') or 'missing'} |",
        f"| latest_date_159557 | {observation.get('latest_date_159557') or 'missing'} |",
        f"| common_trade_date | {observation.get('common_trade_date') or observation.get('observation_trade_date') or 'missing'} |",
        f"| report_trade_date | {observation.get('report_trade_date') or report_date.replace('-', '')} |",
        f"| lag_days_159567 | {observation.get('lag_days_159567', 'missing')} |",
        f"| lag_days_159557 | {observation.get('lag_days_159557', 'missing')} |",
        f"| calendar_lag_days | {observation.get('calendar_lag_days', 'missing')} |",
        f"| trading_lag_days | {observation.get('trading_lag_days', 'missing')} |",
        f"| report_day_price_available_externally | {str(bool(observation.get('report_day_price_available_externally'))).lower()} |",
        f"| local_fetch_failed | {str(bool(observation.get('local_fetch_failed'))).lower()} |",
        f"| data_fetch_failed | {str(bool(observation.get('data_fetch_failed'))).lower()} |",
        f"| 数据源 | {observation.get('data_source') or '数据缺失'} |",
        f"| primary_source_status | {observation.get('primary_source_status') or '数据缺失'} |",
        f"| fallback_source_status | {observation.get('fallback_source_status') or '数据缺失'} |",
        f"| final_data_source | {observation.get('final_data_source') or observation.get('data_source') or '数据缺失'} |",
        f"| 159567_audit_final_source | {_audit_value(audit_159567, 'final_source')} |",
        f"| 159567_audit_final_source_reason | {_audit_value(audit_159567, 'final_source_reason')} |",
        f"| 159567_audit_fetched_at | {_audit_value(audit_159567, 'fetched_at')} |",
        f"| 159567_audit_data_quality | {_audit_value(audit_159567, 'data_quality')} |",
        f"| 159567_audit_can_use_for_latest_signal | {_audit_value(audit_159567, 'can_use_for_latest_signal')} |",
        f"| 159567_audit_raw_latest_date | {_audit_value(audit_159567, 'raw_latest_date')} |",
        f"| 159567_audit_cache_latest_date | {_audit_value(audit_159567, 'cache_latest_date')} |",
        f"| 159567_audit_processed_latest_date | {_audit_value(audit_159567, 'processed_latest_date')} |",
        f"| 159557_audit_final_source | {_audit_value(audit_159557, 'final_source')} |",
        f"| 159557_audit_final_source_reason | {_audit_value(audit_159557, 'final_source_reason')} |",
        f"| 159557_audit_fetched_at | {_audit_value(audit_159557, 'fetched_at')} |",
        f"| 159557_audit_data_quality | {_audit_value(audit_159557, 'data_quality')} |",
        f"| 159557_audit_can_use_for_latest_signal | {_audit_value(audit_159557, 'can_use_for_latest_signal')} |",
        f"| 159557_audit_raw_latest_date | {_audit_value(audit_159557, 'raw_latest_date')} |",
        f"| 159557_audit_cache_latest_date | {_audit_value(audit_159557, 'cache_latest_date')} |",
        f"| 159557_audit_processed_latest_date | {_audit_value(audit_159557, 'processed_latest_date')} |",
        f"| 是否参与判断 | {'是' if observation.get('is_valid_for_judgement') else '否'} |",
    ]
    if observation.get("is_valid_for_judgement"):
        lines.extend([
            f"| 159567 1日收益 | {_fmt(observation.get('return_159567_1d'), True)} |",
            f"| 159557 1日收益 | {_fmt(observation.get('return_159557_1d'), True)} |",
            f"| 159567 - 159557 单日超额 | {_fmt(observation.get('excess_159567_vs_159557_1d'), True)} |",
            f"| 159567 5日收益 | {_fmt(observation.get('return_159567_5d'), True)} |",
            f"| 159557 5日收益 | {_fmt(observation.get('return_159557_5d'), True)} |",
            f"| 159567 - 159557 5日超额 | {_fmt(observation.get('excess_159567_vs_159557_5d'), True)} |",
            f"| 159567 10日收益 | {_fmt(observation.get('return_159567_10d'), True)} |",
            f"| 159557 10日收益 | {_fmt(observation.get('return_159557_10d'), True)} |",
            f"| 159567 - 159557 10日超额 | {_fmt(observation.get('excess_159567_vs_159557_10d'), True)} |",
            f"| 159567相对收益data_scope | {_relative_data_scope(observation, observation.get('excess_159567_vs_159557_5d'))} |",
        ])
    elif observation.get("common_trade_excess_159567_vs_159557_5d") is not None:
        lines.extend([
            f"| 共同交易日历史159567 5日收益 | {_fmt(observation.get('common_trade_return_159567_5d'), True)} |",
            f"| 共同交易日历史159557 5日收益 | {_fmt(observation.get('common_trade_return_159557_5d'), True)} |",
            f"| 共同交易日历史159567 - 159557 5日超额 | {_fmt(observation.get('common_trade_excess_159567_vs_159557_5d'), True)} |",
            f"| 共同交易日历史159567相对收益data_scope | {_relative_data_scope(observation, observation.get('common_trade_excess_159567_vs_159557_5d'))} |",
        ])
    lines.extend([
        f"| 原因 | {observation['comment']} |",
        "",
        f"- {observation['comment']}",
        "- HK_observation 不进入 S2_total，不改变 S2 adjusted_score，只用于辅助解释 159567 是否强于 159557。",
        "",
        "### 159567 相对 159557 连续强弱",
        "",
        "| 项目 | 数值 |",
        "| --- | ---: |",
        f"| 今日单日超额 | {_fmt(observation.get('excess_159567_vs_159557_1d'), True)} |",
        f"| 今日单日超额data_scope | {_relative_data_scope(observation, observation.get('excess_159567_vs_159557_1d'))} |",
        f"| 今日5日超额 | {_fmt(observation.get('excess_159567_vs_159557_5d'), True)} |",
        f"| 今日5日超额data_scope | {_relative_data_scope(observation, observation.get('excess_159567_vs_159557_5d'))} |",
        f"| 今日10日超额 | {_fmt(observation.get('excess_159567_vs_159557_10d'), True)} |",
        f"| 今日10日超额data_scope | {_relative_data_scope(observation, observation.get('excess_159567_vs_159557_10d'))} |",
        f"| 共同交易日历史5日超额 | {_fmt(observation.get('common_trade_excess_159567_vs_159557_5d'), True)} |",
        f"| 共同交易日历史5日超额data_scope | {_relative_data_scope(observation, observation.get('common_trade_excess_159567_vs_159557_5d'))} |",
        f"| 连续跑输天数 | {trend['hk_underperform_streak_days']} |",
        f"| 连续跑赢天数 | {trend['hk_outperform_streak_days']} |",
        f"| 相对趋势状态 | {trend['hk_relative_trend_state']} |",
    ])
    return lines


def _clinical_status_section(s2: S2Score, hk_observation: dict[str, object], output_dir: Path) -> list[str]:
    item = s2.items["S2-04"]
    statuses = item.clinical_event_statuses
    audit_rows = _market_audit_rows(output_dir)
    lines = [
        "### S2-04 临床事件成熟度",
        "",
        f"- S2-04_official_status：{item.rating}。",
        f"- S2-04_official_sample_count：{item.sample_count}。",
        f"- raw_mature_event_count：{item.raw_mature_event_count}。",
        f"- deduped_trade_sample_count：{item.deduped_trade_sample_count}。",
        f"- success_count：{item.success_count}。",
        f"- success_rate：{_fmt(item.success_rate, True)}。",
        f"- S2-04_hk_event_pending_count：{_hk_event_pending_count(s2)}。",
        f"- S2-04_hk_event_pending_or_missing_count：{_hk_event_pending_count(s2)}。",
        f"- HK_observation_status：{_hk_etf_proxy_status(hk_observation)}。",
        "- 港股临床事件若本地 `s2/data/hk_daily.csv` 有完整个股价格，则进入 S2-04 正式样本；缺行情时列明缺失标的，不编造。",
        f"- 成熟可计算样本：{sum(status.included_in_official_score for status in statuses)}；等待满 5 日：{sum(status.trading_status == 'pending_not_enough_days' for status in statuses)}；港股行情缺失/待补：{sum(status.is_hk_event and status.trading_status == 'missing_price' for status in statuses)}；本地价格缺失：{sum(status.trading_status == 'missing_price' for status in statuses)}。",
    ]
    if item.deduped_trade_sample_count >= 3 and item.success_rate == 0:
        lines.append("- 样本数量满足，但交易转化失败。")
    maturity_dates = sorted({status.next_maturity_date for status in statuses if status.next_maturity_date})
    lines.append(f"- 下一批预计成熟日期：{', '.join(maturity_dates[:3]) if maturity_dates else '暂无'}。")
    lines.extend([
        "",
        "### S2-04 待成熟事件日历",
        "",
        "| 预计成熟日期 | 事件数量 | 涉及公司 | 说明 |",
        "| --- | ---: | --- | --- |",
    ])
    calendar: dict[str, list[str]] = {}
    for status in statuses:
        if status.trading_status == "pending_not_enough_days" and status.next_maturity_date:
            calendar.setdefault(status.next_maturity_date, []).append(status.company)
    if calendar:
        for date, companies in sorted(calendar.items()):
            unique_companies = sorted(set(companies))
            lines.append(f"| {date} | {len(companies)} | {', '.join(unique_companies)} | 可开始计算5日交易转化 |")
    else:
        lines.append("| 暂无 | 0 | - | 无待成熟事件 |")
    lines.extend([
        "",
        "| 公司 | 标的 | 事件日期 | benchmark_code | window_days | trade_sample_id | mature_date | days_to_mature | 已过交易日 | 状态 | stock_audit_status | benchmark_audit_status | stock_data_quality | benchmark_data_quality | stock_can_use_for_latest_signal | benchmark_can_use_for_latest_signal | 说明 | 是否进入去重正式分 |",
        "| --- | --- | --- | --- | ---: | --- | --- | ---: | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    if not statuses:
        lines.append("| 数据缺失 | - | - | - | - | - | - | - | - | 无临床事件 | missing | missing | missing | missing | missing | missing | - | 否 |")
    for status in statuses:
        stock_audit = _audit_row_for_symbol(audit_rows, status.ticker)
        benchmark_audit = _audit_row_for_symbol(audit_rows, status.benchmark_code)
        days_to_mature = max(0, status.required_days - status.days_elapsed)
        mature_date = status.next_maturity_date or ("已满5日" if status.is_mature else "数据缺失")
        if status.trading_status == "pending_not_enough_days":
            note = "未满5个完整交易日"
        elif status.trading_status == "missing_price":
            note = "成熟但本地价格缺失，暂不进入正式S2-04"
        elif status.trading_status == "mature_calculable":
            note = "成熟可算"
        elif status.trading_status == "mature_deduped_duplicate":
            note = status.dedupe_note or "同一交易样本已计分，本项目仅保留明细"
        else:
            note = "成熟但不可算"
        lines.append(
            f"| {_cell(status.company)} | {_cell(status.ticker)} | {_cell(status.event_date)} | {_cell(status.benchmark_code or '-')} | {status.window_days} | {_cell(status.trade_sample_id or '-')} | {_cell(mature_date)} | {days_to_mature} | {status.days_elapsed}/{status.required_days} | {_cell(status.trading_status)} | "
            f"{_cell(_audit_status(stock_audit))} | {_cell(_audit_status(benchmark_audit))} | "
            f"{_cell(_audit_value(stock_audit, 'data_quality'))} | {_cell(_audit_value(benchmark_audit, 'data_quality'))} | "
            f"{_cell(_audit_value(stock_audit, 'can_use_for_latest_signal'))} | {_cell(_audit_value(benchmark_audit, 'can_use_for_latest_signal'))} | "
            f"{_cell(note)} | {'是' if status.included_in_deduped_trade_sample else '否'} |"
        )
    lines.extend([
        "",
        "### HK_observation ETF观察",
        "",
        "- 港股临床事件只有在港股个股行情可得时才进入正式S2-04；HK_observation只回答159567是否强于159557。",
        "- HK_observation不进入S2_total，不改变adjusted_score。",
        "",
        "| 字段 | 数值 |",
        "| --- | ---: |",
        f"| hk_observation_available | {'true' if hk_observation.get('is_valid_for_judgement') else 'false'} |",
        f"| hk_observation_return_159567 | {_fmt(hk_observation.get('return_159567_5d'), True)} |",
        f"| hk_observation_return_159557 | {_fmt(hk_observation.get('return_159557_5d'), True)} |",
        f"| hk_observation_excess_159567_vs_159557 | {_fmt(hk_observation.get('excess_159567_vs_159557_5d'), True)} |",
        f"| hk_observation_excess_data_scope | {_relative_data_scope(hk_observation, hk_observation.get('excess_159567_vs_159557_5d'))} |",
    ])
    return lines


def _earnings_observation_section(earnings_events: list[dict[str, str]], consensus_rows: list[dict[str, str]]) -> list[str]:
    active = [event for event in earnings_events if event.get("status", "active") == "active"]
    lines = [
        "### S2-03a / S2-03b 业绩验证层",
        "",
        "S2-03a 只判断财报客观改善；S2-03b 必须基于可靠一致预期来源判断 beat / miss。不得用同比增长冒充超预期。",
        "",
        "| 公司 | 期间 | 营收同比 | 产品收入同比 | 利润同比/状态 | 业务改善 | 亏损收窄 | 扭亏 | 指引上调 | has_consensus | beat | 一致预期来源 |",
        "| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not active:
        lines.append("| missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing |")
    for event in active:
        lines.append(
            f"| {event.get('company') or 'missing'} | {event.get('period') or 'missing'} | {event.get('revenue_yoy') or 'missing'} | "
            f"{event.get('product_revenue_yoy') or 'missing'} | {event.get('profit_yoy') or 'missing'} | {event.get('business_improved') or 'missing'} | "
            f"{event.get('loss_narrowed') or 'missing'} | {event.get('turned_profitable') or 'missing'} | {event.get('guidance_raised') or 'missing'} | "
            f"{event.get('has_consensus') or 'missing'} | {event.get('beat') or 'missing'} | {event.get('consensus_source_url') or 'missing'} |"
        )
    lines.extend([
        "",
        "### S2-03b 一致预期验证表",
        "",
        "- 若没有可靠一致预期来源，S2-03b = missing；同比增长不得替代 beat / miss。",
        "",
        "| company_name | symbol | report_period | actual_revenue | consensus_revenue | revenue_beat | actual_adjusted_profit | consensus_adjusted_profit | profit_beat | actual_eps | consensus_eps | eps_beat | consensus_source | source_url | source_date | confidence | note |",
        "| --- | --- | --- | ---: | ---: | --- | ---: | ---: | --- | ---: | ---: | --- | --- | --- | --- | --- | --- |",
    ])
    if not consensus_rows:
        lines.append("| missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing |")
    for row in consensus_rows:
        lines.append(
            f"| {_cell(row.get('company_name'))} | {_cell(row.get('symbol'))} | {_cell(row.get('report_period'))} | "
            f"{_cell(row.get('actual_revenue'))} | {_cell(row.get('consensus_revenue'))} | {_cell(row.get('revenue_beat'))} | "
            f"{_cell(row.get('actual_adjusted_profit'))} | {_cell(row.get('consensus_adjusted_profit'))} | {_cell(row.get('profit_beat'))} | "
            f"{_cell(row.get('actual_eps'))} | {_cell(row.get('consensus_eps'))} | {_cell(row.get('eps_beat'))} | "
            f"{_cell(row.get('consensus_source'))} | {_cell(row.get('source_url'))} | {_cell(row.get('source_date'))} | "
            f"{_cell(row.get('confidence'))} | {_cell(row.get('note'))} |"
        )
    return lines


def _commercialization_section(s2: S2Score, data_dir: Path) -> list[str]:
    path = data_dir / "commercialization_metrics.csv"
    rows = load_events(path)
    item = s2.explanation_items["S2-06"]
    report_state = _commercialization_report_state(data_dir)
    display_status = report_state["status"] if report_state["status"] != "scorable" else item.rating
    display_score = "missing" if report_state["status"] == "insufficient_data" else _fmt(item.value)
    lines = [
        "### S2-06 商业化兑现质量",
        "",
        "- S2-06 只判断商业化兑现质量，不替代 S2-03，不进入 S2_event_score 或 S2_total。",
        "- S2-06 只有有效覆盖核心公司数 >= 3 且关键字段完整度 >= 50% 时才允许评分。",
        f"- S2-06_status：{display_status}。",
        f"- S2-06_score：{display_score}。",
        f"- S2-06_usable_core_company_count：{report_state['usable_count']}/{report_state['core_count']}。",
        f"- S2-06_key_field_completeness：{report_state['field_completeness']:.0%}。",
        f"- S2-06_missing：{report_state['note'] if report_state['status'] != 'scorable' else item.missing or '无'}。",
        f"- S2-06_basis：{item.basis}。",
        "",
        "| company_name | symbol | report_period | total_revenue_yoy | product_revenue_yoy | innovation_drug_revenue_yoy | adjusted_profit_yoy | operating_cash_flow | cash_balance | source_url | source_date | source_type |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    if not rows:
        lines.append("| missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing |")
    for row in rows:
        lines.append(
            f"| {row.get('company_name') or row.get('company') or 'missing'} | {row.get('symbol') or row.get('ticker') or 'missing'} | {row.get('report_period') or 'missing'} | "
            f"{row.get('total_revenue_yoy') or 'missing'} | {row.get('product_revenue_yoy') or 'missing'} | {row.get('innovation_drug_revenue_yoy') or 'missing'} | "
            f"{row.get('adjusted_profit_yoy') or 'missing'} | {row.get('operating_cash_flow') or 'missing'} | {row.get('cash_balance') or 'missing'} | "
            f"{row.get('source_url') or 'missing'} | {row.get('source_date') or 'missing'} | {row.get('source_type') or 'missing'} |"
        )
    return lines


def _condition_direction(current: float | None, previous: float | None, higher_is_better: bool = True) -> str:
    if current is None or previous is None:
        return "unknown"
    if current == previous:
        return "unchanged"
    improved = current > previous if higher_is_better else current < previous
    return "improving" if improved else "worsening"


def _direction_cn(direction: str) -> str:
    return {
        "improving": "改善",
        "worsening": "走弱",
        "unchanged": "持平",
        "unknown": "方向未知",
    }.get(direction, direction)


def _observation_conditions(s1: S1Record, recent_s1: list[S1Record], s2: S2Score, observation: dict[str, object], output_dir: Path, report_date: str, data_dir: Path) -> list[str]:
    s102 = s1.indicators.get("S1-02", {}).get("value")
    s105 = s1.indicators.get("S1-05", {}).get("value")
    clinical = s2.items["S2-04"]
    leader = s2.items["S2-05"]
    previous_s1 = recent_s1[-2] if len(recent_s1) >= 2 else None
    previous_score = _previous_score_row(output_dir, report_date)
    previous_event_score = float(previous_score["s2_event_score"]) if previous_score and previous_score.get("s2_event_score") else None
    previous_conversion_score = float(previous_score["s2_conversion_score"]) if previous_score and previous_score.get("s2_conversion_score") else None
    previous_s204 = _previous_item_row(output_dir, report_date, "S2-04")
    previous_s205 = _previous_item_row(output_dir, report_date, "S2-05")
    s2_conversion = _s2_conversion_score(s2)
    current_excess = observation.get("excess_159567_vs_159557_5d")
    commercialization_state = _commercialization_report_state(data_dir)
    lines = [
        "### 基本面条件",
        f"- S1_total >= 0.60：{'满足' if s1.total_score >= 0.60 else '未满足'}，{_direction_cn(_condition_direction(s1.total_score, previous_s1.total_score if previous_s1 else None))}，当前{s1.total_score:.2f}。",
        f"- S1-02 份额变化 >= 0：{'满足' if s102 is not None and s102 >= 0 else '未满足'}，当前{_fmt(s102, True)}。",
        f"- S1-05 板块广度 >= 40%：{'满足' if s105 is not None and s105 >= 0.40 else '未满足'}，当前{_fmt(s105, True)}。",
        f"- S2_event_score >= 0.60：{'满足' if _s2_event_score(s2) >= 0.60 else '未满足'}，{_direction_cn(_condition_direction(_s2_event_score(s2), previous_event_score))}，当前{_s2_event_score(s2):.2f}。",
        "",
        "### 交易转化条件",
        f"- S2_conversion_score >= 0.60：{'满足' if s2_conversion >= 0.60 else '未满足'}，{_conversion_score_state(s2)}，当前{s2_conversion:.2f}。",
        f"- S2-04 去重正式样本 >= 3：{'满足' if clinical.deduped_trade_sample_count >= 3 else '未满足'}，当前{clinical.deduped_trade_sample_count}个；raw_mature_event_count={clinical.raw_mature_event_count}。",
        f"- S2-04 success_rate > 0：{'满足' if clinical.success_rate is not None and clinical.success_rate > 0 else '未满足'}，success_count={clinical.success_count}，success_rate={_fmt(clinical.success_rate, True)}。",
        f"- S2-05 龙头接力中位超额收益 >= 0：{'满足' if leader.value is not None and leader.value >= 0 else '未满足'}，{_direction_cn(_condition_direction(leader.value, float(previous_s205.get('value', 0)) if previous_s205 and previous_s205.get('value') else None))}，当前{_fmt(leader.value, True)}。",
        "",
        "### 持仓标的条件",
        f"- 159567 vs 159557 同步行情：{'满足' if observation.get('is_valid_for_judgement') else '未满足'}，HK_observation_status={observation.get('hk_observation_status') or observation.get('status')}。",
        f"- 159567 近5日强于159557：{'满足' if current_excess is not None and current_excess > 0 else '不可确认'}，最新判断超额={_fmt(current_excess, True)}；共同交易日历史超额={_fmt(observation.get('common_trade_excess_159567_vs_159557_5d'), True)}。",
        "",
        "### 数据质量条件",
        f"- HK日期同步：latest_date_159567={observation.get('latest_date_159567') or 'missing'}；latest_date_159557={observation.get('latest_date_159557') or 'missing'}；common_trade_date={observation.get('common_trade_date') or observation.get('observation_trade_date') or 'missing'}。",
        f"- S2-03b一致预期：{'missing' if s2.items['S2-03b'].rating == '数据缺失' else 'valid'}；{s2.items['S2-03b'].missing or s2.items['S2-03b'].basis}。",
        f"- S2-06商业化兑现质量：{commercialization_state['status']}；{commercialization_state['note'] if commercialization_state['status'] != 'scorable' else s2.explanation_items['S2-06'].basis}。",
        "",
        "### 不可判定",
        f"- 159567 是否右侧：{'无' if observation.get('is_valid_for_judgement') else '159567/159557同步行情未确认'}。",
        f"- 一致预期验证：{'无' if s2.items['S2-03b'].rating != '数据缺失' else 'S2-03b missing'}。",
        f"- 商业化兑现完整性：{'无' if commercialization_state['status'] == 'scorable' else 'S2-06 ' + str(commercialization_state['status'])}。",
    ]
    return lines


def render_report(
    s1: S1Record,
    recent_s1: list[S1Record],
    s2: S2Score,
    data_dir: Path,
    output_dir: Path,
    report_date: str,
    hk_observation: dict[str, object],
    hk_update_status: dict[str, object],
) -> str:
    _ensure_auxiliary_layers(data_dir)
    observation = _combination_observation(s1, s2)
    bd_events = load_events(data_dir / "bd_events.csv")
    clinical_events = load_events(data_dir / "clinical_events.csv")
    earnings_events = load_events(data_dir / "earnings_events.csv")
    earnings_consensus = load_events(data_dir / "earnings_consensus.csv")
    regulatory_events = load_events(data_dir / "regulatory_events.csv")
    policy_events = load_events(data_dir / "policy_risk_events.csv")
    today_new = [
        event for event in bd_events + clinical_events + earnings_events + regulatory_events
        if event.get("discovered_at", "").replace("-", "") == report_date.replace("-", "")
    ]
    historical_backfills = sum(not _within_days(event, report_date, days=3) for event in today_new)
    new_text = "今日无新增重大产业事件，产业事件分沿用当前观察窗口。" if not today_new else f"今日新增 {len(today_new)} 条事件，其中一次性历史回填 {historical_backfills} 条。"
    industry_status = _industry_event_status(s2, len(today_new))
    trading_status = _trading_conversion_status(s2)
    explanation_status = _explanation_status(s2)
    next_s204 = _next_s204_validation(s2, report_date)
    hk_relative_trend = _hk_relative_trend(output_dir, report_date, hk_observation)
    final_view = _final_view(s1, s2, hk_observation, policy_events, [], report_date)
    final_view_fields = _final_view_fields(s1, s2, hk_observation, recent_s1, next_s204["all_dates"], policy_events, [], report_date)
    daily_change_summary = _daily_change_summary(output_dir, report_date, s2)
    s1_trend = _s1_trend(recent_s1)
    s1_flags = _s1_structure_flags(s1)
    s1_contrib = _s1_score_contribution(s1)
    clinical = s2.items["S2-04"]
    policy_state = _policy_risk_state(policy_events)
    commercialization_state = _commercialization_report_state(data_dir)
    data_risk_factors = []
    if not hk_observation.get("is_valid_for_judgement"):
        data_risk_factors.append(f"HK_observation={hk_observation.get('hk_observation_status') or hk_observation.get('status')}")
    if s2.items["S2-03b"].rating == "数据缺失":
        data_risk_factors.append("S2-03b一致预期缺失")
    if commercialization_state["status"] != "insufficient_data" and s2.explanation_items["S2-06"].rating == "数据缺失":
        data_risk_factors.append("S2-06商业化兑现数据缺失")
    if commercialization_state["status"] == "insufficient_data":
        data_risk_factors.append("S2-06商业化兑现数据不足")
    elif commercialization_state["status"] == "scorable_low_confidence":
        data_risk_factors.append("S2-06商业化兑现低置信度")
    positive_factors = [item for item in _main_positive_factors(s2, hk_observation).split("；") if item]
    negative_factors = [item for item in _main_negative_factors(s1, s2, hk_observation).split("；") if item]
    s105 = s1.indicators.get("S1-05", {}).get("value")
    if s105 is not None:
        negative_factors.append(f"S1-05={_fmt(float(s105), True)}，{s1_flags['s1_breadth_state']}")
    negative_factors.append(f"S2-04 success_rate={_fmt(clinical.success_rate, True)}")
    negative_factors.append(f"S2_conversion_score={_s2_conversion_score(s2):.2f}，修复但未确认")
    if policy_state["state"] == "政策风险升高":
        negative_factors.append("Policy_Risk_Layer=risk_up")
    negative_factors = list(dict.fromkeys(negative_factors))
    data_risk_factors = list(dict.fromkeys(data_risk_factors))
    factor_rows = max(len(positive_factors), len(negative_factors), len(data_risk_factors), 1)

    lines = [
        "# 创新药 S2 产业验证日报",
        "",
        f"**报告日期**: {report_date}",
        f"**S1交易日**: {s1.trade_date}",
        "**输出范围**: 独立 S2 模块，不修改 S1 日报",
        "**版本状态**: 数据治理后试运行版，行情层已接入 audit，但部分解释标签仍在迭代校验。",
        "**港股观察标的**: 159567.SZ 港股创新药ETF",
        "**正式量化温度计**: 589720.SH 科创创新药ETF",
        "**港股对照标的**: 159557.SZ 港股医疗宽基参考",
        "",
        "589720.SH 用于观察 A 股创新药资金状态；159567.SZ 用于观察港股创新药实际交易方向；159557.SZ 用于判断港股创新药是否强于港股医疗宽基。",
        "",
        "**口径边界**: 589720.SH 弱，只表示 A 股科创创新药资金状态偏弱；159567.SZ 是否强，需要单独读取 HK_observation。",
        "**外部风格分析**: AI/科技成长风格观察请参见 `ai_style_daily_report.md`；不进入 S2 正式评分。",
        "",
        "## 一、今日结论",
        "",
        "- 港股观察标的：159567.SZ 港股创新药ETF。",
        f"- A股温度计状态：589720.SH S1={s1.total_score:.2f}，状态为{_s1_market_state(s1)}；{_s1_line(s1)}",
        f"- s1_structure_quality = {s1_flags['s1_structure_quality']}；s1_breadth_state = {s1_flags['s1_breadth_state']}。",
        f"- S1_score_contribution：flow_score_contribution={s1_contrib['flow_score_contribution']:.3f}；price_strength_contribution={s1_contrib['price_strength_contribution']:.3f}；volume_contribution={s1_contrib['volume_contribution']:.3f}；breadth_contribution={s1_contrib['breadth_contribution']:.3f}；leader_contribution={s1_contrib['leader_contribution']:.3f}。",
        f"- {_s1_contribution_sentence(s1)}",
        f"- S2正式量化等级：adjusted_score={s2.adjusted_score:.2f}，等级为{s2.level}。",
        f"- S2产业事件侧得分：S2_event_score={_s2_event_score(s2):.2f}，状态为{_event_score_state(_s2_event_score(s2))}。",
        f"- S2交易转化侧得分：S2_conversion_score={_s2_conversion_score(s2):.2f}，状态为{_conversion_score_state(s2)}。",
        f"- BD联动解释：{_bd_linkage_explanation(s2)}",
        f"- HK_observation ETF观察：{_hk_proxy_summary(hk_observation)}该观察不进入正式S2分。",
        f"- 下一批S2-04事件将在{next_s204['date'] or '暂无'}开始成熟，届时可开始观察临床事件5日交易转化。",
        f"- 日间变化说明：{daily_change_summary}",
        f"- S2解释性状态：{explanation_status}。",
        f"- 港股观察层：159567 数据状态为 {hk_observation.get('hk_observation_status') or hk_observation['status']}；{'可判断相对强弱' if hk_observation.get('is_valid_for_judgement') else '不判断 159567 强弱'}。",
        f"- 综合客观状态：{final_view}",
        "",
        f"- 产业事件状态：{industry_status}",
        f"- 交易转化成熟度：{trading_status}",
        f"- S1/S2组合观察：{observation}",
        f"- S2原始得分（raw_score）：{s2.raw_score:.2f}",
        f"- S2置信度调整后得分（adjusted_score）：{s2.adjusted_score:.2f}",
        f"- 正式口径可用权重：{s2.available_weight:.0%}；缺失指标：{s2.missing_indicator_count}；待验证指标：{s2.pending_indicator_count}；含观察口径指标：{s2.proxy_indicator_count}；过期沿用指标：{s2.stale_indicator_count}",
        f"- {_hk_observation_line(hk_observation, hk_update_status)}",
        f"- {_s1_update_line(output_dir)}",
        f"- {new_text}",
        "",
        "### 正负因素摘要",
        "",
        "| 正面确认 | 负面确认 | 数据风险/不可确认 |",
        "| --- | --- | --- |",
        *[
            f"| {_cell(positive_factors[i] if i < len(positive_factors) else '')} | {_cell(negative_factors[i] if i < len(negative_factors) else '')} | {_cell(data_risk_factors[i] if i < len(data_risk_factors) else '')} |"
            for i in range(factor_rows)
        ],
        "",
        *_today_delta_section(s1, recent_s1, s2, output_dir, report_date, hk_observation),
        "",
        *_data_quality_section(s1, s2, len(today_new), hk_observation, hk_update_status, bd_events + clinical_events + earnings_events + regulatory_events, data_dir),
        "",
        "## 四、第一层：S1_A股温度计",
        "",
        "589720.SH 用于判断 A 股科创创新药资金是否确认，不代表 159567.SZ 的实时交易强弱。",
        "",
        f"- A股创新药资金状态：{_s1_market_state(s1)}。",
        f"- S1趋势状态：s1_weak_streak_days={s1_trend['s1_weak_streak_days']}；s1_trend_state={s1_trend['s1_trend_state']}；s1_recent_direction={s1_trend['s1_recent_direction']}。",
        f"- s1_structure_quality = {s1_flags['s1_structure_quality']}；s1_breadth_state = {s1_flags['s1_breadth_state']}。",
        f"- S1_score_contribution：flow_score_contribution={s1_contrib['flow_score_contribution']:.3f}；price_strength_contribution={s1_contrib['price_strength_contribution']:.3f}；volume_contribution={s1_contrib['volume_contribution']:.3f}；breadth_contribution={s1_contrib['breadth_contribution']:.3f}；leader_contribution={s1_contrib['leader_contribution']:.3f}。",
        f"- {_s1_contribution_sentence(s1)}",
        f"- {_s1_line(s1)}",
        "",
        "### 最近 10 个交易日 S1",
        "",
        "| 日期 | S1综合得分 | S1等级 |",
        "| --- | ---: | --- |",
    ]
    for record in recent_s1:
        lines.append(f"| {record.trade_date} | {record.total_score:.2f} | {record.expectation_level} |")

    lines.extend([
        "",
        "## 五、第二层：S2_产业验证正式分",
        "",
        "S2_total 只基于事件库、本地行情、589720.SH 与 A 股龙头池。S2_total 是产业验证正式分，不等于 159567.SZ 的实时交易强弱。",
        "",
        "| 指标 | 名称 | 指标值 | 状态 | raw_score | adjusted_score | 置信度 | 正式样本 | pending样本 | 正式计分状态 | 观察层样本 | 缺失原因 | 依据 |",
        "| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- | --- |",
    ])
    for item in s2.items.values():
        percent = item.code in {"S2-02", "S2-03a", "S2-03b", "S2-04", "S2-05"}
        money = False
        value = "待验证" if item.value is None and item.rating == "待验证" else _fmt(item.value, percent, money)
        official_status = "中性占位" if item.rating in {"待验证", "数据缺失"} else "正式评分"
        observation_samples = item.proxy_sample_count + item.hk_pending_count
        basis = item.basis
        if item.code == "S2-05" and item.carried_forward_from and "当前S2-05为沿用观察" not in basis:
            basis = f"当前S2-05为沿用观察，不是今日新增验证；{basis}"
        lines.append(
            f"| {item.code} | {item.name} | {value} | {item.rating} | {item.raw_score:.2f} | {item.adjusted_score:.2f} | {item.confidence:.2f} | {item.sample_count} | {item.pending_count} | {official_status} | {observation_samples} | {item.missing or '-'} | {basis} |"
        )
    if s2.items["S2-05"].carried_forward_from:
        lines.append("")
        lines.append(f"- S2-05 当前为沿用观察，不是今日新增验证。最近有效观测日：{s2.items['S2-05'].carried_forward_from}；距今 {s2.items['S2-05'].stale_days} 个交易日；类型：{s2.items['S2-05'].carry_forward_type}。")

    lines.extend([
        "",
        "### 事件库状态",
        "",
        f"- BD事件库：{len(bd_events)} 条",
        f"- 临床事件库：{len(clinical_events)} 条",
        f"- 业绩事件库：{len(earnings_events)} 条",
        f"- 一致预期验证表：{len(earnings_consensus)} 条",
        f"- 审批事件库：{len(regulatory_events)} 条",
        f"- {new_text}",
        "",
        "### 今日新增事件明细",
        "",
    ])
    if today_new:
        for event in today_new:
            title = " / ".join(
                part for part in [
                    event.get("date"),
                    event.get("company"),
                    event.get("asset") or event.get("period") or event.get("approval_type"),
                ]
                if part
            )
            lines.append(f"- {title}: {event.get('note', '')} 来源: {event.get('source_url') or '来源缺失'}")
    else:
        lines.append("- 今日无新增重大产业事件，产业事件分沿用当前观察窗口。")

    lines.extend([
        "",
        "### 当前观察窗口内的重要事件",
        "",
    ])
    active_events = [
        event for event in bd_events + clinical_events + earnings_events + regulatory_events
        if event.get("status", "active") == "active" and _within_days(event, report_date)
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

    lines.extend(["", *_clinical_status_section(s2, hk_observation, output_dir)])
    lines.extend(["", *_earnings_observation_section(earnings_events, earnings_consensus)])
    lines.extend(["", *_commercialization_section(s2, data_dir)])
    lines.extend(["", *_hk_observation_section(hk_observation, output_dir, report_date)])
    lines.extend(["", *_policy_risk_section(policy_events)])
    lines.extend(["", "## 十、外部风格分析", "", "- 外部风格分析请参见 `ai_style_daily_report.md`；本S2报告仅保留产业验证口径。"])
    lines.extend(["", *_position_explanation_section(s1, s2, hk_observation, output_dir, report_date, policy_events)])
    lines.extend([
        "",
        "## 十二、第四层：final_view_客观状态汇总",
        "",
        f"- {final_view}",
        f"- final_view_code = {final_view_fields['final_view_code']}",
        f"- final_view_sub_code = {final_view_fields['final_view_sub_code'] or 'missing'}",
        "- final_view_code_dict：A = 产业强 + 交易强；B = 产业中性 + 交易改善；C = 产业强 + 交易弱；D = 产业弱 + 交易弱；E = 数据不足 / 待验证。",
        "- final_view_sub_code_dict：C1 = 产业强 + 交易弱但有修复；C2 = 产业强 + 交易弱且恶化；C3 = 产业强 + 总分改善但关键确认项失败。",
        f"- industry_event_state = {final_view_fields['industry_event_state']}",
        f"- conversion_state = {final_view_fields['conversion_state']}",
        f"- a_share_temperature_state = {final_view_fields['a_share_temperature_state']}",
        f"- hk_observation_state = {final_view_fields['hk_observation_state']}",
        f"- hk_relative_state = {final_view_fields['hk_relative_state']}",
        f"- policy_risk_state = {final_view_fields['policy_risk_state']}",
        f"- macro_risk_state = {final_view_fields['macro_risk_state']}",
        f"- main_positive_factors = {final_view_fields['main_positive_factors']}",
        f"- main_negative_factors = {final_view_fields['main_negative_factors']}",
        f"- next_validation_dates = {final_view_fields['next_validation_dates']}",
        "- final_view 只做客观状态汇总，不参与评分，不包含交易建议。",
        "- 本报告不输出买卖建议；159567是否右侧必须以159567 vs 159557同步行情为准。",
        "",
        "## 十三、数据缺失与待验证事项",
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
        "## 十四、缺口治理",
        "",
    ])
    lines.extend(f"- {action}" for action in _data_quality_actions(s2))
    lines.extend([
        "",
        "## 十五、客观观察条件",
        "",
    ])
    lines.extend(_observation_conditions(s1, recent_s1, s2, hk_observation, output_dir, report_date, data_dir))
    lines.extend([
        "",
        "## 十六、复核清单",
        "",
        "- S2分数来自本地事件库和行情计算，不靠临场主观重打分。",
        "- 新事件必须由智能体联网查证后写入事件库。",
        "- 缺失数据保留为“数据缺失”，不编造。",
        "- S2仅呈现客观产业验证结果，不输出仓位或交易建议。",
        "- 本报告不输出买卖建议；159567是否右侧必须以159567 vs 159557同步行情为准。",
    ])
    return "\n".join(lines) + "\n"


def _upsert_score(
    output_dir: Path,
    report_date: str,
    s1: S1Record,
    recent_s1: list[S1Record],
    s2: S2Score,
    observation: str,
    hk_observation: dict[str, object],
    policy_events: list[dict[str, str]] | None = None,
    macro_rows: list[dict[str, str]] | None = None,
) -> None:
    path = output_dir / "s2_scores.csv"
    fields = [
        "date", "s1_trade_date", "s1_total", "s2_raw_score", "s2_adjusted_score", "s2_total",
        "s2_industry", "s2_style", "s2_total_with_style", "style_level", "style_regime", "style_data_status",
        "s2_level", "combination_observation", "available_weight", "missing_indicator_count",
        "pending_indicator_count", "proxy_indicator_count", "stale_indicator_count", "missing_data",
        "s2_raw_total", "s2_adjusted_total", "formal_rating", "explanation_status",
        "official_usable_weight", "s2_event_score", "s2_event_state", "s2_event_rating",
        "s2_conversion_score", "s2_conversion_state", "s2_conversion_rating",
        "final_view", "final_view_code", "final_view_sub_code", "industry_event_state",
        "conversion_state", "a_share_temperature_state", "hk_observation_state",
        "hk_relative_state", "policy_risk_state", "macro_risk_state",
        "main_positive_factors", "main_negative_factors", "next_validation_dates",
        "hk_observation_available", "hk_observation_excess_159567_vs_159557", "hk_observation_relative_state",
        "next_s2_04_validation_date", "days_to_next_s2_04_validation", "pending_mature_event_count_next_date",
        "s1_structure_quality", "s1_breadth_state",
        "flow_score_contribution", "price_strength_contribution", "volume_contribution", "breadth_contribution", "leader_contribution",
    ]
    rows: list[dict[str, str]] = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            rows = [row for row in csv.DictReader(fh) if row.get("date") != report_date]
    next_s204 = _next_s204_validation(s2, report_date)
    final_view_fields = _final_view_fields(s1, s2, hk_observation, recent_s1, next_s204["all_dates"], policy_events, macro_rows, report_date)
    s1_flags = _s1_structure_flags(s1)
    s1_contrib = _s1_score_contribution(s1)
    rows.append({
        "date": report_date,
        "s1_trade_date": s1.trade_date,
        "s1_total": f"{s1.total_score:.4f}",
        "s2_raw_score": f"{s2.raw_score:.4f}",
        "s2_adjusted_score": f"{s2.adjusted_score:.4f}",
        "s2_total": f"{s2.adjusted_score:.4f}",
        "s2_industry": f"{s2.adjusted_score:.4f}",
        "s2_style": "",
        "s2_total_with_style": "",
        "style_level": "deprecated",
        "style_regime": "deprecated",
        "style_data_status": "deprecated",
        "s2_level": s2.level,
        "combination_observation": observation,
        "available_weight": f"{s2.available_weight:.4f}",
        "missing_indicator_count": str(s2.missing_indicator_count),
        "pending_indicator_count": str(s2.pending_indicator_count),
        "proxy_indicator_count": str(s2.proxy_indicator_count),
        "stale_indicator_count": str(s2.stale_indicator_count),
        "missing_data": s2.missing_data,
        "s2_raw_total": f"{s2.raw_score:.4f}",
        "s2_adjusted_total": f"{s2.adjusted_score:.4f}",
        "formal_rating": s2.level,
        "explanation_status": _explanation_status(s2),
        "official_usable_weight": f"{s2.available_weight:.4f}",
        "s2_event_score": f"{_s2_event_score(s2):.4f}",
        "s2_event_state": _event_score_state(_s2_event_score(s2)),
        "s2_event_rating": _event_score_state(_s2_event_score(s2)),
        "s2_conversion_score": f"{_s2_conversion_score(s2):.4f}",
        "s2_conversion_state": _conversion_score_state(s2),
        "s2_conversion_rating": _conversion_score_state(s2),
        "final_view": _final_view(s1, s2, hk_observation, policy_events, macro_rows, report_date),
        **final_view_fields,
        "hk_observation_available": str(bool(hk_observation.get("is_valid_for_judgement"))).lower(),
        "hk_observation_excess_159567_vs_159557": _csv_float(hk_observation.get("excess_159567_vs_159557_5d")),
        "hk_observation_relative_state": _hk_proxy_state(hk_observation),
        "next_s2_04_validation_date": next_s204["date"],
        "days_to_next_s2_04_validation": next_s204["days_to"],
        "pending_mature_event_count_next_date": next_s204["count"],
        "s1_structure_quality": s1_flags["s1_structure_quality"],
        "s1_breadth_state": s1_flags["s1_breadth_state"],
        "flow_score_contribution": f"{s1_contrib['flow_score_contribution']:.4f}",
        "price_strength_contribution": f"{s1_contrib['price_strength_contribution']:.4f}",
        "volume_contribution": f"{s1_contrib['volume_contribution']:.4f}",
        "breadth_contribution": f"{s1_contrib['breadth_contribution']:.4f}",
        "leader_contribution": f"{s1_contrib['leader_contribution']:.4f}",
    })
    output_dir.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in sorted(rows, key=lambda row: row["date"]))


def _upsert_item_scores(output_dir: Path, report_date: str, s1: S1Record, s2: S2Score, hk_observation: dict[str, object]) -> None:
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
        "baseline_bd_amount",
        "true_value",
        "proxy_value",
        "true_sample_count",
        "proxy_sample_count",
        "proxy_type",
        "leader_excess_median_5d",
        "leader_win_rate_5d",
        "leader_excess_median_10d",
        "leader_breadth_20d",
        "pending_count",
        "hk_pending_count",
        "price_missing_count",
        "raw_mature_event_count",
        "deduped_trade_sample_count",
        "success_count",
        "success_rate",
        "carried_forward_from",
        "stale_days",
        "is_stale",
        "carry_forward_type",
        "indicator_status",
        "official_sample_count",
        "pending_sample_count",
        "missing_reason",
        "explanation_status",
        "last_valid_observation_date",
        "days_since_last_valid_observation",
        "s2_04_official_status",
        "s2_04_official_sample_count",
        "s2_04_hk_event_pending_count",
        "hk_observation_status",
        "hk_observation_available",
        "hk_observation_return_159567",
        "hk_observation_return_159557",
        "hk_observation_excess_159567_vs_159557",
        "is_carry_forward",
    ]
    rows: list[dict[str, str]] = []
    if path.exists():
        with path.open(newline="", encoding="utf-8") as fh:
            rows = [row for row in csv.DictReader(fh) if row.get("date") != report_date]

    for item in [*s2.items.values(), *s2.explanation_items.values()]:
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
            "baseline_bd_amount": _csv_float(item.baseline_bd_amount),
            "true_value": _csv_float(item.true_value),
            "proxy_value": _csv_float(item.proxy_value),
            "true_sample_count": str(item.true_sample_count),
            "proxy_sample_count": str(item.proxy_sample_count),
            "proxy_type": item.proxy_type,
            "leader_excess_median_5d": _csv_float(item.leader_excess_median_5d),
            "leader_win_rate_5d": _csv_float(item.leader_win_rate_5d),
            "leader_excess_median_10d": _csv_float(item.leader_excess_median_10d),
            "leader_breadth_20d": _csv_float(item.leader_breadth_20d),
            "pending_count": str(item.pending_count),
            "hk_pending_count": str(item.hk_pending_count),
            "price_missing_count": str(item.price_missing_count),
            "raw_mature_event_count": str(item.raw_mature_event_count),
            "deduped_trade_sample_count": str(item.deduped_trade_sample_count),
            "success_count": str(item.success_count),
            "success_rate": _csv_float(item.success_rate),
            "carried_forward_from": item.carried_forward_from,
            "stale_days": str(item.stale_days),
            "is_stale": str(item.is_stale).lower(),
            "carry_forward_type": item.carry_forward_type,
            "indicator_status": item.rating,
            "official_sample_count": str(item.sample_count),
            "pending_sample_count": str(item.pending_count),
            "missing_reason": item.missing,
            "explanation_status": item.basis,
            "last_valid_observation_date": item.carried_forward_from,
            "days_since_last_valid_observation": str(item.stale_days),
            "s2_04_official_status": item.rating if item.code == "S2-04" else "",
            "s2_04_official_sample_count": str(item.sample_count) if item.code == "S2-04" else "",
            "s2_04_hk_event_pending_count": str(_hk_event_pending_count(s2)) if item.code == "S2-04" else "",
            "hk_observation_status": _hk_etf_proxy_status(hk_observation) if item.code == "S2-04" else "",
            "hk_observation_available": str(bool(hk_observation.get("is_valid_for_judgement"))).lower() if item.code == "S2-04" else "",
            "hk_observation_return_159567": _csv_float(hk_observation.get("return_159567_5d")) if item.code == "S2-04" else "",
            "hk_observation_return_159557": _csv_float(hk_observation.get("return_159557_5d")) if item.code == "S2-04" else "",
            "hk_observation_excess_159567_vs_159557": _csv_float(hk_observation.get("excess_159567_vs_159557_5d")) if item.code == "S2-04" else "",
            "is_carry_forward": str(bool(item.carried_forward_from)).lower(),
        })

    output_dir.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            {field: row.get(field, "") for field in fields}
            for row in sorted(rows, key=lambda row: (row["date"], row["code"]))
        )


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
        "| 日期 | 指标 | 指标值 | 原始得分 | 调整后得分 | 置信度 | 样本数 | 原始成熟事件 | 去重交易样本 | 成功样本 | 观察口径样本 | 待验证样本 | 港股观察样本 | 本地价格缺失 | 沿用日期 | 沿用交易日 | 沿用类型 | 评级 | 缺失说明 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- | --- | --- |",
    ]
    for row in sorted(rows, key=lambda item: (item["date"], item["code"]), reverse=True):
        value = row["value"] or ("待验证" if row["rating"] == "待验证" else "数据缺失")
        lines.append(
            f"| {row['date']} | {row['code']} {row['name']} | {value} | {float(row['raw_score']):.2f} | "
            f"{float(row['adjusted_score']):.2f} | {float(row['confidence']):.2f} | {row['sample_count']} | "
            f"{row.get('raw_mature_event_count', '0')} | {row.get('deduped_trade_sample_count', '0')} | {row.get('success_count', '0')} | "
            f"{row.get('proxy_sample_count', '0')} | {row.get('pending_count', '0')} | {row.get('hk_pending_count', '0')} | "
            f"{row.get('price_missing_count', '0')} | {row.get('carried_forward_from', '') or '-'} | {row.get('stale_days', '0')} | "
            f"{row.get('carry_forward_type', '') or '-'} | {row['rating']} | {row['missing'] or '-'} |"
        )
    return "\n".join(lines) + "\n"


def _render_daily_brief(
    s1: S1Record,
    s2: S2Score,
    output_dir: Path,
    report_date: str,
    hk_observation: dict[str, object],
    hk_update_status: dict[str, object],
) -> str:
    observation = _combination_observation(s1, s2)
    lines = [
        "# 创新药 S2 当日简报",
        "",
        f"**报告日期**: {report_date}",
        f"**S1交易日**: {s1.trade_date}",
        "**港股观察标的**: 159567.SZ 港股创新药ETF",
        "**正式量化温度计**: 589720.SH 科创创新药ETF",
        "**港股对照标的**: 159557.SZ 港股医疗宽基参考",
        "",
        f"- A股温度计状态：{_s1_market_state(s1)}。",
        f"- 正式量化等级：{s2.level}",
        "- 外部风格分析请参见 ai_style_daily_report.md；不进入S2正式评分。",
        f"- S2产业事件侧得分：S2_event_score={_s2_event_score(s2):.2f}，状态为{_event_score_state(_s2_event_score(s2))}。",
        f"- S2交易转化侧得分：S2_conversion_score={_s2_conversion_score(s2):.2f}，状态为{_conversion_score_state(s2)}。",
        f"- BD联动解释：{_bd_linkage_explanation(s2)}",
        f"- 日间变化说明：{_daily_change_summary(output_dir, report_date, s2)}",
        f"- S2解释性状态：{_explanation_status(s2)}。",
        f"- S2原始得分（raw_score）：{s2.raw_score:.2f}",
        f"- S2置信度调整后得分（adjusted_score）：{s2.adjusted_score:.2f}",
        f"- S1/S2组合观察：{observation}",
        f"- 正式口径可用权重：{s2.available_weight:.0%}",
        f"- 缺失指标：{s2.missing_indicator_count}；待验证指标：{s2.pending_indicator_count}",
        f"- 综合客观状态（final_view）：{_final_view(s1, s2, hk_observation)}",
        f"- {_hk_observation_line(hk_observation, hk_update_status)}",
        f"- {_s1_update_line(output_dir)}",
        f"- 数据缺失：{s2.missing_data or '无'}",
        "",
        "该简报仅陈述客观指标变化，不构成仓位或交易建议。",
    ]
    return "\n".join(lines) + "\n"


def generate_report(
    indicators_dir: Path = DEFAULT_INDICATORS_DIR,
    data_dir: Path = DEFAULT_DATA_DIR,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    market_data_dir: Path = DEFAULT_MARKET_DATA_DIR,
    excel_path: Path = DEFAULT_EXCEL_PATH,
    report_date: str | None = None,
) -> Path:
    ensure_event_store(data_dir)
    _ensure_auxiliary_layers(data_dir)
    latest_s1, recent_s1 = load_latest_s1(indicators_dir)
    if report_date is None:
        report_date = f"{latest_s1.trade_date[:4]}-{latest_s1.trade_date[4:6]}-{latest_s1.trade_date[6:]}"
    s2 = score_s2(
        trade_date=latest_s1.trade_date,
        data_dir=data_dir,
        output_dir=output_dir,
        market_data_dir=market_data_dir,
        excel_path=excel_path,
        s1_total=latest_s1.total_score,
        s1_share_change=latest_s1.indicators.get("S1-02", {}).get("value"),
        report_date=report_date,
    )
    hk_observation = read_hk_observation(
        output_dir / "hk_cache",
        today=datetime.strptime(report_date, "%Y-%m-%d"),
    )
    hk_update_status = read_hk_update_status(output_dir / "hk_cache")
    for key in [
        "primary_source",
        "primary_source_status",
        "primary_source_error",
        "fallback_source",
        "fallback_source_status",
        "fallback_source_error",
        "final_data_source",
    ]:
        if hk_update_status.get(key):
            hk_observation[key] = hk_update_status[key]
    _apply_hk_external_availability(data_dir, report_date, hk_observation)
    content = render_report(latest_s1, recent_s1, s2, data_dir, output_dir, report_date, hk_observation, hk_update_status)
    policy_events = load_events(data_dir / "policy_risk_events.csv")
    macro_rows = load_events(data_dir / "macro_market_snapshot.csv")
    reports_dir = output_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{report_date}.md"
    report_path.write_text(content, encoding="utf-8")
    (output_dir / "s2_daily_report.md").write_text(content, encoding="utf-8")
    brief = _render_daily_brief(latest_s1, s2, output_dir, report_date, hk_observation, hk_update_status)
    briefs_dir = output_dir / "briefs"
    briefs_dir.mkdir(parents=True, exist_ok=True)
    (briefs_dir / f"{report_date}.md").write_text(brief, encoding="utf-8")
    (output_dir / "s2_daily_brief.md").write_text(brief, encoding="utf-8")
    _upsert_score(output_dir, report_date, latest_s1, recent_s1, s2, _combination_observation(latest_s1, s2), hk_observation, policy_events, [])
    _upsert_item_scores(output_dir, report_date, latest_s1, s2, hk_observation)
    upsert_hk_observation_history(output_dir, report_date, hk_observation)
    (output_dir / "s2_indicator_history.md").write_text(_render_indicator_history(output_dir), encoding="utf-8")
    return report_path


def main() -> None:
    path = generate_report()
    print(f"S2日报已更新: {path}")


if __name__ == "__main__":
    main()
