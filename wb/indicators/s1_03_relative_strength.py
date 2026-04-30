"""
S1-03: ETF相对强度（权重 0.20）

量化口径: 589720近10日收益 - 159557近10日收益

数据源: fund_daily（ETF日线行情）
- 589720.SH: 目标ETF
- 159557.SZ: 基准ETF（替代HSHCI）
"""
from typing import Optional
import pandas as pd

from .base import BaseIndicator, IndicatorResult


class S1_03RelativeStrength(BaseIndicator):
    """ETF相对强度指标"""

    code = "S1-03"
    name = "ETF相对强度"
    weight = 0.20
    unit = "pct"
    direction = "higher_better"
    threshold_exceed = 0.05   # 超预期: 超越基准5%以上
    threshold_meet = 0.0      # 符合预期: 0%-5%

    ETF_CODE = "589720.SH"
    BENCHMARK_CODE = "159557.SZ"
    LOOKBACK_DAYS = 10

    def calculate(self, trade_date: Optional[str] = None, **kwargs) -> IndicatorResult:
        """
        计算ETF相对强度

        Args:
            trade_date: 交易日期，格式 YYYYMMDD

        Returns:
            IndicatorResult: 589720收益 - 基准收益
        """
        if not self.data_fetcher:
            raise ValueError("data_fetcher 未设置")

        end_date = trade_date or self._get_latest_date()
        start_date = self._get_start_date(end_date, self.LOOKBACK_DAYS)

        # 获取ETF日线数据
        etf_df = self.data_fetcher.get_fund_daily(
            ts_code=self.ETF_CODE,
            start_date=start_date,
            end_date=end_date
        )

        benchmark_df = self.data_fetcher.get_fund_daily(
            ts_code=self.BENCHMARK_CODE,
            start_date=start_date,
            end_date=end_date
        )

        if etf_df is None or len(etf_df) < 2:
            etf_return = 0.0
        else:
            etf_df = etf_df.sort_values("trade_date")
            etf_return = self._calc_return(etf_df["close"])

        if benchmark_df is None or len(benchmark_df) < 2:
            benchmark_return = 0.0
        else:
            benchmark_df = benchmark_df.sort_values("trade_date")
            benchmark_return = self._calc_return(benchmark_df["close"])

        relative_strength = etf_return - benchmark_return

        return self.create_result(
            value=relative_strength,
            trade_date=end_date,
            raw_data={
                "etf_return": etf_return,
                "benchmark_return": benchmark_return,
                "etf_start_close": etf_df["close"].iloc[0] if etf_df is not None and len(etf_df) > 0 else None,
                "etf_end_close": etf_df["close"].iloc[-1] if etf_df is not None and len(etf_df) > 0 else None,
                "benchmark_start_close": benchmark_df["close"].iloc[0] if benchmark_df is not None and len(benchmark_df) > 0 else None,
                "benchmark_end_close": benchmark_df["close"].iloc[-1] if benchmark_df is not None and len(benchmark_df) > 0 else None,
            }
        )

    def _calc_return(self, prices: pd.Series) -> float:
        """计算收益率"""
        if len(prices) < 2 or prices.iloc[0] == 0:
            return 0.0
        return (prices.iloc[-1] - prices.iloc[0]) / prices.iloc[0]

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