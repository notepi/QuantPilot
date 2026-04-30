"""
数据更新脚本

功能：
1. 检查数据完整性
2. 增量更新数据（只获取缺失的部分）
3. 自动补齐历史数据

使用方式：
    uv run python -m wb.update_data
"""
import os
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv

from wb.tushare_proxy import pro_api as citydata_pro_api

load_dotenv()

# 数据目录
DATA_DIR = Path(__file__).parent.parent / "data" / "raw"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# ETF配置
ETF_CODE = "589720.SH"
BENCHMARK_CODE = "159557.SZ"
ETF_START_DATE = "20250801"  # 589720 上市日期


# ==================== 数据状态检查 ====================

def get_local_dates(filename: str, ts_code: str = None) -> set:
    """
    获取本地文件中的日期列表

    Args:
        filename: 文件名
        ts_code: 筛选的代码（可选）

    Returns:
        日期集合（格式：YYYYMMDD）
    """
    filepath = DATA_DIR / filename
    if not filepath.exists():
        return set()

    df = pd.read_csv(filepath)
    if ts_code:
        df = df[df["ts_code"] == ts_code]

    if "trade_date" not in df.columns:
        return set()

    return set(df["trade_date"].astype(str).tolist())


def check_data_status():
    """
    检查数据状态

    返回各数据源的日期范围和统计信息
    """
    print("=" * 50)
    print("数据状态检查")
    print("=" * 50)

    status = {}

    # 1. fund_daily (589720)
    dates = get_local_dates("fund_daily.csv", ETF_CODE)
    if dates:
        sorted_dates = sorted(dates)
        status["fund_daily_etf"] = {
            "count": len(dates),
            "min": sorted_dates[0],
            "max": sorted_dates[-1],
            "dates": dates,
        }
        print(f"fund_daily ({ETF_CODE}): {sorted_dates[0]} ~ {sorted_dates[-1]} ({len(dates)} 条)")
    else:
        status["fund_daily_etf"] = {"count": 0, "dates": set()}
        print(f"fund_daily ({ETF_CODE}): 无数据")

    # 2. fund_daily (159557)
    dates = get_local_dates("fund_daily.csv", BENCHMARK_CODE)
    if dates:
        sorted_dates = sorted(dates)
        status["fund_daily_benchmark"] = {
            "count": len(dates),
            "min": sorted_dates[0],
            "max": sorted_dates[-1],
            "dates": dates,
        }
        print(f"fund_daily ({BENCHMARK_CODE}): {sorted_dates[0]} ~ {sorted_dates[-1]} ({len(dates)} 条)")
    else:
        status["fund_daily_benchmark"] = {"count": 0, "dates": set()}
        print(f"fund_daily ({BENCHMARK_CODE}): 无数据")

    # 3. fund_share
    dates = get_local_dates("fund_share.csv", ETF_CODE)
    if dates:
        sorted_dates = sorted(dates)
        status["fund_share"] = {
            "count": len(dates),
            "min": sorted_dates[0],
            "max": sorted_dates[-1],
            "dates": dates,
        }
        print(f"fund_share: {sorted_dates[0]} ~ {sorted_dates[-1]} ({len(dates)} 条)")
    else:
        status["fund_share"] = {"count": 0, "dates": set()}
        print("fund_share: 无数据")

    # 4. daily (成分股)
    dates = get_local_dates("daily.csv")
    if dates:
        sorted_dates = sorted(dates)
        status["daily"] = {
            "count": len(dates),
            "min": sorted_dates[0],
            "max": sorted_dates[-1],
            "dates": dates,
        }
        print(f"daily (成分股): {sorted_dates[0]} ~ {sorted_dates[-1]} ({len(dates)} 个交易日)")
    else:
        status["daily"] = {"count": 0, "dates": set()}
        print("daily (成分股): 无数据")

    return status


# ==================== 数据获取 ====================

def fetch_fund_daily(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    获取ETF日线数据

    注意：API 可能返回全部数据，需要在此过滤

    Args:
        ts_code: ETF代码
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)

    Returns:
        DataFrame (已过滤)
    """
    pro = citydata_pro_api()
    df = pro.fund_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
    if df is None or len(df) == 0:
        return pd.DataFrame()

    # 过滤日期范围
    df = df[(df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)]
    return df


def fetch_fund_share(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    获取ETF份额数据

    注意：API 可能返回全部数据，需要在此过滤

    Args:
        ts_code: ETF代码
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)

    Returns:
        DataFrame (已过滤)
    """
    pro = citydata_pro_api()
    df = pro.fund_share(ts_code=ts_code)
    if df is None or len(df) == 0:
        return pd.DataFrame()

    # 过滤日期范围
    df = df[(df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)]
    return df


def fetch_daily(ts_codes: list, start_date: str, end_date: str) -> pd.DataFrame:
    """
    获取A股日线数据

    注意：API 可能返回全部数据，需要在此过滤

    Args:
        ts_codes: 股票代码列表
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)

    Returns:
        DataFrame (已过滤)
    """
    pro = citydata_pro_api()
    codes_str = ",".join(ts_codes)
    df = pro.daily(ts_code=codes_str, start_date=start_date, end_date=end_date)
    if df is None or len(df) == 0:
        return pd.DataFrame()

    # 过滤日期范围
    df = df[(df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)]
    return df


# ==================== 数据合并 ====================

def append_to_file(new_df: pd.DataFrame, filename: str, key_cols: list = None):
    """
    追加数据到本地文件（去重）

    Args:
        new_df: 新数据
        filename: 文件名
        key_cols: 用于去重的键列（默认 ['ts_code', 'trade_date']）
    """
    if key_cols is None:
        key_cols = ["ts_code", "trade_date"]

    filepath = DATA_DIR / filename

    if filepath.exists():
        old_df = pd.read_csv(filepath)

        # 合并并去重
        combined = pd.concat([old_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=key_cols, keep="last")

        # 按日期排序
        combined = combined.sort_values(key_cols)

        combined.to_csv(filepath, index=False)
        print(f"  追加 {len(new_df)} 条，总计 {len(combined)} 条")
    else:
        new_df = new_df.sort_values(key_cols)
        new_df.to_csv(filepath, index=False)
        print(f"  新建 {len(new_df)} 条")


# ==================== 增量更新 ====================

def get_trading_dates_from_daily() -> set:
    """
    从 daily.csv 推断交易日历
    """
    return get_local_dates("daily.csv")


def update_fund_daily_incremental():
    """增量更新ETF日线数据"""
    print("\n更新 fund_daily...")

    today = datetime.now().strftime("%Y%m%d")

    for ts_code in [ETF_CODE, BENCHMARK_CODE]:
        local_dates = get_local_dates("fund_daily.csv", ts_code)

        # 确定起始日期
        if ts_code == ETF_CODE:
            start = ETF_START_DATE
        else:
            # 基准ETF更早，从2024年开始
            start = "20240101"

        if local_dates:
            # 从最新日期的下一天开始
            latest = max(local_dates)
            next_day = (datetime.strptime(latest, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")
            if next_day > today:
                print(f"  {ts_code}: 已是最新")
                continue
            fetch_start = next_day
        else:
            fetch_start = start

        print(f"  {ts_code}: 获取 {fetch_start} ~ {today}...")
        df = fetch_fund_daily(ts_code, fetch_start, today)

        if len(df) > 0:
            append_to_file(df, "fund_daily.csv")
        else:
            print(f"  {ts_code}: 无新数据")


def update_fund_share_incremental():
    """增量更新ETF份额数据"""
    print("\n更新 fund_share...")

    today = datetime.now().strftime("%Y%m%d")
    local_dates = get_local_dates("fund_share.csv", ETF_CODE)

    if local_dates:
        latest = max(local_dates)
        next_day = (datetime.strptime(latest, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")
        if next_day > today:
            print(f"  已是最新")
            return
        fetch_start = next_day
    else:
        fetch_start = ETF_START_DATE

    print(f"  获取 {fetch_start} ~ {today}...")
    df = fetch_fund_share(ETF_CODE, fetch_start, today)

    if len(df) > 0:
        append_to_file(df, "fund_share.csv")
    else:
        print("  无新数据")


def update_daily_incremental():
    """增量更新成分股日线数据"""
    print("\n更新 daily...")

    # 获取成分股列表
    portfolio_file = DATA_DIR / "fund_portfolio.csv"
    if not portfolio_file.exists():
        print("  请先更新 fund_portfolio")
        return

    df_portfolio = pd.read_csv(portfolio_file)
    latest_period = df_portfolio["end_date"].max()
    holdings = df_portfolio[df_portfolio["end_date"] == latest_period]
    ts_codes = holdings["symbol"].tolist()

    if not ts_codes:
        print("  无成分股数据")
        return

    today = datetime.now().strftime("%Y%m%d")
    local_dates = get_local_dates("daily.csv")

    if local_dates:
        latest = max(local_dates)
        next_day = (datetime.strptime(latest, "%Y%m%d") + timedelta(days=1)).strftime("%Y%m%d")
        if next_day > today:
            print(f"  已是最新 ({len(local_dates)} 个交易日)")
            return
        fetch_start = next_day
    else:
        fetch_start = ETF_START_DATE

    print(f"  获取 {len(ts_codes)} 只股票: {fetch_start} ~ {today}...")
    df = fetch_daily(ts_codes, fetch_start, today)

    if len(df) > 0:
        append_to_file(df, "daily.csv")
    else:
        print("  无新数据")


def update_fund_portfolio():
    """更新ETF持仓数据（覆盖式更新）"""
    print("\n更新 fund_portfolio...")

    pro = citydata_pro_api()
    df = pro.fund_portfolio(ts_code=ETF_CODE)

    if df is not None and len(df) > 0:
        filepath = DATA_DIR / "fund_portfolio.csv"
        df.to_csv(filepath, index=False)
        print(f"  保存 {len(df)} 条记录")
    else:
        print("  获取失败")


# ==================== 主流程 ====================

def update_all():
    """更新所有数据"""
    print("=" * 50)
    print("开始更新数据")
    print("=" * 50)

    # 1. 检查状态
    check_data_status()

    # 2. 增量更新
    update_fund_daily_incremental()
    update_fund_share_incremental()
    update_fund_portfolio()
    update_daily_incremental()

    # 3. 再次检查状态
    print("\n" + "=" * 50)
    print("更新后状态")
    print("=" * 50)
    check_data_status()

    print("\n" + "=" * 50)
    print("数据更新完成")
    print("=" * 50)


if __name__ == "__main__":
    update_all()