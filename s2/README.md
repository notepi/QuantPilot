# S2 产业验证模块

S2 模块独立于现有 S1 代码。S1 继续由项目原流程生成；S2 只读取本地 S1 输出、事件库和行情数据，然后按固定口径计算 S2 指标并生成独立日报。

## 每日工作流

1. 检查本地 S1 是否更新
   - 读取 `data/indicators/*.json`。
   - 使用最新 S1 交易日和最近 10 个交易日。
   - 如果 S1 未更新，S2 日报必须写明。

2. 智能体联网查新事件
   - 搜索最近 1-3 天新增 BD、临床、业绩、审批事件。
   - 不重复写入已有事件。
   - 新事件必须有来源链接。

3. 更新事件库
   - 新 BD 写入 `s2/data/bd_events.csv`。
   - 新临床写入 `s2/data/clinical_events.csv`。
   - 新业绩写入 `s2/data/earnings_events.csv`。
   - 新审批写入 `s2/data/regulatory_events.csv`。

4. 本地计算 S2
   - 读取 `docs/创新药_第一阶段_v2_claude.xlsx` 的 `第二阶段` sheet。
   - 按 Excel 的 S2-01 到 S2-05 口径、阈值、权重计算。
   - 缺数据则标记“数据缺失”，不编造。

5. 生成输出
   - 最新报告：`s2/output/s2_daily_report.md`
   - 每日归档：`s2/output/reports/YYYY-MM-DD.md`
   - 时间序列：`s2/output/s2_scores.csv`
   - 子指标历史：`s2/output/s2_item_scores.csv`
   - 子指标历史报表：`s2/output/s2_indicator_history.md`

6. 复核报告
   - 每项 S2 是否有依据。
   - 是否说明新增事件和沿用事件。
   - 是否说明数据缺口。
   - 是否给出阶段判断和操作倾向。

## 指标计算

| 指标 | 本地计算方式 | 智能体输入 |
| --- | --- | --- |
| S2-01 BD落地频率 | 统计事件库近90日重大BD笔数 / 过去4个季度单季平均笔数 | 新 BD 事件 |
| S2-02 BD金额质量 | 统计近90日首付款+近期里程碑；同时沉淀质量金额 | 金额、合作方、来源 |
| S2-03 龙头业绩兑现率 | 统计已披露龙头中 beat=true 的占比 | 财报/预告/一致预期判断 |
| S2-04 数据催化转化率 | 事件后5日，真实标的样本与ETF承接替代样本的加权转化率 | 临床事件日期、标的 |
| S2-05 龙头接力强度 | 事件后5日，重点龙头相对主题ETF超额收益中位数；同时沉淀10D延续和20D广度 | 事件日期、龙头标的 |

评分映射：

- 超预期：1.0
- 符合预期：0.7
- 低于预期：0.4
- 数据缺失：0.5，并在报告中写清楚

置信度约束：

- 样本数 < 3，单项 `adjusted_score` 上限 0.65。
- 样本数 < 5，单项 `adjusted_score` 上限 0.75。
- 使用替代口径，单项 `adjusted_score` 上限 0.70。
- S2-04 仅有替代样本、没有真实标的样本时，上限 0.60。
- S2-01 的 BD 事件库成熟度：过去365日事件数 < 8 为 `low`，上限 0.70；< 15 为 `medium`，上限 0.80；否则为 `high`。
- `S2_total = S2_adjusted_total`；`S2_raw_total` 只作为参考，不参与阶段判断。

## 事件库规则

事件只记录一次，每天读取观察窗口：

- BD：90 天
- Clinical：事件后 5-20 个交易日
- Earnings：到下一财报前
- Regulatory：30-90 天

事件状态：

- `active`
- `expired`
- `superseded`
- `invalid`

去重键：

```text
date + company + asset + source_url
```

没有新增事件时，日报必须写：

```text
今日无新增重大产业事件，产业事件分沿用当前观察窗口。
```

## 运行

```bash
python -m s2.generate_s2_report
```

输出只写入 `s2/output/`，不会覆盖 `docs/daily_report.md`。

## 历史底稿

S2 每天保留两层历史：

- `s2/output/s2_scores.csv`：按日期记录 S2 总分、S1 总分、阶段判断和缺失项。
- `s2/output/s2_item_scores.csv`：按日期和指标记录 S2-01 到 S2-05 的指标值、原始得分、调整后得分、置信度、样本数、替代口径数、来源、依据和缺失项。
- `s2/output/s2_item_scores.csv` 同时沉淀 S2 v1 扩展字段：`event_db_maturity`、`raw_bd_amount`、`quality_bd_amount`、`true_value`、`proxy_value`、`true_sample_count`、`proxy_sample_count`、`proxy_type`、`leader_excess_median_5d`、`leader_win_rate_5d`、`leader_excess_median_10d`、`leader_breadth_20d`。

`s2/output/s2_indicator_history.md` 是从 `s2_item_scores.csv` 自动渲染的人读版历史报表，用来像 S1 的 `docs/daily_report.md` 一样快速回看子指标变化。
