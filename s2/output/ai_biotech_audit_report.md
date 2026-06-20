# AI—创新药风格关系模块审计报告

## 20项审计结论

1. 当前AI_CORE：CN_AI_CORE_V1，成分=[{'symbol': '588000.SH', 'name': '科创50ETF', 'weight': 1.0}]。
2. 权重：当前版本为固定权重，588000.SH=100%。
3. 市场范围：China A-share technology proxy，不是美股AI，也不是混合AI。
4. 收益计算：1/3/5/10/20日收益按共同有效交易日收盘价 close_t / close_t-n - 1 计算；缺失不补0。
5. 日期映射：当前CN_AI_CORE_V1全为亚洲上市ETF，同一亚洲交易日内对齐；美股AI版本未启用，对应美股收盘日期为not_applicable。
6. 未来函数：历史统计使用当日及未来收益时只用于回测表，日报当前状态不使用未来收益；右侧评分训练目标shift(-5)仅用于历史权重估计。
7. 自然日拼接：研究表用共同交易日inner join，不按自然日直接填充；但原S1指标内部使用自然日扩大窗口后取可得交易日。
8. 节假日错位：当前单一亚洲交易体系风险较低；如启用美股AI_CORE需使用上一美股收盘映射。
9. 重复日期：研究表重复日期数=0。
10. 收益窗口重复计数：窗口统计按每个交易日滚动样本，回测会有重叠持有期，报告标注为描述性/验证性统计，不视为独立交易次数。
11. 复权混用：market_daily ETF adjusted_type当前为none；HK个股缓存存在qfq来源但本模块只用ETF market_daily。
12. ETF分红/拆分风险：unadjusted_close无法完全消除ETF分红/拆并导致的伪收益风险，已写入低置信风险。
13. 描述性统计：当前S2_STYLE、相关性、条件收益为描述性统计；新增窗口/状态/领先表为历史验证统计。
14. 历史回测：新增AI状态、A股领先、右侧确认权重均使用最近最多250个共同有效交易日。
15. 实时值：当前状态、当日收益、右侧评分、仓位标签。
16. 沿用值：S1/S2历史分数按已生成日报读取；S2内部沿用项仍由原S2报告披露。
17. 老化数据：none。
18. 缺失/低置信度：['US_AI_CORE missing']。
19. 复现性：固定输入文件、AI_CORE版本和配置即可复现。
20. 测试：新增单元/完整性测试覆盖；原S2测试保留。

## 数据源

- market_daily: /Users/pan/Desktop/research/0workspace/QuantPilot/data/processed/market_daily.csv
- S1 indicators: /Users/pan/Desktop/research/0workspace/QuantPilot/data/indicators
- S2 scores: /Users/pan/Desktop/research/0workspace/QuantPilot/s2/output/s2_scores.csv
- 有效样本数：211
