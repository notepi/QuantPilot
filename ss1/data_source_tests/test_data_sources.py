"""
SS1 原始数据源验证脚本

测试 159567.SZ 及其固定持仓池在多种原始外部数据源中的可用性。
"""

import sys
from pathlib import Path
from datetime import datetime
import pandas as pd

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 固定配置
TARGET_ETF = "159567.SZ"
BENCHMARK_ETF = "159557.SZ"
TOP10_HOLDINGS = [
    ("09926.HK", "康方生物", 11.86),
    ("01801.HK", "信达生物", 9.81),
    ("01093.HK", "石药集团", 9.40),
    ("06160.HK", "百济神州", 9.06),
    ("01177.HK", "中国生物制药", 9.02),
    ("03692.HK", "翰森制药", 6.93),
    ("01530.HK", "三生制药", 6.62),
    ("06990.HK", "科伦博泰", 4.15),
    ("09995.HK", "荣昌生物", 2.78),
    ("00867.HK", "康哲药业", 2.69),
]

test_results = []


def record_test(
    source_name: str,
    source_api_or_url: str,
    data_category: str,
    target_symbol: str,
    available: bool,
    fields_present: list,
    field_mapping: dict,
    latest_trade_date: str,
    history_depth: int,
    adjusted_type: str,
    failure_reason: str,
    sample_rows: int,
    can_feed_s1: bool,
):
    """记录测试结果"""
    test_results.append({
        "source_name": source_name,
        "source_api_or_url": source_api_or_url,
        "data_category": data_category,
        "target_symbol": target_symbol,
        "available": "yes" if available else "no",
        "fields_present": ",".join(fields_present) if fields_present else "",
        "field_mapping_to_S1": str(field_mapping) if field_mapping else "",
        "latest_trade_date": latest_trade_date,
        "history_depth": history_depth,
        "adjusted_type": adjusted_type,
        "failure_reason": failure_reason,
        "sample_rows": sample_rows,
        "can_feed_S1_original_formula": "yes" if can_feed_s1 else "no",
    })


def test_tencent_etf_daily(symbol: str):
    """测试腾讯 ETF 日线"""
    print(f"\n[测试] 腾讯 ETF 日线: {symbol}")
    try:
        from s2.update_market_data import _fetch_tencent_etf_daily

        df = _fetch_tencent_etf_daily(symbol.split(".")[0])
        if df.empty:
            record_test(
                source_name="腾讯 ETF K线",
                source_api_or_url="web.ifzq.gtimg.cn/appstock/app/fqkline/get",
                data_category="ETF日线",
                target_symbol=symbol,
                available=False,
                fields_present=[],
                field_mapping={},
                latest_trade_date="",
                history_depth=0,
                adjusted_type="qfq",
                failure_reason="返回空数据",
                sample_rows=0,
                can_feed_s1=False,
            )
            return

        latest = df["date"].max() if "date" in df.columns else ""
        depth = len(df)

        # 映射到 S1 字段
        field_mapping = {
            "date": "trade_date",
            "open": "open",
            "close": "close",
            "high": "high",
            "low": "low",
            "volume": "volume",
        }

        record_test(
            source_name="腾讯 ETF K线",
            source_api_or_url="web.ifzq.gtimg.cn/appstock/app/fqkline/get",
            data_category="ETF日线",
            target_symbol=symbol,
            available=True,
            fields_present=list(df.columns),
            field_mapping=field_mapping,
            latest_trade_date=latest,
            history_depth=depth,
            adjusted_type="qfq",
            failure_reason="",
            sample_rows=depth,
            can_feed_s1=True,
        )
        print(f"  ✓ 成功: latest={latest}, rows={depth}")
    except Exception as e:
        record_test(
            source_name="腾讯 ETF K线",
            source_api_or_url="web.ifzq.gtimg.cn/appstock/app/fqkline/get",
            data_category="ETF日线",
            target_symbol=symbol,
            available=False,
            fields_present=[],
            field_mapping={},
            latest_trade_date="",
            history_depth=0,
            adjusted_type="qfq",
            failure_reason=str(e),
            sample_rows=0,
            can_feed_s1=False,
        )
        print(f"  ✗ 失败: {e}")


def test_citydata_fund_daily(symbol: str):
    """测试 citydata fund_daily"""
    print(f"\n[测试] citydata fund_daily: {symbol}")
    try:
        from s2.update_market_data import _fetch_citydata_fund_daily

        df = _fetch_citydata_fund_daily(symbol)
        if df.empty:
            record_test(
                source_name="citydata fund_daily",
                source_api_or_url="citydata.pro/fund_daily",
                data_category="ETF日线",
                target_symbol=symbol,
                available=False,
                fields_present=[],
                field_mapping={},
                latest_trade_date="",
                history_depth=0,
                adjusted_type="none",
                failure_reason="返回空数据",
                sample_rows=0,
                can_feed_s1=False,
            )
            return

        latest = df["trade_date"].max() if "trade_date" in df.columns else ""
        depth = len(df)

        field_mapping = {
            "trade_date": "trade_date",
            "open": "open",
            "close": "close",
            "high": "high",
            "low": "low",
            "vol": "volume",
            "amount": "amount",
        }

        record_test(
            source_name="citydata fund_daily",
            source_api_or_url="citydata.pro/fund_daily",
            data_category="ETF日线",
            target_symbol=symbol,
            available=True,
            fields_present=list(df.columns),
            field_mapping=field_mapping,
            latest_trade_date=latest,
            history_depth=depth,
            adjusted_type="none",
            failure_reason="",
            sample_rows=depth,
            can_feed_s1=True,
        )
        print(f"  ✓ 成功: latest={latest}, rows={depth}")
    except Exception as e:
        record_test(
            source_name="citydata fund_daily",
            source_api_or_url="citydata.pro/fund_daily",
            data_category="ETF日线",
            target_symbol=symbol,
            available=False,
            fields_present=[],
            field_mapping={},
            latest_trade_date="",
            history_depth=0,
            adjusted_type="none",
            failure_reason=str(e),
            sample_rows=0,
            can_feed_s1=False,
        )
        print(f"  ✗ 失败: {e}")


def test_eastmoney_etf_daily(symbol: str):
    """测试东方财富 ETF 日线"""
    print(f"\n[测试] 东方财富 ETF 日线: {symbol}")
    try:
        from s2.hk_observation import _fetch_eastmoney, EASTMONEY_SECIDS

        if symbol not in EASTMONEY_SECIDS:
            print(f"  ⊘ 跳过: {symbol} 不在 EASTMONEY_SECIDS 配置中")
            return

        df = _fetch_eastmoney(symbol)
        if df.empty:
            record_test(
                source_name="东方财富 ETF K线",
                source_api_or_url="push2his.eastmoney.com/api/qt/stock/kline/get",
                data_category="ETF日线",
                target_symbol=symbol,
                available=False,
                fields_present=[],
                field_mapping={},
                latest_trade_date="",
                history_depth=0,
                adjusted_type="none",
                failure_reason="返回空数据",
                sample_rows=0,
                can_feed_s1=False,
            )
            return

        latest = df["date"].max() if "date" in df.columns else ""
        depth = len(df)

        field_mapping = {
            "date": "trade_date",
            "open": "open",
            "close": "close",
            "high": "high",
            "low": "low",
            "volume": "volume",
        }

        record_test(
            source_name="东方财富 ETF K线",
            source_api_or_url="push2his.eastmoney.com/api/qt/stock/kline/get",
            data_category="ETF日线",
            target_symbol=symbol,
            available=True,
            fields_present=list(df.columns),
            field_mapping=field_mapping,
            latest_trade_date=latest,
            history_depth=depth,
            adjusted_type="none",
            failure_reason="",
            sample_rows=depth,
            can_feed_s1=True,
        )
        print(f"  ✓ 成功: latest={latest}, rows={depth}")
    except Exception as e:
        record_test(
            source_name="东方财富 ETF K线",
            source_api_or_url="push2his.eastmoney.com/api/qt/stock/kline/get",
            data_category="ETF日线",
            target_symbol=symbol,
            available=False,
            fields_present=[],
            field_mapping={},
            latest_trade_date="",
            history_depth=0,
            adjusted_type="none",
            failure_reason=str(e),
            sample_rows=0,
            can_feed_s1=False,
        )
        print(f"  ✗ 失败: {e}")


def test_akshare_etf_daily(symbol: str):
    """测试 akshare ETF 日线"""
    print(f"\n[测试] akshare ETF 日线: {symbol}")
    try:
        import akshare as ak

        code = symbol.split(".")[0]
        df = ak.fund_etf_hist_em(symbol=code, period="daily", adjust="")

        if df is None or df.empty:
            record_test(
                source_name="akshare fund_etf_hist_em",
                source_api_or_url="ak.fund_etf_hist_em",
                data_category="ETF日线",
                target_symbol=symbol,
                available=False,
                fields_present=[],
                field_mapping={},
                latest_trade_date="",
                history_depth=0,
                adjusted_type="none",
                failure_reason="返回空数据",
                sample_rows=0,
                can_feed_s1=False,
            )
            return

        latest = df["日期"].max() if "日期" in df.columns else ""
        depth = len(df)

        field_mapping = {
            "日期": "trade_date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount",
        }

        record_test(
            source_name="akshare fund_etf_hist_em",
            source_api_or_url="ak.fund_etf_hist_em",
            data_category="ETF日线",
            target_symbol=symbol,
            available=True,
            fields_present=list(df.columns),
            field_mapping=field_mapping,
            latest_trade_date=str(latest),
            history_depth=depth,
            adjusted_type="none",
            failure_reason="",
            sample_rows=depth,
            can_feed_s1=True,
        )
        print(f"  ✓ 成功: latest={latest}, rows={depth}")
    except Exception as e:
        record_test(
            source_name="akshare fund_etf_hist_em",
            source_api_or_url="ak.fund_etf_hist_em",
            data_category="ETF日线",
            target_symbol=symbol,
            available=False,
            fields_present=[],
            field_mapping={},
            latest_trade_date="",
            history_depth=0,
            adjusted_type="none",
            failure_reason=str(e),
            sample_rows=0,
            can_feed_s1=False,
        )
        print(f"  ✗ 失败: {e}")


def test_citydata_fund_share(ts_code: str):
    """测试 citydata fund_share"""
    print(f"\n[测试] citydata fund_share: {ts_code}")
    try:
        from wb.update_data import fetch_fund_share
        from datetime import datetime

        end_date = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - pd.Timedelta(days=30)).strftime("%Y%m%d")

        df = fetch_fund_share(ts_code, start_date, end_date)

        if df is None or df.empty:
            record_test(
                source_name="citydata fund_share",
                source_api_or_url="citydata.pro/fund_share",
                data_category="ETF份额",
                target_symbol=ts_code,
                available=False,
                fields_present=[],
                field_mapping={},
                latest_trade_date="",
                history_depth=0,
                adjusted_type="n/a",
                failure_reason="返回空数据",
                sample_rows=0,
                can_feed_s1=False,
            )
            return

        latest = df["trade_date"].max() if "trade_date" in df.columns else ""
        depth = len(df)

        field_mapping = {
            "trade_date": "trade_date",
            "fd_share": "share",
        }

        record_test(
            source_name="citydata fund_share",
            source_api_or_url="citydata.pro/fund_share",
            data_category="ETF份额",
            target_symbol=ts_code,
            available=True,
            fields_present=list(df.columns),
            field_mapping=field_mapping,
            latest_trade_date=str(latest),
            history_depth=depth,
            adjusted_type="n/a",
            failure_reason="",
            sample_rows=depth,
            can_feed_s1=True,
        )
        print(f"  ✓ 成功: latest={latest}, rows={depth}")
    except Exception as e:
        record_test(
            source_name="citydata fund_share",
            source_api_or_url="citydata.pro/fund_share",
            data_category="ETF份额",
            target_symbol=ts_code,
            available=False,
            fields_present=[],
            field_mapping={},
            latest_trade_date="",
            history_depth=0,
            adjusted_type="n/a",
            failure_reason=str(e),
            sample_rows=0,
            can_feed_s1=False,
        )
        print(f"  ✗ 失败: {e}")


def test_eastmoney_fund_share_em(ts_code: str):
    """测试东方财富 fund_etf_spot_em"""
    print(f"\n[测试] 东方财富 fund_etf_spot_em: {ts_code}")
    try:
        from wb.update_data import fetch_fund_share_em

        df = fetch_fund_share_em(ts_code)

        if df is None or df.empty:
            record_test(
                source_name="东方财富 fund_etf_spot_em",
                source_api_or_url="ak.fund_etf_spot_em",
                data_category="ETF份额",
                target_symbol=ts_code,
                available=False,
                fields_present=[],
                field_mapping={},
                latest_trade_date="",
                history_depth=0,
                adjusted_type="n/a",
                failure_reason="返回空数据或代码不存在",
                sample_rows=0,
                can_feed_s1=False,
            )
            return

        latest = df["trade_date"].iloc[0] if "trade_date" in df.columns else ""
        depth = len(df)

        field_mapping = {
            "trade_date": "trade_date",
            "fd_share": "share",
        }

        record_test(
            source_name="东方财富 fund_etf_spot_em",
            source_api_or_url="ak.fund_etf_spot_em",
            data_category="ETF份额",
            target_symbol=ts_code,
            available=True,
            fields_present=list(df.columns),
            field_mapping=field_mapping,
            latest_trade_date=str(latest),
            history_depth=depth,
            adjusted_type="n/a",
            failure_reason="",
            sample_rows=depth,
            can_feed_s1=True,
        )
        print(f"  ✓ 成功: latest={latest}, rows={depth}")
    except Exception as e:
        record_test(
            source_name="东方财富 fund_etf_spot_em",
            source_api_or_url="ak.fund_etf_spot_em",
            data_category="ETF份额",
            target_symbol=ts_code,
            available=False,
            fields_present=[],
            field_mapping={},
            latest_trade_date="",
            history_depth=0,
            adjusted_type="n/a",
            failure_reason=str(e),
            sample_rows=0,
            can_feed_s1=False,
        )
        print(f"  ✗ 失败: {e}")


def test_tencent_hk_stock(ticker: str):
    """测试腾讯港股日线"""
    print(f"\n[测试] 腾讯港股日线: {ticker}")
    try:
        from s2.update_market_data import _fetch_tencent_hk_stock

        df = _fetch_tencent_hk_stock(ticker)

        if df.empty:
            record_test(
                source_name="腾讯港股K线",
                source_api_or_url="web.ifzq.gtimg.cn/appstock/app/hkfqkline/get",
                data_category="持仓股票日线",
                target_symbol=ticker,
                available=False,
                fields_present=[],
                field_mapping={},
                latest_trade_date="",
                history_depth=0,
                adjusted_type="qfq",
                failure_reason="返回空数据",
                sample_rows=0,
                can_feed_s1=False,
            )
            return

        latest = df["trade_date"].max() if "trade_date" in df.columns else ""
        depth = len(df)

        field_mapping = {
            "trade_date": "trade_date",
            "open": "open",
            "close": "close",
            "high": "high",
            "low": "low",
            "vol": "volume",
            "amount": "amount",
        }

        record_test(
            source_name="腾讯港股K线",
            source_api_or_url="web.ifzq.gtimg.cn/appstock/app/hkfqkline/get",
            data_category="持仓股票日线",
            target_symbol=ticker,
            available=True,
            fields_present=list(df.columns),
            field_mapping=field_mapping,
            latest_trade_date=latest,
            history_depth=depth,
            adjusted_type="qfq",
            failure_reason="",
            sample_rows=depth,
            can_feed_s1=True,
        )
        print(f"  ✓ 成功: latest={latest}, rows={depth}")
    except Exception as e:
        record_test(
            source_name="腾讯港股K线",
            source_api_or_url="web.ifzq.gtimg.cn/appstock/app/hkfqkline/get",
            data_category="持仓股票日线",
            target_symbol=ticker,
            available=False,
            fields_present=[],
            field_mapping={},
            latest_trade_date="",
            history_depth=0,
            adjusted_type="qfq",
            failure_reason=str(e),
            sample_rows=0,
            can_feed_s1=False,
        )
        print(f"  ✗ 失败: {e}")


def test_akshare_hk_stock(ticker: str):
    """测试 akshare 港股日线"""
    print(f"\n[测试] akshare 港股日线: {ticker}")
    try:
        from s2.update_market_data import _fetch_hk_stock

        df = _fetch_hk_stock(ticker)

        if df.empty:
            record_test(
                source_name="akshare stock_hk_hist",
                source_api_or_url="ak.stock_hk_hist",
                data_category="持仓股票日线",
                target_symbol=ticker,
                available=False,
                fields_present=[],
                field_mapping={},
                latest_trade_date="",
                history_depth=0,
                adjusted_type="none",
                failure_reason="返回空数据",
                sample_rows=0,
                can_feed_s1=False,
            )
            return

        latest = df["trade_date"].max() if "trade_date" in df.columns else ""
        depth = len(df)

        field_mapping = {
            "trade_date": "trade_date",
            "open": "open",
            "close": "close",
            "high": "high",
            "low": "low",
            "vol": "volume",
            "amount": "amount",
        }

        record_test(
            source_name="akshare stock_hk_hist",
            source_api_or_url="ak.stock_hk_hist",
            data_category="持仓股票日线",
            target_symbol=ticker,
            available=True,
            fields_present=list(df.columns),
            field_mapping=field_mapping,
            latest_trade_date=latest,
            history_depth=depth,
            adjusted_type="none",
            failure_reason="",
            sample_rows=depth,
            can_feed_s1=True,
        )
        print(f"  ✓ 成功: latest={latest}, rows={depth}")
    except Exception as e:
        record_test(
            source_name="akshare stock_hk_hist",
            source_api_or_url="ak.stock_hk_hist",
            data_category="持仓股票日线",
            target_symbol=ticker,
            available=False,
            fields_present=[],
            field_mapping={},
            latest_trade_date="",
            history_depth=0,
            adjusted_type="none",
            failure_reason=str(e),
            sample_rows=0,
            can_feed_s1=False,
        )
        print(f"  ✗ 失败: {e}")


def test_eastmoney_holdings():
    """测试东方财富/天天基金持仓数据"""
    print(f"\n[测试] 东方财富/天天基金持仓: 159567")
    try:
        import akshare as ak

        # 尝试获取 ETF 持仓
        df = ak.fund_etf_portfolio_em(fund="159567")

        if df is None or df.empty:
            record_test(
                source_name="东方财富 ETF持仓",
                source_api_or_url="ak.fund_etf_portfolio_em",
                data_category="持仓/成分",
                target_symbol="159567",
                available=False,
                fields_present=[],
                field_mapping={},
                latest_trade_date="",
                history_depth=0,
                adjusted_type="n/a",
                failure_reason="返回空数据",
                sample_rows=0,
                can_feed_s1=False,
            )
            return

        depth = len(df)

        field_mapping = {
            "股票代码": "ticker",
            "股票名称": "name",
            "持仓占比": "weight",
        }

        record_test(
            source_name="东方财富 ETF持仓",
            source_api_or_url="ak.fund_etf_portfolio_em",
            data_category="持仓/成分",
            target_symbol="159567",
            available=True,
            fields_present=list(df.columns),
            field_mapping=field_mapping,
            latest_trade_date=datetime.now().strftime("%Y%m%d"),
            history_depth=depth,
            adjusted_type="n/a",
            failure_reason="",
            sample_rows=depth,
            can_feed_s1=True,
        )
        print(f"  ✓ 成功: rows={depth}")
    except Exception as e:
        record_test(
            source_name="东方财富 ETF持仓",
            source_api_or_url="ak.fund_etf_portfolio_em",
            data_category="持仓/成分",
            target_symbol="159567",
            available=False,
            fields_present=[],
            field_mapping={},
            latest_trade_date="",
            history_depth=0,
            adjusted_type="n/a",
            failure_reason=str(e),
            sample_rows=0,
            can_feed_s1=False,
        )
        print(f"  ✗ 失败: {e}")


def main():
    print("=" * 60)
    print("SS1 原始数据源验证")
    print("=" * 60)

    # 1. ETF 日线测试
    print("\n### 1. ETF 日线测试 ###")
    for symbol in [TARGET_ETF, BENCHMARK_ETF]:
        test_tencent_etf_daily(symbol)
        test_citydata_fund_daily(symbol)
        test_eastmoney_etf_daily(symbol)
        test_akshare_etf_daily(symbol)

    # 2. ETF 份额测试
    print("\n### 2. ETF 份额测试 ###")
    test_citydata_fund_share(TARGET_ETF)
    test_eastmoney_fund_share_em(TARGET_ETF)

    # 3. 持仓数据测试
    print("\n### 3. 持仓数据测试 ###")
    test_eastmoney_holdings()

    # 4. 持仓股票日线测试
    print("\n### 4. 持仓股票日线测试 ###")
    for ticker, name, weight in TOP10_HOLDINGS[:3]:  # 只测试前3只作为样本
        test_tencent_hk_stock(ticker)
        test_akshare_hk_stock(ticker)

    # 输出结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    df = pd.DataFrame(test_results)
    output_dir = PROJECT_ROOT / "ss1/data_source_tests"
    output_dir.mkdir(parents=True, exist_ok=True)

    # CSV 输出
    csv_path = output_dir / "test_results.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\nCSV 已保存: {csv_path}")

    # Markdown 输出
    md_path = output_dir / "test_results.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# SS1 数据源验证结果\n\n")
        f.write(f"**测试时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        # 按数据类别分组
        for category in ["ETF日线", "ETF份额", "持仓/成分", "持仓股票日线"]:
            subset = df[df["data_category"] == category]
            if subset.empty:
                continue

            f.write(f"## {category}\n\n")
            f.write("| 源 | 标的 | 可用 | 最新日期 | 历史深度 | 能喂给S1 |\n")
            f.write("|---|---|---|---|---|---|\n")
            for _, row in subset.iterrows():
                f.write(
                    f"| {row['source_name']} | {row['target_symbol']} | {row['available']} | {row['latest_trade_date']} | {row['history_depth']} | {row['can_feed_S1_original_formula']} |\n"
                )
            f.write("\n")

        # 失败详情
        failed = df[df["available"] == "no"]
        if not failed.empty:
            f.write("## 失败详情\n\n")
            for _, row in failed.iterrows():
                f.write(f"### {row['source_name']} - {row['target_symbol']}\n\n")
                f.write(f"**失败原因**: {row['failure_reason']}\n\n")

    print(f"Markdown 已保存: {md_path}")

    # 打印汇总
    print("\n汇总:")
    available_count = len(df[df["available"] == "yes"])
    total_count = len(df)
    print(f"  可用: {available_count}/{total_count}")


if __name__ == "__main__":
    main()
