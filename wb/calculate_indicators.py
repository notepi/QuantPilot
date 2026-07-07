"""
指标计算脚本

从本地CSV读取数据，计算指标并保存到JSON文件
"""
import json
from pathlib import Path
from datetime import datetime

from wb.data_fetcher import DataFetcher
from wb.score_engine import ScoreEngine


# 数据目录
DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
INDICATORS_DIR = DATA_DIR / "indicators"
INDICATORS_DIR.mkdir(parents=True, exist_ok=True)


def calculate_and_save(trade_date: str = None):
    """
    计算指标并保存到本地JSON

    Args:
        trade_date: 交易日期，格式 YYYYMMDD，默认最新
    """
    # 初始化（使用本地数据）
    fetcher = DataFetcher(use_local=True)
    engine = ScoreEngine(data_fetcher=fetcher)

    # 计算
    result = engine.calculate_all(trade_date=trade_date)

    if result is None:
        print("计算失败")
        return None

    # 保存到JSON
    date_str = result.trade_date
    filepath = INDICATORS_DIR / f"{date_str}.json"

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

    print(f"指标结果已保存到 {filepath}")
    print(f"综合得分: {result.total_score:.2f}")
    print(f"预期等级: {result.expectation_level}")

    return result


def calculate_history(days: int = 30):
    """
    计算历史指标（只在真实交易日上）

    Args:
        days: 回溯天数
    """
    import pandas as pd

    # 从 fund_daily.csv 获取 589720.SH 的交易日
    fund_daily_path = RAW_DIR / "fund_daily.csv"
    if not fund_daily_path.exists():
        print("错误: fund_daily.csv 不存在")
        return

    fund_daily = pd.read_csv(fund_daily_path)

    trade_dates = (
        fund_daily[fund_daily["ts_code"] == "589720.SH"]["trade_date"]
        .astype(str)
        .sort_values()
        .tail(days)
    )

    count = 0
    for date_str in trade_dates:
        result = calculate_and_save(trade_date=date_str)
        if result:
            count += 1

    print(f"共计算 {count} 天的指标")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "history":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            calculate_history(days=days)
        else:
            # 指定日期
            calculate_and_save(trade_date=sys.argv[1])
    else:
        # 计算最新
        calculate_and_save()