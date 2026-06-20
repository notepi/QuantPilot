# 创新药 S2 产业验证日报

**报告日期**: 2026-06-18
**S1交易日**: 20260618
**输出范围**: 独立 S2 模块，不修改 S1 日报
**版本状态**: 数据治理后试运行版，行情层已接入 audit，但部分解释标签仍在迭代校验。
**港股观察标的**: 159567.SZ 港股创新药ETF
**正式量化温度计**: 589720.SH 科创创新药ETF
**港股对照标的**: 159557.SZ 港股医疗宽基参考

589720.SH 用于观察 A 股创新药资金状态；159567.SZ 用于观察港股创新药实际交易方向；159557.SZ 用于判断港股创新药是否强于港股医疗宽基。

**口径边界**: 589720.SH 弱，只表示 A 股科创创新药资金状态偏弱；159567.SZ 是否强，需要单独读取 HK_observation。

## 一、今日结论

- 港股观察标的：159567.SZ 港股创新药ETF。
- A股温度计状态：589720.SH S1=0.61，状态为中性；S1最新日期 20260618，综合得分 0.61，等级 符合预期；S1-02=5.59%，S1-05=46.67%，S1-06=-0.62%。
- s1_structure_quality = normal；s1_breadth_state = normal。
- S1_score_contribution：flow_score_contribution=0.268；price_strength_contribution=0.140；volume_contribution=0.056；breadth_contribution=0.098；leader_contribution=0.048。
- S1改善主要来自资金/份额流入，非价格强度和广度扩散。
- S2正式量化等级：adjusted_score=0.60，等级为符合预期。
- S2_INDUSTRY=0.60；S2_STYLE=0.34；S2_TOTAL=0.54；style_regime=NEUTRAL。
- AI—创新药严格验证：右侧确认评分=23.54；命题状态=weakened；仓位动作标签=reduce。
- S2产业事件侧得分：S2_event_score=0.65，状态为符合预期。
- S2交易转化侧得分：S2_conversion_score=0.50，状态为交易转化修复中，但未确认。
- BD联动解释：BD频率与金额质量均符合预期，说明产业事件侧较前期改善；但该改善尚未通过S2-04和S2-05转化为交易确认。
- HK_observation ETF观察：159567最近5个交易日跑赢159557 1.19%，说明港股创新药ETF强于港股医疗宽基。该观察不进入正式S2分。
- 下一批S2-04事件将在暂无开始成熟，届时可开始观察临床事件5日交易转化。
- 日间变化说明：产业事件侧较前一日改善；交易转化侧状态为交易转化修复中，但未确认。
- S2解释性状态：一致预期验证缺数据；财报客观改善有效，但不能冒充超一致预期。
- 港股观察层：159567 数据状态为 latest_valid；可判断相对强弱。
- 综合客观状态：C；C1；产业事件侧符合预期，BD频率与金额质量均符合预期；交易转化修复中，但未确认；A股温度计中性，S1=0.61；latest_valid，港股创新药 ETF 最近 5 个交易日强于港股医疗宽基。；政策风险升高；risk_off_defensive=false；ai_crowding_unwind=false；biotech_relative_strength=true；hk_innovation_vs_health=positive

- 产业事件状态：今日无新增重大产业事件，产业事件分沿用当前观察窗口。
- 交易转化成熟度：S2-04 去重正式交易样本 9 个，raw成熟事件 10 个，success_rate=22.22%，评级 低于预期；S2-05 评级 符合预期。
- S1/S2组合观察：S1/S2总分达到符合预期，但关键交易确认项仍未达标。
- S2原始得分（raw_score）：0.71
- S2置信度调整后得分（adjusted_score）：0.60
- 正式口径可用权重：90%；缺失指标：1；待验证指标：0；含观察口径指标：0；过期沿用指标：0
- 港股观察层：状态=latest_valid。citydata_fund_daily抓取成功。159567最近5个交易日跑赢159557 1.19%，说明港股创新药ETF强于港股医疗宽基。该观察层不进入 S2_total，也不改变 adjusted_score。
- S1更新状态：S1指标已更新到 20260618；本地 589720.SH 行情最新交易日为 20260618；fund_share 已通过上交所fallback补至 20260617。
- 今日无新增重大产业事件，产业事件分沿用当前观察窗口。

### 正负因素摘要

| 正面确认 | 负面确认 | 数据风险/不可确认 |
| --- | --- | --- |
| BD频率符合预期 | S2_conversion_score=0.50，修复但未确认 | S2-03b一致预期缺失 |
| BD金额质量符合预期 | S1-05=46.67%，normal | S2-06商业化兑现低置信度 |
| 产业事件侧得分0.65 | S2-04 success_rate=22.22% | Macro_Risk_Layer核心字段缺失1/10 |
| HK_observation=latest_valid | Policy_Risk_Layer=risk_up | missing |

## 二、今日变化

| 项目 | 昨日 | 今日 | 变化 | 解释 |
| --- | ---: | ---: | ---: | --- |
| S1_total | 0.54 | 0.61 | +0.07 | 温度计修复 |
| S2_adjusted | 0.59 | 0.60 | +0.01 | 产业事件侧较前一日改善；交易转化侧状态为交易转化修复中，但未确认。 |
| S2_event_score | 0.64 | 0.65 | +0.01 | 产业事件侧符合预期 |
| S2_conversion_score | 0.50 | 0.50 | +0.00 | 交易转化修复中，但未确认 |
| S2-04 pending | 0.00 | 0.00 | +0.00 | ASCO/临床事件等待满5个完整交易日 |
| HK_observation | valid | latest_valid | 变化 | 可判断159567相对159557强弱 |

## 三、数据质量摘要

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| S1 | valid | 589720行情和指标更新到20260618 |
| S2事件库 | valid | 今日新增0条确认事件 |
| 事件去重检查 | 有待复核 | is_duplicate=true 的事件不进入正式统计 |
| S2-04交易转化 | valid | raw_mature_event_count=10；deduped_trade_sample_count=9；0个事件未满5日 |
| HK_observation | latest_valid | source=citydata_fund_daily；source_status=success->not_used；primary_source_status=success；fallback_source_status=not_used；latest_date_159567=20260618；latest_date_159557=20260618；common_trade_date=20260618；calendar_lag_days=0；trading_lag_days=0；report_day_price_available_externally=false；local_fetch_failed=false；data_fetch_failed=false |
| S2-03a财报客观改善 | positive_low_sample | 财报客观改善为正，但样本不足且没有一致预期验证，不得称为超预期 |
| S2-03b一致预期验证 | missing | 具备一致预期来源的业绩样本缺失 |
| S2-06商业化兑现质量 | scorable_low_confidence | 商业化核心公司指标达到最低评分覆盖，但完整度或来源置信度偏低：6/6；关键字段完整度=50%；非官方/媒体来源样本=4；缺失字段保留missing |

## 四、第一层：S1_A股温度计

589720.SH 用于判断 A 股科创创新药资金是否确认，不代表 159567.SZ 的实时交易强弱。

- A股创新药资金状态：中性。
- S1趋势状态：s1_weak_streak_days=0；s1_trend_state=温度计修复；s1_recent_direction=上升 +0.07。
- s1_structure_quality = normal；s1_breadth_state = normal。
- S1_score_contribution：flow_score_contribution=0.268；price_strength_contribution=0.140；volume_contribution=0.056；breadth_contribution=0.098；leader_contribution=0.048。
- S1改善主要来自资金/份额流入，非价格强度和广度扩散。
- S1最新日期 20260618，综合得分 0.61，等级 符合预期；S1-02=5.59%，S1-05=46.67%，S1-06=-0.62%。

### 最近 10 个交易日 S1

| 日期 | S1综合得分 | S1等级 |
| --- | ---: | --- |
| 20260605 | 0.61 | 符合预期 |
| 20260608 | 0.68 | 符合预期 |
| 20260609 | 0.68 | 符合预期 |
| 20260610 | 0.68 | 符合预期 |
| 20260611 | 0.56 | 低于预期 |
| 20260612 | 0.62 | 符合预期 |
| 20260615 | 0.60 | 低于预期 |
| 20260616 | 0.54 | 低于预期 |
| 20260617 | 0.54 | 低于预期 |
| 20260618 | 0.61 | 符合预期 |

## 五、第二层：S2_产业验证正式分

S2_total 只基于事件库、本地行情、589720.SH 与 A 股龙头池。S2_total 是产业验证正式分，不等于 159567.SZ 的实时交易强弱。

| 指标 | 名称 | 指标值 | 状态 | raw_score | adjusted_score | 置信度 | 正式样本 | pending样本 | 正式计分状态 | 观察层样本 | 缺失原因 | 依据 |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | --- | --- |
| S2-01 | BD落地频率 | 1.60 | 超预期 | 1.00 | 0.75 | 0.75 | 4 | 0 | 正式评分 | 0 | - | 近90日重大BD 4 笔；前4个完整90日窗口 4/3/1/2 笔，单窗口均值 2.50 |
| S2-02 | BD金额质量 | 109.06% | 符合预期 | 0.70 | 0.70 | 0.75 | 4 | 0 | 正式评分 | 0 | - | 近90日raw金额 1,799,500,000 USD；去年同期90日 1,650,000,000 USD；质量金额 1,980,700,000 USD |
| S2-03a | 财报客观改善 | 100.00% | positive_low_sample | 1.00 | 0.65 | 0.60 | 1 | 0 | 正式评分 | 0 | - | 财报客观改善样本 1/1；仅基于同比、利润改善、亏损收窄、现金流/经营改善等客观项，不代表超一致预期；样本不足3个时不得写超预期 |
| S2-03b | 一致预期验证 | 数据缺失 | 数据缺失 | 0.50 | 0.50 | 0.45 | 0 | 0 | 中性占位 | 0 | 具备一致预期来源的业绩样本缺失 | earnings_consensus.csv 无可靠一致预期来源；不得用同比增长冒充超预期 |
| S2-04 | 数据催化转化率 | 22.22% | 低于预期 | 0.40 | 0.40 | 0.90 | 9 | 0 | 正式评分 | 0 | - | 正式口径：raw_mature_event_count=10；deduped_trade_sample_count=9；success_count=2；success_rate=22.22%；港股事件使用159557.SZ作宽基对照，A股事件使用589720.SH作温度计对照；本日无新增成熟样本，沿用 2026-06-11 有效观测；待验证 0 个；沿用已超过2个交易日，adjusted_score封顶0.60 |
| S2-05 | 龙头接力强度 | 0.78% | 符合预期 | 0.70 | 0.60 | 0.90 | 18 | 0 | 正式评分 | 0 | - | 当前S2-05为沿用观察，不是今日新增验证；正式口径：核心催化后本地A股龙头池相对 589720.SH 的5日中位超额收益 0.78%；本日无新增成熟样本，沿用 2026-06-12 有效观测；待验证 0 个；沿用已超过2个交易日，adjusted_score封顶0.60 |

- S2-05 当前为沿用观察，不是今日新增验证。最近有效观测日：2026-06-12；距今 4 个交易日；类型：aging_carry_forward。

### 事件库状态

- BD事件库：16 条
- 临床事件库：10 条
- 业绩事件库：1 条
- 一致预期验证表：6 条
- 审批事件库：3 条
- 今日无新增重大产业事件，产业事件分沿用当前观察窗口。

### 今日新增事件明细

- 今日无新增重大产业事件，产业事件分沿用当前观察窗口。

### 当前观察窗口内的重要事件

- 2026-05-28 / 信达生物 / 12 early-stage and de novo oncology programs: Pfizer官方披露与信达建立全球肿瘤药物研发合作 来源: https://www.pfizer.com/news/press-release/press-release-detail/pfizer-and-innovent-biologics-enter-global-strategic
- 2026-05-12 / 恒瑞医药 / oncology hematology immunology portfolio: BMS官方披露与恒瑞达成战略合作；近期周年付款按公开IR材料计入near-term 来源: https://news.bms.com/news/details/2026/Bristol-Myers-Squibb-and-Hengrui-Pharma-Announce-Strategic-Agreements-to-Advance-Innovative-Medicines-Across-Oncology-Hematology-and-Immunology-2026-EbQpaI6Zdc/default.aspx
- 2026-05-29 / 海思科 / up to five innovative target programs: 海思科与Lilly达成最多5个创新靶点项目的许可及研发合作；公开口径未拆分首付款与近期付款，合计最高87M USD。 来源: https://www.prnewswire.com/news-releases/haisco-announces-licensing-and-research-collaboration-agreement-with-lilly-to-develop-innovative-medicines-across-multiple-therapeutic-areas-302786957.html
- 2026-06-02 / 云顶新耀 / civorebrutinib / EVER001: 云顶新耀与Travere就BTK抑制剂civorebrutinib达成区域外许可合作；协议待HSR等条件满足后生效。 来源: https://www.prnewswire.com/apac/news-releases/everest-medicines-enters-into-exclusive-licensing-agreement-with-travere-therapeutics-for-civorebrutinib-a-potential-best-in-class-btk-inhibitor-for-rare-kidney-diseases-302788528.html
- 2026-06-04 / 云顶新耀 / Bejescin (maijianxituximab injection): 云顶新耀与Mabworks就Bejescin亚太部分市场商业化达成许可协议；补充PRAsia金额披露，按非重大BD记录。 来源: https://www.prnewswire.com/news-releases/everest-medicines-enters-into-license-agreement-with-mabworks-for-commercialization-of-bejescin-in-asia-pacific-markets-302788815.html
- 2026-05-29 / 科伦博泰 / sacituzumab tirumotecan (sac-TMT) OptiTROP-Lung05: OptiTROP-Lung05口头报告并同步发表于The Lancet；PFS显著获益，OS尚未成熟 来源: https://www.prnewswire.com/news-releases/the-results-of-phase-iii-optitrop-lung05-study-of-sacituzumab-tirumotecan-sac-tmt-presented-as-an-asco-oral-presentation-and-simultaneously-published-in-the-lancet-302786204.html
- 2026-05-29 / 科伦博泰 / lunbotinib fumarate (A400/EP0031): RET融合阳性NSCLC关键II期口头报告；NMPA已受理NDA 来源: https://www.prnewswire.com/news-releases/kelun-biotech-presents-pivotal-phase-ii-data-for-lunbotinib-fumarate-a400ep0031-in-ret-fusion-positive-nsclc-at-2026-asco-302786202.html
- 2026-05-31 / 康方生物 / ivonescimab HARMONi-6: HARMONi-6头对头III期达到OS和PFS双重显著获益；会后5日交易反应待验证 来源: https://www.prnewswire.com/news-releases/harmoni-6-demonstrates-significant-overall-survival-benefit-hr0-66-ivonescimab-plus-chemotherapy-superior-to-pd-1-plus-chemotherapy-in-first-line-sq-nsclc-landmark-results-to-be-presented-at-asco-2026-plenary-session-302786433.html
- 2026-05-30 / 迪哲医药 / DZD6008 and golidocitinib plus anti-PD-1: 迪哲医药披露ASCO 2026两项NSCLC研究数据；会后5日交易反应待验证 来源: https://www.prnewswire.com/news-releases/dizal-presented-positive-data-of-dzd6008-and-golidocitinib-at-the-2026-asco-annual-meeting-showing-potential-to-address-significant-unmet-medical-needs-in-non-small-cell-lung-cancer-302786349.html
- 2026-06-01 / 康宁杰瑞 / anbenitamab (KN026) plus HB1801: 康宁杰瑞官网披露KN026联合HB1801新辅助治疗HER2阳性乳腺癌III期LBA口头报告；tpCR显著优于对照，市场反应待满5个交易日验证 来源: https://www.alphamabonc.com/en/html/news/2808.html

### S2-04 临床事件成熟度

- S2-04_official_status：低于预期。
- S2-04_official_sample_count：9。
- raw_mature_event_count：10。
- deduped_trade_sample_count：9。
- success_count：2。
- success_rate：22.22%。
- S2-04_hk_event_pending_count：1。
- S2-04_hk_event_pending_or_missing_count：1。
- HK_observation_status：159567 强于 159557。
- 港股临床事件若本地 `s2/data/hk_daily.csv` 有完整个股价格，则进入 S2-04 正式样本；缺行情时列明缺失标的，不编造。
- 成熟可计算样本：9；等待满 5 日：0；港股行情缺失/待补：0；本地价格缺失：0。
- 下一批预计成熟日期：暂无。

### S2-04 待成熟事件日历

| 预计成熟日期 | 事件数量 | 涉及公司 | 说明 |
| --- | ---: | --- | --- |
| 暂无 | 0 | - | 无待成熟事件 |

| 公司 | 标的 | 事件日期 | benchmark_code | window_days | trade_sample_id | mature_date | days_to_mature | 已过交易日 | 状态 | stock_audit_status | benchmark_audit_status | stock_data_quality | benchmark_data_quality | stock_can_use_for_latest_signal | benchmark_can_use_for_latest_signal | 说明 | 是否进入去重正式分 |
| --- | --- | --- | --- | ---: | --- | --- | ---: | ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 康方生物 | 9926.HK | 2026-05-26 | 159557.SZ | 5 | 09926.HK\|20260526\|159557.SZ\|5 | 已满5日 | 0 | 17/5 | mature_calculable | passed | passed | latest_valid | latest_valid | true | true | 成熟可算 | 是 |
| 科伦博泰 | 6990.HK | 2026-05-29 | 159557.SZ | 5 | 06990.HK\|20260529\|159557.SZ\|5 | 已满5日 | 0 | 14/5 | mature_calculable | passed | passed | latest_valid | latest_valid | true | true | 成熟可算 | 是 |
| 科伦博泰 | 6990.HK | 2026-05-29 | 159557.SZ | 5 | 06990.HK\|20260529\|159557.SZ\|5 | 已满5日 | 0 | 14/5 | mature_deduped_duplicate | passed | passed | latest_valid | latest_valid | true | true | 同一 stock_code + event_date + benchmark_code + window_days 已有正式交易样本，本项目仅保留明细 | 否 |
| 康方生物 | 9926.HK | 2026-05-31 | 159557.SZ | 5 | 09926.HK\|20260531\|159557.SZ\|5 | 已满5日 | 0 | 13/5 | mature_calculable | passed | passed | latest_valid | latest_valid | true | true | 成熟可算 | 是 |
| 迪哲医药 | 688192.SH | 2026-05-30 | 589720.SH | 5 | 688192.SH\|20260530\|589720.SH\|5 | 已满5日 | 0 | 13/5 | mature_calculable | passed | passed | latest_valid | latest_valid | true | true | 成熟可算 | 是 |
| 康宁杰瑞 | 9966.HK | 2026-06-01 | 159557.SZ | 5 | 09966.HK\|20260601\|159557.SZ\|5 | 已满5日 | 0 | 13/5 | mature_calculable | passed | passed | latest_valid | latest_valid | true | true | 成熟可算 | 是 |
| 先声再明 | 2096.HK | 2026-06-02 | 159557.SZ | 5 | 02096.HK\|20260602\|159557.SZ\|5 | 已满5日 | 0 | 12/5 | mature_calculable | passed | passed | latest_valid | latest_valid | true | true | 成熟可算 | 是 |
| 亚盛医药 | 6855.HK | 2026-06-01 | 159557.SZ | 5 | 06855.HK\|20260601\|159557.SZ\|5 | 已满5日 | 0 | 13/5 | mature_calculable | passed | passed | latest_valid | latest_valid | true | true | 成熟可算 | 是 |
| 科伦博泰 | 6990.HK | 2026-06-03 | 159557.SZ | 5 | 06990.HK\|20260603\|159557.SZ\|5 | 已满5日 | 0 | 11/5 | mature_calculable | passed | passed | latest_valid | latest_valid | true | true | 成熟可算 | 是 |
| 信达生物 | 01801.HK | 2026-06-04 | 159557.SZ | 5 | 01801.HK\|20260604\|159557.SZ\|5 | 已满5日 | 0 | 10/5 | mature_calculable | passed | passed | latest_valid | latest_valid | true | true | 成熟可算 | 是 |

### HK_observation ETF观察

- 港股临床事件只有在港股个股行情可得时才进入正式S2-04；HK_observation只回答159567是否强于159557。
- HK_observation不进入S2_total，不改变adjusted_score。

| 字段 | 数值 |
| --- | ---: |
| hk_observation_available | true |
| hk_observation_return_159567 | 1.19% |
| hk_observation_return_159557 | 0.00% |
| hk_observation_excess_159567_vs_159557 | 1.19% |
| hk_observation_excess_data_scope | latest_valid |

### S2-03a / S2-03b 业绩验证层

S2-03a 只判断财报客观改善；S2-03b 必须基于可靠一致预期来源判断 beat / miss。不得用同比增长冒充超预期。

| 公司 | 期间 | 营收同比 | 产品收入同比 | 利润同比/状态 | 业务改善 | 亏损收窄 | 扭亏 | 指引上调 | has_consensus | beat | 一致预期来源 |
| --- | --- | ---: | ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| 百济神州 | 2026Q1 | 31.0 | missing | turnaround | missing | missing | true | missing | missing | true | missing |

### S2-03b 一致预期验证表

- 若没有可靠一致预期来源，S2-03b = missing；同比增长不得替代 beat / miss。

| company_name | symbol | report_period | actual_revenue | consensus_revenue | revenue_beat | actual_adjusted_profit | consensus_adjusted_profit | profit_beat | actual_eps | consensus_eps | eps_beat | consensus_source | source_url | source_date | confidence | note |
| --- | --- | --- | ---: | ---: | --- | ---: | ---: | --- | ---: | ---: | --- | --- | --- | --- | --- | --- |
| 百济神州 | 06160.HK | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | 未接入可靠一致预期来源；不得用同比增长替代 beat/miss |
| 信达生物 | 01801.HK | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | 未接入可靠一致预期来源；不得用同比增长替代 beat/miss |
| 康方生物 | 09926.HK | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | 未接入可靠一致预期来源；不得用同比增长替代 beat/miss |
| 恒瑞医药 | 600276.SH | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | 未接入可靠一致预期来源；不得用同比增长替代 beat/miss |
| 药明康德 | 603259.SH | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | 未接入可靠一致预期来源；不得用同比增长替代 beat/miss |
| 药明生物 | 02269.HK | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | missing | 未接入可靠一致预期来源；不得用同比增长替代 beat/miss |

### S2-06 商业化兑现质量

- S2-06 只判断商业化兑现质量，不替代 S2-03，不进入 S2_event_score 或 S2_total。
- S2-06 只有有效覆盖核心公司数 >= 3 且关键字段完整度 >= 50% 时才允许评分。
- S2-06_status：scorable_low_confidence。
- S2-06_score：0.67。
- S2-06_usable_core_company_count：6/6。
- S2-06_key_field_completeness：50%。
- S2-06_missing：商业化核心公司指标达到最低评分覆盖，但完整度或来源置信度偏低：6/6；关键字段完整度=50%；非官方/媒体来源样本=4；缺失字段保留missing。
- S2-06_basis：商业化兑现质量通过样本 4/6；只判断收入、利润、现金流和现金余额等商业化质量，不替代S2-03。

| company_name | symbol | report_period | total_revenue_yoy | product_revenue_yoy | innovation_drug_revenue_yoy | adjusted_profit_yoy | operating_cash_flow | cash_balance | source_url | source_date | source_type |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| 百济神州 | 06160.HK | 2026Q1 | 31.0 | 29.0 | missing | turnaround | missing | missing | https://media.drugdu.com/ddu-news/beigenes-q1-2026-results-product-revenue-reached-rmb-10-3-billion-a-year-on-year-increase-of-29.html | 2026-05-12 | credible_financial_media |
| 信达生物 | 01801.HK | 2025FY | 38.4 | 45.0 | missing | 419.6 | missing | RMB24.3bn | https://www.hkexnews.hk/listedco/listconews/sehk/2026/0428/2026042805171.pdf | 2026-04-28 | annual_report |
| 康方生物 | 09926.HK | 2025FY | 43.9 | 51.48 | missing | missing | missing | missing | https://www.prnewswire.com/news-releases/akeso-reports-full-year-2025-financial-results-302726959.html | 2026-03-26 | company_press_release |
| 恒瑞医药 | 600276.SH | 2025FY | 13.0 | missing | 26.1 | missing | RMB11.2354bn | RMB40.955bn | https://www.hengrui.com/images/investor/%E6%81%92%E7%91%9E%E9%86%AB%E8%97%A5%202025%E5%B9%B4%E5%A0%B1.pdf | 2026-04-29 | annual_report |
| 药明康德 | 603259.SH | 2025FY | 21.4 | missing | missing | 41.3 | RMB16.67bn | missing | https://www.wuxiapptec.com/news/wuxi-news/ukp6jpdhyncifp8ovk4kv1z6 | 2026-03-24 | company_press_release |
| 药明生物 | 02269.HK | 2025FY | 16.7 | missing | missing | 22.0 | missing | missing | https://www.wuxibiologics.com/press-release/wuxi-biologics-reports-record-2025-annual-results/ | 2026-03-26 | company_press_release |

## 六、第三层：HK_observation_159567观察层

| 项目 | 数值 |
| --- | ---: |
| 底层数据状态 | valid |
| hk_observation_status | latest_valid |
| latest_date_159567 | 20260618 |
| latest_date_159557 | 20260618 |
| common_trade_date | 20260618 |
| report_trade_date | 20260618 |
| lag_days_159567 | 0 |
| lag_days_159557 | 0 |
| calendar_lag_days | 0 |
| trading_lag_days | 0 |
| report_day_price_available_externally | false |
| local_fetch_failed | false |
| data_fetch_failed | false |
| 数据源 | citydata_fund_daily |
| primary_source_status | success |
| fallback_source_status | not_used |
| final_data_source | citydata_fund_daily |
| 159567_audit_final_source | processed |
| 159567_audit_final_source_reason | processed table has latest symbol row |
| 159567_audit_fetched_at | 2026-06-20T21:49:33 |
| 159567_audit_data_quality | latest_valid |
| 159567_audit_can_use_for_latest_signal | true |
| 159567_audit_raw_latest_date | missing |
| 159567_audit_cache_latest_date | 20260618 |
| 159567_audit_processed_latest_date | 20260618 |
| 159557_audit_final_source | processed |
| 159557_audit_final_source_reason | processed table has latest symbol row |
| 159557_audit_fetched_at | 2026-06-20T21:49:34 |
| 159557_audit_data_quality | latest_valid |
| 159557_audit_can_use_for_latest_signal | true |
| 159557_audit_raw_latest_date | missing |
| 159557_audit_cache_latest_date | 20260618 |
| 159557_audit_processed_latest_date | 20260618 |
| 是否参与判断 | 是 |
| 159567 1日收益 | 1.19% |
| 159557 1日收益 | 1.03% |
| 159567 - 159557 单日超额 | 0.16% |
| 159567 5日收益 | 1.19% |
| 159557 5日收益 | 0.00% |
| 159567 - 159557 5日超额 | 1.19% |
| 159567 10日收益 | -3.73% |
| 159557 10日收益 | -4.48% |
| 159567 - 159557 10日超额 | 0.74% |
| 159567相对收益data_scope | latest_valid |
| 原因 | 港股创新药 ETF 最近 5 个交易日强于港股医疗宽基。 |

- 港股创新药 ETF 最近 5 个交易日强于港股医疗宽基。
- HK_observation 不进入 S2_total，不改变 S2 adjusted_score，只用于辅助解释 159567 是否强于 159557。

### 159567 相对 159557 连续强弱

| 项目 | 数值 |
| --- | ---: |
| 今日单日超额 | 0.16% |
| 今日单日超额data_scope | latest_valid |
| 今日5日超额 | 1.19% |
| 今日5日超额data_scope | latest_valid |
| 今日10日超额 | 0.74% |
| 今日10日超额data_scope | latest_valid |
| 共同交易日历史5日超额 | 1.19% |
| 共同交易日历史5日超额data_scope | latest_valid |
| 连续跑输天数 | 0 |
| 连续跑赢天数 | 5 |
| 相对趋势状态 | 连续强于港股医疗宽基 |

## 七、Policy_Risk_Layer 政策风险层

- Policy_Risk_Layer 不进入 S2_event_score，不改变 S2_total，只进入 final_view 解释和反证层。
- 当前状态：政策风险升高。

| event_name | event_date | region | affected_chain | risk_direction | severity | status | affected_symbols | source_url | last_checked_date | explanation |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BIOSECURE | 2025-12-18 | US | procurement_supply_chain_risk | risk_up | high | effective | 603259.SH\|02269.HK | https://www.bakermckenzie.com/en/insight/publications/2026/01/united-states-the-biosecure-act-becomes-law | 2026-06-08 | BIOSECURE已成为法律并形成美国政府采购/供应链合规风险；仅进入政策风险观察层，不进入S2正式分 |
| BINSA | 2026-06-02 | US | outbound_investment_BD_sentiment_risk | risk_up | medium | proposed | 600276.SH\|01801.HK\|09926.HK | https://chinaselectcommittee.house.gov/media/press-releases/moolenaar-dingell-introduce-legislation-to-prevent-offshoring-biotech-industry-to-china | 2026-06-08 | BINSA拟把生物技术纳入对外投资审查，可能压制BD出海风险偏好；仅进入政策风险观察层，不进入S2正式分 |

## 八、Macro_Risk_Layer 宏观资金层

- Macro_Risk_Layer 不进入 S2正式分，只用于解释交易转化强弱。
- macro_layer_status = valid；核心字段缺失 1/10（10%）。
- macro_risk_state = valid。

| 状态 | 数值 |
| --- | ---: |
| snapshot_date | 2026-06-09 |
| macro_layer_status | valid |
| risk_off_defensive | false |
| ai_crowding_unwind | false |
| biotech_relative_strength | true |
| hk_innovation_vs_health | positive |

| 资产 | 日度/窗口变化 |
| --- | ---: |
| QQQ_pct | 1.56% |
| SOXX_pct | 5.87% |
| SMH_pct | 5.00% |
| XBI_pct | -0.19% |
| IBB_pct | -0.90% |
| XLV_pct | -0.24% |
| XLP_pct | -0.44% |
| XLU_pct | -1.87% |
| US10Y_change | -0.09% |
| DXY_pct | -0.34% |
| HSTECH_pct | missing |
| ETF_159557_pct | -0.76% |
| ETF_159567_pct | 0.34% |
| data_source | hk_cache+yahoo_chart |
| source_status | QQQ_pct:success；SOXX_pct:success；SMH_pct:success；XBI_pct:success；IBB_pct:success；XLV_pct:success；XLP_pct:success；XLU_pct:success；US10Y_change:success；DXY_pct:success；HSTECH_pct:HTTPError: HTTP Error 404: Not Found；ETF_159557_pct:success；ETF_159567_pct:success |

## 十、科技成长—创新药风格

该模块独立于 S2 产业评分，只判断资金风格和独立性，不改 S2-01 至 S2-06 权重。

- TECH_GROWTH_CORE = 588000.SH；创新药主对象 = 159567.SZ；医疗宽基对照 = 159557.SZ。
- S2_INDUSTRY = 0.60；S2_STYLE = 0.34；S2_TOTAL = 0.54。
- style_level = 被动承接；style_regime = NEUTRAL；data_status = valid。
- negative_rotation_flag = false；missing_reason = none。
- 结论：当前科技成长—创新药风格为中性：尚未形成稳定的独立主线或跷跷板证据。

| 周期 | 159567收益 | TECH_GROWTH_CORE收益 | 159567 vs 科技成长 | 159567 vs 159557 | independence | 状态 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 1D | 1.19% | 4.02% | -2.83% | 0.16% | 0.70 | TECH_UP_BIO_UP_LAGS_TECH |
| 3D | -2.79% | 9.38% | -12.17% | 0.03% | 0.15 | TECH_UP_BIO_DOWN |
| 5D | 1.19% | 14.86% | -13.67% | 1.19% | 0.70 | TECH_UP_BIO_UP_LAGS_TECH |
| 10D | -3.73% | 10.10% | -13.83% | 0.74% | 0.15 | TECH_UP_BIO_DOWN |
| 20D | -13.81% | 8.44% | -22.25% | -1.68% | 0.15 | TECH_UP_BIO_DOWN |

| 辅助指标 | 数值 |
| --- | ---: |
| corr_10d | 0.32 |
| corr_20d | -0.05 |
| corr_60d | 0.17 |
| bio_avg_ret_when_tech_up_20d | -1.24% |
| bio_avg_ret_when_tech_down_20d | -0.46% |
| bio_excess_when_tech_up_20d | -3.95% |
| bio_excess_when_tech_down_20d | 2.87% |
| bio_avg_ret_when_tech_up_60d | 0.04% |
| bio_avg_ret_when_tech_down_60d | -1.08% |
| bio_excess_when_tech_up_60d | -2.36% |
| bio_excess_when_tech_down_60d | 1.38% |

- 60日累计收益图：/Users/pan/Desktop/research/0workspace/QuantPilot/s2/output/charts/style_cumulative_2026-06-18.svg
- 60日超额曲线图：/Users/pan/Desktop/research/0workspace/QuantPilot/s2/output/charts/style_excess_2026-06-18.svg

## 十一、AI/科技成长—创新药严格验证

该模块使用最近最多250个共同有效交易日，分别验证科技成长虹吸、AI虹吸、AI回调轮动、A股领先港股和右侧确认，不进入原S1/S2正式评分。

- 报告日期：2026-06-18；A股数据日期：20260618；港股数据日期：20260618；对应美股收盘日期：20260617。
- TECH_GROWTH_CORE版本：TECH_GROWTH_CORE_V1；数据日期：20260618。
- AI_CORE版本：AI_GLOBAL_V1；AI_CORE数据日期：20260617|20260618；有效样本数：211。
- 科技成长状态：TECH_GROWTH_3D_PLUS_UP；AI状态：AI_INTERNAL_ROTATION；市场状态：RISK_ON。
- 右侧确认评分：23.54；等级：无右侧；置信度：high；score_status=valid；feature_coverage=1.00000000。
- 核心指数状态：VALID。
- 当前命题状态：weakened；仓位动作标签：reduce。
- 最强支持证据：159567当日跑赢159557 0.16%；159567当日绝对上涨 1.19%；S1-05广度达到46.67%。
- 最强反对证据：科技成长上涨时159567跑输TECH_GROWTH_CORE -2.83%；AI_CORE上涨时159567跑输AI_CORE -1.29%；S2_conversion_score=0.50，交易转化未确认。
- 验证日报：/Users/pan/Desktop/research/0workspace/QuantPilot/s2/output/ai_biotech_validation_report.md
- 审计报告：/Users/pan/Desktop/research/0workspace/QuantPilot/s2/output/ai_biotech_audit_report.md

## 九、HK_observation反证层_159567

- 本层只输出159567相对159557的客观状态、反证与待验证项，不输出买卖建议。
- 产业事件是否有效：是，S2_event_score=0.65。
- 交易转化是否确认：否，S2_conversion_score=0.50。
- 159567 是否强于 159557：港股创新药ETF强于港股医疗宽基。
- 今日是否出现反证信号：是。
  - BD出海估值折价风险
  - 港股创新药风险偏好压制

| 临床事件 | 标的 | 相关性 | 成熟状态 | 个股5日 | 个股-159567 | 个股-159567_scope | 个股-159557 | 159567-159557 | 159567-159557_scope |
| --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | --- |
| 康方生物 / ivonescimab HARMONi-6 | 9926.HK | high | mature_calculable | -5.08% | 0.40% | latest_valid | -1.03% | -1.43% | latest_valid |
| 科伦博泰 / sacituzumab tirumotecan (sac-TMT) OptiTROP-Lung05 | 6990.HK | high | mature_calculable | -14.85% | -6.02% | latest_valid | -8.49% | -2.48% | latest_valid |
| 科伦博泰 / lunbotinib fumarate (A400/EP0031) | 6990.HK | high | mature_deduped_duplicate | -14.85% | -6.02% | latest_valid | -8.49% | -2.48% | latest_valid |
| 康方生物 / ivonescimab HARMONi-6 | 9926.HK | high | mature_calculable | -20.41% | 数据缺失 | missing | -11.68% | 数据缺失 | missing |
| 迪哲医药 / DZD6008 and golidocitinib plus anti-PD-1 | 688192.SH | medium | mature_calculable | -22.32% | 数据缺失 | missing | -13.59% | 数据缺失 | missing |
| 康宁杰瑞 / anbenitamab (KN026) plus HB1801 | 9966.HK | high | mature_calculable | -19.78% | 数据缺失 | missing | -11.06% | 数据缺失 | missing |
| 先声再明 / SIM0505 (CDH6 ADC) | 2096.HK | high | mature_calculable | -4.19% | 数据缺失 | missing | 4.03% | 数据缺失 | missing |
| 亚盛医药 / olverembatinib (HQP1351) plus blinatumomab | 6855.HK | high | mature_calculable | -9.96% | 数据缺失 | missing | -1.23% | 数据缺失 | missing |
| 科伦博泰 / SKB500 (B7-H3 ADC) | 6990.HK | high | mature_calculable | 0.70% | 数据缺失 | missing | 4.74% | 数据缺失 | missing |
| 信达生物 / IBI343 (arcotatug vedotin) | 01801.HK | high | mature_calculable | -4.52% | 数据缺失 | missing | -0.04% | 数据缺失 | missing |

## 十二、第四层：final_view_客观状态汇总

- C；C1；产业事件侧符合预期，BD频率与金额质量均符合预期；交易转化修复中，但未确认；A股温度计中性，S1=0.61；latest_valid，港股创新药 ETF 最近 5 个交易日强于港股医疗宽基。；政策风险升高；risk_off_defensive=false；ai_crowding_unwind=false；biotech_relative_strength=true；hk_innovation_vs_health=positive
- final_view_code = C
- final_view_sub_code = C1
- final_view_code_dict：A = 产业强 + 交易强；B = 产业中性 + 交易改善；C = 产业强 + 交易弱；D = 产业弱 + 交易弱；E = 数据不足 / 待验证。
- final_view_sub_code_dict：C1 = 产业强 + 交易弱但有修复；C2 = 产业强 + 交易弱且恶化；C3 = 产业强 + 总分改善但关键确认项失败。
- industry_event_state = 产业事件侧符合预期，BD频率与金额质量均符合预期
- conversion_state = 交易转化修复中，但未确认
- a_share_temperature_state = A股温度计中性，S1=0.61
- hk_observation_state = latest_valid，港股创新药 ETF 最近 5 个交易日强于港股医疗宽基。
- hk_relative_state = 159567近5日强于159557
- policy_risk_state = 政策风险升高
- macro_risk_state = risk_off_defensive=false；ai_crowding_unwind=false；biotech_relative_strength=true；hk_innovation_vs_health=positive
- main_positive_factors = BD频率符合预期；BD金额质量符合预期；产业事件侧得分0.65；HK_observation=latest_valid
- main_negative_factors = S2_conversion_score=0.50，修复但未确认；Policy_Risk_Layer=risk_up
- next_validation_dates = 
- final_view 只做客观状态汇总，不参与评分，不包含交易建议。
- 本报告不输出买卖建议；159567是否右侧必须以159567 vs 159557同步行情为准。

## 十三、数据缺失与待验证事项

- 具备一致预期来源的业绩样本缺失

## 十四、缺口治理

- 外部来源缺口：S2-03b 需要接入可靠一致预期来源；仅有同比增长不能替代 beat / miss。

## 十五、客观观察条件

### 基本面条件
- S1_total >= 0.60：满足，改善，当前0.61。
- S1-02 份额变化 >= 0：满足，当前5.59%。
- S1-05 板块广度 >= 40%：满足，当前46.67%。
- S2_event_score >= 0.60：满足，改善，当前0.65。

### 交易转化条件
- S2_conversion_score >= 0.60：未满足，交易转化修复中，但未确认，当前0.50。
- S2-04 去重正式样本 >= 3：满足，当前9个；raw_mature_event_count=10。
- S2-04 success_rate > 0：满足，success_count=2，success_rate=22.22%。
- S2-05 龙头接力中位超额收益 >= 0：满足，持平，当前0.78%。

### 持仓标的条件
- 159567 vs 159557 同步行情：满足，HK_observation_status=latest_valid。
- 159567 近5日强于159557：满足，最新判断超额=1.19%；共同交易日历史超额=1.19%。

### 数据质量条件
- HK日期同步：latest_date_159567=20260618；latest_date_159557=20260618；common_trade_date=20260618。
- S2-03b一致预期：missing；具备一致预期来源的业绩样本缺失。
- S2-06商业化兑现质量：scorable_low_confidence；商业化核心公司指标达到最低评分覆盖，但完整度或来源置信度偏低：6/6；关键字段完整度=50%；非官方/媒体来源样本=4；缺失字段保留missing。
- Macro_Risk_Layer：valid；核心字段缺失 1/10，macro_risk_state=valid。

### 不可判定
- 159567 是否右侧：无。
- 一致预期验证：S2-03b missing。
- 商业化兑现完整性：S2-06 scorable_low_confidence。
- 宏观资金环境：无。

## 十六、复核清单

- S2分数来自本地事件库和行情计算，不靠临场主观重打分。
- 新事件必须由智能体联网查证后写入事件库。
- 缺失数据保留为“数据缺失”，不编造。
- S2仅呈现客观产业验证结果，不输出仓位或交易建议。
- 本报告不输出买卖建议；159567是否右侧必须以159567 vs 159557同步行情为准。
