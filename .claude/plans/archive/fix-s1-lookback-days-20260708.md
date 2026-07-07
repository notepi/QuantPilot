# S1-01~06 交易日数量修复计划

## 一、前因后果

### 1.1 问题发现

用户在审阅 S1 计划时，要求我检查 S1-01 算的是几天的数据。

分析代码后发现：**S1-01 没有限制只计算近10个交易日**，而是计算了获取到的所有交易日。

进一步检查 S1-02、S1-03、S1-06，发现都有同样的问题。

### 1.2 问题根源

**设计意图**（Excel 定义）：
- S1-01：近**10个交易日**份额增加天数占比
- S1-02：近**10个交易日**份额变化率
- S1-03：近**10个交易日**相对强度
- S1-06：近**10个交易日**龙头强度

**实际实现**：
```python
# s1_01_capital_flow.py
start_date = self._get_start_date(end_date, self.LOOKBACK_DAYS)  # end_date - 20个自然日
df = self.data_fetcher.get_fund_share(ts_code, start_date, end_date)
df = df.sort_values("trade_date")  # 没有 .tail(N)
positive_days = (df["share_change"].dropna() > 0).sum()
total_days = len(df["share_change"].dropna())  # 可能是 12、14、15 天
```

**问题本质**：
- `_get_start_date` 计算 `end_date - LOOKBACK_DAYS * 2`（预留空间）
- 获取这个范围内的**所有**数据
- 计算时没有限制只取最近10个交易日

### 1.3 影响范围

| 指标 | 是否受影响 | 说明 |
|------|-----------|------|
| S1-01 | ✗ 有问题 | 计算所有获取到的交易日 |
| S1-02 | ✗ 有问题 | 同上 |
| S1-03 | ✗ 有问题 | 收益率用第一天到最后一天 |
| S1-04 | ✓ 正确 | 使用 `.iloc[-5:]` 和 `.iloc[-20:]` |
| S1-05 | ✓ 正确 | 口径不同 |
| S1-06 | ✗ 有问题 | 同 S1-03 |

---

## 二、参考项目：phosphate

### 2.1 项目路径

```
/Users/pan/Desktop/research/0workspace/phosphate
```

### 2.2 参考的文件和代码

#### 文件1：`phos_etf/indicators.py`

**S1-01（第54-66行）**：phosphate 用逐日判断，不是份额 diff
```python
# 获取近10个交易日
df = self._nav_df[self._nav_df["trade_date"] <= int(trade_date)].tail(10)
dates = df["trade_date"].astype(str).tolist()

flow_days = 0
total_days = len(dates)

for date in dates:
    _, _, _, is_flow_day = self.synthesizer.synthesize_flow_intensity(...)
    if is_flow_day:
        flow_days += 1
```

**注意**：phosphate 的 S1-01 不是份额 diff，是逐日资金流判断。QuantPilot 用份额 diff，逻辑不同。

**S1-03（第101-112行）**：10日收益需要11个点
```python
nav_data = self._nav_df[self._nav_df["trade_date"] <= int(trade_date)]
if len(nav_data) < 11:
    return {"value": 0.0, "raw_data": {}}
nav_return = nav_data["nav"].iloc[-1] / nav_data["nav"].iloc[-11] - 1
```

**S1-06（第162-166行）**：同上
```python
if len(nav_data) < 11:
    return {"value": 0.0, "raw_data": {}}
nav_return = nav_data["nav"].iloc[-1] / nav_data["nav"].iloc[-11] - 1
```

#### 文件2：`phos_etf/synthesizer.py`

**S1-02（第182-186行）**：
```python
def synthesize_accumulated_flow(self, data, date, days: int = 10):
    trade_dates = self._get_recent_dates(data, date, days + 20)
    if len(trade_dates) < days:
        return 0.0, 0.0, 0
    recent_dates = trade_dates[-days:]  # 近10日（含当日）
```

### 2.3 核心模式

| 场景 | 需要的数据点 | 原因 |
|------|-------------|------|
| 计算 10 日收益 | **11个** | `iloc[-1] / iloc[-11]` |
| 计算份额 diff 得 10 个变化 | **11个** | diff 产生 N-1 个变化 |
| 取最近 N 个交易日 | **N个** | 直接 `.tail(N)` |

---

## 三、修复方案（第三版）

### 3.1 S1-01 修复

**文件**：`wb/indicators/s1_01_capital_flow.py`

**口径分析**：
- 目标：近**10个交易日**份额增加天数占比
- 当前实现：`fd_share.diff()` 判断份额变化
- **关键问题**：10 条份额数据只能产生 **9 个变化样本**

**修复方案**：
```python
# 修改前
df = df.sort_values("trade_date")

# 修改后 - 取最近11条份额记录，diff后得到10个变化日
df = df.sort_values("trade_date").tail(self.LOOKBACK_DAYS + 1)

# diff 计算
df["share_change"] = df["fd_share"].diff()

# 统计份额增加的天数（排除第一行 NaN）
positive_days = (df["share_change"].dropna() > 0).sum()
total_days = len(df["share_change"].dropna())  # 应该是 10

# 记录实际回看天数
actual_share_records = len(df)  # 应该是 11
actual_change_days = total_days  # 应该是 10
```

**新增 raw_data 字段**：
```python
raw_data={
    "positive_days": positive_days,
    "total_days": total_days,  # 应该是 10
    "actual_share_records": actual_share_records,  # 应该是 11
    "actual_change_days": actual_change_days,  # 应该是 10
    "expected_change_days": self.LOOKBACK_DAYS,  # 10
    "share_changes": df["share_change"].dropna().tolist(),
}
```

---

### 3.2 S1-02 修复

**文件**：`wb/indicators/s1_02_share_change.py`

**口径分析**：
- 目标：近**10个交易日**份额变化率
- 如果要 10 日跨度变化率，应取 **11 条份额记录**

**修复方案**：
```python
# 修改前
df = df.sort_values("trade_date")
start_share = df["fd_share"].iloc[0]
end_share = df["fd_share"].iloc[-1]

# 修改后 - 取最近11条份额记录，计算10日跨度变化率
df = df.sort_values("trade_date").tail(self.LOOKBACK_DAYS + 1)
start_share = df["fd_share"].iloc[0]  # 11天前的份额
end_share = df["fd_share"].iloc[-1]   # 最新份额

# 记录实际天数
actual_share_records = len(df)  # 应该是 11
actual_trade_days = actual_share_records - 1  # 跨度天数，应该是 10
```

**新增 raw_data 字段**：
```python
raw_data={
    "start_share": start_share,
    "end_share": end_share,
    "share_change": end_share - start_share,
    "start_date": df["trade_date"].iloc[0],
    "end_date": df["trade_date"].iloc[-1],
    "actual_share_records": actual_share_records,  # 新增
    "actual_trade_days": actual_trade_days,  # 新增
    "expected_trade_days": self.LOOKBACK_DAYS,  # 新增
}
```

---

### 3.3 S1-03 修复（修正共同日期对齐顺序）

**文件**：`wb/indicators/s1_03_relative_strength.py`

**核心问题**：原 plan 先 `.tail(11)` 再取共同日期，可能导致共同日期不足 11 个。

**正确顺序**：
1. 在完整 fetched window 里取 ETF 和 benchmark 的共同交易日
2. 从共同交易日里取最近 11 个
3. 计算收益率

**修复方案**：
```python
# 1. 先获取数据（不限制数量）
etf_df = self.data_fetcher.get_fund_daily(
    ts_code=self.ETF_CODE,
    start_date=start_date,
    end_date=end_date
)

benchmark_df = self.data_fetcher.get_fund_daily(
    ts_code=self.BENCHMARK_CODE,
    start_date=start_date,
    end_date=end_date
)

# 2. 检查数据是否可用
if etf_df is None or len(etf_df) == 0 or benchmark_df is None or len(benchmark_df) == 0:
    return self.create_result(
        value=0.0,
        trade_date=end_date,
        data_date="",
        raw_data={
            "insufficient_data": True,
            "reason": "ETF 或 benchmark 数据获取失败",
        }
    )

# 3. 先取共同日期，再 tail(11)
etf_dates = set(etf_df["trade_date"].astype(str))
benchmark_dates = set(benchmark_df["trade_date"].astype(str))
common_dates = sorted(etf_dates & benchmark_dates, reverse=True)

if len(common_dates) < self.LOOKBACK_DAYS + 1:
    return self.create_result(
        value=0.0,
        trade_date=end_date,
        data_date="",
        raw_data={
            "insufficient_data": True,
            "reason": f"共同交易日不足，需要 {self.LOOKBACK_DAYS + 1} 个，实际 {len(common_dates)} 个",
            "etf_dates_count": len(etf_dates),
            "benchmark_dates_count": len(benchmark_dates),
            "common_dates_count": len(common_dates),
        }
    )

# 4. 从共同日期里取最近 11 个
common_dates = common_dates[:self.LOOKBACK_DAYS + 1]

# 5. 按共同日期过滤
etf_df = etf_df[etf_df["trade_date"].astype(str).isin(common_dates)].sort_values("trade_date")
benchmark_df = benchmark_df[benchmark_df["trade_date"].astype(str).isin(common_dates)].sort_values("trade_date")

# 6. 计算收益率（11 个数据点，计算 10 日收益）
etf_return = self._calc_return(etf_df["close"])
benchmark_return = self._calc_return(benchmark_df["close"])

# 7. 记录 data_date
data_date = str(min(etf_df["trade_date"].max(), benchmark_df["trade_date"].max()))
```

**修改 `_calc_return` 方法**：
```python
def _calc_return(self, prices: pd.Series) -> float:
    """计算 10 日收益率"""
    if len(prices) < 11:
        # 不应该发生，因为前面已经检查过共同日期
        return 0.0
    if prices.iloc[-11] == 0:
        return 0.0
    return (prices.iloc[-1] - prices.iloc[-11]) / prices.iloc[-11]
```

**新增 raw_data 字段**：
```python
raw_data={
    "etf_return": etf_return,
    "benchmark_return": benchmark_return,
    "common_dates_count": len(common_dates),
    "etf_start_close": etf_df["close"].iloc[0],
    "etf_end_close": etf_df["close"].iloc[-1],
    "benchmark_start_close": benchmark_df["close"].iloc[0],
    "benchmark_end_close": benchmark_df["close"].iloc[-1],
    "insufficient_data": False,  # 明确标记
}
```

---

### 3.4 S1-06 修复（与 ETF 日期窗口对齐 + 每只股票单独判断）

**文件**：`wb/indicators/s1_06_leader_strength.py`

**核心问题**：
1. 原 plan 要求所有龙头股和 ETF 都有共同日期，太严格
2. 当前 plan 每只股票只是自己 `len(stock_df) >= 11` 后直接算自己的最近 11 条，没有和 ETF 日期对齐

**修复方案**：
1. 先取 ETF 最近 11 个交易日作为 `etf_window_dates`
2. 每只股票只在 `etf_window_dates` 内过滤
3. 若该股窗口内不足 11 条，则跳过
4. 有效股票按剩余权重重归一化
5. raw_data 明确标记 `insufficient_data: True`

**修复代码**：
```python
# 1. 获取 ETF 数据
etf_df = self.data_fetcher.get_fund_daily(
    ts_code=self.ETF_CODE,
    start_date=start_date,
    end_date=end_date
)

if etf_df is None or len(etf_df) < self.LOOKBACK_DAYS + 1:
    return self.create_result(
        value=0.0,
        trade_date=end_date,
        data_date="",
        raw_data={
            "insufficient_data": True,
            "reason": "ETF 数据不足",
        }
    )

# 2. 先取 ETF 最近 11 个交易日作为窗口
etf_df = etf_df.sort_values("trade_date")
etf_window_dates = set(etf_df["trade_date"].astype(str).tail(self.LOOKBACK_DAYS + 1))

if len(etf_window_dates) < self.LOOKBACK_DAYS + 1:
    return self.create_result(
        value=0.0,
        trade_date=end_date,
        data_date="",
        raw_data={
            "insufficient_data": True,
            "reason": "ETF 窗口日期不足 11 个",
        }
    )

# 3. 计算 ETF 收益
etf_return = self._calc_return(etf_df["close"])

# 4. 获取龙头股数据
df_all = self.data_fetcher.get_daily_batch(
    ts_codes=self.LEADER_STOCKS,
    start_date=start_date,
    end_date=end_date
)

if df_all is None or len(df_all) == 0:
    return self.create_result(
        value=0.0,
        trade_date=end_date,
        data_date="",
        raw_data={
            "insufficient_data": True,
            "reason": "龙头股数据获取失败",
        }
    )

# 5. 计算每只龙头股收益（在 ETF 窗口内判断数据充足性）
leader_returns = []
leader_weights_used = []
leader_details = []

for code, weight in zip(self.LEADER_STOCKS, self.LEADER_WEIGHTS):
    stock_df = df_all[df_all["ts_code"] == code]
    
    # 只保留在 ETF 窗口内的数据
    stock_df_in_window = stock_df[stock_df["trade_date"].astype(str).isin(etf_window_dates)].sort_values("trade_date")

    if len(stock_df_in_window) < self.LOOKBACK_DAYS + 1:
        # 该股票在窗口内数据不足，跳过
        leader_details.append({
            "code": code,
            "return": 0.0,
            "weight": weight,
            "insufficient_data": True,
            "data_points_in_window": len(stock_df_in_window),
            "required_points": self.LOOKBACK_DAYS + 1,
        })
        continue

    # 计算该股票收益
    ret = self._calc_return(stock_df_in_window["close"])
    leader_returns.append(ret)
    leader_weights_used.append(weight)
    leader_details.append({
        "code": code,
        "return": ret,
        "weight": weight,
        "insufficient_data": False,
        "data_points_in_window": len(stock_df_in_window),
        "start_date": str(stock_df_in_window["trade_date"].iloc[-11]),
        "end_date": str(stock_df_in_window["trade_date"].iloc[-1]),
        "start_close": stock_df_in_window["close"].iloc[-11],
        "end_close": stock_df_in_window["close"].iloc[-1],
    })

# 6. 检查是否有足够的有效股票
if len(leader_returns) == 0:
    return self.create_result(
        value=0.0,
        trade_date=end_date,
        data_date="",
        raw_data={
            "insufficient_data": True,
            "reason": "所有龙头股在 ETF 窗口内数据均不足",
            "leader_details": leader_details,
        }
    )

# 7. 加权平均收益（使用有效股票的权重重归一化）
total_weight = sum(leader_weights_used)
weighted_return = sum(r * w for r, w in zip(leader_returns, leader_weights_used)) / total_weight

# 8. 计算龙头先行强度
leader_strength = weighted_return - etf_return

# 9. 记录 data_date（取最保守的日期）
etf_data_date = str(etf_df["trade_date"].max())
stock_data_dates = [d["end_date"] for d in leader_details if not d.get("insufficient_data")]
data_dates = [etf_data_date] + stock_data_dates
actual_data_date = min(data_dates) if data_dates else ""

return self.create_result(
    value=leader_strength,
    trade_date=end_date,
    data_date=actual_data_date,
    raw_data={
        "leader_weighted_return": weighted_return,
        "etf_return": etf_return,
        "leader_details": leader_details,
        "valid_stocks_count": len(leader_returns),
        "total_stocks": len(self.LEADER_STOCKS),
        "etf_window_dates_count": len(etf_window_dates),
        "insufficient_data": False,
    }
)
```

**修改 `_calc_return` 方法**：
```python
def _calc_return(self, prices: pd.Series) -> float:
    """计算 10 日收益率"""
    if len(prices) < 11:
        return 0.0
    if prices.iloc[-11] == 0:
        return 0.0
    return (prices.iloc[-1] - prices.iloc[-11]) / prices.iloc[-11]
```

---

### 3.5 数据不足的处理规范

**问题**：S1-03/S1-06 数据不足时返回 `0.0`，但 `threshold_meet = 0.0`，会被误判为"符合预期"。

**解决方案**：
1. **raw_data 必须包含 `insufficient_data: True`**
2. **本次先在 raw_data 标记，日报展示另做后续**（需要修改 `to_dict()` 序列化和日报生成逻辑，不在本次修复范围）
3. **评分层识别数据不足**（后续优化）

**示例**：
```python
# 数据不足时
return self.create_result(
    value=0.0,
    trade_date=end_date,
    data_date="",
    raw_data={
        "insufficient_data": True,
        "reason": "共同交易日不足 11 个",
    }
)

# 数据正常时
return self.create_result(
    value=leader_strength,
    trade_date=end_date,
    data_date=actual_data_date,
    raw_data={
        "insufficient_data": False,
        ...
    }
)
```

---

## 四、修复文件清单

| 文件 | 修改内容 | 关键修正 |
|------|---------|---------|
| `wb/indicators/s1_01_capital_flow.py` | `.tail(11)`，diff 得 10 个变化日 | - |
| `wb/indicators/s1_02_share_change.py` | `.tail(11)`，10 日跨度变化率 | - |
| `wb/indicators/s1_03_relative_strength.py` | 先取共同日期再 tail(11)；raw_data 标记 insufficient_data | **用户反馈修正** |
| `wb/indicators/s1_06_leader_strength.py` | 每只股票单独判断；raw_data 标记 insufficient_data | **用户反馈修正** |

---

## 五、验证方案

### 5.1 单元测试

**测试文件**：`tests/test_s1_lookback.py`

```python
def test_s1_01_change_days():
    """验证 S1-01 diff 产生 10 个变化日"""
    result = indicator.calculate("20260707")
    assert result.raw_data["expected_change_days"] == 10
    assert result.raw_data["actual_change_days"] == 10
    assert result.raw_data["actual_share_records"] == 11

def test_s1_03_common_dates_order():
    """验证 S1-03 先取共同日期再 tail"""
    result = indicator.calculate("20260707")
    # 检查 raw_data 中的共同日期数量
    assert result.raw_data["common_dates_count"] == 11
    assert result.raw_data["insufficient_data"] == False

def test_s1_06_etf_window_alignment():
    """验证 S1-06 龙头股与 ETF 窗口日期对齐"""
    result = indicator.calculate("20260707")
    # 检查 raw_data 中是否有 insufficient_data 标记
    assert "insufficient_data" in result.raw_data
    # 检查有效股票数量
    assert result.raw_data["valid_stocks_count"] > 0
    # 检查 ETF 窗口日期数量
    assert result.raw_data["etf_window_dates_count"] == 11

def test_s1_insufficient_data_marking():
    """验证数据不足时的标记"""
    # 模拟数据不足的情况
    # 检查 raw_data["insufficient_data"] == True
```

### 5.2 raw_data 不落盘问题

**方案**：
1. 单测直接检查 `IndicatorResult.raw_data`
2. 打印日志验证
3. 如果需要落盘，后续修改 `to_dict()` 方法

### 5.3 报告验证

运行 `uv run python -m wb.daily_flow` 后检查：
- S1 指标数值是否合理
- raw_data 是否包含 `insufficient_data` 字段
- 数据不足时是否正确标记

---

## 六、用户反馈已解决

| 问题 | 解决方案 |
|------|---------|
| S1-03 共同日期对齐顺序 | 先取共同日期，再 tail(11) |
| S1-06 所有股票全共同太严 | 每只股票单独判断，跳过数据不足的股票 |
| 数据不足返回 0.0 混进评分 | raw_data 明确标记 `insufficient_data: True` |
| S1-06 未与 ETF 日期窗口对齐 | 先取 ETF 最近 11 个交易日作为窗口，每只股票在该窗口内判断 |
| S1-06 actual_data_date 计算错误 | 记录 start_date/end_date，用 end_date 计算最保守日期 |
| raw_data 不落盘问题 | 本次先在 raw_data 标记，日报展示另做后续 |

---

## 七、Timeline

- 修改代码：50 分钟
- 新增测试：20 分钟
- 验证报告：15 分钟

**Total**: 1.5 小时
