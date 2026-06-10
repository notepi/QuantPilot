# S2 产业验证模块

S2 是独立的产业验证日报模块。它不修改 S1 原始计算，也不覆盖
`docs/daily_report.md`。S2 只读取本地 S1 输出、S2 事件库、行情数据和
审计结果，然后生成独立的 S2 日报、简报和历史底稿。

当前 S2 报告定位为：

```text
数据治理后试运行版，行情层已接入 audit，但部分解释标签仍在迭代校验。
```

## 标的角色

| 标的 | 角色 | 说明 |
| --- | --- | --- |
| `159567.SZ` | 港股观察标的 | 港股创新药 ETF，观察实际持仓方向 |
| `159557.SZ` | 港股宽基对照 | 判断 159567 是否强于港股医疗宽基 |
| `589720.SH` | A 股温度计 | 科创创新药 ETF，只代表 A 股创新药资金状态 |

固定原则：

- `159567.SZ` 是港股观察标的，不进入 S2 正式分。
- `159557.SZ` 是港股医疗宽基对照。
- `589720.SH` 是 A 股温度计，不能直接解释成 `159567.SZ` 强弱。
- S2 不输出买卖建议。
- 缺失数据必须保留 `missing` 或明确写出 `data_quality`，不得编造。
- 产业事件分和交易转化分必须分开。

## 每日更新总流程

推荐顺序如下：

```bash
# 1. 确认 S1 已由原流程更新
ls -lt data/indicators | head

# 2. 更新 S2 的 HK_observation 缓存和港股个股行情
./.venv/bin/python -m s2.update_market_data

# 3. 构建 S2 数据层：行情、宏观、audit、S2-04交易样本、质量报告
./.venv/bin/python -m s2.build_data_layer

# 4. 如 S1 状态展示文件滞后，先同步 s2/output/s1_update_status.json
#    该文件只影响 S2 报告展示，不影响 S1 原始计算。

# 5. 生成 S2 日报和简报
./.venv/bin/python -m s2.generate_s2_report

# 6. 复核
./.venv/bin/python -m pytest s2/tests
```

只运行 `s2.generate_s2_report` 不会刷新行情，也不会重建 audit。当天更新
日报前，必须先确认数据层已经更新到报告日。

## S1 前置检查

S2 读取 `data/indicators/*.json` 中最新的 S1 指标文件。

必须确认：

- 最新 S1 文件日期等于当天交易日，例如 `data/indicators/20260610.json`。
- `trade_date` 与报告中 `S1交易日` 一致。
- `s2/output/s1_update_status.json` 的展示文字不要停留在旧日期。

`s2/output/s1_update_status.json` 只用于 S2 报告展示：

```json
{
  "attempted_at": "2026-06-10T20:03:00",
  "success": true,
  "partial_failure": false,
  "message": "S1指标已更新到 20260610；本地 589720.SH 行情最新交易日为 20260610。"
}
```

该文件不是 S1 原始计算结果。若它滞后，只能同步展示状态，不能据此改 S1
指标值。

## 事件库更新

事件库位于 `s2/data/`：

| 文件 | 内容 |
| --- | --- |
| `bd_events.csv` | BD 事件 |
| `clinical_events.csv` | 临床/ASCO/数据读出事件 |
| `earnings_events.csv` | 财报客观改善事件 |
| `earnings_consensus.csv` | 一致预期验证 |
| `regulatory_events.csv` | 审批/监管事件 |
| `policy_risk_events.csv` | 政策风险层 |
| `commercialization_metrics.csv` | 商业化兑现质量 |
| `macro_market_snapshot.csv` | 宏观资金层快照 |

事件只记录一次，同一事件新增可靠来源时归并到 `source_urls`，不重复新增。

事件身份键：

```text
event_type + company + asset/period/approval_type + partner + date
```

事件状态：

```text
active / expired / superseded / invalid
```

规则：

- `is_duplicate=true` 的事件保留在事件明细中，但不进入正式统计。
- `superseded` 事件可保留为历史催化样本。
- `invalid` 或明确退出观察窗口的事件不再参与市场验证。
- 新事件必须有来源链接。
- 没有新增事件时，日报必须写：

```text
今日无新增重大产业事件，产业事件分沿用当前观察窗口。
```

## 行情更新层

### `s2.update_market_data`

用途：

- 刷新 `159567.SZ` 和 `159557.SZ` 的 HK_observation 缓存。
- 更新港股个股行情到 `s2/data/hk_daily.csv`。
- 记录最近一次刷新状态到 `s2/output/hk_cache/status.txt`。

数据源：

- HK_observation ETF：`citydata_fund_daily` 优先，腾讯 `fqkline` 兜底。
- 港股个股：东方财富/AkShare 优先，腾讯港股 K 线兜底。

输出：

| 文件 | 说明 |
| --- | --- |
| `s2/output/hk_cache/159567.csv` | 159567 缓存 |
| `s2/output/hk_cache/159557.csv` | 159557 缓存 |
| `s2/output/hk_cache/status.txt` | 本次刷新状态 |
| `s2/data/hk_daily.csv` | 港股个股行情 |

HK cache 字段：

```text
date,ticker,open,high,low,close,volume,amount,source,fetched_at
```

旧 `trade_date/close` 缓存仍兼容读取。

### `s2.build_data_layer`

这是推荐的完整数据层入口。

它会执行：

1. `build_market_daily()`
   - 抓取 A 股个股、ETF、港股个股行情。
   - 写入 `data/processed/market_daily.csv`。
2. `build_macro_market_daily()`
   - 抓取海外 ETF/指数/宏观行情。
   - 写入 `data/processed/macro_market_daily.csv`。
3. `refresh_market_data_audit()`
   - 生成 `s2/output/data_audit/market_data_audit.csv`。
4. `build_clinical_trade_returns()`
   - 根据 audit 结果计算 S2-04 事件后收益。
   - 写入 `s2/data/clinical_trade_returns.csv`。
5. 复制事件/财务/政策数据到 `data/processed/`。
6. 生成 `reports/data_quality_report.md`。

### A 股数据源细节

A 股个股现在的链路是：

```text
AkShare stock_zh_a_hist
    成功且最新日期到报告日 -> 使用 AkShare
    失败或最新日期滞后 -> citydata 长区间 daily
        若长区间 daily 仍未到报告日 -> citydata trade_date=报告日 单日补拉
```

这个单日补拉很重要。实际遇到过：

- citydata 长区间查询只返回到 `20260609`。
- 但 `pro.daily(ts_code=..., trade_date='20260610')` 有当天数据。

因此 A 股个股不能只依赖长区间查询结果判断 `stale`。

### ETF 数据源细节

ETF 链路：

```text
AkShare fund_etf_hist_em
    失败 -> 对 159567/159557/512010/512170 使用腾讯 fqkline 兜底
    再失败 -> citydata fund_daily
```

`159567.SZ`、`159557.SZ`、`589720.SH` 不再检查废弃的
`data/raw/fund_daily.csv` 作为 active source。

## 行情审计层

审计文件：

```text
s2/output/data_audit/market_data_audit.csv
```

关键字段：

| 字段 | 含义 |
| --- | --- |
| `expected_report_date` | 报告要求日期 |
| `raw_latest_date` | raw 层最新日期 |
| `cache_latest_date` | HK cache 最新日期 |
| `processed_latest_date` | processed 层最新日期 |
| `final_latest_date` | 最终可用日期 |
| `final_source` | 最终采用的数据层 |
| `final_source_reason` | 采用原因 |
| `fetched_at` | 抓取时间 |
| `source_conflict` | 活跃数据源日期是否冲突 |
| `stability_check_status` | 关键标的双抓稳定性 |
| `data_quality` | `latest_valid` / `stale` / `source_conflict` / `unstable_source` 等 |
| `can_use_for_latest_signal` | 是否允许进入 latest 判断和 S2-04 |
| `reason` | 阻断原因 |

审计规则：

- `can_use_for_latest_signal=true` 才能进入 latest 判断。
- `can_use_for_latest_signal=false` 的标的不得进入 S2-04 正式样本。
- `source_conflict`、`stale`、`unstable_source` 必须在报告中披露。
- `159567.SZ` 与 `159557.SZ` 日期不同步时，HK_observation 不得写成
  `latest_valid`。

快速复核命令：

```bash
./.venv/bin/python - <<'PY'
import csv
rows=list(csv.DictReader(open('s2/output/data_audit/market_data_audit.csv')))
blocked=[r for r in rows if r.get('can_use_for_latest_signal')!='true']
unstable=[r for r in rows if r.get('data_quality')=='unstable_source']
print('audited_symbols', len(rows))
print('blocked_count', len(blocked))
print('unstable_count', len(unstable))
print('blocked_symbols', ','.join(r['symbol'] for r in blocked) or 'none')
PY
```

不要用下面这种方式判断 blocked 数量：

```bash
grep ",false," s2/output/data_audit/market_data_audit.csv | wc -l
```

因为它会把 `source_conflict=false` 这类正常字段也算进去。

## S2 指标口径

| 指标 | 当前口径 |
| --- | --- |
| S2-01 BD落地频率 | 近 90 日重大 BD 笔数 / 前 4 个完整 90 日窗口单窗口均值 |
| S2-02 BD金额质量 | 近 90 日首付款+近期里程碑 / 去年同期 90 日金额；同时沉淀质量金额 |
| S2-03a 财报客观改善 | 只判断同比、利润改善、亏损收窄、现金流/经营改善等客观项 |
| S2-03b 一致预期验证 | 必须有可靠一致预期来源，判断 beat / miss |
| S2-04 数据催化转化率 | 满事件后 5 个完整交易日，真实标的跑赢对应基准 |
| S2-05 龙头接力强度 | 核心催化后 A 股龙头池相对 589720.SH 的 5 日中位超额收益 |
| S2-06 商业化兑现质量 | 只做解释层，不进入 S2_total，不替代 S2-03 |

评分映射：

```text
超预期 = 1.0
符合预期 = 0.7
低于预期 = 0.4
数据缺失 = 0.5，并在报告中写清楚
```

置信度约束：

- 样本数 < 3，单项 `adjusted_score` 上限 0.65。
- 样本数 < 5，单项 `adjusted_score` 上限 0.75。
- S2-03a 样本不足 3 个时，不得写“超预期”，显示
  `positive_low_sample`。
- S2-03b 没有可靠一致预期来源时，必须是 `missing`，不得用同比增长
  冒充超一致预期。
- S2-06 覆盖率达到最低评分线但字段完整度低或存在媒体来源时，显示
  `scorable_low_confidence`。

解释层：

```text
S2_event_score = mean(S2-01, S2-02, S2-03a, S2-03b adjusted_score)
S2_conversion_score = mean(S2-04, S2-05 adjusted_score)
```

这两个分数只用于解释产业事件侧和交易转化侧，不改变正式 S2 分。

S2_conversion 状态：

```text
<0.45      = weak
0.45-0.60  = recovering_not_confirmed
>=0.60     = confirmed_improving
>=0.70     = strong_confirmed
```

## S2-04 交易样本规则

S2-04 只统计满 5 个完整交易日且 audit 通过的样本。

基准：

- A 股事件：真实 A 股标的 vs `589720.SH`。
- 港股事件：真实港股个股 vs `159557.SZ`。
- `159567.SZ - 159557.SZ` 只进入 HK_observation，不进入 S2-04 正式分。

交易样本 ID：

```text
trade_sample_id = stock_code + event_date + benchmark_code + window_days
```

去重规则：

- 同一 `trade_sample_id` 下多个临床项目事件，只保留一个正式交易样本计分。
- 项目级事件仍保留在事件明细中，不删除。
- `raw_mature_event_count`、`deduped_trade_sample_count`、`success_count`、
  `success_rate` 必须同时输出。
- `deduped_trade_sample_count >= 3` 但 `success_rate = 0` 时，报告必须写：

```text
样本数量满足，但交易转化失败。
```

S2-04 明细表必须包含 audit 字段：

```text
stock_audit_status
benchmark_audit_status
stock_data_quality
benchmark_data_quality
stock_can_use_for_latest_signal
benchmark_can_use_for_latest_signal
```

若某标的 audit blocked，事件明细保留，但不得进入去重正式分。

## HK_observation 规则

HK_observation 只回答：

```text
159567.SZ 是否强于 159557.SZ
```

它不进入 S2_total，也不改变 `adjusted_score`。

必须输出：

```text
latest_date_159567
latest_date_159557
common_trade_date
report_trade_date
lag_days_159567
lag_days_159557
calendar_lag_days
trading_lag_days
report_day_price_available_externally
local_fetch_failed
data_fetch_failed
```

若 159567 与 159557 最新日期不一致：

- `HK_observation_status` 不得为 `latest_valid`。
- 只能使用 `common_trade_date` 计算历史 5 日超额。
- 不得更新连续跑赢/跑输天数。
- 不得把历史共同日期数据写成 latest 判断。

若报告日外部行情已有、但本地未抓到：

```text
local_fetch_failed=true
HK_observation_status=data_fetch_failed
```

## S1 解释映射

A 股温度计状态：

```text
S1_total >= 0.80        = 强
0.60 <= S1_total < 0.80 = 中性
S1_total < 0.60         = 弱
```

S1 广度：

```text
S1-05 < 40% = weak_breadth
S1-05 < 20% = weak_breadth_repair
S1-05 < 10% = breadth_collapse
```

如果 `S1_total` 达到符合预期，但 `S1-03`、`S1-04`、`S1-05` 弱，报告
不能写成“全面确认”，只能写：

```text
S1/S2总分达到符合预期，但关键交易确认项仍未达标。
```

## Policy_Risk_Layer

文件：

```text
s2/data/policy_risk_events.csv
```

字段：

```text
event_name,event_date,region,affected_chain,risk_direction,severity,status,
affected_symbols,source_url,last_checked_date,explanation
```

规则：

- BIOSECURE、BINSA 等进入该层。
- 不进入 S2_event_score。
- 只进入 final_view 解释和反证层。
- 风险升高时，反证层提示：

```text
BD出海估值折价风险
港股创新药风险偏好压制
```

## Macro_Risk_Layer

文件：

```text
s2/data/macro_market_snapshot.csv
data/processed/macro_market_daily.csv
```

核心字段：

```text
QQQ, SOXX/SMH, XBI, IBB, XLV, XLP, XLU, HSTECH, 159557, 159567
```

输出状态：

```text
risk_off_defensive
ai_crowding_unwind
biotech_relative_strength
hk_innovation_vs_health
```

若核心字段缺失超过 50%：

```text
macro_layer_status = insufficient_data
macro_risk_state = 不可判定
```

Macro_Risk_Layer 不进入 S2 正式分，只解释交易转化强弱。

## 生成输出

`s2.generate_s2_report` 会写：

| 文件 | 说明 |
| --- | --- |
| `s2/output/reports/YYYY-MM-DD.md` | 当日 S2 日报归档 |
| `s2/output/s2_daily_report.md` | 最新 S2 日报镜像 |
| `s2/output/briefs/YYYY-MM-DD.md` | 当日 S2 简报归档 |
| `s2/output/s2_daily_brief.md` | 最新 S2 简报镜像 |
| `s2/output/s2_scores.csv` | S2 总分历史 |
| `s2/output/s2_item_scores.csv` | S2 子指标历史 |
| `s2/output/hk_observation_scores.csv` | HK_observation 历史 |
| `s2/output/s2_indicator_history.md` | 人读版子指标历史 |

不会覆盖：

```text
docs/daily_report.md
docs/indicators.md
```

## 日报复核清单

生成后必须至少检查：

```bash
rg -n "报告日期|S1交易日|S1-05|s1_breadth_state|S2-03a|S2-03b|S2-04|success_rate|HK_observation|final_view_code|S2-06_status" s2/output/reports/YYYY-MM-DD.md
```

并确认：

- 报告日期是今天。
- S1 交易日是最新交易日。
- `market_data_audit.csv` 没有非预期 blocked；若有，报告必须披露。
- S2-04 样本表有 audit 字段。
- S2-03a 不用“小样本客观改善”冒充“超预期”。
- S2-03b 没有一致预期时保持 missing。
- S2-06 低完整度或媒体来源时显示 `scorable_low_confidence`。
- final_view 不输出买卖建议。

推荐最终验证：

```bash
./.venv/bin/python -m pytest s2/tests
```
