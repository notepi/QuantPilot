# AI/科技成长—创新药风格验证日报

## 1. 数据日期

- 报告日期：2026-06-22
- A股数据日期：20260622
- 港股数据日期：20260622
- 对应美股收盘日期：20260618
- TECH_GROWTH_CORE版本：TECH_GROWTH_CORE_V1；China A-share technology/growth style
- AI_CORE版本：AI_GLOBAL_V1；Global AI proxy
- 有效样本数：212；历史上限：250

## 2. 今日状态

- 科技成长状态：TECH_GROWTH_3D_PLUS_UP
- AI状态：AI_3D_PLUS_UP
- 市场状态：NEUTRAL
- 创新药相对医疗：-0.76%
- 创新药相对科技成长：-2.61%
- 创新药相对AI_CORE：-4.95%
- 589720情绪状态：589720偏弱
- A股领先候选：S1-04_upcross_1.00x
- 右侧确认评分：14.26；无右侧
- 评分置信度：high
- score_status：valid；feature_coverage：1.00000000
- 核心指数状态：VALID

## 2A. 数据质量

- 核心数据完整性：VALID
- 使用主数据源：588000.SH=market_daily; 512760.SH=market_daily; SMH=macro_market_daily; SOXX=macro_market_daily; QQQ=macro_market_daily; 159567.SZ=market_daily; 159557.SZ=market_daily; 589720.SH=market_daily
- 使用备用数据源：588000.SH=local_verified_cache; 512760.SH=local_verified_cache; SMH=local_verified_cache; SOXX=local_verified_cache; QQQ=local_verified_cache; 159567.SZ=local_verified_cache; 159557.SZ=local_verified_cache; 589720.SH=local_verified_cache
- 数据源切换次数：0
- 缺失交易日：none
- 异常交易日：none
- 跨源冲突：none
- 特征覆盖率：1.00000000
- 核心指数状态：VALID
- 评分状态：valid

## 3. 多窗口结论

| 窗口 | 科技成长—创新药关系 | AI—创新药关系 | 绝对上涨胜率 | 相对医疗跑赢胜率 | 稳定性 |
| --- | --- | --- | ---: | ---: | --- |
| 20日 | 跑输科技成长 | 跑输AI | 0.25000000 | 0.45000000 | 存在统计信号，需结合经济意义 |
| 60日 | 跑输科技成长 | 跑输AI | 0.33333333 | 0.50000000 | 存在统计信号，需结合经济意义 |
| 120日 | 跑输科技成长 | 跑输AI | 0.38333333 | 0.49166667 | 存在统计信号，需结合经济意义 |
| 250日 | 跑输科技成长 | 跑输AI | 0.41509434 | 0.46226415 | 存在统计信号，需结合经济意义 |

## 4. 最强支持证据

- S1-05广度达到53.33%

## 5. 最强反对证据

- 科技成长上涨时159567跑输TECH_GROWTH_CORE -2.61%
- AI_CORE上涨时159567跑输AI_CORE -4.95%
- 159567绝对收益为负 -0.67%

## 6. 科技成长/AI回调验证

- 科技成长是否回调：否
- AI是否回调：否
- AI回调类型：AI_3D_PLUS_UP
- 市场是否Risk Off：否
- 159567绝对收益：-0.67%
- 159567相对159557超额：-0.76%
- 159567相对科技成长超额：-2.61%
- 159567相对AI_CORE超额：-4.95%
- 是否属于有效轮动：当前AI未回调，不适用。

## 7. A股领先港股验证

- 当前最佳历史lead_signal：S1-04_upcross_1.00x
- S1是否先动：S1-04_upcross_1.00x，样本10，胜率0.80000000
- 可能领先窗口：2日
- 历史样本数：10
- 历史胜率：0.80000000
- 当前是否有效：未确认。

## 8. 当前命题

- AI资金虹吸假设：strengthened：AI_CORE上涨且159567跑输AI_CORE。
- 科技成长虹吸假设：strengthened：科技成长上涨且159567跑输TECH_GROWTH_CORE。
- 创新药接力假设：weakened：右侧评分不足。
- A股领先港股假设：weakened：589720及S1对159567未表现出稳定领先价值，只适合作为同步情绪温度计。
- 状态：weakened

## 9. 仓位建议

- 建议：reduce
- 理由：right_side_score=14.26; score_status=valid; confidence=high; thesis_state=weakened
- 下一增加条件：右侧确认评分>=70、置信度不低、159567相对159557和量能同时确认、反对证据少于2条。
- 下一减少条件：AI回调后159567仍不涨或跑输159557，或右侧评分<30，或S2_conversion继续低于0.60。
- 当前最强反对证据：科技成长上涨时159567跑输TECH_GROWTH_CORE -2.61% | AI_CORE上涨时159567跑输AI_CORE -4.95% | 159567绝对收益为负 -0.67%

## 10. 当前仍不能确认的事项

- AI_CORE已拆分为AI_CHINA/AI_US/AI_GLOBAL；若宏观美股数据缺失，AI_GLOBAL置信度下降。
- 当前只能在可用样本内判断创新药相对医疗、相对科技成长、相对AI_CORE的关系；不得用588000替代AI。
- 当前复权口径为unadjusted_close，ETF分红/拆分仍可能影响历史收益精度。
- 120/250日窗口包含重叠持有期统计，不等于独立交易次数。
- 若20/60日与120/250日结论冲突，应解释为近期关系变化，但长期稳定性不足。
- 本模块输出仓位动作标签，不构成投资建议。
