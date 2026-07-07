"""
S1-06: 龙头先行强度（权重 0.12）

量化口径: 龙头组合近10日平均收益 - 589720近10日收益

数据源:
- daily: A股日线行情（citydata代理）
- fund_daily: 589720日线行情（citydata代理）

龙头组合（待从 fund_portfolio 获取前五大持仓）:
"""
from typing import Optional
import pandas as pd

from .base import BaseIndicator, IndicatorResult


class S1_06LeaderStrength(BaseIndicator):
    """龙头先行强度指标"""

    code = "S1-06"
    name = "龙头先行强度"
    weight = 0.12
    unit = "pct"
    direction = "higher_better"
    threshold_exceed = 0.05   # 超预期: 龙头超越ETF 5%以上
    threshold_meet = 0.0      # 符合预期: 0%-5%

    ETF_CODE = "589720.SH"
    LOOKBACK_DAYS = 10

    # 龙头组合（前五大持仓）
    LEADER_STOCKS = [
        "688235.SH",  # 百济神州-U
        "688578.SH",  # 科伦博泰-B
        "688506.SH",  # 百利天恒-U
        "688180.SH",  # 君实生物-U
        "688266.SH",  # 泽璟制药-U
    ]

    # 对应权重（归一化）
    LEADER_WEIGHTS = [0.2413, 0.2363, 0.2241, 0.154, 0.1444]

    def calculate(self, trade_date: Optional[str] = None, **kwargs) -> IndicatorResult:
        """
        计算龙头先行强度

        Args:
            trade_date: 交易日期，格式 YYYYMMDD

        Returns:
            IndicatorResult: 龙头组合收益 - ETF收益
        """
        if not self.data_fetcher:
            raise ValueError("data_fetcher 未设置")

        end_date = trade_date or self._get_latest_date()
        start_date = self._get_start_date(end_date, self.LOOKBACK_DAYS)

        # 1. 获取 ETF 数据
        etf_df = self.data_fetcher.get_fund_daily(
            ts_code=self.ETF_CODE,
            start_date=start_date,
            end_date=end_date
        )

        if etf_df is None or len(etf_df) < self.LOOKBACK_DAYS + 1:
            return self.create_result(
                value=0.0,
                trade_date=end_date,
                data_date="",
                raw_data={
                    "insufficient_data": True,
                    "reason": "ETF 数据不足",
                }
            )

        # 2. 先取 ETF 最近 11 个交易日作为窗口
        etf_df = etf_df.sort_values("trade_date")
        etf_window_dates = set(etf_df["trade_date"].astype(str).tail(self.LOOKBACK_DAYS + 1))

        if len(etf_window_dates) < self.LOOKBACK_DAYS + 1:
            return self.create_result(
                value=0.0,
                trade_date=end_date,
                data_date="",
                raw_data={
                    "insufficient_data": True,
                    "reason": "ETF 窗口日期不足 11 个",
                }
            )

        # 3. 计算 ETF 收益
        etf_return = self._calc_return(etf_df["close"])

        # 4. 获取龙头股数据
        df_all = self.data_fetcher.get_daily_batch(
            ts_codes=self.LEADER_STOCKS,
            start_date=start_date,
            end_date=end_date
        )

        if df_all is None or len(df_all) == 0:
            return self.create_result(
                value=0.0,
                trade_date=end_date,
                data_date="",
                raw_data={
                    "insufficient_data": True,
                    "reason": "龙头股数据获取失败",
                }
            )

        # 5. 计算每只龙头股收益（在 ETF 窗口内判断数据充足性）
        leader_returns = []
        leader_weights_used = []
        leader_details = []

        for code, weight in zip(self.LEADER_STOCKS, self.LEADER_WEIGHTS):
            stock_df = df_all[df_all["ts_code"] == code]

            # 只保留在 ETF 窗口内的数据
            stock_df_in_window = stock_df[stock_df["trade_date"].astype(str).isin(etf_window_dates)].sort_values("trade_date")

            if len(stock_df_in_window) < self.LOOKBACK_DAYS + 1:
                # 该股票在窗口内数据不足，跳过
                leader_details.append({
                    "code": code,
                    "return": 0.0,
                    "weight": weight,
                    "insufficient_data": True,
                    "data_points_in_window": len(stock_df_in_window),
                    "required_points": self.LOOKBACK_DAYS + 1,
                })
                continue

            # 计算该股票收益
            ret = self._calc_return(stock_df_in_window["close"])
            leader_returns.append(ret)
            leader_weights_used.append(weight)
            leader_details.append({
                "code": code,
                "return": ret,
                "weight": weight,
                "insufficient_data": False,
                "data_points_in_window": len(stock_df_in_window),
                "start_date": str(stock_df_in_window["trade_date"].iloc[-11]),
                "end_date": str(stock_df_in_window["trade_date"].iloc[-1]),
                "start_close": float(stock_df_in_window["close"].iloc[-11]),
                "end_close": float(stock_df_in_window["close"].iloc[-1]),
            })

        # 6. 检查是否有足够的有效股票
        if len(leader_returns) == 0:
            return self.create_result(
                value=0.0,
                trade_date=end_date,
                data_date="",
                raw_data={
                    "insufficient_data": True,
                    "reason": "所有龙头股在 ETF 窗口内数据均不足",
                    "leader_details": leader_details,
                }
            )

        # 7. 加权平均收益（使用有效股票的权重重归一化）
        total_weight = sum(leader_weights_used)
        weighted_return = sum(r * w for r, w in zip(leader_returns, leader_weights_used)) / total_weight

        # 8. 计算龙头先行强度
        leader_strength = weighted_return - etf_return

        # 9. 记录 data_date（取最保守的日期）
        etf_data_date = str(etf_df["trade_date"].max())
        stock_data_dates = [d["end_date"] for d in leader_details if not d.get("insufficient_data")]
        data_dates = [etf_data_date] + stock_data_dates
        actual_data_date = min(data_dates) if data_dates else ""

        return self.create_result(
            value=leader_strength,
            trade_date=end_date,
            data_date=actual_data_date,
            raw_data={
                "leader_weighted_return": weighted_return,
                "etf_return": etf_return,
                "leader_details": leader_details,
                "valid_stocks_count": len(leader_returns),
                "total_stocks": len(self.LEADER_STOCKS),
                "etf_window_dates_count": len(etf_window_dates),
                "insufficient_data": False,
            }
        )

    def _calc_return(self, prices: pd.Series) -> float:
        """计算 10 日收益率"""
        if len(prices) < 11:
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