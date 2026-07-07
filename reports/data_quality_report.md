# S2 数据质量报告

**生成时间**: 2026-07-07T17:07:20

## 数据分工

- 代码自动抓取：A股股票、ETF、港股个股、海外ETF/指数/宏观行情、事件后收益计算、market_data_audit。
- 需要人工/智能体查证：BD事件、临床事件、审批事件、公司财务字段、商业化兑现、一致预期、政策风险事件。
- 本阶段不生成日报；未过审计的数据不得进入 latest 判断、S2-04、Macro_Risk_Layer 或 final_view。

## 行情审计

- audited_symbols=31
- can_use_for_latest_signal=false：0
- unstable_source：0
- blocked_symbols：none
- unstable_symbols：none

## 表级质量

| 文件 | 行数 | missing_ratio | source_status分布 | fetched_at覆盖率 |
| --- | ---: | ---: | --- | ---: |
| data/processed/market_daily.csv | 14989 | 7.46% | success:14989 | 100.00% |
| data/processed/macro_market_daily.csv | 4504 | 8.61% | failed:2；success:4502 | 100.00% |
| s2/output/data_audit/market_data_audit.csv | 31 | 26.93% | missing:31 | 100.00% |
| s2/data/clinical_trade_returns.csv | 10 | 1.05% | missing:10 | 0.00% |
| data/processed/company_financials.csv | 6 | 51.85% | present_not_reverified:6 | 0.00% |
| data/processed/bd_events.csv | 16 | 13.72% | present_not_reverified:16 | 0.00% |
| data/processed/clinical_events.csv | 10 | 13.16% | present_not_reverified:10 | 0.00% |
| data/processed/approval_events.csv | 3 | 13.33% | present_not_reverified:3 | 0.00% |
| data/processed/policy_risk_events.csv | 2 | 19.05% | present_not_reverified:2 | 0.00% |

## 暂不能生成的结论

- 任何 `can_use_for_latest_signal=false` 的标的不得进入 latest_valid。
- 需要人工核验的事件/财务/政策表，本阶段只做结构化和 source_status 标注，不新增未经查证事实。
