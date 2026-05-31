# 创新药 S2 产业验证日报

**报告日期**: 2026-05-30
**S1交易日**: 20260529
**输出范围**: 独立 S2 模块，不修改 S1 日报

## 一、今日结论

- 当前阶段：产业验证强、资金未确认
- 操作倾向：小仓试探
- S2原始得分：0.94
- S2置信度调整后得分：0.65
- S1最新日期 20260529，综合得分 0.46，等级 低于预期；S1-02=-2.71%，S1-05=20.00%。
- 今日无新增重大产业事件，产业事件分沿用当前观察窗口。

## 二、最近 10 个交易日 S1

| 日期 | S1综合得分 | S1等级 |
| --- | ---: | --- |
| 20260518 | 0.62 | 符合预期 |
| 20260519 | 0.71 | 符合预期 |
| 20260520 | 0.65 | 符合预期 |
| 20260521 | 0.59 | 低于预期 |
| 20260522 | 0.70 | 符合预期 |
| 20260525 | 0.74 | 符合预期 |
| 20260526 | 0.70 | 符合预期 |
| 20260527 | 0.70 | 符合预期 |
| 20260528 | 0.63 | 符合预期 |
| 20260529 | 0.46 | 低于预期 |

## 三、S2 本地计算结果

| 指标 | 名称 | 指标值 | 原始得分 | 调整后得分 | 置信度 | 样本数 | 替代口径数 | 评级 | 来源 | 依据 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| S2-01 | BD落地频率 | 4.00 | 1.00 | 0.65 | 0.60 | 2 | 0 | 超预期 | bd_events.csv | 近90日重大BD 2 笔；过去365日事件库记录 2 笔 |
| S2-02 | BD金额质量 | 1,600,000,000 USD | 1.00 | 0.65 | 0.60 | 2 | 0 | 超预期 | bd_events.csv | 近90日raw金额 1,600,000,000 USD；质量金额 1,425,000,000 USD |
| S2-03 | 龙头业绩兑现率 | 100.00% | 1.00 | 0.65 | 0.60 | 1 | 0 | 超预期 | earnings_events.csv | 1/1 个已披露龙头事件标记为超预期 |
| S2-04 | 数据催化转化率 | 100.00% | 1.00 | 0.60 | 0.60 | 1 | 1 | 超预期 | clinical_events.csv + 本地行情 | 真实标的样本 0/0；含替代口径样本 1/1；其中 1 个因标的行情缺失，使用 589720.SH 跑赢 159557.SZ 作为ETF承接替代口径 |
| S2-05 | 龙头接力强度 | 1.54% | 0.70 | 0.70 | 0.65 | 3 | 3 | 符合预期 | 事件库 + 本地行情 | 核心催化后5日超额收益中位数 1.54%；其中 3 个事件因标的行情缺失，使用本地A股龙头池相对 589720.SH 的中位超额收益 |

## 四、事件库状态

- BD事件库：2 条
- 临床事件库：1 条
- 业绩事件库：1 条
- 今日无新增重大产业事件，产业事件分沿用当前观察窗口。

### 当前观察窗口内的重要事件

- 2026-05-28 / 信达生物 / 12 early-stage and de novo oncology programs: Pfizer官方披露与信达建立全球肿瘤药物研发合作 来源: https://www.pfizer.com/news/press-release/press-release-detail/pfizer-and-innovent-biologics-enter-global-strategic
- 2026-05-12 / 恒瑞医药 / oncology hematology immunology portfolio: BMS官方披露与恒瑞达成战略合作；近期周年付款按公开IR材料计入near-term 来源: https://news.bms.com/news/details/2026/Bristol-Myers-Squibb-and-Hengrui-Pharma-Announce-Strategic-Agreements-to-Advance-Innovative-Medicines-Across-Oncology-Hematology-and-Immunology-2026-EbQpaI6Zdc/default.aspx
- 2026-05-26 / 康方生物 / ivonescimab HARMONi-6: HARMONi-6 OS数据入选ASCO plenary；正式数据与会后5日交易反应待验证 来源: https://www.prnewswire.com/news-releases/over-40-studies-featuring-akesos-innovative-oncology-agents-to-be-presented-at-asco-2026-ivonescimabs-harmoni-6-overall-survival-data-selected-for-plenary-session-302781500.html
- 2026-05-11 / 百济神州 / 2026Q1: 2026Q1营收105.44亿元、产品收入103.21亿元、归母净利润16.08亿元；扭亏为盈 来源: https://stockmc.xueqiu.com/202605/688235_20260512_26VW.pdf

## 五、数据缺失与待验证事项

- 过去4季度基准不足，当前倍数仅基于事件库现有样本
- 去年同期金额基准不足，V1以近90日金额绝对强度辅助评分

## 六、复核清单

- S2分数来自本地事件库和行情计算，不靠临场主观重打分。
- 新事件必须由智能体联网查证后写入事件库。
- 缺失数据保留为“数据缺失”，不编造。
