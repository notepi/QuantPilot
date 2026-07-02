# QuantPilot 每日更新执行规程

本文档是给 Claude Code、Codex 或其他执行智能体看的每日运行入口。  
不要只运行报告生成命令就结束；每日更新包含“数据/报告更新”和“S2 事件智能体扫描”两部分。S2 智能体不是固定扫源脚本，而是研究判断任务：正式事件库严格入库，watchlist 承接灰度线索。

---

## 一、执行顺序

每日按以下顺序执行：

1. 读取本文件。
2. 读取 `s2/agent_task.md`。
3. 读取 `s2/output/watchlist.md`。
4. 读取最新 S1/S2/S3 报告或行情摘要，形成今日研究问题。
5. 执行 S2 事件智能体扫描。
6. 如发现符合阈值的新事件，使用 `s2.event_store.append_events()` 写入 `s2/data/*.csv`。
7. 将未达阈值但值得跟踪的线索更新到 `s2/output/watchlist.md`。
8. 无论是否新增事件，都写一份 agent run 记录到 `s2/output/agent_runs/YYYY-MM-DD.md`。
9. 运行统一日报入口。
10. 审计三个报告的数据日期和来源对齐状态。

---

## 二、S2 事件智能体扫描

事件扫描不是代码自动抓行情，而是研究判断任务。执行者必须按 `s2/agent_task.md` 做以下事情：

- 先阅读当天市场与报告线索，提出今日研究问题。
- 回看 `s2/output/watchlist.md`，判断旧线索是否升级、延续、排除或过期。
- 检查公司公告、交易所公告、监管公告、权威行业媒体。
- 根据今日行情、watchlist、会议/监管窗口自主扩展搜索方向。
- 判断是否属于 BD、临床、审批、业绩、政策风险等重要事件。
- 判断是否影响 159567 创新药 ETF 相关标的或行业预期。
- 只把有来源链接、能交叉验证、达到重要性阈值的事件写入正式事件库。
- 不得把未经验证的传闻写入事件库。

没有新增正式事件时也必须明确记录“无新增重大产业事件”，不能省略智能体扫描步骤。没有正式入库不等于没有研究输出；候选线索、排除理由和 watchlist 变化也要记录。

文件边界：

| 文件 | 职责 | 是否进入 S2 正式评分 |
| --- | --- | --- |
| `s2/data/*.csv` | 已验证、达到阈值的正式事件库 | 是 |
| `s2/output/watchlist.md` | 未达阈值或待验证的观察线索 | 否 |
| `s2/output/agent_runs/YYYY-MM-DD.md` | 当日研究过程和验证记录 | 否 |

建议运行记录路径：

```text
s2/output/agent_runs/YYYY-MM-DD.md
```

运行记录至少包含：

```markdown
# S2 Agent Run YYYY-MM-DD

## 执行结论

- 今日新增事件：0 条 / N 条
- 是否写入事件库：否 / 是
- 原因：...

## 今日研究问题

- ...

## 市场与报告线索

| 来源 | 观察 | 是否触发扩展搜索 |
|------|------|------------------|

## Watchlist 回看

| id | 线索 | 今日处理 | 原因 |
|----|------|----------|------|

## 检查范围

- 公司公告：
- 监管公告：
- 行业媒体：
- 交易所公告：

## 自主扩展搜索

| 触发原因 | 搜索方向 | 结果 |
|----------|----------|------|

## 候选事件

| 事件 | 来源 | 状态 | 判断 | 处理 |
|------|------|------|------|------|

## 写入文件

- 无 / `s2/data/bd_events.csv` 等

## Watchlist 更新

- 新增：
- 延续：
- 升级：
- 删除：

## 对今日 S2 结论的影响

- 正式评分影响：
- 观察性影响：
- 不确定性：

## 验证命令

```bash
./.venv/bin/python -m s2.generate_s2_report
```
```

---

## 三、统一日报入口

完成事件扫描后运行：

```bash
./.venv/bin/python -m s2.daily_report_flow
```

该入口会执行：

```text
wb.daily_flow
-> s2.update_market_data
-> s2.build_data_layer
-> s2.generate_s2_report
-> s3.generate_report
-> 输出日期复核
```

不要用单独的 `s2.generate_s2_report` 代替每日完整流程。

若本次只验证 S2 智能体流程，可在不刷新行情的情况下运行：

```bash
./.venv/bin/python -m s2.generate_s2_report
```

但这只能验证 S2 报告生成，不能替代完整每日更新。

---

## 四、报告审计清单

每天至少审计这三个报告：

```text
docs/daily_report.md
s2/output/reports/YYYY-MM-DD.md
s3/output/ai_style_daily_report.md
```

必须确认：

- `docs/daily_report.md` 的最新日期等于最新 S1 交易日。
- `data/indicators/YYYYMMDD.json` 存在，且 6 个 S1 指标都有 `data_date`。
- `s2/output/reports/YYYY-MM-DD.md` 的报告日期等于 `S1交易日`。
- `159567.SZ` 与 `159557.SZ` 的 `latest_date`、`common_trade_date` 对齐。
- `fund_share 最新披露日` 不晚于报告日；若滞后，报告必须明确披露。
- `s3/output/ai_style_daily_report.md` 的数据源状态链接必须指向存在的 audit 文件。
- 跨市场数据允许使用上一美股交易日，但必须由 audit 文件披露。
- `missing` 只能表示真实缺失，不能用于表示负面信号或跑输。

建议命令：

```bash
git status --short
ls -lt data/indicators | head
head -12 docs/daily_report.md
rg -n "报告日期|S1交易日|S1指标已更新到|fund_share 最新披露日|latest_date_159567|latest_date_159557|common_trade_date|数据源状态|score_status" \
  s2/output/reports/*.md s3/output/ai_style_daily_report.md
```

---

## 五、完成标准

每日更新只有在以下条件全部满足后才算完成：

- 数据更新流程已运行。
- S2 事件智能体扫描已运行。
- 有 agent run 记录。
- `s2/output/watchlist.md` 已回看并更新，或明确记录“无变化”。
- 三个报告已生成。
- 报告日期、数据日期、来源 audit 不冲突。
- 若有缺失或滞后，报告中已明确披露。
- `git status --short` 中的变更已解释清楚。

---

## 六、给执行智能体的最短指令

以后可以直接给 Claude Code 或 Codex 这句话：

```text
请按 docs/daily_update_runbook.md 执行今日 QuantPilot 日报更新和审计。不要只跑 s2.daily_report_flow；必须执行 s2/agent_task.md 的事件扫描，并留下 s2/output/agent_runs/YYYY-MM-DD.md 运行记录。
```
