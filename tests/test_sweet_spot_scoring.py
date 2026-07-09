"""
甜蜜区间评分测试

测试 S1-03 和 S1-07 的甜蜜区间评分逻辑
"""
import pytest
from wb.indicators.base import IndicatorResult, BaseIndicator
from wb.score_engine import ScoreEngine


class TestSweetSpotScoring:
    """甜蜜区间评分测试"""

    # ==================== S1-03 测试 ====================

    def test_s1_03_below_threshold(self):
        """S1-03 跑输医药基准"""
        result = IndicatorResult(
            code="S1-03",
            name="ETF相对强度",
            value=-0.02,  # -2%
            weight=0.10,
            direction="sweet_spot",
            threshold_sweet_low=0.0,
            threshold_sweet_high=0.12,
            threshold_overheat_low=0.18,
        )
        assert result.evaluate_expectation() == "低于预期"

    def test_s1_03_sweet_spot_lower_bound(self):
        """S1-03 甜蜜区间下界"""
        result = IndicatorResult(
            code="S1-03",
            name="ETF相对强度",
            value=0.0,  # 0%
            weight=0.10,
            direction="sweet_spot",
            threshold_sweet_low=0.0,
            threshold_sweet_high=0.12,
            threshold_overheat_low=0.18,
        )
        assert result.evaluate_expectation() == "超预期"

    def test_s1_03_sweet_spot_middle(self):
        """S1-03 甜蜜区间中间"""
        result = IndicatorResult(
            code="S1-03",
            name="ETF相对强度",
            value=0.08,  # 8%
            weight=0.10,
            direction="sweet_spot",
            threshold_sweet_low=0.0,
            threshold_sweet_high=0.12,
            threshold_overheat_low=0.18,
        )
        assert result.evaluate_expectation() == "超预期"

    def test_s1_03_sweet_spot_upper_bound(self):
        """S1-03 甜蜜区间上界"""
        result = IndicatorResult(
            code="S1-03",
            name="ETF相对强度",
            value=0.12,  # 12%
            weight=0.10,
            direction="sweet_spot",
            threshold_sweet_low=0.0,
            threshold_sweet_high=0.12,
            threshold_overheat_low=0.18,
        )
        assert result.evaluate_expectation() == "超预期"

    def test_s1_03_slight_overheat(self):
        """S1-03 轻度超涨"""
        result = IndicatorResult(
            code="S1-03",
            name="ETF相对强度",
            value=0.15,  # 15%
            weight=0.10,
            direction="sweet_spot",
            threshold_sweet_low=0.0,
            threshold_sweet_high=0.12,
            threshold_overheat_low=0.18,
        )
        assert result.evaluate_expectation() == "符合预期"

    def test_s1_03_overheat_boundary(self):
        """S1-03 过热边界"""
        result = IndicatorResult(
            code="S1-03",
            name="ETF相对强度",
            value=0.18,  # 18%
            weight=0.10,
            direction="sweet_spot",
            threshold_sweet_low=0.0,
            threshold_sweet_high=0.12,
            threshold_overheat_low=0.18,
        )
        assert result.evaluate_expectation() == "符合预期"

    def test_s1_03_severe_overheat(self):
        """S1-03 明显过热"""
        result = IndicatorResult(
            code="S1-03",
            name="ETF相对强度",
            value=0.25,  # 25%
            weight=0.10,
            direction="sweet_spot",
            threshold_sweet_low=0.0,
            threshold_sweet_high=0.12,
            threshold_overheat_low=0.18,
        )
        assert result.evaluate_expectation() == "符合预期"

    # ==================== S1-07 测试 ====================

    def test_s1_07_below_threshold(self):
        """S1-07 跑输科创50"""
        result = IndicatorResult(
            code="S1-07",
            name="科创板相对强度",
            value=-0.05,  # -5%
            weight=0.10,
            direction="sweet_spot",
            threshold_sweet_low=0.0,
            threshold_sweet_high=0.08,
            threshold_overheat_low=0.15,
        )
        assert result.evaluate_expectation() == "低于预期"

    def test_s1_07_sweet_spot_lower_bound(self):
        """S1-07 甜蜜区间下界"""
        result = IndicatorResult(
            code="S1-07",
            name="科创板相对强度",
            value=0.0,  # 0%
            weight=0.10,
            direction="sweet_spot",
            threshold_sweet_low=0.0,
            threshold_sweet_high=0.08,
            threshold_overheat_low=0.15,
        )
        assert result.evaluate_expectation() == "超预期"

    def test_s1_07_sweet_spot_middle(self):
        """S1-07 甜蜜区间中间"""
        result = IndicatorResult(
            code="S1-07",
            name="科创板相对强度",
            value=0.05,  # 5%
            weight=0.10,
            direction="sweet_spot",
            threshold_sweet_low=0.0,
            threshold_sweet_high=0.08,
            threshold_overheat_low=0.15,
        )
        assert result.evaluate_expectation() == "超预期"

    def test_s1_07_sweet_spot_upper_bound(self):
        """S1-07 甜蜜区间上界"""
        result = IndicatorResult(
            code="S1-07",
            name="科创板相对强度",
            value=0.08,  # 8%
            weight=0.10,
            direction="sweet_spot",
            threshold_sweet_low=0.0,
            threshold_sweet_high=0.08,
            threshold_overheat_low=0.15,
        )
        assert result.evaluate_expectation() == "超预期"

    def test_s1_07_slight_overheat(self):
        """S1-07 轻度超涨"""
        result = IndicatorResult(
            code="S1-07",
            name="科创板相对强度",
            value=0.12,  # 12%
            weight=0.10,
            direction="sweet_spot",
            threshold_sweet_low=0.0,
            threshold_sweet_high=0.08,
            threshold_overheat_low=0.15,
        )
        assert result.evaluate_expectation() == "符合预期"

    def test_s1_07_severe_overheat(self):
        """S1-07 明显过热（模拟 7/6 的 23.37%）"""
        result = IndicatorResult(
            code="S1-07",
            name="科创板相对强度",
            value=0.2337,  # 23.37%
            weight=0.10,
            direction="sweet_spot",
            threshold_sweet_low=0.0,
            threshold_sweet_high=0.08,
            threshold_overheat_low=0.15,
        )
        assert result.evaluate_expectation() == "符合预期"

    def test_s1_07_july_9_scenario(self):
        """S1-07 7/9 场景（3.20%）"""
        result = IndicatorResult(
            code="S1-07",
            name="科创板相对强度",
            value=0.032,  # 3.20%
            weight=0.10,
            direction="sweet_spot",
            threshold_sweet_low=0.0,
            threshold_sweet_high=0.08,
            threshold_overheat_low=0.15,
        )
        assert result.evaluate_expectation() == "超预期"

    # ==================== 精细化评分测试 ====================

    def test_sweet_spot_fine_grained_scoring(self):
        """甜蜜区间精细化评分"""
        engine = ScoreEngine.__new__(ScoreEngine)  # 不初始化，只测试方法

        # 跑输：0.4
        result = IndicatorResult(
            code="S1-03",
            name="ETF相对强度",
            value=-0.02,
            weight=0.10,
            direction="sweet_spot",
            threshold_sweet_low=0.0,
            threshold_sweet_high=0.12,
            threshold_overheat_low=0.18,
        )
        assert engine._get_sweet_spot_score(result) == 0.4

        # 健康跑赢：1.0
        result.value = 0.08
        assert engine._get_sweet_spot_score(result) == 1.0

        # 轻度超涨：0.85
        result.value = 0.15
        assert engine._get_sweet_spot_score(result) == 0.85

        # 明显过热：0.7
        result.value = 0.25
        assert engine._get_sweet_spot_score(result) == 0.7

    # ==================== 向后兼容性测试 ====================

    def test_backward_compatibility_higher_better(self):
        """向后兼容性：higher_better 仍然有效"""
        result = IndicatorResult(
            code="S1-01",
            name="资金回流连续性",
            value=0.8,
            weight=0.22,
            direction="higher_better",
            threshold_exceed=0.7,
            threshold_meet=0.4,
        )
        assert result.evaluate_expectation() == "超预期"

    def test_backward_compatibility_lower_better(self):
        """向后兼容性：lower_better 仍然有效"""
        result = IndicatorResult(
            code="S1-XX",
            name="测试指标",
            value=0.02,
            weight=0.10,
            direction="lower_better",
            threshold_exceed=0.03,
            threshold_meet=0.05,
        )
        assert result.evaluate_expectation() == "超预期"

    def test_backward_compatibility_linear_scoring(self):
        """向后兼容性：线性评分仍然有效"""
        engine = ScoreEngine.__new__(ScoreEngine)

        assert engine._get_linear_score("超预期") == 1.0
        assert engine._get_linear_score("符合预期") == 0.7
        assert engine._get_linear_score("低于预期") == 0.4
        assert engine._get_linear_score("未设定阈值") == 0.5
