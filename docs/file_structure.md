# 文件结构

```
QuantPilot/
├── CLAUDE.md
├── pyproject.toml
├── .env
├── .claude/plans/
│   ├── active/
│   └── archive/
├── data/
│   ├── raw/
│   │   ├── fund_daily.csv          # ETF 日线行情（589720/159557/159567）
│   │   ├── fund_share.csv          # ETF 份额数据（含 source 字段）
│   │   ├── fund_portfolio.csv      # ETF 持仓成分股
│   │   └── daily.csv               # A 股成分股日线
│   ├── processed/
│   │   ├── market_daily.csv        # 处理后市场行情
│   │   └── macro_market_daily.csv  # 处理后宏观/海外行情
│   └── indicators/
│       └── YYYYMMDD.json           # S1 指标计算结果（含 data_date）
├── docs/
│   ├── file_structure.md
│   ├── usage.md
│   ├── indicators.md
│   ├── daily_report.md             # S1 指标日报（自动生成）
│   ├── dashboard_prd.md
│   ├── data_governance_plan.md
│   ├── data_governance_audit.md
│   ├── report_semantic_audit.md
│   ├── daily_update_runbook.md
│   ├── api.md
│   ├── architecture.md
│   └── 创新药_第一阶段_v2_claude.xlsx
├── wb/                              # S1 模块：资金面观察
│   ├── update_data.py              # 数据抓取（含多源降级）
│   ├── calculate_indicators.py     # 指标计算
│   ├── generate_report.py          # S1 日报生成
│   ├── daily_flow.py               # S1 统一入口
│   ├── data_fetcher.py
│   ├── score_engine.py
│   ├── api_server.py
│   ├── dashboard.py
│   ├── tushare_proxy.py
│   └── indicators/
│       ├── base.py                 # BaseIndicator + IndicatorResult（含 data_date）
│       ├── s1_01_capital_flow.py
│       ├── s1_02_share_change.py
│       ├── s1_03_relative_strength.py
│       ├── s1_04_volume_ratio.py
│       ├── s1_05_breadth_repair.py
│       └── s1_06_leader_strength.py
├── s2/                              # S2 模块：产业验证（代码 + 智能体）
│   ├── generate_s2_report.py       # S2 日报生成
│   ├── daily_report_flow.py        # S1→S2→S3 统一入口
│   ├── update_market_data.py       # 港股 ETF 缓存刷新
│   ├── build_data_layer.py         # S2 行情/宏观/审计数据层
│   ├── event_store.py              # 事件库写入接口
│   ├── agent_task.md               # S2 产业验证智能体任务
│   ├── generate_ai_style_report.py # 兼容 wrapper → 转发到 s3
│   ├── ai_biotech_validation.py    # 原验证模块（S2 不直接 import）
│   ├── style_rotation.py           # 原风格模块（S2 不直接 import）
│   ├── data/
│   │   ├── bd_events.csv           # BD 事件库
│   │   ├── clinical_events.csv     # 临床事件库
│   │   ├── earnings_events.csv     # 业绩事件库
│   │   ├── regulatory_events.csv   # 审批事件库
│   │   ├── policy_risk_events.csv  # 政策风险库
│   │   ├── earnings_consensus.csv  # 一致预期表
│   │   ├── leader_pool.csv         # A 股龙头池
│   │   └── hk_daily.csv            # 港股个股日线
│   ├── output/
│   │   ├── reports/YYYY-MM-DD.md   # S2 产业验证日报
│   │   ├── watchlist.md            # S2 观察线索池（不进入正式评分）
│   │   ├── agent_runs/YYYY-MM-DD.md # 智能体扫描留痕
│   │   ├── hk_cache/               # 港股 ETF 缓存
│   │   ├── data_audit/             # 数据审计文件
│   │   ├── s2_scores.csv           # S2 分数
│   │   └── s2_item_scores.csv      # S2 各指标分
│   └── tests/
├── s3/                              # S3 模块：AI 风格轮动
│   ├── generate_report.py          # S3 日报生成
│   ├── daily_flow.py               # S3 独立入口
│   ├── style_rotation.py           # 风格轮动计算引擎
│   ├── validation.py               # AI vs 创新药验证层
│   ├── s1_reader.py                # S1 数据读取
│   ├── config.json                 # 风格轮动配置
│   ├── versions.json               # AI_CORE / TECH_GROWTH_CORE 版本定义
│   ├── README.md
│   └── output/
│       ├── ai_style_daily_report.md # S3 AI 风格日报
│       ├── ai_style_reports/*.md    # 按日期归档
│       ├── ai_biotech_*.csv         # 验证统计输出
│       └── charts/*.svg             # 累计收益和超额收益图
└── reports/
    └── data_quality_report.md
```
