# S2 产业验证模块

S2 模块独立于现有 S1 代码。S1 继续由项目原流程生成；S2 只读取本地 S1 输出、事件库和行情数据，然后按固定口径计算 S2 指标并生成独立日报。

标的角色：

- 港股观察标的：`159567.SZ` 港股创新药 ETF。
- 正式量化温度计：`589720.SH` 科创创新药 ETF，用于观察 A 股创新药资金状态。
- 港股对照标的：`159557.SZ` 港股医疗宽基参考，用于判断 159567 是否相对更强。

`589720.SH` 弱只表示 A 股科创创新药资金状态偏弱，不能直接解释成 `159567.SZ` 弱。

A 股温度计状态映射固定为：`S1_total >= 0.80` 为强，`0.60 <= S1_total < 0.80` 为中性，`S1_total < 0.60` 为弱。

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
   - 运行 `python -m s2.update_market_data`，刷新 S2 自己的 `159567/159557` HK_observation 缓存，并尝试把港股个股行情写入 `s2/data/hk_daily.csv`。
   - 读取 `docs/创新药_第一阶段_v2_claude.xlsx` 的 `第二阶段` sheet。
   - 按 Excel 的 S2-01 到 S2-05 口径、阈值、权重计算。
   - 缺数据则标记“数据缺失”，不编造。

5. 生成输出
   - 最新报告：`s2/output/s2_daily_report.md`
   - 每日归档：`s2/output/reports/YYYY-MM-DD.md`
   - 时间序列：`s2/output/s2_scores.csv`
   - 子指标历史：`s2/output/s2_item_scores.csv`
   - 子指标历史报表：`s2/output/s2_indicator_history.md`
   - 当日客观简报：`s2/output/s2_daily_brief.md`
   - 当日简报归档：`s2/output/briefs/YYYY-MM-DD.md`

6. 复核报告
   - 每项 S2 是否有依据。
   - 是否说明新增事件和沿用事件。
   - 是否说明数据缺口。
   - 是否给出 S2 产业验证等级和 S1/S2 客观组合观察。

## 指标计算

| 指标 | 本地计算方式 | 智能体输入 |
| --- | --- | --- |
| S2-01 BD落地频率 | 统计近90日重大BD笔数 / 前4个完整90日窗口单窗口均值 | 新 BD 事件 |
| S2-02 BD金额质量 | 统计近90日首付款+近期里程碑 / 去年同期90日金额；同时沉淀质量金额 | 金额、合作方、来源 |
| S2-03 龙头业绩兑现率 | 仅统计具备一致预期来源的已披露龙头中 `beat=true` 的占比 | 财报、一致预期来源 |
| S2-04 数据催化转化率 | 严格满事件后5个交易日，A股事件用真实标的跑赢589720.SH，港股事件用真实港股个股跑赢159557.SZ；159567-159557只作HK_observation观察 | 临床事件日期、标的 |
| S2-05 龙头接力强度 | 严格满事件后5个交易日，计算本地A股龙头池相对589720.SH超额收益中位数；同时沉淀10D延续和20D广度 | 事件日期、本地龙头池 |

评分映射：

- 超预期：1.0
- 符合预期：0.7
- 低于预期：0.4
- 数据缺失：0.5，并在报告中写清楚

置信度约束：

- 样本数 < 3，单项 `adjusted_score` 上限 0.65。
- 样本数 < 5，单项 `adjusted_score` 上限 0.75。
- ETF承接、港股行情缺失等替代结果只进入观察字段，不进入正式得分。
- S2-01 的 BD 事件库成熟度：过去365日事件数 < 8 为 `low`，上限 0.70；< 15 为 `medium`，上限 0.80；否则为 `high`。
- `S2_total = S2_adjusted_total`；`S2_raw_total` 只作为参考，不参与阶段判断。
- `S2_event_score = mean(S2-01, S2-02, S2-03 adjusted_score)`，只用于解释产业事件侧是否改善，并写入 `s2_scores.csv`。
- `S2_conversion_score = mean(S2-04, S2-05 adjusted_score)`，只用于解释交易转化侧是否确认，并写入 `s2_scores.csv`。
- `S2_event_score` 和 `S2_conversion_score` 是解释层，不改变五项正式指标、`S2_total` 或阶段判断。

市场验证更新规则：

- 新事件立即进入事件库，但不足 5 个交易日时只标记为待验证，不参与 `S2-04` / `S2-05` 计算。
- `s2.update_market_data` 使用 S2 自己的 citydata client，不依赖 `wb.tushare_proxy`，不修改 S1 核心代码。
- `s2.update_market_data` 刷新 `159567` 与 `159557` 两个 ETF 的观察缓存，并尝试抓取港股个股行情到 `s2/data/hk_daily.csv`；不写入 `docs/daily_report.md`。
- AkShare 不可用或接口失败时使用东方财富 K 线接口兜底；两个外部源都失败才读取旧缓存；缓存缺失则标记 `missing`，不会中断 S2 正式计算。
- HK cache 新字段为 `date,ticker,open,high,low,close,volume,amount,source,fetched_at`；旧 `trade_date/close` 缓存仍兼容读取。
- 首次切换到新缓存时，可从本地 `data/raw/fund_daily.csv` 迁移已有 ETF 历史；最近一次刷新状态简要记录在 `s2/output/hk_cache/status.txt`。
- 当日没有新增成熟样本时，`S2-04` / `S2-05` 沿用最近一次有效观测值，不因等待行情而降分。
- 沿用值在 2 个交易日内标记为 `recent`；第 3-5 个交易日标记为 `aging` 且 `adjusted_score` 上限 0.60；超过 5 个交易日后记为数据缺失，不再沿用。
- 满 5 个交易日后，样本一次性进入评分，避免第 1-5 个交易日持续漂移。
- `superseded` 事件保留为历史催化样本；只有 `invalid` 或明确退出观察窗口的事件不再参与市场验证。
- `is_duplicate=true` 的事件保留在事件库中，但不进入正式统计；预告与正式数据通过 `related_event_id` 关联。

## 事件库规则

事件只记录一次，每天读取观察窗口：

- BD：90 天
- Clinical：事件后满 5 个完整交易日再进入正式验证
- Earnings：到下一财报前
- Regulatory：30-90 天

事件状态：

- `active`
- `expired`
- `superseded`
- `invalid`

事件身份键：

```text
event_type + company + asset/period/approval_type + partner + date
```

同一事件新增可靠来源时归并到 `source_urls`，不重复新增事件。

没有新增事件时，日报必须写：

```text
今日无新增重大产业事件，产业事件分沿用当前观察窗口。
```

## 运行

```bash
python -m s2.update_market_data
python -m s2.generate_s2_report
```

输出只写入 `s2/output/`，不会覆盖 `docs/daily_report.md`。

## 历史底稿

S2 每天保留两层历史：

- `s2/output/s2_scores.csv`：按日期记录 S2 总分、S1 总分、阶段判断和缺失项。
- `s2/output/s2_item_scores.csv`：按日期和指标记录 S2-01 到 S2-05 的指标值、原始得分、调整后得分、置信度、样本数、替代口径数、来源、依据和缺失项。
- `s2/output/s2_item_scores.csv` 同时沉淀 S2 v1 扩展字段：`event_db_maturity`、`raw_bd_amount`、`quality_bd_amount`、`baseline_bd_amount`、`true_value`、`proxy_value`、`true_sample_count`、`proxy_sample_count`、`proxy_type`、`leader_excess_median_5d`、`leader_win_rate_5d`、`leader_excess_median_10d`、`leader_breadth_20d`、`pending_count`、`hk_pending_count`、`price_missing_count`、`carried_forward_from`、`stale_days`、`is_stale`、`carry_forward_type`。

港股观察层的缓存位于 `s2/output/hk_cache/159567.csv` 和 `s2/output/hk_cache/159557.csv`，历史位于 `s2/output/hk_observation_scores.csv`。它只回答 159567 最近是否强于 159557，不进入 `S2_total`。

当 HK_observation 为 `stale` 或 `missing` 时，日报和观察历史不展示收益、超额收益，也不判断 159567 强弱。

S2-04 在日报中拆成两层：`official` 只统计本地行情可得且满 5 个完整交易日的确认事件；港股临床事件若缺少港股个股行情则进入 `S2-04_hk_event_pending`；ETF 层面的 `159567 - 159557` 五日超额只进入 `HK_observation`，不污染正式分。

`s2/output/s2_indicator_history.md` 是从 `s2_item_scores.csv` 自动渲染的人读版历史报表，用来像 S1 的 `docs/daily_report.md` 一样快速回看子指标变化。

`s2/output/s2_daily_brief.md` 是当日客观摘要，不输出仓位或交易建议。
