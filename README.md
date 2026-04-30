# 创新药投资阶段评价量化系统

基于 Tushare 数据源的创新药投资第一阶段量化指标计算系统。

## 环境设置

使用 uv 管理 Python 包依赖：

```bash
# 安装依赖
uv sync

# 运行 API 服务
uv run python -m wb.api_server
```

## 数据源

系统使用两种数据源：
- **citydata 代理**: fund_daily, fund_share, fund_portfolio (ETF数据)
- **官方 Tushare**: hk_daily (港股日线，120积分可用)

## 第一阶段指标

| 指标代码 | 指标名称 | 权重 | 数据源 |
|---------|---------|-----|-------|
| S1-01 | 资金回流连续性 | 0.22 | fund_share |
| S1-02 | ETF份额变化 | 0.18 | fund_share |
| S1-03 | ETF相对强度 | 0.20 | fund_daily |
| S1-04 | 成交放大持续性 | 0.14 | fund_daily |
| S1-05 | 板块广度修复 | 0.14 | fund_portfolio + hk_daily |
| S1-06 | 龙头先行强度 | 0.12 | hk_daily |

## API 端点

- `/` - 系统信息
- `/health` - 健康检查
- `/indicators` - 指标列表
- `/calculate` - 计算所有指标
- `/calculate/{code}` - 计算单个指标

## 配置

在 `.env` 文件中设置：
- `TUSHARE_TOKEN`: 官方 Tushare token
- `CITYDATA_TOKEN`: citydata 代理 token