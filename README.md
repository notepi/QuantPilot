# QuantPilot - 创新药投资阶段评价量化系统

基于 Tushare 数据源的 ETF 投资阶段量化评价系统，通过多维度指标计算帮助投资者识别不同阶段的投资机会。

## 项目定位

QuantPilot 是一个**阶段导向**的量化评价系统，核心思路：

```
投资决策 = 阶段识别 + 指标量化 + 信号确认
```

系统通过计算 6 个核心指标（资金回流、份额变化、相对强度、成交放大、广度修复、龙头先行），综合评价当前投资阶段的预期等级，辅助投资者做出更理性的决策。

## 核心功能

### 1. 数据更新
自动获取并更新多维度数据：
- **ETF 日线行情**: 价格、成交额（标的 + 基准）
- **ETF 份额数据**: 份额变化追踪
- **ETF 持仓成分股**: 持仓明细
- **成分股日线行情**: 个股行情数据

### 2. 指标计算
第一阶段（预期重定价）的 6 个量化指标：

| 指标代码 | 指标名称 | 权重 | 数据源 | 阈值 |
|---------|---------|-----|-------|------|
| S1-01 | 资金回流连续性 | 22% | fund_share | ≥70% 超预期 |
| S1-02 | ETF 份额变化 | 18% | fund_share | ≥3% 超预期 |
| S1-03 | ETF 相对强度 | 20% | fund_daily | ≥5% 超预期 |
| S1-04 | 成交放大持续性 | 14% | fund_daily | ≥1.5x 超预期 |
| S1-05 | 板块广度修复 | 14% | fund_portfolio | ≥60% 超预期 |
| S1-06 | 龙头先行强度 | 12% | hk_daily | ≥5% 超预期 |

### 3. 日报生成
自动生成指标日报（Markdown 格式）：
- 30 天历史数据对比
- 预期等级可视化（🟢 超预期 / 🟡 符合预期 / 🔴 低于预期）
- 趋势分析和关注点提示

### 4. API 服务
FastAPI 接口，支持：
- `/health` - 健康检查
- `/indicators` - 指标列表
- `/calculate` - 计算所有指标
- `/calculate/{code}` - 计算单个指标

### 5. 可视化界面
Streamlit Dashboard，提供交互式数据探索。

## 快速开始

### 安装依赖

```bash
# 使用 uv 安装依赖（推荐）
uv sync

# 或使用 pip
pip install -r requirements.txt
```

### 配置环境

创建 `.env` 文件：

```bash
# 必需：数据源配置
CITYDATA_TOKEN=your_citydata_token
TUSHARE_TOKEN=your_tushare_token
```

### 一键运行

```bash
# 更新数据 → 计算指标 → 生成日报
uv run python -m wb.daily_flow
```

### 分步执行

```bash
# 1. 更新数据
uv run python -m wb.update_data

# 2. 计算指标
uv run python -m wb.calculate_indicators

# 3. 生成日报
uv run python -m wb.generate_report
```

### 启动服务

```bash
# API 服务
uv run python -m wb.api_server

# 可视化界面
uv run streamlit run wb/dashboard.py
```

## 项目结构

```
QuantPilot/
├── wb/                     # 核心模块
│   ├── daily_flow.py       # 一键流程入口
│   ├── update_data.py      # 数据更新
│   ├── calculate_indicators.py  # 指标计算
│   ├── generate_report.py  # 日报生成
│   ├── api_server.py       # FastAPI 服务
│   ├── dashboard.py        # Streamlit 界面
│   └── indicators/         # 指标实现
│       ├── s1_01_capital_flow.py
│       ├── s1_02_share_change.py
│       ├── s1_03_relative_strength.py
│       ├── s1_04_volume_ratio.py
│       ├── s1_05_breadth_repair.py
│       └── s1_06_leader_strength.py
├── data/                   # 数据目录
│   ├── raw/                # 原始数据 CSV
│   └── indicators/         # 指标结果 JSON
├── docs/                   # 文档目录
│   ├── usage.md            # 使用指南
│   ├── indicators.md       # 指标定义
│   ├── daily_report.md     # 指标日报
│   └── dashboard_prd.md    # 界面设计
├── tests/                  # 测试目录
├── pyproject.toml          # 项目配置
└── CLAUDE.md               # Claude 协作指南
```

## 扩展性设计

QuantPilot 采用模块化设计，支持扩展到更多场景：

### 标的扩展
切换不同的 ETF 标的，只需修改配置：
- 创新药 ETF → 医药 ETF、新能源 ETF、半导体 ETF...
- 基准 ETF 可自由选择

### 阶段扩展
系统支持多阶段评价体系：
- **Phase 1**: 预期重定价阶段（当前）
- **Phase 2**: 趋势确认阶段（可扩展）
- **Phase 3**: 动量加速阶段（可扩展）

### 指标扩展
新增指标只需：
1. 在 `wb/indicators/` 创建新模块
2. 实现 `BaseIndicator` 接口
3. 注册到 `score_engine.py`

```python
class NewIndicator(BaseIndicator):
    code = "S1-07"
    name = "新指标名称"
    weight = 0.10

    def calculate(self, data):
        # 计算逻辑
        return value
```

## 数据源说明

| 数据类型 | 数据源 | 说明 |
|---------|-------|------|
| ETF 行情 | citydata 代理 | 需要 CITYDATA_TOKEN |
| ETF 份额 | citydata 代理 | 需要 CITYDATA_TOKEN |
| ETF 持仓 | citydata 代理 | 需要 CITYDATA_TOKEN |
| 港股日线 | Tushare 官方 | 需要 TUSHARE_TOKEN（120积分） |

## 评分规则

综合得分 = Σ(指标得分 × 权重)

| 综合得分 | 预期等级 | 说明 |
|----------|----------|------|
| ≥0.80 | 🟢 超预期 | 多个指标强势共振 |
| 0.60-0.80 | 🟡 符合预期 | 指标表现正常 |
| 0.40-0.60 | 🔴 低于预期 | 部分指标偏弱 |
| <0.40 | ⚠️ 严重低于预期 | 需谨慎观察 |

## 文档索引

- [使用指南](docs/usage.md) - 命令详细说明
- [指标定义](docs/indicators.md) - 指标口径说明
- [日报示例](docs/daily_report.md) - 最新日报
- [界面设计](docs/dashboard_prd.md) - Dashboard PRD

## 技术栈

- **Python 3.11+**
- **FastAPI** - API 服务
- **Streamlit** - 可视化界面
- **uv** - 包管理（替代 pip）

## License

MIT License

## Author

QuantPilot Team