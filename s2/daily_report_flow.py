"""Unified daily report flow for S1, S2, and AI style reports.

This entrypoint exists to prevent partial reruns from producing internally
inconsistent reports. In particular, S2's HK_observation layer reads
``s2/output/hk_cache`` and must be refreshed separately from
``data/processed/market_daily.csv``.
"""

from __future__ import annotations

import csv
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from s2.s1_reader import load_latest_s1


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDICATORS_DIR = PROJECT_ROOT / "data" / "indicators"
S2_OUTPUT_DIR = PROJECT_ROOT / "s2" / "output"


@dataclass(frozen=True)
class Step:
    module: str
    description: str


STEPS = [
    Step("wb.daily_flow", "更新S1数据、指标和S1日报"),
    Step("s2.update_market_data", "刷新HK_observation缓存和港股个股行情"),
    Step("s2.build_data_layer", "构建S2行情、宏观、audit和交易样本数据层"),
    Step("s2.generate_s2_report", "生成纯S2产业验证日报"),
    Step("s3.generate_report", "生成AI/科技成长风格日报"),
]


def _run_step(step: Step) -> None:
    print(f"\n{'=' * 60}")
    print(f"步骤: {step.description}")
    print(f"模块: {step.module}")
    print("=" * 60)
    result = subprocess.run([sys.executable, "-m", step.module], cwd=PROJECT_ROOT)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def _latest_cache_date(symbol: str) -> str:
    path = S2_OUTPUT_DIR / "hk_cache" / f"{symbol}.csv"
    if not path.exists():
        return ""
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    dates = [str(row.get("date") or row.get("trade_date") or "").strip() for row in rows]
    dates = [date for date in dates if date]
    return max(dates) if dates else ""


def _validate_outputs() -> None:
    latest_s1, _ = load_latest_s1(INDICATORS_DIR)
    report_date = f"{latest_s1.trade_date[:4]}-{latest_s1.trade_date[4:6]}-{latest_s1.trade_date[6:]}"
    s2_report = S2_OUTPUT_DIR / "reports" / f"{report_date}.md"
    ai_report = S2_OUTPUT_DIR / "ai_style_daily_report.md"
    if not s2_report.exists():
        raise SystemExit(f"S2报告缺失: {s2_report}")
    if not ai_report.exists():
        raise SystemExit(f"AI风格报告缺失: {ai_report}")

    s2_text = s2_report.read_text(encoding="utf-8")
    if f"**报告日期**: {report_date}" not in s2_text:
        raise SystemExit(f"S2报告日期未对齐最新S1日期: expected={report_date}")
    if f"S1指标已更新到 {latest_s1.trade_date}" not in s2_text:
        raise SystemExit(f"S2报告内S1状态未对齐: expected={latest_s1.trade_date}")

    print("\n数据链路复核:")
    print(f"- S1 trade_date: {latest_s1.trade_date}")
    print(f"- S2 report: {s2_report}")
    print(f"- HK cache 159567 latest: {_latest_cache_date('159567') or 'missing'}")
    print(f"- HK cache 159557 latest: {_latest_cache_date('159557') or 'missing'}")
    print(f"- AI style report: {ai_report}")


def main() -> None:
    for step in STEPS:
        _run_step(step)
    _validate_outputs()
    print("\n全部日报链路已完成。")


if __name__ == "__main__":
    main()
