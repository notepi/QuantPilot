# 使用指南

## 每日流程（推荐）

**收盘后执行**，一条命令跑完 S1/S2/S3 全链路：

```bash
uv run python -m s2.daily_report_flow
```

执行步骤：

| # | 模块 | 说明 |
|---|------|------|
| 1 | `wb.daily_flow` | 更新数据 → 计算指标 → 生成 S1 日报 |
| 2 | `s2.update_market_data` | 刷新港股 ETF 缓存（腾讯/东方财富兜底） |
| 3 | `s2.build_data_layer` | 构建 S2 行情、宏观、审计数据层 |
| 4 | `s2.generate_s2_report` | 生成 S2 产业验证日报 |
| 5 | `s3.generate_report` | 生成 S3 AI 风格轮动日报 |

最后自动校验：S2 报告日期 = S1 trade_date，S3 报告存在。

## 只跑 S1（快）

```bash
uv run python -m wb.daily_flow
```

三步：更新数据 → 计算指标 → 生成日报。输出 `docs/daily_report.md`。

## 分步执行

```bash
# 1. 更新数据（citydata + 东方财富份额补充）
uv run python -m wb.update_data

# 2. 计算指标（CSV → JSON，含 data_date）
uv run python -m wb.calculate_indicators

# 3. 生成 S1 日报（JSON → Markdown）
uv run python -m wb.generate_report

# 4. 生成 S2 报告
uv run python -m s2.generate_s2_report

# 5. 生成 S3 报告
uv run python -m s3.generate_report
```

## 数据对齐

**必须收盘后跑**。原因：

- 份额数据：citydata `fund_share` 滞后约 T+4，东方财富 `fund_etf_spot_em` 有当天数据
- 如果收盘前跑，东方财富给的还是昨天的份额，S1-01/S1-02 的 `data_date` 就会滞后
- 收盘后跑，东方财富给当天份额，`data_date` 与 `trade_date` 对齐

**份额滞后时的表现**：

- S1-01/S1-02 的 `data_date` 诚实地反映实际数据日期
- `docs/daily_report.md` 显示 ⚠️ 警告
- `data/raw/fund_share.csv` 的 `source` 字段标注来源

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
| `data/raw/fund_daily.csv` | ETF 日线行情（589720/159557/159567） | 价格、成交额 |
| `data/raw/fund_share.csv` | ETF 份额数据（含 source 字段） | 份额变化 |
| `data/raw/fund_portfolio.csv` | ETF 持仓成分股 | 持仓明细 |
| `data/raw/daily.csv` | A 股成分股日线 | 个股行情 |
| `data/indicators/*.json` | S1 指标计算结果（含 data_date） | 指标值 |
| `s2/output/reports/*.md` | S2 产业验证日报 | 事件驱动评分 |
| `s3/output/ai_style_daily_report.md` | S3 AI 风格日报 | 风格轮动判断 |
