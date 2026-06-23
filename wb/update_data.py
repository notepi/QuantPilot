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
    if "trade_date" not in df.columns:
        print(f"  {ts_code}: fund_daily返回缺少trade_date，按无新数据处理；columns={list(df.columns)}")
        return pd.DataFrame()

    # 过滤日期范围
    df = df[(df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)]
    return df


def fetch_fund_share(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    获取ETF份额数据：citydata（历史）→ 东方财富（当天补充）→ 上交所（沪市备用）

    数据源优先级：
    1. citydata fund_share（历史数据完整）
    2. 东方财富 fund_etf_spot_em（当天数据补充）
    3. 上交所 fund_etf_scale_sse（沪市备用，当前有 akshare bug）

    注意：API 可能返回全部数据，需要在此过滤

    Args:
        ts_code: ETF代码
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)

    Returns:
        DataFrame (已过滤)
    """
    pro = citydata_pro_api()
    frames = []

    # 1. 主源：citydata（历史数据）
    df = pro.fund_share(ts_code=ts_code, start_date=start_date, end_date=end_date)
    if df is not None and len(df) > 0 and "trade_date" in df.columns:
        df = df[(df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)]
        frames.append(df)
    elif df is not None and len(df) > 0:
        print(f"  {ts_code}: fund_share返回缺少trade_date，尝试备用源；columns={list(df.columns)}")

    # 2. 检查是否需要补充当天数据（东方财富备用源）
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    latest = str(combined["trade_date"].max()) if not combined.empty and "trade_date" in combined.columns else ""

    if latest < end_date:
        try:
            em_df = fetch_fund_share_em(ts_code)
            if em_df is not None and len(em_df) > 0:
                # 校验：东方财富日期必须在 [start_date, end_date] 区间内，且大于 citydata 最新日期
                em_date = str(em_df["trade_date"].iloc[0]) if "trade_date" in em_df.columns else ""
                if em_date and em_date >= start_date and em_date <= end_date and em_date > latest:
                    frames.append(em_df)
                    print(f"  {ts_code}: 东方财富补充当天份额数据成功 (日期={em_date})")
                elif em_date and em_date == latest:
                    # 同日期，跳过不重复追加
                    print(f"  {ts_code}: 东方财富日期={em_date} 与 citydata 一致，跳过")
                elif em_date:
                    print(f"  {ts_code}: 东方财富日期={em_date} 不在补充范围 [{latest}, {end_date}]，跳过")
        except Exception as e:
            print(f"  {ts_code}: 东方财富份额获取失败: {e}")

    # 3. 上交所备用源（仅沪市 ETF）
    if ts_code.endswith(".SH"):
        combined2 = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        latest2 = str(combined2["trade_date"].max()) if not combined2.empty and "trade_date" in combined2.columns else ""
        if latest2 < end_date:
            fallback_start = max(start_date, latest2) if latest2 else start_date
            fallback = fetch_fund_share_sse(ts_code, fallback_start, end_date)
            if len(fallback) > 0:
                frames.append(fallback)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined["trade_date"] = combined["trade_date"].astype(str)
    combined = combined[(combined["trade_date"] >= start_date) & (combined["trade_date"] <= end_date)]
    # 去重：同 ts_code + trade_date 只保留最后一条（备用源覆盖主源）
    if "ts_code" in combined.columns and "trade_date" in combined.columns:
        combined = combined.drop_duplicates(subset=["ts_code", "trade_date"], keep="last")
    return combined


def fetch_fund_share_em(ts_code: str) -> pd.DataFrame:
    """从东方财富获取当天份额数据（fund_etf_spot_em）

    注意：该接口只返回最新一条数据，没有历史区间。

    Args:
        ts_code: ETF代码，如 "589720.SH"

    Returns:
        DataFrame 包含 ts_code, trade_date, fd_share, source 字段
    """
    try:
        import akshare as ak
    except ImportError:
        print(f"  {ts_code}: akshare不可用，跳过东方财富份额获取")
        return pd.DataFrame()

    code = ts_code.split(".")[0]
    try:
        df = ak.fund_etf_spot_em()
    except Exception as e:
        print(f"  {ts_code}: 东方财富 fund_etf_spot_em 调用失败: {e}")
        return pd.DataFrame()

    if df is None or len(df) == 0:
        return pd.DataFrame()

    df["代码"] = df["代码"].astype(str)
    hit = df[df["代码"] == code]

    if len(hit) == 0:
        return pd.DataFrame()

    row = hit.iloc[0]
    # 数据日期格式可能是 "20260622" 或 "2026-06-22"
    raw_date = str(row.get("数据日期", ""))
    trade_date = raw_date[:10].replace("-", "")

    share_raw = row.get("最新份额")
    if share_raw is None or share_raw == "" or share_raw == "-":
        return pd.DataFrame()

    try:
        fd_share = float(share_raw) / 10000  # 转为万份
    except (ValueError, TypeError):
        return pd.DataFrame()

    return pd.DataFrame([{
        "ts_code": ts_code,
        "trade_date": trade_date,
        "fd_share": fd_share,
        "source": "eastmoney_fund_etf_spot_em",
    }])


def fetch_fund_share_sse(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """从上交所 ETF 规模接口补充沪市 ETF 份额，fd_share 统一为万份。"""
    try:
        import akshare as ak
    except Exception as e:
        print(f"  {ts_code}: akshare不可用，跳过SSE fund_share fallback: {e}")
        return pd.DataFrame()

    code = ts_code.split(".")[0]
    rows = []
    for date in pd.date_range(start=start_date, end=end_date, freq="D"):
        date_str = date.strftime("%Y%m%d")
        try:
            scale = ak.fund_etf_scale_sse(date=date_str)
        except Exception:
            continue
        required = {"基金代码", "统计日期", "基金份额"}
        if scale is None or len(scale) == 0 or not required.issubset(scale.columns):
            continue
        scale["基金代码"] = scale["基金代码"].astype(str).str.zfill(6)
        hit = scale[scale["基金代码"] == code]
        if hit.empty:
            continue
        share = pd.to_numeric(hit.iloc[0]["基金份额"], errors="coerce")
        if pd.isna(share):
            continue
        rows.append(
            {
                "ts_code": ts_code,
                "trade_date": str(hit.iloc[0]["统计日期"]).replace("-", ""),
                "fd_share": float(share) / 10000.0,
                "fund_type": "ETF",
                "market": "SH",
            }
        )

    if rows:
        print(f"  {ts_code}: SSE fallback补充 {len(rows)} 条fund_share")
    return pd.DataFrame(rows)


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
    if "trade_date" not in df.columns:
        print(f"  daily返回缺少trade_date，按无新数据处理；columns={list(df.columns)}")
        return pd.DataFrame()

    # 过滤日期范围
    df = df[(df["trade_date"] >= start_date) & (df["trade_date"] <= end_date)]
    return df


# ==================== 数据合并 ====================

def append_to_file(new_df: pd.DataFrame, filename: str, key_cols: list = None):
    """
    追加数据到本地文件（去重）

    兼容策略：
    - 新数据可能包含旧数据没有的列（如 source），合并时自动补 NaN
    - 旧数据没有 source 字段时默认视为 citydata_fund_share
    - 去重时 keep="last"，新数据覆盖旧数据

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

        # 旧记录补 source 默认值（仅 fund_share.csv）
        if filename == "fund_share.csv" and "source" not in old_df.columns:
            old_df["source"] = "citydata_fund_share"

        # 合并并去重
        combined = pd.concat([old_df, new_df], ignore_index=True)
        for col in key_cols:
            if col in combined.columns:
                combined[col] = combined[col].astype(str)
        combined = combined.drop_duplicates(subset=key_cols, keep="last")

        # 按日期排序
        combined = combined.sort_values(key_cols)

        combined.to_csv(filepath, index=False)
        print(f"  追加 {len(new_df)} 条，总计 {len(combined)} 条")
    else:
        # 新文件也补 source 默认值
        if filename == "fund_share.csv" and "source" not in new_df.columns:
            new_df["source"] = "citydata_fund_share"
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

    for ts_code in [ETF_CODE, BENCHMARK_CODE, "159567.SZ"]:
        local_dates = get_local_dates("fund_daily.csv", ts_code)

        # 确定起始日期
        if ts_code == ETF_CODE:
            start = ETF_START_DATE
        elif ts_code == "159567.SZ":
            # 港股创新药ETF
            start = "20240101"
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
        # fund_share 在 citydata 上窄窗口查询可能漏返回最新份额，
        # 用重叠回看窗口抓取，再按 ts_code/trade_date 去重覆盖。
        fetch_start = (datetime.strptime(latest, "%Y%m%d") - timedelta(days=30)).strftime("%Y%m%d")
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

    required_cols = {"ts_code", "ann_date", "end_date", "symbol"}
    if df is not None and len(df) > 0 and required_cols.issubset(df.columns):
        filepath = DATA_DIR / "fund_portfolio.csv"
        df.to_csv(filepath, index=False)
        print(f"  保存 {len(df)} 条记录")
    else:
        columns = list(df.columns) if df is not None else []
        print(f"  获取失败或返回结构异常，保留本地既有持仓；columns={columns}")


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
