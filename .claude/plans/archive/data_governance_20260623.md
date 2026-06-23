# 数据治理实施计划

> 状态：待确认
> 来源：docs/data_governance_plan.md

## 实施步骤

### 第一阶段：数据日期披露（A1）
1. `wb/indicators/base.py` - IndicatorResult 增加 `data_date` 字段，to_dict() 输出
2. `wb/indicators/s1_01_capital_flow.py` - 从 fund_share 数据获取实际最新日期
3. `wb/indicators/s1_02_share_change.py` - 同上
4. `wb/generate_report.py` - 日报中显示数据日期，不一致时警告

### 第二阶段：份额数据备用源（A2）
1. `wb/update_data.py` - 新增 `fetch_fund_share_em()` 东方财富备用源
2. `wb/update_data.py` - 修改 `fetch_fund_share()` 增加 fallback 逻辑
3. `wb/update_data.py` - `append_to_file()` 兼容 source 字段

### 第三阶段：159567.SZ raw 层更新（B）
1. `wb/update_data.py` - 第326行增加 159567.SZ
2. `docs/indicators.md` - 修正 S1-05 数据源说明 hk_daily → daily

### 第四阶段：S3 模块拆分（C）
1. 创建 `s3/` 目录及文件
2. 迁移 AI 风格相关代码（style_rotation, validation, generate_report）
3. s2 保留兼容 wrapper
4. 更新 daily_report_flow.py 引用 s3

### 验收
- S1 指标 JSON 含 data_date
- 份额数据含东方财富来源
- 159567 raw 层更新
- S3 独立运行
- S2 测试通过
