"""
S1-04: 成交放大持续性（权重 0.14）

量化口径: 近5日平均成交额 / 近20日平均成交额

数据源: fund_daily（589720日线行情）
- amount 字段为成交额（单位：万元）
"""
from typing import Optional
import pandas as pd

from .base import BaseIndicator, IndicatorResult


class S1_04VolumeRatio(BaseIndicator):
    """成交放大持续性指标"""

    code = "S1-04"
    name = "成交放大持续性"
    weight = 0.14
    unit = "ratio"
    direction = "higher_better"
    threshold_exceed = 1.5   # 超预期: 近5日成交额是近20日的1.5倍以上
    threshold_meet = 1.1     # 符合预期: 1.1-1.5倍

    ETF_CODE = "589720.SH"
    LOOKBACK_SHORT = 5
    LOOKBACK_LONG = 20

    def calculate(self, trade_date: Optional[str] = None, **kwargs) -> IndicatorResult:
        """
        计算成交放大持续性

        Args:
            trade_date: 交易日期，格式 YYYYMMDD

        Returns:
            IndicatorResult: 近5日平均成交额 / 近20日平均成交额
        """
        if not self.data_fetcher:
            raise ValueError("data_fetcher 未设置")

        end_date = trade_date or self._get_latest_date()
        start_date = self._get_start_date(end_date, self.LOOKBACK_LONG)

        df = self.data_fetcher.get_fund_daily(
            ts_code=self.ETF_CODE,
            start_date=start_date,
            end_date=end_date
        )

        if df is None or len(df) < self.LOOKBACK_SHORT:
            return self.create_result(0.0, trade_date=end_date)

        # 按日期排序
        df = df.sort_values("trade_date")

        # 计算近5日平均成交额
        avg_5d = df["amount"].iloc[-self.LOOKBACK_SHORT:].mean()

        # 计算近20日平均成交额（或全部可用数据）
        lookback = min(self.LOOKBACK_LONG, len(df))
        avg_long = df["amount"].iloc[-lookback:].mean()

        # 计算比值
        if avg_long == 0:
            ratio = 0.0
        else:
            ratio = avg_5d / avg_long

        return self.create_result(
            value=ratio,
            trade_date=end_date,
            raw_data={
                "avg_5d": avg_5d,
                "avg_20d": avg_long,
                "lookback_days": lookback,
                "latest_amount": df["amount"].iloc[-1],
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