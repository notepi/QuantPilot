# S3 - AI风格轮动模块

## 职责

独立运行 AI/科技成长 vs 创新药风格轮动分析，不依赖 S2 产业验证模块。

## 数据源

| 数据 | 路径 | 说明 |
|------|------|------|
| 市场行情 | `data/processed/market_daily.csv` | ETF 行情（A 股 + 港股） |
| 宏观行情 | `data/processed/macro_market_daily.csv` | 海外 ETF/指数 |
| S1 指标 | `data/indicators/*.json` | 资金面信号 |
| S2 分数 | `s2/output/s2_scores.csv` | 产业验证分数（只读） |
| 配置 | `s3/config.json` | 风格轮动配置 |
| AI 核心版本 | `s3/versions.json` | AI_CORE 和 TECH_GROWTH_CORE 版本化定义 |

## 模块结构

| 文件 | 说明 |
|------|------|
| `style_rotation.py` | 风格轮动计算引擎 |
| `validation.py` | AI vs 创新药验证层 |
| `generate_report.py` | 报告生成入口 |
| `s1_reader.py` | S1 数据读取 |
| `daily_flow.py` | 独立运行入口 |
| `config.json` | 风格轮动配置 |
| `versions.json` | 核心指数版本定义 |

## 运行方式

```bash
# 独立运行 S3 报告
uv run python -m s3.generate_report

# 或通过 daily_flow
uv run python -m s3.daily_flow
```

## 输出

| 文件 | 说明 |
|------|------|
| `s3/output/ai_style_daily_report.md` | 当日风格日报 |
| `s3/output/ai_style_reports/*.md` | 按日期归档 |
| `s3/output/ai_biotech_*.csv` | 验证统计输出 |
| `s3/output/charts/*.svg` | 累计收益和超额收益图 |

## 迁移说明

S3 模块从 s2/ 迁移而来，s2 中的遗留文件和兼容 wrapper 已清除：
- `s2/generate_ai_style_report.py` → 已删除（daily_flow 直接调用 s3）
- `s2/style_rotation.py` → 已删除（s3/style_rotation.py 为正式版）
- `s2/ai_biotech_validation.py` → 已删除（s3/validation.py 为正式版）
- `s2/style_config.json` → 已删除（s3/config.json 为正式版）
- `s2/ai_core_versions.json` → 已删除（s3/versions.json 为正式版）
- 测试已从 s2/tests/ 迁移到 s3/tests/
