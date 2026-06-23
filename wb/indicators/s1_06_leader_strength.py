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

        # 1. 批量获取龙头组合A股数据（一次请求）
        df_all = self.data_fetcher.get_daily_batch(
            ts_codes=self.LEADER_STOCKS,
            start_date=start_date,
            end_date=end_date
        )

        leader_returns = []
        leader_details = []

        if df_all is None or len(df_all) == 0:
            # 数据获取失败
            daily_data_date = ""
            for code in self.LEADER_STOCKS:
                leader_returns.append(0.0)
                leader_details.append({
                    "code": code,
                    "return": 0.0,
                    "reason": "数据获取失败"
                })
        else:
            # 按股票分组计算收益
            daily_data_date = str(df_all["trade_date"].max()) if "trade_date" in df_all.columns else ""
            for code in self.LEADER_STOCKS:
                stock_df = df_all[df_all["ts_code"] == code].sort_values("trade_date")

                if len(stock_df) < 2:
                    leader_returns.append(0.0)
                    leader_details.append({
                        "code": code,
                        "return": 0.0,
                        "reason": "数据不足"
                    })
                    continue

                ret = self._calc_return(stock_df["close"])
                leader_returns.append(ret)
                leader_details.append({
                    "code": code,
                    "return": ret,
                    "start_close": stock_df["close"].iloc[0],
                    "end_close": stock_df["close"].iloc[-1],
                })

        # 加权平均收益
        total_weight = sum(self.LEADER_WEIGHTS)
        weighted_return = sum(r * w for r, w in zip(leader_returns, self.LEADER_WEIGHTS)) / total_weight

        # 2. 计算ETF收益
        etf_df = self.data_fetcher.get_fund_daily(
            ts_code=self.ETF_CODE,
            start_date=start_date,
            end_date=end_date
        )

        if etf_df is None or len(etf_df) < 2:
            etf_return = 0.0
            etf_data_date = ""
        else:
            etf_df = etf_df.sort_values("trade_date")
            etf_return = self._calc_return(etf_df["close"])
            etf_data_date = str(etf_df["trade_date"].max())

        # 取最保守的数据日期
        data_dates = [d for d in [daily_data_date, etf_data_date] if d]
        actual_data_date = min(data_dates) if data_dates else ""

        # 3. 计算龙头先行强度
        leader_strength = weighted_return - etf_return

        return self.create_result(
            value=leader_strength,
            trade_date=end_date,
            data_date=actual_data_date,
            raw_data={
                "leader_weighted_return": weighted_return,
                "etf_return": etf_return,
                "leader_returns": leader_returns,
                "leader_details": leader_details,
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