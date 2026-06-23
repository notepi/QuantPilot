、# QuantPilot 数据治理与智能体协作改造方案审计意见

**审计对象**：`docs/data_governance_plan.md`  
**审计日期**：2026-06-23  
**审计性质**：方案审计，不包含代码实施  
**审计范围**：数据日期披露、份额数据备用源、raw 层完整性、S1/S2/S3 模块边界、S2 智能体事件维护、验收与回滚设计。

---

## 一、总体审计结论

本轮修订后的 `docs/data_governance_plan.md` 已基本吸收上一轮审计意见，具备进入代码实施阶段的条件。

已确认修正项：

1. 文档标题已调整为“QuantPilot 数据治理与智能体协作改造方案”，范围说明覆盖数据治理、智能体协作、S3 拆分和日报验收。
2. “一、目标”编号已修正为连续编号。
3. 问题 1 下的两个“当前代码状态”已拆分为“数据源代码状态”和“指标结果代码状态”。
4. 方案 A 已拆分为 A1 数据日期披露与 A2 份额数据备用源。
5. A2 已补充东方财富 fallback 的触发约束、schema 兼容策略和来源追溯要求。
6. 回滚方案已补充实施前 `git status --short`、`git diff --stat` 检查，以及代码改造与数据刷新分离原则。

审计结论：**通过，可进入实施阶段**。

仍建议在实施时特别关注两类执行风险：`fund_share.csv` schema 变更的兼容性，以及 dirty worktree 下代码变更与数据刷新文件的边界管理。

---

## 二、审计通过项

### 1. 文档定位通过

文档已从狭义“数据治理方案”调整为“数据治理与智能体协作改造方案”，并明确包含：

- 数据治理整改
- S1/S2/S3 模块边界调整
- S2 智能体事件维护任务设计
- S3 AI 风格报告拆分
- 日报流程与验收机制

第九至十一章可保留在同一文档中，不再建议拆分。

### 2. 数据日期披露方案通过

方案 A1 明确修改：

- `wb/indicators/base.py`
- `wb/indicators/s1_01_capital_flow.py`
- `wb/indicators/s1_02_share_change.py`
- `wb/generate_report.py`

目标是让报告日期与实际数据日期可区分。该方案方向正确。

### 3. 份额备用源方案通过

方案 A2 已明确：

- 主源为 citydata `fund_share`
- 备用源为东方财富 `fund_etf_spot_em`
- fallback 只补最新一条，不做历史区间回填
- 东方财富返回日期必须位于 `[start_date, end_date]`
- 返回日期必须大于 citydata 最新日期才追加
- 同日期数据覆盖或跳过，避免重复

该方案已具备实施可操作性。

### 4. raw 层补齐方案通过

将 `159567.SZ` 加入 `wb/update_data.py` 的 fund_daily 更新列表，能解决 raw 层 `fund_daily.csv` 中 159567 行情滞后的审计断点。该方案通过。

### 5. S3 兼容迁移方案通过

方案明确保留 `s2` 兼容层，避免旧 import 立即失效。验收命令使用：

```bash
uv run python -m s3.generate_report
uv run pytest s2/tests/
```

该策略符合低风险迁移原则。

### 6. 回滚与实施前检查通过

计划已补充：

```bash
git status --short
git diff --stat
```

并要求代码改造与数据刷新文件分开提交。该项满足实施前审计要求。

---

## 三、实施关注点

### 关注点 1：`fund_share.csv` schema 变更

**风险等级**：中

方案 A2 计划在 `fund_share.csv` 中增加 `source` 字段，旧记录默认填 `citydata_fund_share`。实施时需要确保：

1. 旧 CSV 读入后能补齐 `source` 列。
2. 新旧数据 concat 后列顺序稳定。
3. `DataFetcher.get_fund_share()` 不依赖 `source` 字段计算。
4. `append_to_file()` 去重仍以 `ts_code`、`trade_date` 为主键，不因 `source` 变化产生重复行。

建议实施后额外验证：

```bash
head -1 data/raw/fund_share.csv
uv run python -m wb.calculate_indicators 20260622
```

### 关注点 2：东方财富 fallback 的数据日期

**风险等级**：中

东方财富 `fund_etf_spot_em` 只提供最新份额，不提供历史区间。实施时要确保它只作为“当天或最新可得日补充”，不能被误用为历史份额源。

验收重点：

- 东方财富日期不在 `[start_date, end_date]` 时不写入。
- 东方财富日期不大于 citydata 最新日期时不追加。
- fallback 写入后，S1-01/S1-02 的 `data_date` 与实际使用数据一致。

### 关注点 3：dirty worktree 下的提交边界

**风险等级**：中

当前项目已有较多数据与输出文件变更。实施时应避免把本次代码改造与既有数据刷新混在一起。

建议：

- 先记录实施前 `git status --short`。
- 本次代码变更优先限制在 `wb/`、`docs/`、必要的 `s3/`/`s2/` 兼容层。
- 数据刷新文件单独归档或单独提交。
- 不要用“一次提交全部当前状态”的方式掩盖变更来源。

### 关注点 4：S2 事件状态日期需标注为快照

**风险等级**：低

第九至十一章中事件库滞后天数基于 2026-06-22 测试状态。后续如果文档继续维护，建议标注为“截至 2026-06-22 快照”，避免未来读者把滞后天数当成实时状态。

---

## 四、实施准入清单

进入代码实施前，建议确认：

1. `git status --short` 已记录。
2. 代码改造与数据刷新文件会分开处理。
3. `fund_share.csv` 的 `source` 字段兼容策略已在实现中覆盖。
4. 东方财富 fallback 只补最新一条，并严格过滤日期。
5. S3 拆分采用兼容迁移，不删除原 `s2` 调用入口。

---

## 五、建议实施顺序

建议按以下顺序推进：

1. **S1 数据日期披露**
   - 增加 `data_date`
   - 日报显示报告日期与数据日期

2. **份额数据备用源**
   - 新增东方财富 fallback
   - 处理 `fund_share.csv` source 字段兼容

3. **159567.SZ raw 层更新**
   - 将 `159567.SZ` 加入 fund_daily 更新列表
   - 修正 `docs/indicators.md` 中 S1-05 数据源

4. **S3 兼容式拆分**
   - 新建 `s3`
   - 保留 `s2` wrapper
   - 跑 S2 相关测试

5. **数据血缘与 S2 智能体维护**
   - 扩展 `source_name`、`source_file`、`data_status`
   - 落地 S2 智能体事件维护流程

---

## 六、最终审计意见

本版 `docs/data_governance_plan.md` 已达到项目改造实施前方案标准。

最终审计意见：**通过，可实施**。

实施过程中需重点控制 `fund_share.csv` schema 兼容、东方财富 fallback 日期过滤、以及代码变更与数据刷新文件的提交边界。
