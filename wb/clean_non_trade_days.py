"""清理非交易日的指标文件"""
import argparse
import pandas as pd
from pathlib import Path


def get_trade_dates() -> set:
    """从 fund_daily.csv 获取交易日"""
    fund_daily_path = Path(__file__).parent.parent / "data" / "raw" / "fund_daily.csv"
    if not fund_daily_path.exists():
        raise FileNotFoundError("fund_daily.csv 不存在")

    fund_daily = pd.read_csv(fund_daily_path)
    return set(
        fund_daily[fund_daily["ts_code"] == "589720.SH"]["trade_date"]
        .astype(str)
        .tolist()
    )


def clean_non_trade_days(dry_run: bool = True):
    """
    删除非交易日的指标文件

    Args:
        dry_run: True = 只打印不删除，False = 实际删除
    """
    try:
        trade_dates = get_trade_dates()
    except FileNotFoundError as e:
        print(f"错误: {e}")
        return

    indicators_dir = Path(__file__).parent.parent / "data" / "indicators"
    if not indicators_dir.exists():
        print("指标目录不存在")
        return

    to_delete = []

    for filepath in indicators_dir.glob("*.json"):
        date_str = filepath.stem
        if date_str not in trade_dates:
            to_delete.append(filepath)

    if not to_delete:
        print("✓ 没有非交易日指标文件")
        return

    print(f"发现 {len(to_delete)} 个非交易日指标文件:")
    for filepath in sorted(to_delete):
        print(f"  - {filepath.name}")

    if dry_run:
        print("\n[DRY RUN] 未删除文件")
        print("确认删除请运行: uv run python -m wb.clean_non_trade_days --apply")
    else:
        for filepath in to_delete:
            filepath.unlink()
        print(f"\n✓ 已删除 {len(to_delete)} 个文件")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="清理非交易日指标文件")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="实际删除文件（默认只打印不删除）",
    )
    args = parser.parse_args()

    clean_non_trade_days(dry_run=not args.apply)
