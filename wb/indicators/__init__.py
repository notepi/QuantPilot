"""
创新药第一阶段量化指标模块
"""
from .base import BaseIndicator, IndicatorResult
from .s1_01_capital_flow import S1_01CapitalFlow
from .s1_02_share_change import S1_02ShareChange
from .s1_03_relative_strength import S1_03RelativeStrength
from .s1_04_volume_ratio import S1_04VolumeRatio
from .s1_05_breadth_repair import S1_05BreadthRepair
from .s1_06_leader_strength import S1_06LeaderStrength
from .s1_07_tech_strength import S1_07TechStrength

__all__ = [
    "BaseIndicator",
    "IndicatorResult",
    "S1_01CapitalFlow",
    "S1_02ShareChange",
    "S1_03RelativeStrength",
    "S1_04VolumeRatio",
    "S1_05BreadthRepair",
    "S1_06LeaderStrength",
    "S1_07TechStrength",
]

# 指标注册表
INDICATORS = {
    "S1-01": S1_01CapitalFlow,
    "S1-02": S1_02ShareChange,
    "S1-03": S1_03RelativeStrength,
    "S1-04": S1_04VolumeRatio,
    "S1-05": S1_05BreadthRepair,
    "S1-06": S1_06LeaderStrength,
    "S1-07": S1_07TechStrength,
}