"""
指标基类和公共工具函数
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

import pandas as pd


@dataclass
class IndicatorResult:
    """指标计算结果"""
    code: str                    # 指标编号，如 "S1-01"
    name: str                    # 指标名称
    value: float                 # 计算值
    weight: float                # 权重
    unit: str = "pct"            # 单位
    direction: str = "higher_better"  # 方向：higher_better 或 lower_better
    threshold_exceed: Optional[float] = None   # 超预期阈值
    threshold_meet: Optional[float] = None     # 符合预期阈值
    threshold_below: Optional[float] = None    # 低于预期阈值
    expectation: str = ""        # 预期判定结果
    trade_date: str = ""         # 计算日期（报告日期）
    data_date: str = ""          # 实际数据日期（数据最新可得日期）
    raw_data: Optional[dict] = None  # 原始数据

    def evaluate_expectation(self) -> str:
        """评估预期结果"""
        if self.threshold_exceed is not None:
            if self.direction == "higher_better":
                if self.value >= self.threshold_exceed:
                    return "超预期"
                elif self.value >= self.threshold_meet:
                    return "符合预期"
                else:
                    return "低于预期"
            else:
                if self.value <= self.threshold_exceed:
                    return "超预期"
                elif self.value <= self.threshold_meet:
                    return "符合预期"
                else:
                    return "低于预期"
        return "未设定阈值"

    def to_dict(self) -> dict:
        """转换为字典"""
        result = {
            "code": self.code,
            "name": self.name,
            "value": self.value,
            "weight": self.weight,
            "unit": self.unit,
            "direction": self.direction,
            "expectation": self.expectation or self.evaluate_expectation(),
            "trade_date": self.trade_date,
        }
        if self.data_date:
            result["data_date"] = self.data_date
        return result


class BaseIndicator(ABC):
    """指标基类"""

    # 子类需要覆盖的类属性
    code: str = ""
    name: str = ""
    weight: float = 0.0
    unit: str = "pct"
    direction: str = "higher_better"
    threshold_exceed: Optional[float] = None
    threshold_meet: Optional[float] = None
    threshold_below: Optional[float] = None

    def __init__(self, data_fetcher=None):
        """
        初始化指标

        Args:
            data_fetcher: 数据获取器实例
        """
        self.data_fetcher = data_fetcher

    @abstractmethod
    def calculate(self, trade_date: Optional[str] = None, **kwargs) -> IndicatorResult:
        """
        计算指标值

        Args:
            trade_date: 交易日期，格式 YYYYMMDD，默认最新交易日
            **kwargs: 其他参数

        Returns:
            IndicatorResult: 指标计算结果
        """
        pass

    def get_trade_dates(self, end_date: str, n_days: int) -> tuple:
        """
        获取过去N个交易日的日期范围

        Args:
            end_date: 结束日期，格式 YYYYMMDD
            n_days: 天数

        Returns:
            (start_date, end_date) 元组
        """
        # 简化实现：使用自然日，实际应从交易日历获取
        end = datetime.strptime(end_date, "%Y%m%d")
        start = end - timedelta(days=n_days * 2)  # 预留足够空间
        return start.strftime("%Y%m%d"), end_date

    def create_result(self, value: float, trade_date: str = "", raw_data: dict = None, data_date: str = "") -> IndicatorResult:
        """
        创建指标结果对象

        Args:
            value: 计算值
            trade_date: 交易日期（报告日期）
            raw_data: 原始数据
            data_date: 实际数据日期

        Returns:
            IndicatorResult
        """
        return IndicatorResult(
            code=self.code,
            name=self.name,
            value=value,
            weight=self.weight,
            unit=self.unit,
            direction=self.direction,
            threshold_exceed=self.threshold_exceed,
            threshold_meet=self.threshold_meet,
            threshold_below=self.threshold_below,
            trade_date=trade_date,
            data_date=data_date,
            raw_data=raw_data,
        )


def get_latest_trade_date() -> str:
    """从数据文件获取最新交易日期"""
    from pathlib import Path

    data_dir = Path(__file__).parent.parent.parent / "data" / "raw"
    fund_daily_path = data_dir / "fund_daily.csv"

    if not fund_daily_path.exists():
        # 数据文件不存在，回退到简化逻辑
        today = datetime.now()
        if today.weekday() == 5:  # 周六
            today -= timedelta(days=1)
        elif today.weekday() == 6:  # 周日
            today -= timedelta(days=2)
        return today.strftime("%Y%m%d")

    # 从 fund_daily.csv 读取最新交易日
    df = pd.read_csv(fund_daily_path)
    latest_date = df["trade_date"].max()
    return str(latest_date)


def calculate_return(prices: pd.Series) -> float:
    """
    计算区间收益率

    Args:
        prices: 价格序列

    Returns:
        收益率（小数）
    """
    if len(prices) < 2:
        return 0.0
    return (prices.iloc[-1] - prices.iloc[0]) / prices.iloc[0]


def calculate_ma(prices: pd.Series, window: int) -> float:
    """
    计算移动平均

    Args:
        prices: 价格序列
        window: 窗口期

    Returns:
        移动平均值
    """
    if len(prices) < window:
        return prices.mean()
    return prices.iloc[-window:].mean()