# 文件结构

```
quant-Claude-KAC/
├── CLAUDE.md
├── pyproject.toml
├── .env
├── .claude/plans/
│   ├── active/
│   └── archive/
├── data/
│   ├── raw/
│   │   ├── fund_daily.csv
│   │   ├── fund_share.csv
│   │   ├── fund_portfolio.csv
│   │   └── daily.csv
│   └── indicators/
├── docs/
│   ├── file_structure.md
│   ├── usage.md
│   ├── indicators.md
│   ├── daily_report.md
│   ├── dashboard_prd.md
│   └── 创新药_第一阶段_v2_claude.xlsx
├── wb/
│   ├── update_data.py
│   ├── calculate_indicators.py
│   ├── generate_report.py
│   ├── data_fetcher.py
│   ├── score_engine.py
│   ├── api_server.py
│   ├── dashboard.py
│   ├── tushare_proxy.py
│   └── indicators/
│       ├── s1_01_capital_flow.py
│       ├── s1_02_share_change.py
│       ├── s1_03_relative_strength.py
│       ├── s1_04_volume_ratio.py
│       ├── s1_05_breadth_repair.py
│       └── s1_06_leader_strength.py
└── tests/
```