# CLAUDE.md 文件结构和文档索引优化

## 目标

将目录树移到 docs/file_structure.md，CLAUDE.md 只保留精简的文档索引。

---

## 修改内容

### 1. 创建 docs/file_structure.md

纯目录树文件：

```markdown
# 文件结构

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
```

### 2. CLAUDE.md 删除文件结构章节

删掉 `## 文件结构` 及目录树内容。

### 3. CLAUDE.md 文档索引改为列表形式

```
## 文档索引

- docs/file_structure.md - 项目文件目录结构
- docs/usage.md - 命令使用指南（每日流程、回测、API、界面）
- docs/indicators.md - 指标定义与阈值（S1-01~S1-06 口径说明）
- docs/daily_report.md - 指标日报（横轴指标，纵轴日期）
- docs/dashboard_prd.md - 可视化界面PRD（5模块设计）
- docs/创新药_第一阶段_v2_claude.xlsx - 指标详细定义（业务口径）
- .claude/plans/archive/ - 历史开发计划
```

---

## 预期效果

- CLAUDE.md：从 81 行 → 约 50 行（删除目录树）
- 新增 docs/file_structure.md：约 35 行纯目录树
- 文档索引：列表形式，增加说明内容