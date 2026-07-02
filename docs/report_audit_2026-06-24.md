# QuantPilot 2026-06-24 日报审计报告

**审计日期**：2026-06-24
**审计范围**：
- `docs/daily_report.md`
- `s2/output/reports/2026-06-24.md`
- `s2/output/s2_daily_report.md`
- `s3/output/ai_style_daily_report.md`
- `s2/output/agent_runs/2026-06-24.md`

## 一、审计结论

本次审计结论为：**有条件通过，已修复 S3 展示层问题后通过**。

S1 与 S2 报告的数据日期、核心指标、S1 贡献拆分、A/H 同日观察和事件留痕一致；S3 底层验证数据正确，但初始生成的 AI 风格日报将有效的 `bio_vs_ai=+3.83%` 误显示为“未确认”。该问题已在生成逻辑中修复，并已重生成 S3 日报。

## 二、关键数据复核

| 项目 | 审计结果 |
| --- | --- |
| S1 数据日期 | `2026-06-24`，与报告日期一致 |
| S2 报告日期 | `2026-06-24` |
| S2 S1交易日 | `20260624` |
| S3 报告日期 | `2026-06-24` |
| S3 A股/港股数据日期 | `20260624` |
| S3 对应美股收盘日期 | `20260623` |
| S3 score_status | `descriptive_only` |
| S3 right_side_score | `51.61` |
| S3 context_action_hint | `HOLD_OBSERVE` |

### S1 指标与总分

`data/indicators/20260624.json` 与 `docs/daily_report.md` 对齐：

| 指标 | 值 | 状态 |
| --- | ---: | --- |
| S1-01 | `41.67%` | 符合预期 |
| S1-02 | `-1.86%` | 低于预期 |
| S1-03 | `+8.16%` | 超预期 |
| S1-04 | `1.43x` | 符合预期 |
| S1-05 | `73.33%` | 超预期 |
| S1-06 | `+3.96%` | 符合预期 |
| total_score | `0.748`，报告展示 `0.75` | 符合预期 |

### S2 贡献拆分

`s2/output/reports/2026-06-24.md` 与 `s2/output/s2_daily_report.md` 一致：

| 贡献项 | 值 |
| --- | ---: |
| flow_score_contribution | `0.226` |
| price_strength_contribution | `0.200` |
| volume_contribution | `0.098` |
| breadth_contribution | `0.140` |
| leader_contribution | `0.084` |

## 三、A/H 与 S3 复核

按 `data/processed/market_daily.csv` 复算：

| 标的 | 20260623 close | 20260624 close | 1日收益 |
| --- | ---: | ---: | ---: |
| 159567.SZ | `0.582` | `0.598` | `+2.75%` |
| 159557.SZ | `1.165` | `1.199` | `+2.92%` |
| 589720.SH | `0.799` | `0.813` | `+1.75%` |

复算结果：

| 指标 | 值 | 报告状态 |
| --- | ---: | --- |
| 159567 vs 159557 1日超额 | `-0.17%` | S2/S3 一致 |
| 159567 vs 159557 5日超额 | `-1.28%` | S2 一致 |
| 159567 vs AI_CORE 1日超额 | `+3.83%` | 已修复为 S3 一致 |
| 159567 vs TECH_GROWTH_CORE 1日超额 | `-0.86%` | S3 一致 |

## 四、发现与修复

### 发现 1：S3 `biotech_vs_ai` 展示误报

**严重度**：中

**现象**：底层验证报告 `s3/output/ai_biotech_validation_report.md` 显示 `创新药相对AI_CORE：3.83%`，但 `s3/output/ai_style_daily_report.md` 初始显示 `biotech_vs_ai: 未确认`。

**根因**：`s3/generate_report.py` 从“最强支持/反对证据”文本中抽取展示值；当有效数值没有进入证据列表时，日报误显示为“未确认”。

**修复**：
- `s3/validation.py`：在 `ValidationResult` 中新增当日结构化字段，包括 `bio_vs_health`、`bio_vs_ai`、`bio_vs_tech`。
- `s3/generate_report.py`：S3 日报直接使用结构化字段渲染相对收益，不再从证据文本反推正式数值。
- `s3/tests/test_ai_biotech_validation.py`：新增回归测试，覆盖“数值有效但不在证据列表中”的场景。
- 已重新生成 `s3/output/ai_style_daily_report.md` 与 `s3/output/ai_style_reports/2026-06-24.md`。

修复后 S3 日报显示：

```text
biotech_vs_health: 159567跑输159557 -0.17%
biotech_vs_ai: 159567跑赢AI_CORE 3.83%
biotech_vs_tech: 159567跑输TECH_GROWTH_CORE -0.86%
```

## 五、智能体留痕审计

`s2/output/agent_runs/2026-06-24.md` 存在，记录如下：

| 项目 | 结果 |
| --- | --- |
| 今日新增事件 | 无新增重大产业事件 |
| 检查范围 | Tier 1 公司 IR、NMPA CDE、FierceBiotech、Endpoints、通用新闻搜索 |
| 写入事件库 | 5 类事件库均为 0 条新增 |
| 报告验证命令 | `uv run python -m s2.generate_s2_report` |

审计判断：本地留痕与 S2 报告一致，满足“无新增也必须留痕”的流程要求。本报告未替代一次新的人工/联网全量事件扫描。

## 六、验证命令

```bash
./.venv/bin/python -m pytest s2/tests s3/tests
```

结果：

```text
36 passed, 1 warning
```

警告为测试中 pandas dtype 兼容性提示，不影响本次报告生成和审计结论。

## 七、最终判断

1. S1/S2 数据日期严格对齐，核心数值通过复算。
2. S2 智能体留痕存在，报告与留痕一致。
3. S3 初始报告存在展示层错误，已修复并重生成。
4. 修复后，三份日报可作为 `2026-06-24` 的项目输出使用。
