"""
指标评分与综合评价引擎

整合6个第一阶段指标，计算加权综合得分
"""
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

from wb.data_fetcher import get_data_fetcher
from wb.indicators import INDICATORS, BaseIndicator, IndicatorResult


@dataclass
class PhaseScore:
    """阶段综合评分结果"""
    phase: str = "第一阶段"
    trade_date: str = ""
    total_score: float = 0.0
    expectation_level: str = ""
    indicator_results: List[Dict] = None
    summary: str = ""

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "phase": self.phase,
            "trade_date": self.trade_date,
            "total_score": self.total_score,
            "expectation_level": self.expectation_level,
            "indicator_results": self.indicator_results,
            "summary": self.summary,
        }


class ScoreEngine:
    """评分引擎"""

    # 阈值定义
    SCORE_EXCEED = 0.8
    SCORE_MEET = 0.6
    SCORE_BELOW = 0.4

    def __init__(self, data_fetcher=None):
        """
        初始化评分引擎

        Args:
            data_fetcher: 数据获取器实例
        """
        self.data_fetcher = data_fetcher or get_data_fetcher()

        # 初始化所有指标实例
        self.indicators: Dict[str, BaseIndicator] = {}
        for code, cls in INDICATORS.items():
            self.indicators[code] = cls(data_fetcher=self.data_fetcher)

    def calculate_all(
        self,
        trade_date: Optional[str] = None,
    ) -> PhaseScore:
        """
        计算所有指标并生成综合评分

        Args:
            trade_date: 交易日期，格式 YYYYMMDD

        Returns:
            PhaseScore: 综合评分结果
        """
        if not trade_date:
            from wb.indicators.base import get_latest_trade_date
            trade_date = get_latest_trade_date()

        # 计算各指标
        results: List[IndicatorResult] = []
        indicator_dicts: List[Dict] = []

        for code, indicator in self.indicators.items():
            try:
                result = indicator.calculate(trade_date=trade_date)
                results.append(result)
                indicator_dicts.append(result.to_dict())
            except Exception as e:
                # 指标计算失败，记录默认值
                print(f"指标 {code} 计算失败: {e}")
                indicator_dicts.append({
                    "code": code,
                    "name": indicator.name,
                    "value": 0.0,
                    "weight": indicator.weight,
                    "expectation": "计算失败",
                    "trade_date": trade_date,
                })

        # 计算加权综合得分
        total_score = self._calculate_weighted_score(results)

        # 评定综合预期等级
        expectation_level = self._evaluate_expectation_level(total_score)

        # 生成评价摘要
        summary = self._generate_summary(results, total_score, expectation_level)

        return PhaseScore(
            phase="第一阶段",
            trade_date=trade_date,
            total_score=total_score,
            expectation_level=expectation_level,
            indicator_results=indicator_dicts,
            summary=summary,
        )

    def calculate_single(
        self,
        indicator_code: str,
        trade_date: Optional[str] = None,
    ) -> IndicatorResult:
        """
        计算单个指标

        Args:
            indicator_code: 指标代码，如 "S1-01"
            trade_date: 交易日期

        Returns:
            IndicatorResult
        """
        if indicator_code not in self.indicators:
            raise ValueError(f"未知的指标代码: {indicator_code}")

        return self.indicators[indicator_code].calculate(trade_date=trade_date)

    def _calculate_weighted_score(self, results: List[IndicatorResult]) -> float:
        """
        计算加权综合得分

        各指标得分计算规则：
        - 超预期: 1.0
        - 符合预期: 0.7
        - 低于预期: 0.4
        - 未设定阈值: 0.5
        """
        total_weight = 0.0
        weighted_sum = 0.0

        for result in results:
            weight = result.weight

            # 根据预期等级计算得分
            expectation = result.expectation or result.evaluate_expectation()
            if expectation == "超预期":
                score = 1.0
            elif expectation == "符合预期":
                score = 0.7
            elif expectation == "低于预期":
                score = 0.4
            else:
                score = 0.5  # 未设定阈值或计算失败

            weighted_sum += score * weight
            total_weight += weight

        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def _evaluate_expectation_level(self, total_score: float) -> str:
        """评定综合预期等级"""
        if total_score >= self.SCORE_EXCEED:
            return "超预期"
        elif total_score >= self.SCORE_MEET:
            return "符合预期"
        elif total_score >= self.SCORE_BELOW:
            return "低于预期"
        else:
            return "严重低于预期"

    def _generate_summary(
        self,
        results: List[IndicatorResult],
        total_score: float,
        expectation_level: str,
    ) -> str:
        """
        生成评价摘要

        Args:
            results: 各指标结果
            total_score: 综合得分
            expectation_level: 预期等级

        Returns:
            评价摘要文本
        """
        # 统计各等级数量
        exceed_count = 0
        meet_count = 0
        below_count = 0

        for result in results:
            expectation = result.expectation or result.evaluate_expectation()
            if expectation == "超预期":
                exceed_count += 1
            elif expectation == "符合预期":
                meet_count += 1
            elif expectation == "低于预期":
                below_count += 1

        # 构建摘要
        summary_parts = [
            f"综合得分 {total_score:.2f}，整体表现{expectation_level}。",
            f"6项指标中：超预期{exceed_count}项，符合预期{meet_count}项，低于预期{below_count}项。",
        ]

        # 添加关键指标说明
        key_indicators = []
        for result in results:
            expectation = result.expectation or result.evaluate_expectation()
            if expectation == "超预期":
                key_indicators.append(f"{result.name}表现突出")
            elif expectation == "低于预期":
                key_indicators.append(f"{result.name}需关注")

        if key_indicators:
            summary_parts.append("主要特征：" + "、".join(key_indicators[:3]) + "。")

        return "".join(summary_parts)


# 单例实例
_score_engine: Optional[ScoreEngine] = None


def get_score_engine(use_local: bool = False) -> ScoreEngine:
    """获取评分引擎单例"""
    global _score_engine
    if _score_engine is None:
        _score_engine = ScoreEngine(data_fetcher=get_data_fetcher(use_local=use_local))
    return _score_engine