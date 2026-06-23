"""Independent AI/technology-growth style report (S3).

This entrypoint does not modify S1 or S2 scores. It reuses the existing style
rotation and strict AI/biotech validation modules, then writes a third report.

Migrated from s2/generate_ai_style_report.py as part of the S3 module split.
"""

from __future__ import annotations

import csv
from pathlib import Path

from s3.s1_reader import load_latest_s1
from s3.style_rotation import StyleAnalysis, calculate_style_analysis
from s3.validation import ValidationResult, run_ai_biotech_validation


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INDICATORS_DIR = PROJECT_ROOT / "data" / "indicators"
DEFAULT_MARKET_DAILY = PROJECT_ROOT / "data" / "processed" / "market_daily.csv"
DEFAULT_MACRO_MARKET_DAILY = PROJECT_ROOT / "data" / "processed" / "macro_market_daily.csv"
DEFAULT_S2_SCORES = PROJECT_ROOT / "s2" / "output" / "s2_scores.csv"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "s3" / "config.json"
DEFAULT_AI_CORE_VERSIONS = PROJECT_ROOT / "s3" / "versions.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "s3" / "output"


def generate_ai_style_report(
    market_daily_path: Path = DEFAULT_MARKET_DAILY,
    macro_market_daily_path: Path = DEFAULT_MACRO_MARKET_DAILY,
    indicators_dir: Path = DEFAULT_INDICATORS_DIR,
    s2_scores_path: Path = DEFAULT_S2_SCORES,
    config_path: Path = DEFAULT_CONFIG_PATH,
    ai_core_versions_path: Path = DEFAULT_AI_CORE_VERSIONS,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    report_date: str | None = None,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    if report_date is None:
        try:
            latest_s1, _ = load_latest_s1(indicators_dir)
            report_date = f"{latest_s1.trade_date[:4]}-{latest_s1.trade_date[4:6]}-{latest_s1.trade_date[6:]}"
        except Exception:  # noqa: BLE001 - missing S1 is reported, not backfilled
            report_date = None

    style = calculate_style_analysis(market_daily_path, config_path, output_dir, report_date)
    validation = run_ai_biotech_validation(
        market_daily_path=market_daily_path,
        indicators_dir=indicators_dir,
        s2_scores_path=s2_scores_path,
        config_path=config_path,
        ai_core_versions_path=ai_core_versions_path,
        output_dir=output_dir,
        report_date=report_date,
        macro_market_daily_path=macro_market_daily_path,
    )
    content = render_ai_style_report(style, validation, output_dir)
    report_path = output_dir / "ai_style_daily_report.md"
    report_path.write_text(content, encoding="utf-8")
    dated_dir = output_dir / "ai_style_reports"
    dated_dir.mkdir(parents=True, exist_ok=True)
    dated_path = dated_dir / f"{validation.report_date}.md"
    dated_path.write_text(content, encoding="utf-8")
    return report_path


def render_ai_style_report(style: StyleAnalysis, validation: ValidationResult, output_dir: Path) -> str:
    right_side = _latest_csv_row(output_dir / "ai_biotech_right_side_score.csv")
    windows = _window_rows(output_dir / "ai_biotech_window_stats.csv")
    lead = _best_lead_row(output_dir / "ai_biotech_a_lead_stats.csv")
    source_audit_path = _source_audit_path(output_dir)
    hint = _context_action_hint(validation, right_side)
    ai_env = _environment_from_relative(validation.strongest_opposition, "AI_CORE")
    tech_env = _environment_from_relative(validation.strongest_opposition, "TECH_GROWTH_CORE")

    lines = [
        "# AI与科技成长风格日报",
        "",
        "## 1. 数据状态",
        "",
        f"- 报告日期：{validation.report_date}",
        f"- 核心指数状态：{validation.core_index_status}",
        f"- A股/港股数据日期：{validation.a_share_date}",
        f"- 对应美股收盘日期：{validation.us_close_date}（跨市场时区，使用上一美股交易日数据）",
        f"- 数据源状态：详见 {source_audit_path}",
        f"- 特征覆盖率：{right_side.get('feature_coverage', validation.feature_coverage)}",
        f"- score_status：{right_side.get('score_status', validation.score_status)}",
        "",
        "## 2. 当前环境",
        "",
        f"- ai_environment: {ai_env}",
        f"- tech_growth_environment: {tech_env}",
        f"- 市场风险状态：{validation.market_state}",
        f"- biotech_vs_health: {_biotech_vs_health_text(validation)}",
        f"- biotech_vs_ai: {_extract_evidence_value(validation.strongest_opposition, 'AI_CORE上涨时159567跑输AI_CORE') or _extract_evidence_value(validation.strongest_support, 'AI_CORE上涨时159567跑赢AI_CORE') or '未确认'}",
        f"- biotech_vs_tech: {_extract_evidence_value(validation.strongest_opposition, '科技成长上涨时159567跑输TECH_GROWTH_CORE') or _extract_evidence_value(validation.strongest_support, '科技成长上涨时159567跑赢TECH_GROWTH_CORE') or '未确认'}",
        "",
        "## 3. 当前轮动判断",
        "",
        f"- AI是否降温：{'是' if 'DOWN' in validation.current_ai_state else '否'}",
        f"- 科技成长是否降温：{'是' if 'DOWN' in validation.current_tech_growth_state else '否'}",
        f"- 创新药是否绝对转强：{'是' if any('绝对上涨' in item for item in validation.strongest_support) else '否'}",
        f"- 创新药是否只是相对少跌：{'否' if any('绝对上涨' in item for item in validation.strongest_support) else '待验证'}",
        f"- rotation_status: {_rotation_status(validation)}",
        "",
        "## 4. A股与港股关系",
        "",
        f"- 589720同日相对强弱：{style.style_regime}",
        f"- 真正lead_signal：{lead.get('condition', 'missing')}",
        f"- 样本量：{lead.get('sample_count', '0')}",
        f"- 未来1/2/3/5日结果：{_lead_summary(output_dir / 'ai_biotech_a_lead_stats.csv', lead.get('condition', ''))}",
        "- 结论：589720及S1目前仅为情绪温度计，除非lead_signal满足样本量、样本外和多窗口稳定要求。",
        "",
        "## 5. 多窗口结果",
        "",
        "| 窗口 | 创新药相对AI | 创新药相对科技成长 | 创新药相对医疗 | 稳定性 |",
        "| --- | ---: | ---: | ---: | --- |",
        *windows,
        "",
        "## 6. 最强支持证据",
        "",
        *[f"- {item}" for item in validation.strongest_support[:3]],
        "",
        "## 7. 最强反对证据",
        "",
        *[f"- {item}" for item in validation.strongest_opposition[:3]],
        "",
        "## 8. 观察评分",
        "",
        f"- right_side_score：{right_side.get('right_side_score') or 'missing'}",
        f"- score_status：{right_side.get('score_status', validation.score_status)}",
        f"- context_action_hint：{hint}",
        "",
        "该评分只反映外部风格与交易状态，不代表上涨概率，不进入S1或S2正式评分，也不单独构成仓位决策。",
        "",
        "## 9. 当前结论",
        "",
        f"- AI是否仍占优：{'是' if ai_env == 'HEADWIND' else '未确认'}",
        f"- 科技成长是否仍占优：{'是' if tech_env == 'HEADWIND' else '未确认'}",
        f"- 创新药是否相对医疗改善：{'是' if any('跑赢159557' in item for item in validation.strongest_support) else '未确认'}",
        "- 创新药是否接棒AI：未确认。",
        f"- 当前是否具备加仓环境：{'否' if hint in {'DO_NOT_ADD', 'RISK_WARNING', 'INSUFFICIENT_DATA'} else '仅允许复核'}",
        "- 未满足条件：AI/科技成长相对超额、S2交易转化、lead_signal稳定性仍需继续验证。",
        "",
    ]
    return "\n".join(lines)


def _source_audit_path(output_dir: Path) -> Path:
    local_path = output_dir / "data_audit" / "core_market_source_audit.csv"
    if local_path.exists():
        return local_path
    return PROJECT_ROOT / "s2" / "output" / "data_audit" / "core_market_source_audit.csv"


def _latest_csv_row(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return rows[-1] if rows else {}


def _window_rows(path: Path) -> list[str]:
    if not path.exists():
        return ["| missing | missing | missing | missing | missing |"]
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    by_window: dict[str, dict[str, dict[str, str]]] = {}
    for row in rows:
        by_window.setdefault(row["window"], {})[row["metric"]] = row
    out = []
    for window in ["20", "60", "120", "250"]:
        metrics = by_window.get(window, {})
        ai = metrics.get("159567相对AI_CORE超额", {})
        tech = metrics.get("159567相对TECH_GROWTH_CORE超额", {})
        health = metrics.get("159567相对159557超额", {})
        stability = ai.get("trading_meaning") or tech.get("trading_meaning") or "missing"
        out.append(f"| {window}日 | {ai.get('mean', 'missing')} | {tech.get('mean', 'missing')} | {health.get('mean', 'missing')} | {stability} |")
    return out


def _best_lead_row(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as fh:
        rows = [row for row in csv.DictReader(fh) if row.get("condition_type") == "a_share_lead_signal" and row.get("horizon_days") in {"1", "2", "3", "5"}]
    if not rows:
        return {}
    return max(rows, key=lambda row: (int(row.get("sample_count") or 0), row.get("bio_vs_health_win_rate") or ""))


def _lead_summary(path: Path, condition: str) -> str:
    if not condition or not path.exists():
        return "missing"
    with path.open(newline="", encoding="utf-8") as fh:
        rows = [row for row in csv.DictReader(fh) if row.get("condition") == condition and row.get("horizon_days") in {"1", "2", "3", "5"}]
    return "；".join(f"{row['horizon_days']}日:样本{row.get('sample_count', '0')},胜率{row.get('bio_vs_health_win_rate', 'missing')}" for row in rows) or "missing"


def _context_action_hint(validation: ValidationResult, right_side: dict[str, str]) -> str:
    status = right_side.get("score_status") or validation.score_status
    score_text = right_side.get("right_side_score")
    try:
        score = float(score_text) if score_text else None
    except ValueError:
        score = None
    if validation.core_index_status == "DATA_ERROR" or status in {"DATA_ERROR", "insufficient_data", "insufficient_predictive_signal"}:
        return "INSUFFICIENT_DATA"
    if score is None:
        return "INSUFFICIENT_DATA"
    if score < 30:
        return "DO_NOT_ADD"
    if score < 50:
        return "RISK_WARNING"
    if score >= 70:
        return "ALLOW_ADD_REVIEW"
    return "HOLD_OBSERVE"


def _environment_from_relative(opposition: list[str], token: str) -> str:
    return "HEADWIND" if any(token in item for item in opposition) else "NEUTRAL"


def _rotation_status(validation: ValidationResult) -> str:
    if validation.core_index_status == "DATA_ERROR":
        return "INSUFFICIENT_DATA"
    if validation.thesis_state == "strengthened":
        return "ROTATION_POSSIBLE"
    if validation.thesis_state == "weakened":
        return "ROTATION_NOT_CONFIRMED"
    return "NEUTRAL"


def _extract_evidence_value(items: list[str], prefix: str) -> str:
    for item in items:
        if prefix in item:
            return item
    return ""


def _biotech_vs_health_text(validation: ValidationResult) -> str:
    """从支持和反对证据中提取 159567 vs 159557 关系，区分跑赢/跑输/未确认。"""
    support_hit = _extract_evidence_value(validation.strongest_support, '159567当日跑赢159557')
    if support_hit:
        return support_hit
    oppose_hit = _extract_evidence_value(validation.strongest_opposition, '159567跑输159557')
    if oppose_hit:
        return oppose_hit
    return "未确认"


def main() -> None:
    path = generate_ai_style_report()
    print(f"AI风格日报已更新: {path}")


if __name__ == "__main__":
    main()
