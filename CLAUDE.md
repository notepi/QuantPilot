# 创新药投资阶段评价量化系统

## 背景

量化评价创新药ETF投资阶段。
- 标的: 589720.SH
- 基准: 159557.SZ
- 当前阶段: 第一阶段（预期重定价）

## 协作流程

严格按以下顺序执行：
1. 用户定任务
2. Claude 做 plan → 写入 `.claude/plans/active/`
3. 用户确认 plan
4. Claude 执行
5. 测试验证
6. **用户确认测试通过后**，Claude 才能修改 CLAUDE.md
7. plan 归档到 `.claude/plans/archive/`

## 操作

见 [docs/usage.md](docs/usage.md)

### 每日流程

**收盘后执行**（确保份额数据对齐）：

```bash
uv run python -m s2.daily_report_flow
```

按顺序执行 5 步，最后自动校验 S1/S2/S3 日期对齐：

1. `wb.daily_flow` — 更新 S1 数据、计算指标、生成 S1 日报
2. `s2.update_market_data` — 刷新港股 ETF 缓存
3. `s2.build_data_layer` — 构建 S2 行情/宏观/审计数据层
4. `s2.generate_s2_report` — 生成 S2 产业验证日报
5. `s3.generate_report` — 生成 S3 AI 风格日报

**只跑 S1（快）**：

```bash
uv run python -m wb.daily_flow
```

### 数据对齐规则

| 规则 | 说明 |
|------|------|
| 收盘后跑 | 东方财富份额是实时的，必须当天收盘后跑才能拿到当天份额，否则 data_date 会滞后 |
| 份额滞后时诚实标注 | S1-01/S1-02 的 `data_date` 反映实际数据日期，滞后时日报显示⚠️警告 |
| fund_share.csv 含 source 字段 | `citydata_fund_share` = 历史数据，`eastmoney_fund_etf_spot_em` = 当天补充 |
| 159567.SZ 已纳入 raw 更新 | `update_fund_daily_incremental()` 包含 589720/159557/159567 三只标的 |

## 数据接口

统一使用 citydata 代理，配置 `.env`:
```
CITYDATA_TOKEN=xxx
```

## 模块结构

| 模块 | 职责 | 入口 | 是否需要智能体 |
|------|------|------|---------------|
| S1 | 资金面观察 | `wb.daily_flow` | 否（代码计算） |
| S2 | 产业验证 | `s2.generate_s2_report` | 是（事件收集） |
| S3 | AI风格轮动 | `s3.generate_report` | 否（代码计算） |

**S1 → S2/S3 依赖**：S2 和 S3 都读取 S1 的 `data/indicators/*.json`，但 S2 与 S3 之间无直接依赖。

**数据日期披露**：S1-01/S1-02 的 `IndicatorResult` 包含 `data_date` 字段，当数据日期与报告日期不一致时在日报中显示警告。

**份额数据备用源**：`wb/update_data.py` 的 `fetch_fund_share()` 支持 citydata（历史）→ 东方财富（当天）多源降级。

## 文档索引

- docs/file_structure.md - 项目文件目录结构
- docs/usage.md - 命令使用指南（每日流程、回测、API、界面）
- docs/indicators.md - 指标定义与阈值（S1-01~S1-06 口径说明）
- docs/daily_report.md - 指标日报（横轴指标，纵轴日期）
- docs/dashboard_prd.md - 可视化界面PRD（5模块设计）
- docs/data_governance_plan.md - 数据治理方案（已实施）
- docs/data_governance_audit.md - 数据治理审计
- docs/创新药_第一阶段_v2_claude.xlsx - 指标详细定义（业务口径）
- s3/README.md - S3 AI风格轮动模块说明
- .claude/plans/archive/ - 历史开发计划