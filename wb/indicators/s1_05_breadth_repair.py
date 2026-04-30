"""
S1-05: 板块广度修复（权重 0.14）

量化口径: 成分股站上20日均线占比

数据源:
- fund_portfolio: 获取589720成分股列表
- daily: A股日线行情（citydata代理）
"""
from typing import Optional, List
import pandas as pd

from .base import BaseIndicator, IndicatorResult


class S1_05BreadthRepair(BaseIndicator):
    """板块广度修复指标"""

    code = "S1-05"
    name = "板块广度修复"
    weight = 0.14
    unit = "pct"
    direction = "higher_better"
    threshold_exceed = 0.6   # 超预期: 60%以上成分股站上均线
    threshold_meet = 0.35    # 符合预期: 35%-60%

    ETF_CODE = "589720.SH"
    MA_WINDOW = 20
    LOOKBACK_DAYS = 25  # 获取25日数据确保有足够交易日

    def calculate(self, trade_date: Optional[str] = None, **kwargs) -> IndicatorResult:
        """
        计算板块广度修复

        Args:
            trade_date: 交易日期，格式 YYYYMMDD

        Returns:
            IndicatorResult: 成分股站上20日均线占比
        """
        if not self.data_fetcher:
            raise ValueError("data_fetcher 未设置")

        end_date = trade_date or self._get_latest_date()
        start_date = self._get_start_date(end_date, self.LOOKBACK_DAYS)

        # 1. 获取成分股列表
        holdings = self.data_fetcher.get_fund_portfolio(ts_code=self.ETF_CODE)

        if holdings is None or len(holdings) == 0:
            return self.create_result(0.0, trade_date=end_date)

        # 取最新报告期
        latest_period = holdings["end_date"].max()
        latest_holdings = holdings[holdings["end_date"] == latest_period]

        # 获取股票代码列表（A股格式：688235.SH）
        stock_codes = latest_holdings["symbol"].tolist()

        # 2. 批量获取所有A股日线数据（一次请求）
        df_all = self.data_fetcher.get_daily_batch(
            ts_codes=stock_codes,
            start_date=start_date,
            end_date=end_date
        )

        if df_all is None or len(df_all) == 0:
            return self.create_result(0.0, trade_date=end_date, raw_data={
                "reason": "A股数据获取失败",
                "report_period": latest_period,
            })

        # 3. 按股票分组计算均线
        stocks_above_ma = 0
        total_stocks = len(stock_codes)
        stock_details = []

        for stock_code in stock_codes:
            stock_df = df_all[df_all["ts_code"] == stock_code].sort_values("trade_date")

            if len(stock_df) < self.MA_WINDOW:
                stock_details.append({
                    "code": stock_code,
                    "above_ma": False,
                    "reason": "数据不足"
                })
                continue

            # 计算20日均线
            ma20 = stock_df["close"].iloc[-self.MA_WINDOW:].mean()
            latest_close = stock_df["close"].iloc[-1]

            above_ma = latest_close > ma20
            if above_ma:
                stocks_above_ma += 1

            stock_details.append({
                "code": stock_code,
                "above_ma": above_ma,
                "latest_close": latest_close,
                "ma20": ma20,
            })

        # 计算占比
        ratio = stocks_above_ma / total_stocks if total_stocks > 0 else 0.0

        return self.create_result(
            value=ratio,
            trade_date=end_date,
            raw_data={
                "stocks_above_ma": stocks_above_ma,
                "total_stocks": total_stocks,
                "report_period": latest_period,
                "stock_details": stock_details[:10],
            }
        )

    def _get_latest_date(self) -> str:
        """获取最新交易日期"""
        from .base import get_latest_trade_date
        return get_latest_trade_date()

    def _get_start_date(self, end_date: str, n_days: int) -> str:
        """获取开始日期"""
        from datetime import datetime, timedelta
        end = datetime.strptime(end_date, "%Y%m%d")
        start = end - timedelta(days=n_days * 2)
        return start.strftime("%Y%m%d")