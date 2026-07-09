"""
S1-07: 科创板相对强度（权重 0.10）

量化口径: 589720近10日收益 - 588000近10日收益

数据源: fund_daily（ETF日线行情）
- 589720.SH: 目标ETF（创新药ETF）
- 588000.SH: 基准ETF（科创50ETF）
"""
from typing import Optional
import pandas as pd

from .base import BaseIndicator, IndicatorResult


class S1_07TechStrength(BaseIndicator):
    """科创板相对强度指标

    评分模式：甜蜜区间（sweet_spot）
    - 跑输科创50（< 0%）：不好
    - 健康跑赢（0% - 8%）：最好
    - 轻度超涨（8% - 15%）：需关注
    - 明显过热（> 15%）：透支风险
    """

    code = "S1-07"
    name = "科创板相对强度"
    weight = 0.10
    unit = "pct"

    # 使用甜蜜区间评分
    direction = "sweet_spot"

    # 甜蜜区间阈值
    threshold_sweet_low = 0.0      # 跑输临界点
    threshold_sweet_high = 0.08    # 健康跑赢上限
    threshold_overheat_low = 0.15  # 过热临界点

    ETF_CODE = "589720.SH"
    BENCHMARK_CODE = "588000.SH"
    LOOKBACK_DAYS = 10

    def calculate(self, trade_date: Optional[str] = None, **kwargs) -> IndicatorResult:
        """
        计算科创板相对强度

        Args:
            trade_date: 交易日期，格式 YYYYMMDD

        Returns:
            IndicatorResult: 589720收益 - 588000收益
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

        # 检查数据是否可用
        if etf_df is None or len(etf_df) == 0 or benchmark_df is None or len(benchmark_df) == 0:
            return self.create_result(
                value=0.0,
                trade_date=end_date,
                data_date="",
                raw_data={
                    "insufficient_data": True,
                    "reason": "ETF 或 benchmark 数据获取失败",
                }
            )

        # 先取共同日期，再 tail(11)
        etf_dates = set(etf_df["trade_date"].astype(str))
        benchmark_dates = set(benchmark_df["trade_date"].astype(str))
        common_dates = sorted(etf_dates & benchmark_dates, reverse=True)

        if len(common_dates) < self.LOOKBACK_DAYS + 1:
            return self.create_result(
                value=0.0,
                trade_date=end_date,
                data_date="",
                raw_data={
                    "insufficient_data": True,
                    "reason": f"共同交易日不足，需要 {self.LOOKBACK_DAYS + 1} 个，实际 {len(common_dates)} 个",
                    "etf_dates_count": len(etf_dates),
                    "benchmark_dates_count": len(benchmark_dates),
                    "common_dates_count": len(common_dates),
                }
            )

        # 从共同日期里取最近 11 个
        common_dates = common_dates[:self.LOOKBACK_DAYS + 1]

        # 按共同日期过滤
        etf_df = etf_df[etf_df["trade_date"].astype(str).isin(common_dates)].sort_values("trade_date")
        benchmark_df = benchmark_df[benchmark_df["trade_date"].astype(str).isin(common_dates)].sort_values("trade_date")

        # 计算收益率（11 个数据点，计算 10 日收益）
        etf_return = self._calc_return(etf_df["close"])
        benchmark_return = self._calc_return(benchmark_df["close"])

        # 记录 data_date（取最保守的日期）
        data_date = str(min(etf_df["trade_date"].max(), benchmark_df["trade_date"].max()))

        relative_strength = etf_return - benchmark_return

        return self.create_result(
            value=relative_strength,
            trade_date=end_date,
            data_date=data_date,
            raw_data={
                "etf_return": etf_return,
                "benchmark_return": benchmark_return,
                "common_dates_count": len(common_dates),
                "etf_start_close": float(etf_df["close"].iloc[0]),
                "etf_end_close": float(etf_df["close"].iloc[-1]),
                "benchmark_start_close": float(benchmark_df["close"].iloc[0]),
                "benchmark_end_close": float(benchmark_df["close"].iloc[-1]),
                "insufficient_data": False,
            }
        )

    def _calc_return(self, prices: pd.Series) -> float:
        """计算 10 日收益率"""
        if len(prices) < 11:
            # 不应该发生，因为前面已经检查过共同日期
            return 0.0
        if prices.iloc[-11] == 0:
            return 0.0
        return (prices.iloc[-1] - prices.iloc[-11]) / prices.iloc[-11]

    def _get_latest_date(self) -> str:
        """获取最新交易日期"""
        from .base import get_latest_trade_date
        return get_latest_trade_date()

    def _get_start_date(self, end_date: str, n_days: int) -> str:
        """获取开始日期"""
        from datetime import datetime, timedelta
        end = datetime.strptime(end_date, "%Y%m%d")
        # 预留足够空间（考虑春节等长假）
        start = end - timedelta(days=n_days * 3)
        return start.strftime("%Y%m%d")
