# 指标库架构

**完成日期**：2026-03

## 目标

数据本地化 + 指标结果本地化

## 已实现

### 文件结构

```
data/
├── raw/           # 原始数据CSV
└── indicators/    # 指标结果JSON

wb/
├── update_data.py         # 数据抓取（新建）
├── calculate_indicators.py # 指标计算（新建）
├── data_fetcher.py        # 本地CSV读取（修改）
└── api_server.py          # 本地JSON读取（修改）
```

### 使用流程

```bash
# 1. 更新数据（接口 → CSV）
uv run python -m wb.update_data

# 2. 计算指标（CSV → JSON）
uv run python -m wb.calculate_indicators

# 3. 启动API（读取JSON）
uv run python -m wb.api_server
```

## 关键修复

- citydata proxy fund_share 忽略日期参数 → 手动过滤
- trade_date dtype 问题 → CSV读取后转为字符串
- hk_daily 接口限制 → 批量请求

## 状态

✅ 已完成