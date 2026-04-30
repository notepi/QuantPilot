# 代码架构

## 数据流

```
接口 → CSV → 计算 → JSON → API
  ↑        ↑        ↑        ↑
update   data_fetcher  score_engine  api_server
```

## 核心模块

### 1. update_data.py - 数据抓取

从接口抓取数据，保存到 `data/raw/`：
- `fund_share.csv` - ETF份额
- `fund_daily.csv` - ETF日线
- `fund_portfolio.csv` - 成分股
- `hk_daily.csv` - 港股日线

特性：
- 自动缓存检查（避免hk_daily超限）
- `--force` 强制更新

### 2. data_fetcher.py - 数据读取

统一数据入口，支持两种模式：
- `use_local=True` - 读本地CSV
- `use_local=False` - 调接口

### 3. indicators/ - 指标计算

6个指标类，继承 `BaseIndicator`：
- `s1_01_capital_flow.py`
- `s1_02_share_change.py`
- `s1_03_relative_strength.py`
- `s1_04_volume_ratio.py`
- `s1_05_breadth_repair.py`
- `s1_06_leader_strength.py`

### 4. score_engine.py - 评分引擎

计算加权综合得分，生成评价摘要。

### 5. calculate_indicators.py - 指标计算脚本

计算指标，保存到 `data/indicators/{日期}.json`

### 6. api_server.py - API服务

FastAPI 服务，读取本地 JSON。

## 扩展指南

添加新指标：
1. 在 `wb/indicators/` 创建 `s1_xx.py`
2. 继承 `BaseIndicator`
3. 实现 `calculate()` 方法
4. 在 `__init__.py` 注册
5. 更新 `docs/indicators.md`