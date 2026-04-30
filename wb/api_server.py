"""
创新药投资阶段评价量化系统 - API 服务

支持两种模式：
1. 从本地JSON读取已计算的指标结果（推荐）
2. 实时计算指标
"""
import json
import os
from pathlib import Path
from typing import Optional, List
from datetime import datetime
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel

from wb.score_engine import get_score_engine
from wb.indicators import INDICATORS


# 数据目录
DATA_DIR = Path(__file__).parent.parent / "data"
INDICATORS_DIR = DATA_DIR / "indicators"


# ==================== API 模型定义 ====================

class IndicatorResultResponse(BaseModel):
    """单个指标结果响应"""
    code: str
    name: str
    value: float
    weight: float
    unit: str
    direction: str
    expectation: str
    trade_date: str


class PhaseScoreResponse(BaseModel):
    """阶段评分响应"""
    phase: str
    trade_date: str
    total_score: float
    expectation_level: str
    indicator_results: list
    summary: str


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    timestamp: str
    indicators_registered: int
    data_available: bool


# ==================== 工具函数 ====================

def get_latest_indicator_file() -> Optional[Path]:
    """获取最新的指标文件"""
    if not INDICATORS_DIR.exists():
        return None

    files = sorted(INDICATORS_DIR.glob("*.json"), reverse=True)
    return files[0] if files else None


def load_indicator_result(trade_date: str = None) -> Optional[dict]:
    """从本地JSON加载指标结果"""
    if trade_date:
        filepath = INDICATORS_DIR / f"{trade_date}.json"
    else:
        filepath = get_latest_indicator_file()

    if not filepath or not filepath.exists():
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# ==================== FastAPI 应用 ====================

app = FastAPI(
    title="创新药投资阶段评价量化系统",
    description="第一阶段6项指标自动化计算API",
    version="0.2.0",
)


# ==================== API 端点 ====================

@app.get("/", response_model=dict)
async def root():
    """根路径"""
    return {
        "name": "创新药投资阶段评价量化系统",
        "phase": "第一阶段",
        "indicators": list(INDICATORS.keys()),
        "endpoints": {
            "latest": "/indicators/latest",
            "history": "/indicators/history",
            "calculate": "/calculate",
        },
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    latest_file = get_latest_indicator_file()
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        indicators_registered=len(INDICATORS),
        data_available=latest_file is not None,
    )


@app.get("/indicators", response_model=list)
async def list_indicators():
    """列出所有指标定义"""
    return [
        {
            "code": code,
            "name": cls.name,
            "weight": cls.weight,
            "unit": cls.unit,
            "direction": cls.direction,
        }
        for code, cls in INDICATORS.items()
    ]


@app.get("/indicators/latest", response_model=PhaseScoreResponse)
async def get_latest():
    """获取最新的指标结果（从本地JSON读取）"""
    result = load_indicator_result()

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="未找到指标数据，请先运行 python -m wb.calculate_indicators"
        )

    return PhaseScoreResponse(**result)


@app.get("/indicators/{trade_date}", response_model=PhaseScoreResponse)
async def get_by_date(trade_date: str):
    """获取指定日期的指标结果"""
    if len(trade_date) != 8 or not trade_date.isdigit():
        raise HTTPException(status_code=400, detail="日期格式错误，应为YYYYMMDD")

    result = load_indicator_result(trade_date=trade_date)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"未找到 {trade_date} 的指标数据"
        )

    return PhaseScoreResponse(**result)


@app.get("/indicators/history", response_model=List[str])
async def get_history(days: int = Query(30, description="返回最近N天的数据")):
    """获取可用的指标日期列表"""
    if not INDICATORS_DIR.exists():
        return []

    files = sorted(INDICATORS_DIR.glob("*.json"), reverse=True)[:days]
    return [f.stem for f in files]


@app.get("/calculate", response_model=PhaseScoreResponse)
async def calculate_all(
    trade_date: Optional[str] = Query(
        None,
        description="交易日期，格式YYYYMMDD，默认最新交易日",
        pattern="^[0-9]{8}$",
    ),
):
    """
    实时计算所有指标（从本地CSV读取数据）

    注意：需要先运行 python -m wb.update_data 更新数据
    """
    try:
        engine = get_score_engine(use_local=True)
        result = engine.calculate_all(trade_date=trade_date)
        return PhaseScoreResponse(**result.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"计算失败: {str(e)}")


@app.post("/calculate", response_model=PhaseScoreResponse)
async def calculate_and_save(
    trade_date: Optional[str] = Query(None, pattern="^[0-9]{8}$"),
):
    """
    计算指标并保存到本地JSON

    返回计算结果
    """
    try:
        from wb.calculate_indicators import calculate_and_save as do_calculate
        result = do_calculate(trade_date=trade_date)

        if result is None:
            raise HTTPException(status_code=500, detail="计算失败")

        return PhaseScoreResponse(**result.to_dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"计算失败: {str(e)}")


# ==================== 启动入口 ====================

def run_server(host: str = "0.0.0.0", port: int = 8000):
    """启动API服务"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()