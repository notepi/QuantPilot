"""
S1-02: ETF份额变化/净申购持续性（权重 0.18）

量化口径: 近10日累计份额变化率

数据源: fund_share（589720份额数据）
- fd_share 字段为份额（单位：万份）
- 计算 (期末份额 - 期初份额) / 期初份额
"""
from typing import Optional
import pandas as pd

from .base import BaseIndicator, IndicatorResult


class S1_02ShareChange(BaseIndicator):
    """ETF份额变化指标"""

    code = "S1-02"
    name = "ETF份额变化"
    weight = 0.18
    unit = "pct"
    direction = "higher_better"
    threshold_exceed = 0.03   # 超预期: 份额增长3%以上
    threshold_meet = 0.0      # 符合预期: 份额增长0%-3%

    ETF_CODE = "589720.SH"
    LOOKBACK_DAYS = 10

    def calculate(self, trade_date: Optional[str] = None, **kwargs) -> IndicatorResult:
        """
        计算ETF份额变化

        Args:
            trade_date: 交易日期，格式 YYYYMMDD

        Returns:
            IndicatorResult: 近10日份额增量占比
        """
        if not self.data_fetcher:
            raise ValueError("data_fetcher 未设置")

        end_date = trade_date or self._get_latest_date()
        start_date = self._get_start_date(end_date, self.LOOKBACK_DAYS)

        df = self.data_fetcher.get_fund_share(
            ts_code=self.ETF_CODE,
            start_date=start_date,
            end_date=end_date
        )

        if df is None or len(df) < 2:
            return self.create_result(0.0, trade_date=end_date, data_date="")

        # 按日期排序
        df = df.sort_values("trade_date")

        # 获取实际数据最新日期
        actual_data_date = str(df["trade_date"].max())

        # 计算份额变化率
        start_share = df["fd_share"].iloc[0]
        end_share = df["fd_share"].iloc[-1]

        if start_share == 0:
            change_rate = 0.0
        else:
            change_rate = (end_share - start_share) / start_share

        return self.create_result(
            value=change_rate,
            trade_date=end_date,
            data_date=actual_data_date,
            raw_data={
                "start_share": start_share,
                "end_share": end_share,
                "share_change": end_share - start_share,
                "start_date": df["trade_date"].iloc[0],
                "end_date": df["trade_date"].iloc[-1],
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