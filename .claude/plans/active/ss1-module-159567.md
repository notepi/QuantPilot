# SS1 原始数据源验证计划：159567.SZ 与固定持仓池

## Context

**目标**：固定 159567.SZ、固定持仓池、固定 S1 算法，测试各类原始外部数据源能否提供 S1 所需数据。

**固定条件**：
- 目标 ETF：159567.SZ（港股创新药ETF）
- 基准 ETF：159557.SZ（港股医疗宽基）
- 持仓池：159567 固定持仓/成分对象
- 算法：S1 六项指标公式不改

**现阶段不做**：日报生成、评分、权重、fallback、代码改造

---

## 数据源测试矩阵

| 数据类别 | 固定对象 | 用途 | 必测原始数据源 |
|----------|----------|------|----------------|
| ETF 日线 | 159567.SZ | S1-03/S1-04/S1-06 | 腾讯、东方财富、akshare、citydata/tushare proxy |
| 基准 ETF 日线 | 159557.SZ | S1-03 | 腾讯、东方财富、akshare、citydata/tushare proxy |
| ETF 份额 | 159567.SZ | S1-01/S1-02 | citydata、东方财富/天天基金、akshare、基金公司/交易所披露 |
| 持仓/成分 | 159567 固定持仓池 | S1-05/S1-06 股票池 | 基金公司公告、天天基金/东方财富、指数公司/交易所披露 |
| 持仓股票日线 | 固定持仓股票 | S1-05/S1-06 | 腾讯港股 K 线、东方财富港股行情、akshare 港股历史、citydata/tushare proxy |

---

## 固定持仓池（159567 前十大，2026-03-31 披露）

**来源**：天天基金/东方财富

| 代码 | 名称 | 权重 |
|------|------|------|
| 09926.HK | 康方生物 | 11.86% |
| 01801.HK | 信达生物 | 9.81% |
| 01093.HK | 石药集团 | 9.40% |
| 06160.HK | 百济神州 | 9.06% |
| 01177.HK | 中国生物制药 | 9.02% |
| 03692.HK | 翰森制药 | 6.93% |
| 01530.HK | 三生制药 | 6.62% |
| 06990.HK | 科伦博泰 | 4.15% |
| 09995.HK | 荣昌生物 | 2.78% |
| 00867.HK | 康哲药业 | 2.69% |

**合计权重**：72.32%

---

## 项目已有函数复用

| 函数 | 文件 | 用途 |
|------|------|------|
| `_fetch_tencent_etf_daily()` | [s2/update_market_data.py:153](s2/update_market_data.py#L153) | 腾讯 ETF K 线 |
| `_fetch_citydata_fund_daily()` | [s2/update_market_data.py:128](s2/update_market_data.py#L128) | citydata fund_daily |
| `_fetch_eastmoney()` | [s2/hk_observation.py:108](s2/hk_observation.py#L108) | 东方财富 ETF K 线 |
| `_fetch_hk_stock()` | [s2/update_market_data.py:94](s2/update_market_data.py#L94) | akshare 港股历史 |
| `_fetch_tencent_hk_stock()` | [s2/update_market_data.py:101](s2/update_market_data.py#L101) | 腾讯港股 K 线 |
| `fetch_fund_share()` | [wb/update_data.py:163](wb/update_data.py#L163) | citydata 份额 |
| `fetch_fund_share_em()` | [wb/update_data.py:239](wb/update_data.py#L239) | 东方财富 ETF spot 份额 |

---

## 测试记录格式

每个数据源测试必须记录：

```text
source_name           # 源名称
source_api_or_url     # API 或 URL
data_category         # 数据类别
target_symbol         # 目标标的
available             # yes/no
fields_present        # 返回字段列表
field_mapping_to_S1   # 映射到 S1 所需字段
latest_trade_date     # 最新交易日期
history_depth         # 历史深度（天数）
adjusted_type         # 复权类型
failure_reason        # 失败原因（如失败）
sample_rows           # 样本行数
can_feed_S1_original_formula  # yes/no
```

---

## 实现步骤

### Step 1: 创建测试脚本

```bash
mkdir -p ss1/data_source_tests
```

### Step 2: 逐类数据源测试

对每类数据编写测试脚本：

1. **ETF 日线测试**：测试腾讯、东方财富、akshare、citydata 能否拿到 159567.SZ 和 159557.SZ 日线
2. **份额数据测试**：测试 citydata、东方财富/天天基金、akshare 能否拿到 159567.SZ 份额
3. **持仓/成分测试**：测试基金公司公告、天天基金、指数公司能否拿到 159567 持仓列表
4. **持仓股票日线测试**：测试腾讯港股、东方财富、akshare 能否拿到固定持仓池日线

### Step 3: 汇总测试结果

输出两份文件：
- `ss1/data_source_tests/test_results.csv` — 供程序读取
- `ss1/data_source_tests/test_results.md` — 供人审阅

---

## Timeline

- Step 1: 5 分钟
- Step 2: 2-3 小时（逐接口测试）
- Step 3: 30 分钟（汇总）

**Total**: 半天
