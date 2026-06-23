"""
S1-01: 资金回流连续性（权重 0.22）

量化口径: 近10个交易日内，589720份额增加的交易日占比

数据源: fund_share（589720份额数据）
- 份额增加 = 资金净流入
- 计算近10日份额变化为正的天数占比
"""
from typing import Optional
import pandas as pd

from .base import BaseIndicator, IndicatorResult


class S1_01CapitalFlow(BaseIndicator):
    """资金回流连续性指标"""

    code = "S1-01"
    name = "资金回流连续性"
    weight = 0.22
    unit = "pct"
    direction = "higher_better"
    threshold_exceed = 0.7  # 超预期: ≥70%
    threshold_meet = 0.4    # 符合预期: 40%-70%

    ETF_CODE = "589720.SH"
    LOOKBACK_DAYS = 10

    def calculate(self, trade_date: Optional[str] = None, **kwargs) -> IndicatorResult:
        """
        计算资金回流连续性

        Args:
            trade_date: 交易日期，格式 YYYYMMDD

        Returns:
            IndicatorResult: 近10日资金净流入为正的天数占比
        """
        if not self.data_fetcher:
            raise ValueError("data_fetcher 未设置")

        # 获取近10日份额数据
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

        # 计算每日份额变化
        df["share_change"] = df["fd_share"].diff()

        # 统计份额增加（资金流入）的天数
        # 排除第一行（diff结果为NaN）
        positive_days = (df["share_change"].dropna() > 0).sum()
        total_days = len(df["share_change"].dropna())

        # 计算占比
        ratio = positive_days / total_days if total_days > 0 else 0.0

        return self.create_result(
            value=ratio,
            trade_date=end_date,
            data_date=actual_data_date,
            raw_data={
                "positive_days": positive_days,
                "total_days": total_days,
                "share_changes": df["share_change"].dropna().tolist(),
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
        # 预留足够空间（考虑非交易日）
        start = end - timedelta(days=n_days * 2)
        return start.strftime("%Y%m%d")