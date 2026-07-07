# AI/科技成长—创新药风格关系模块审计报告

## 当前问题确认

- 原CN_AI_CORE_V1 = 100% x 588000.SH。
- 588000.SH代表科创50科技成长风格，不是纯AI指数；不得继续把588000涨跌直接表述为AI涨跌。
- 本次修复后：588000.SH迁移为TECH_GROWTH_CORE，AI_CORE改用AI_CHINA/AI_US/AI_GLOBAL版本化篮子。

## 20项审计结论

1. 当前TECH_GROWTH_CORE：TECH_GROWTH_CORE_V1，成分=[{'symbol': '588000.SH', 'name': '科创50ETF', 'weight': 1.0, 'source_table': 'market_daily'}]。
2. 当前AI_CORE：AI_GLOBAL_V1，成分=[{'version_ref': 'AI_CHINA_V1', 'name': 'China AI proxy', 'weight': 0.45}, {'version_ref': 'AI_US_V1', 'name': 'US AI proxy', 'weight': 0.55}]。
3. 市场范围：TECH=China A-share technology/growth style；AI=Global AI proxy。
4. 收益计算：1/3/5/10/20日收益按共同有效交易日收盘价 close_t / close_t-n - 1 计算；缺失不补0。
5. 日期映射：TECH_GROWTH_CORE使用亚洲交易日同日收盘；AI_US/AI_GLOBAL中的美股成分按亚洲交易日映射上一可用美股收盘，禁止使用同日未来美股收盘。
6. 未来函数：历史统计使用当日及未来收益时只用于回测表，日报当前状态不使用未来收益；右侧评分训练目标shift(-5)仅用于历史权重估计。
7. 自然日拼接：研究表用共同交易日inner join，不按自然日直接填充；但原S1指标内部使用自然日扩大窗口后取可得交易日。
8. 节假日错位：跨市场分析保留a_share_date/hk_date/us_close_date/ai_core_date字段；美股节假日沿用最近已收盘日并降低新鲜度。
9. 重复日期：研究表重复日期数=0。
10. 收益窗口重复计数：窗口统计按每个交易日滚动样本，回测会有重叠持有期，报告标注为描述性/验证性统计，不视为独立交易次数。
11. 复权混用：market_daily ETF adjusted_type当前为none；HK个股缓存存在qfq来源但本模块只用ETF market_daily。
12. ETF分红/拆分风险：unadjusted_close无法完全消除ETF分红/拆并导致的伪收益风险，已写入低置信风险。
13. 描述性统计：当前S2_STYLE、相关性、条件收益为描述性统计；新增窗口/状态/领先表为历史验证统计。
14. 历史回测：新增AI状态、A股领先、右侧确认权重均使用最近最多250个共同有效交易日。
15. 实时值：当前状态、当日收益、右侧评分、仓位标签。
16. 沿用值：S1/S2历史分数按已生成日报读取；S2内部沿用项仍由原S2报告披露。
17. 老化数据：none。
18. 缺失/低置信度：none。
19. 复现性：固定输入文件、AI_CORE版本和配置即可复现。
20. 测试：新增单元/完整性测试覆盖；原S2测试保留。

## 数据源

- market_daily: /Users/pan/Desktop/research/0workspace/QuantPilot/data/processed/market_daily.csv
- macro_market_daily: /Users/pan/Desktop/research/0workspace/QuantPilot/data/processed/macro_market_daily.csv
- S1 indicators: /Users/pan/Desktop/research/0workspace/QuantPilot/data/indicators
- S2 scores: /Users/pan/Desktop/research/0workspace/QuantPilot/s2/output/s2_scores.csv
- 有效样本数：223

## 核心数据完整性

- 核心指数状态：VALID
- 数据源切换次数：0
- 缺失交易日：none
- 异常交易日：none
- 跨源冲突：none

| 标的 | 主数据源 | 备用源1 | 备用源2 | 复权口径 | 最新日期 | 缺失天数 | 状态 |
| --- | --- | --- | --- | --- | --- | ---: | --- |
| 588000.SH | market_daily | local_verified_cache | not_configured | unadjusted_close | 20260707 | 0 | valid |
| 512760.SH | market_daily | local_verified_cache | not_configured | unadjusted_close | 20260707 | 0 | valid |
| SMH | macro_market_daily | local_verified_cache | not_configured | unadjusted_close | 20260706 | 0 | valid |
| SOXX | macro_market_daily | local_verified_cache | not_configured | unadjusted_close | 20260706 | 0 | valid |
| QQQ | macro_market_daily | local_verified_cache | not_configured | unadjusted_close | 20260706 | 0 | valid |
| 159567.SZ | market_daily | local_verified_cache | not_configured | unadjusted_close | 20260707 | 0 | valid |
| 159557.SZ | market_daily | local_verified_cache | not_configured | unadjusted_close | 20260707 | 0 | valid |
| 589720.SH | market_daily | local_verified_cache | not_configured | unadjusted_close | 20260707 | 0 | valid |
