# 使用指南

## 快捷命令（推荐）

```bash
# 一键执行：更新数据 → 计算指标 → 生成日报
uv run python -m wb.daily_flow
```

## 分步执行

```bash
# 1. 更新数据（接口 → CSV）
uv run python -m wb.update_data

# 2. 计算指标（CSV → JSON）
uv run python -m wb.calculate_indicators

# 3. 生成日报（JSON → Markdown）
uv run python -m wb.generate_report

# 日报文件: docs/daily_report.md
# 格式: 横轴指标(S1-01~S1-06)，纵轴日期，带预期图标(🟢🟡🔴)
```

## 其他命令

```bash
# 计算历史指标（回测）
uv run python -m wb.calculate_indicators history 30

# 启动API（读取JSON）
uv run python -m wb.api_server

# 启动可视化界面
uv run streamlit run wb/dashboard.py
```

## 数据文件说明

| 文件 | 内容 | 用途 |
|------|------|------|
| fund_daily.csv | ETF日线行情 | 价格、成交额 |
| fund_share.csv | ETF份额数据 | 份额变化 |
| fund_portfolio.csv | ETF持仓成分股 | 持仓明细 |
| daily.csv | A股成分股日线 | 个股行情 |
| indicators/*.json | 计算结果 | 指标值 |