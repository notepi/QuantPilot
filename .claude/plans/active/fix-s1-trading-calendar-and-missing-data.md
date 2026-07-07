# 修复 S1 指标数据链路问题

## 问题概述

用户在审查日报时发现两个问题：
1. **非交易日被当作交易日计算**：日报中出现节假日重复数据
2. **零值被误用表示缺失数据**：历史数据中有大量零值，实际是数据不足

## 完整诊断结果

### 一、数据源层面

| 数据源 | 状态 | 说明 |
|--------|------|------|
| citydata API | ✅ 正确 | 不包含节假日，只返回真实交易日 |
| 本地 fund_share.csv | ⚠️ 部分不一致 | 比 API 多了一些日期（东方财富补充），少了一些日期 |
| 本地 fund_daily.csv | ✅ 一致 | 与 API 完全一致 |

**具体数据**：
```
citydata API fund_share:  20250731 ~ 20260702, 214 条
本地 fund_share.csv:      20250731 ~ 20260707, 222 条

只在 API 中（本地缺失）: 20260430, 20260506, 20260507
只在本地中（API 无）:   20260622 ~ 20260707 等（东方财富/上交所补充）
```

### 二、数据源边界

**当前 S1 数据链路的数据来源**：

| 数据文件 | 主数据源 | 备用数据源 | 说明 |
|----------|----------|------------|------|
| `fund_daily.csv` | citydata `fund_daily` | 无 | ETF 日线价格 |
| `daily.csv` | citydata `daily` | 无 | A 股股票价格 |
| `fund_portfolio.csv` | citydata `fund_portfolio` | 无 | ETF 持仓 |
| `fund_share.csv` | citydata `fund_share` | 东方财富 `fund_etf_spot_em`、上交所 `fund_etf_scale_sse` | ETF 份额 |

**关键点**：
- 东方财富**只用于 ETF 份额的最新数据补充**
- citydata `fund_share` 只到 20260702
- 本地最新数据（20260703~20260707）来自东方财富/上交所补充

### 三、问题根源分析

#### 问题1：非交易日被当作交易日

**直接原因**：`wb/calculate_indicators.py` 的 `calculate_history` 函数只跳过周末，没有跳过节假日

```python
# 当前代码（错误）
for i in range(days):
    date = end_date - timedelta(days=i)
    if date.weekday() >= 5:  # 只跳周末
        continue
    calculate_and_save(date_str)
```

**发现 21 个非交易日指标文件**：
```
20251002, 20251003, 20251006, 20251007, 20251008  （国庆）
20260101, 20260102  （元旦）
20260216~20260223  （春节）
20260406  （清明）
20260501, 20260504~20260507  （五一）
```

#### 问题2：零值表示数据缺失

**原因1：数据积累不足**
- fund_share.csv 最早日期是 20250731
- 指标计算"近10日"需要 11 个数据点
- 节假日前后数据缺失，回溯窗口不足

**原因2：序列化丢失信息**
- `IndicatorResult.to_dict()` 没有序列化 `raw_data` 字段
- `insufficient_data` 标记丢失

**零值统计**：
- S1-01: 36 个零值
- S1-02: 36 个零值
- S1-03: 24 个零值
- S1-06: 24 个零值

## 解决方案

### 核心原则

1. **交易日来源**：以 `fund_daily.csv` 中 `589720.SH` 的 `trade_date` 为准
   - 不新建独立交易日历
   - citydata 行情数据天然只包含真实交易日
   - S1 核心标的是 589720.SH，它的行情日期就是 S1 可计算日期

2. **保留 ETF 份额补充源**：东方财富/上交所补充最新份额

3. **改进缺失数据标记**：区分真零值和数据不足

### 实施步骤

#### 阶段1：备份数据

```bash
mkdir -p data_backup_$(date +%Y%m%d)
cp -R data docs reports s2 s3 data_backup_$(date +%Y%m%d)/
```

#### 阶段2：修改指标计算逻辑

**文件**：`wb/calculate_indicators.py`

**修改前**：
```python
def calculate_history(days: int = 30):
    end_date = datetime.now()
    for i in range(days):
        date = end_date - timedelta(days=i)
        date_str = date.strftime("%Y%m%d")
        if date.weekday() >= 5:  # 只跳周末
            continue
        result = calculate_and_save(trade_date=date_str)
```

**修改后**：
```python
def calculate_history(days: int = 30):
    """计算历史指标（只在真实交易日上）"""
    import pandas as pd
    from pathlib import Path
    
    # 从 fund_daily.csv 获取 589720.SH 的交易日
    fund_daily_path = Path(__file__).parent.parent / "data" / "raw" / "fund_daily.csv"
    fund_daily = pd.read_csv(fund_daily_path)
    
    trade_dates = (
        fund_daily[fund_daily["ts_code"] == "589720.SH"]["trade_date"]
        .astype(str)
        .sort_values()
        .tail(days)
    )
    
    count = 0
    for date_str in trade_dates:
        result = calculate_and_save(trade_date=date_str)
        if result:
            count += 1
    
    print(f"共计算 {count} 天的指标")
```

**优点**：
- 不需要新建交易日历文件
- 不需要维护额外的同步逻辑
- 天然只包含 citydata 的真实交易日

#### 阶段3：序列化 raw_data 字段

**文件**：`wb/indicators/base.py`

**修改**：`IndicatorResult.to_dict()`
```python
def to_dict(self) -> dict:
    result = {
        "code": self.code,
        "name": self.name,
        "value": self.value,
        "weight": self.weight,
        "unit": self.unit,
        "direction": self.direction,
        "expectation": self.expectation or self.evaluate_expectation(),
        "trade_date": self.trade_date,
    }
    if self.data_date:
        result["data_date"] = self.data_date
    if self.raw_data:
        result["raw_data"] = self.raw_data
    return result
```

#### 阶段4：修改日报生成逻辑

**文件**：`wb/generate_report.py`

**修改**：
```python
def format_value(code: str, value: float, raw_data: dict = None) -> str:
    """格式化指标值，检查数据不足"""
    if raw_data and raw_data.get("insufficient_data"):
        return "数据不足 ⚪"
    
    if code == "S1-04":
        return f"{value:.2f}x"
    else:
        return f"{value:.2%}"
```

#### 阶段5：修改评分引擎

**⚠️ 重要：这是评分口径变化**

当部分指标数据不足时，有两种处理方式：

**方案 A（推荐）**：数据不足指标不参与评分，权重重归一化
- 例：6 个指标中 2 个数据不足，剩下 4 个指标权重会被放大
- 日报标注"部分指标不可判定"
- 综合得分基于有效指标

**方案 B**：数据不足指标保守记为"低于预期"
- 例：6 个指标中 2 个数据不足，按 score=0.4 计算
- 日报显示"数据不足"
- 综合得分会被拉低

**采用方案 A**：

**文件**：`wb/score_engine.py`

**修改**：`_calculate_weighted_score()`
```python
def _calculate_weighted_score(self, results: List[IndicatorResult]) -> tuple:
    """
    计算加权综合得分，排除数据不足的指标
    
    Returns:
        (score, insufficient_count): 综合得分和数据不足指标数
    """
    total_weight = 0.0
    weighted_sum = 0.0
    insufficient_count = 0
    
    for result in results:
        # 检查数据不足
        if result.raw_data and result.raw_data.get("insufficient_data"):
            insufficient_count += 1
            continue  # 跳过，不参与评分
        
        weight = result.weight
        expectation = result.expectation or result.evaluate_expectation()
        
        if expectation == "超预期":
            score = 1.0
        elif expectation == "符合预期":
            score = 0.7
        elif expectation == "低于预期":
            score = 0.4
        else:
            score = 0.5
        
        weighted_sum += score * weight
        total_weight += weight
    
    # 剩余指标权重归一化
    final_score = weighted_sum / total_weight if total_weight > 0 else 0.0
    return final_score, insufficient_count
```

**修改**：`calculate_all()` 传递 insufficient_count 到日报
```python
def calculate_all(self, trade_date: Optional[str] = None) -> PhaseScore:
    # ... 计算各指标 ...
    
    total_score, insufficient_count = self._calculate_weighted_score(results)
    
    # 生成评价摘要时标注
    if insufficient_count > 0:
        summary = f"[{insufficient_count}项指标数据不足] " + summary
    
    return PhaseScore(
        # ...
        total_score=total_score,
        summary=summary,
    )
```

#### 阶段6：清理非交易日指标文件

**文件**：`wb/clean_non_trade_days.py`（新建）

```python
"""清理非交易日的指标文件"""
import argparse
import pandas as pd
from pathlib import Path

def get_trade_dates() -> set:
    """从 fund_daily.csv 获取交易日"""
    fund_daily_path = Path("data/raw/fund_daily.csv")
    if not fund_daily_path.exists():
        raise FileNotFoundError("fund_daily.csv 不存在")
    
    fund_daily = pd.read_csv(fund_daily_path)
    return set(
        fund_daily[fund_daily["ts_code"] == "589720.SH"]["trade_date"]
        .astype(str)
        .tolist()
    )

def clean_non_trade_days(dry_run: bool = True):
    """
    删除非交易日的指标文件
    
    Args:
        dry_run: True = 只打印不删除，False = 实际删除
    """
    trade_dates = get_trade_dates()
    
    indicators_dir = Path("data/indicators")
    to_delete = []
    
    for filepath in indicators_dir.glob("*.json"):
        date_str = filepath.stem
        if date_str not in trade_dates:
            to_delete.append(filepath)
    
    if not to_delete:
        print("✓ 没有非交易日指标文件")
        return
    
    print(f"发现 {len(to_delete)} 个非交易日指标文件:")
    for filepath in to_delete:
        print(f"  - {filepath.name}")
    
    if dry_run:
        print("\n[DRY RUN] 未删除文件")
        print("确认删除请运行: uv run python -m wb.clean_non_trade_days --apply")
    else:
        for filepath in to_delete:
            filepath.unlink()
        print(f"\n✓ 已删除 {len(to_delete)} 个文件")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="清理非交易日指标文件")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="实际删除文件（默认只打印不删除）",
    )
    args = parser.parse_args()
    
    clean_non_trade_days(dry_run=not args.apply)
```

**执行**：
```bash
# 先 dry-run 查看将删除的文件
uv run python -m wb.clean_non_trade_days

# 确认后实际删除
uv run python -m wb.clean_non_trade_days --apply
```

#### 阶段7：补充缺失数据

**检查缺失日期**：
```bash
# 对比 API 和本地数据，找出缺失的交易日
uv run python -c "
from wb.tushare_proxy import pro_api
import pandas as pd

pro = pro_api()
df_api = pro.fund_share(ts_code='589720.SH', start_date='20260420', end_date='20260510')
df_local = pd.read_csv('data/raw/fund_share.csv')
df_local = df_local[df_local['ts_code'] == '589720.SH']

api_dates = set(df_api['trade_date'].astype(str))
local_dates = set(df_local['trade_date'].astype(str))

missing = sorted(api_dates - local_dates)
print(f'缺失的交易日: {missing}')
"
```

**补充方式（二选一）**：

**方式1：运行 update_data 自动补充**
```bash
uv run python -m wb.update_data
```

**方式2：手动补充并追加**
```bash
uv run python -c "
from wb.update_data import fetch_fund_share, append_to_file, ETF_CODE, DATA_DIR

# 获取缺失数据
df = fetch_fund_share(ETF_CODE, '20260420', '20260510')
if df is not None and len(df) > 0:
    # 追加到 fund_share.csv
    append_to_file(df, 'fund_share.csv')
    print(f'已补充 {len(df)} 条记录')
else:
    print('无数据需要补充')
"
```

#### 阶段8：重新计算指标

```bash
uv run python -m wb.calculate_indicators history 365
```

#### 阶段9：生成日报

```bash
uv run python -m wb.generate_report
```

## 数据补齐逻辑总结

| 数据类型 | 来源 | 说明 |
|----------|------|------|
| 价格数据 | citydata `fund_daily` / `daily` | 无备用源 |
| 交易日集合 | citydata `589720.SH fund_daily` | 作为 S1 可计算日期 |
| ETF 份额 | citydata `fund_share` + 东方财富/上交所补充 | 最新缺口允许补充 |
| 指标计算 | 如份额不足 11 条，标记 `insufficient_data` | 不伪装成真实 0 |

## 审计意见响应

### ✅ 已修正

1. **`calculate_history` 初始化 `count = 0`**：已添加
2. **补充缺失数据命令修正**：
   - 原命令缺少 `ts_code` 参数
   - 已改为运行 `update_data` 或手动追加逻辑
3. **评分口径变化明确为中风险**：
   - 采用方案 A：数据不足指标不参与评分
   - 权重重归一化
   - 日报标注"X项指标数据不足"
4. **清理脚本支持 dry-run**：
   - 默认只打印不删除
   - 使用 `--apply` 参数确认删除

## 验证清单

### 1. 交易日验证
- [ ] `calculate_history` 只遍历 `fund_daily.csv` 中 589720.SH 的交易日
- [ ] 不再生成节假日指标文件

### 2. 指标文件验证
- [ ] `data/indicators/` 中没有非交易日文件
- [ ] 零值文件有 `raw_data.insufficient_data = True` 标记
- [ ] `raw_data` 字段被正确序列化

### 3. 日报验证
- [ ] 日报中没有重复数据
- [ ] 数据不足显示为"数据不足 ⚪"
- [ ] 综合得分基于有效指标计算

### 4. ETF 份额验证
- [ ] `fund_share.csv` 包含最新数据
- [ ] `source` 字段正确标记数据来源

## 风险评估

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 数据备份不完整 | 低 | 备份整个目录 |
| 东方财富补充逻辑丢失 | 低 | 不修改 update_data.py 的补充逻辑 |
| **综合得分口径变化** | **中** | 采用方案 A（不参与评分），日报标注"部分指标不可判定" |
| 删除错误文件 | 低 | dry-run 模式先预览，备份后再删除 |

## 评分口径变化说明

**变化内容**：数据不足的指标不参与评分，剩余指标权重重归一化

**影响示例**：
- 原来：6 个指标全部参与评分
- 现在：如果 2 个指标数据不足，则只有 4 个指标参与评分，权重从 (0.22, 0.18, 0.20, 0.14, 0.14, 0.12) 变为归一化后的权重

**应对措施**：
- 日报中标注"X项指标数据不足"
- 历史数据重新计算后，综合得分可能有变化
- 建议对比新旧评分口径的差异

## 执行命令汇总

```bash
# 1. 备份数据
mkdir -p data_backup_$(date +%Y%m%d)
cp -R data docs reports s2 s3 data_backup_$(date +%Y%m%d)/

# 2. 清理非交易日指标文件（先 dry-run）
uv run python -m wb.clean_non_trade_days
# 确认后删除
uv run python -m wb.clean_non_trade_days --apply

# 3. 补充缺失数据（可选）
uv run python -m wb.update_data
# 或手动补充
# uv run python -c "from wb.update_data import fetch_fund_share, append_to_file, ETF_CODE; ..."

# 4. 重新计算指标
uv run python -m wb.calculate_indicators history 365

# 5. 生成日报
uv run python -m wb.generate_report
```

## 关键修改文件

| 文件 | 类型 | 说明 |
|------|------|------|
| `wb/calculate_indicators.py` | 修改 | 使用 fund_daily 的交易日，初始化 count=0 |
| `wb/clean_non_trade_days.py` | 新建 | 清理非交易日指标文件，支持 dry-run |
| `wb/indicators/base.py` | 修改 | 序列化 raw_data |
| `wb/generate_report.py` | 修改 | 显示数据不足 |
| `wb/score_engine.py` | 修改 | 排除数据不足指标，返回 insufficient_count |

**不需要新建**：
- ~~`wb/utils/trade_calendar.py`~~
- ~~`data/trade_calendar.csv`~~

## 方案优势

1. **简洁**：不需要新建独立交易日历
2. **可靠**：以 citydata 行情数据为事实源，天然只包含真实交易日
3. **一致**：S1 核心标的 589720.SH 的行情日期 = S1 可计算日期
4. **易维护**：不需要同步节假日、临时休市等额外信息
