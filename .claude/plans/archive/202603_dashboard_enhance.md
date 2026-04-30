# 可视化界面增强

## 目标

在 dashboard.py 中增加4个模块，丰富界面内容。

---

## 模块1：ETF行情数据

**展示内容**：
- 价格走势图：589720.SH 收盘价折线图
- 成交额柱状图：近20日成交额
- 份额变化图：fund_share 趋势
- 关键指标卡片：最新价、涨跌幅、成交额、份额

**数据来源**：
- `fund_daily.csv` - ts_code, trade_date, close, pct_chg, amount
- `fund_share.csv` - trade_date, fd_share

---

## 模块2：成分股详情

**展示内容**：
- 持仓表格：代码、权重、最新价、涨跌幅
- 龙头股收益贡献：前5大持仓对组合的贡献

**数据来源**：
- `fund_portfolio.csv` - symbol, stk_mkv_ratio
- `daily.csv` - ts_code, trade_date, close, pct_chg

---

## 模块3：广度指标明细

**展示内容**：
- 涨跌分布：上涨/下跌/平盘数量
- 个股强弱排名：按涨跌幅排序的成分股列表
- 均线突破明细：站上/跌破20日均线的股票

**数据来源**：
- `daily.csv` - 所有成分股数据

---

## 模块4：指标雷达图

**展示内容**：
- 六边形雷达图：6个指标值
- 颜色标注：每个指标的预期等级

**数据来源**：
- 已有指标计算结果

---

## 实现步骤

1. 添加数据加载函数：`load_fund_daily()`, `load_fund_share()`, `load_daily()`, `load_portfolio()`
2. 用 `st.tabs()` 组织4个tab页面
3. 实现各模块图表
4. 调整布局样式

## 修改文件

`wb/dashboard.py`

## 验证

```bash
uv run streamlit run wb/dashboard.py
```