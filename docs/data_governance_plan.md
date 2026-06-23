# QuantPilot 数据治理与智能体协作改造方案

> **状态**：方案已实施，四阶段全部完成
> **审计文档**：`docs/data_governance_audit.md`
> **最后更新**：2026-06-23

---

## 范围说明

本文档包含以下内容：

- 数据治理整改（数据日期披露、份额备用源、raw 层补齐）
- S1/S2/S3 模块边界调整
- S2 智能体事件维护任务设计
- S3 AI 风格报告拆分
- 日报流程与验收机制

---

## 零、实施状态总览

| 阶段 | 内容 | 状态 | 说明 |
|------|------|------|------|
| 第一阶段 | S1 数据日期披露 | ✅ 已实施 | IndicatorResult 增加 data_date 字段，S1-01/S1-02 输出实际数据日期 |
| 第二阶段 | 份额数据备用源 | ✅ 已实施 | 东方财富 fallback 已实现，fetch_fund_share_em 函数已添加 |
| 第三阶段 | 159567.SZ raw 层更新 | ✅ 已实施 | update_fund_daily_incremental 已增加 159567.SZ |
| 第四阶段 | S3 模块拆分 | ✅ 已实施 | s3/ 目录独立运行，s2 保留兼容 wrapper |
| 第五阶段 | 数据血缘元数据 | 📋 待规划 | 建议中期补充 |

---

## 一、目标

1. **数据日期透明化**：报告日期与数据日期不一致时，必须在报告中明确披露
2. **份额数据及时性**：通过东方财富备用源补充当天份额数据
3. **数据来源可追溯**：每个数据字段都能追溯到具体的数据源和抓取时间
4. **模块职责清晰**：S1、S2、S3 各自独立，数据流向清晰

---

## 二、已测试验证的事实

> **说明**：以下测试验证的是"方案可行性"，非"代码已完成"。

### 2.1 citydata 数据源测试

**测试时间**：2026-06-22

| 测试项 | 测试方法 | 结果 | 结论 |
|--------|----------|------|------|
| fund_daily API 连通性 | 调用 citydata fund_daily 接口查询 589720/159557/159567 | ✅ 成功返回数据 | API 正常 |
| fund_daily 数据时效性 | 查询 20260615-20260622 区间 | 最新日期 20260622 | 数据实时 |
| fund_share API 连通性 | 调用 citydata fund_share 接口查询 589720 | ✅ 成功返回数据 | API 正常 |
| fund_share 数据时效性 | 查询最新数据 | 最新日期 20260618 | ⚠️ 滞后 4 天 |
| fund_share 单日查询行为 | 查询单日 20260622 | 返回全部历史数据 | ⚠️ API 行为特殊，需代码过滤 |

**测试代码**：
```python
from wb.tushare_proxy import pro_api
pro = pro_api()
df = pro.fund_daily(ts_code='589720.SH', start_date='20260615', end_date='20260622')
```

### 2.2 东方财富备用数据源测试（新增）

**测试时间**：2026-06-22 19:53

**发现**：东方财富 `fund_etf_spot_em` 接口可获取当天的份额数据

| 标的 | 东方财富份额（万份） | 东方财富日期 | citydata 份额 | citydata 日期 |
|------|---------------------|-------------|---------------|---------------|
| 589720.SH | 191082.3 | 20260622 ✅ | 191082.0 | 20260618 |
| 159557.SZ | 15589.5 | 20260622 ✅ | - | - |
| 159567.SZ | 1057773.0 | 20260622 ✅ | - | - |

**测试代码**：
```python
import akshare as ak
df = ak.fund_etf_spot_em()
df['代码'] = df['代码'].astype(str)
hit = df[df['代码'] == '589720']
share = float(hit.iloc[0]['最新份额']) / 10000  # 转为万份
date = hit.iloc[0]['数据日期']
```

**为什么不用上交所接口？**

代码里有 `fetch_fund_share_sse` 函数调用 `ak.fund_etf_scale_sse`，但测试发现：

| 问题 | 上交所 `fund_etf_scale_sse` | 东方财富 `fund_etf_spot_em` |
|------|---------------------------|---------------------------|
| 带日期参数 | ❌ akshare bug 报错 | ✅ 不需要参数 |
| 默认数据日期 | 2025-01-15（过期） | 当天 |
| 是否包含 589720 | ❌ 未找到 | ✅ 有 |

**结论**：
- ❌ 上交所接口不适用（akshare bug + 数据不全）
- ✅ 东方财富接口是可行的备用方案
- ✅ 东方财富有当天的份额数据，与 citydata 历史数据一致

**建议方案**：
1. 主数据源：citydata fund_share（历史数据完整）
2. 备用数据源：东方财富 fund_etf_spot_em（当天数据及时）
3. 更新逻辑：先查 citydata，若滞后则从东方财富补当天

### 2.3 本地数据状态测试

**测试时间**：2026-06-22

| 数据文件 | 标的 | 本地最新日期 | citydata 最新日期 | 状态 |
|----------|------|-------------|------------------|------|
| `data/raw/fund_daily.csv` | 589720.SH | 20260622 | 20260622 | ✅ 同步 |
| `data/raw/fund_daily.csv` | 159557.SZ | 20260622 | 20260622 | ✅ 同步 |
| `data/raw/fund_daily.csv` | 159567.SZ | 20260605 | 20260622 | ❌ 滞后 17 天 |
| `data/raw/fund_share.csv` | 589720.SH | 20260618 | 20260618 | ✅ 同步 |
| `s2/output/hk_cache/159567.csv` | 159567.SZ | 20260622 | - | ✅ 腾讯兜底 |
| `data/processed/market_daily.csv` | 159567.SZ | 20260622 | - | ✅ 从 hk_cache 合并 |

### 2.4 S1 指标计算测试

**测试时间**：2026-06-22

| 指标 | 预期计算逻辑 | 实测结果 | 结论 |
|------|-------------|----------|------|
| S1-01 | 近10日份额增加天数占比 | 5/12 = 41.67% | ✅ 正确 |
| S1-02 | (期末-期初)/期初 份额变化率 | -3.53% | ✅ 正确 |
| S1-05 文档 | 数据源写 `hk_daily` | - | ❌ 文档错误，实际用 `daily` |

### 2.5 S2 数据状态测试

**测试时间**：2026-06-22

| 数据文件 | 状态 | 说明 |
|----------|------|------|
| `s2/data/earnings_consensus.csv` | 全部 missing | 未接入一致预期数据源 |
| `s2/output/hk_cache/status.txt` | primary=failed, fallback=success | citydata 滞后，腾讯兜底成功 |

---

## 三、发现的问题

### 问题 1：报告日期与数据日期不一致（已验证）

**现象**：
- S1 报告日期：20260622
- S1-01/S1-02 使用的份额数据日期：20260618（滞后 4 天）

**根本原因**：S1 份额数据源缺少当天数据的备用方案

**数据源代码状态**：
- `wb/update_data.py` 的 `fetch_fund_share` 只用 citydata + 上交所接口
- 上交所接口 `ak.fund_etf_scale_sse` 有 akshare bug，无法工作
- 没有东方财富备用源

**影响**：用户可能误以为份额数据是 20260622 的

**指标结果代码状态**：✅ 已实现 `data_date` 字段
- `wb/indicators/base.py` 的 `IndicatorResult` 已增加 `data_date` 字段
- `data/indicators/20260622.json` 中 S1-01/S1-02 已包含 `data_date`

#### 份额数据源对比

| 数据源 | 当天数据 | 历史数据 | 稳定性 | 适用场景 |
|--------|---------|---------|--------|---------|
| citydata fund_share | ❌ 滞后 | ✅ 有历史区间 | 稳定 | 历史数据 |
| 东方财富 fund_etf_spot_em | ✅ 及时 | ❌ 只有最新一条 | 稳定 | 当天数据 |
| 上交所 fund_etf_scale_sse | ❌ akshare bug | ❌ 数据过期 | 不可用 | 不适用 |

#### 份额数据更新策略（建议）

**数据源优先级**：
1. citydata（历史数据完整）
2. 东方财富（当天数据补充）

**更新逻辑**：
```python
def fetch_fund_share(ts_code, start_date, end_date):
    """
    份额数据获取：citydata（历史）→ 东方财富（当天补充）
    
    原因：
    - 东方财富只有当天最新份额，没有历史区间
    - S1-01/S1-02 需要近 10 日份额变化，必须用 citydata
    - 当 citydata 滞后时，用东方财富补充当天
    """
    frames = []
    latest = None
    
    # 1. 主源：citydata（历史数据）
    try:
        df = pro.fund_share(ts_code=ts_code, start_date=start_date, end_date=end_date)
        if df is not None and len(df) > 0:
            frames.append(df)
            latest = df['trade_date'].max()
    except Exception as e:
        log_error(f"citydata fund_share failed: {e}")
    
    # 2. 检查是否需要补充当天数据
    if latest is None or latest < end_date:
        try:
            # 备用源：东方财富（当天数据）
            df_em = fetch_fund_share_em(ts_code)  # 新增函数
            if df_em is not None and len(df_em) > 0:
                frames.append(df_em)
                log_info(f"东方财富补充当天份额数据成功")
        except Exception as e:
            log_error(f"东方财富份额获取失败: {e}")
    
    # 3. 合并去重
    if frames:
        return pd.concat(frames).drop_duplicates(subset=['trade_date'])
    
    return pd.DataFrame()

def fetch_fund_share_em(ts_code: str) -> pd.DataFrame:
    """从东方财富获取当天份额数据"""
    import akshare as ak
    
    code = ts_code.split('.')[0]
    df = ak.fund_etf_spot_em()
    df['代码'] = df['代码'].astype(str)
    hit = df[df['代码'] == code]
    
    if len(hit) > 0:
        return pd.DataFrame([{
            'ts_code': ts_code,
            'trade_date': str(hit.iloc[0]['数据日期'])[:10].replace('-', ''),
            'fd_share': float(hit.iloc[0]['最新份额']) / 10000,  # 转为万份
            'source': 'eastmoney_fund_etf_spot_em'
        }])
    return pd.DataFrame()
```

**稳定性保障措施**：

| 措施 | 说明 |
|------|------|
| 多数据源降级 | citydata → 东方财富 → 返回空+标记 |
| 超时控制 | 每个接口设置 timeout=30s |
| 错误日志 | 记录失败原因便于排查 |
| 数据源标记 | 记录 source 字段，便于追溯 |
| 去重合并 | 合并历史和当天数据时去重 |

### 问题 2：159567.SZ 在 raw 层数据滞后（已验证）

**现象**：
- `data/raw/fund_daily.csv` 中 159567.SZ 最新日期：20260605
- 但 `s2/output/hk_cache/159567.csv` 通过腾讯兜底已更新到 20260622

**原因**：
- S1 的 `update_data.py` 只配置了 589720.SH 和 159557.SZ
- 159567.SZ 由 S2 单独更新到 hk_cache

**影响**：raw 层数据不完整，影响审计

**当前代码状态**：✅ 已修改 `update_data.py`
- ETF 列表已增加 159567.SZ

### 问题 3：S2-03b 一致预期数据缺失（已验证）

**现象**：`s2/data/earnings_consensus.csv` 全部字段为 missing

**原因**：未接入可靠的一致预期数据源

**影响**：S2-03b 指标无法计算，报告中显示"一致预期验证缺数据"

**当前处理方式**：✅ 正确 - 显示 missing 并说明原因，不伪造数据

### 问题 4：AI 风格报告代码混在 s2 目录（设计问题）

**现象**：
- `s2/generate_ai_style_report.py`
- `s2/style_rotation.py`
- `s2/ai_biotech_validation.py`

**影响**：模块职责不清晰，不利于维护

**当前代码状态**：✅ 已拆分到 s3/

---

## 四、解决方案

### 方案 A1：数据日期披露（优先级：高）

**目标**：报告日期与数据日期不一致时，明确披露

**修改内容**：
1. `wb/indicators/base.py` - 增加 `data_date` 字段
2. `wb/indicators/s1_01_capital_flow.py` - 获取份额数据日期
3. `wb/indicators/s1_02_share_change.py` - 获取份额数据日期
4. `wb/generate_report.py` - 在日报中显示数据日期

**实施状态**：✅ 已实施

**验证方法**：
```bash
uv run python -m wb.calculate_indicators
cat data/indicators/20260622.json | grep data_date
```

### 方案 A2：份额数据备用源（优先级：高）

**目标**：解决当天份额数据缺失问题

**背景**：citydata `fund_share` 接口滞后 4 天，东方财富 `fund_etf_spot_em` 可获取当天份额

**修改内容**：

1. **新增函数** `wb/update_data.py`：
```python
def fetch_fund_share_em(ts_code: str) -> pd.DataFrame:
    """从东方财富获取当天份额数据"""
    import akshare as ak

    code = ts_code.split('.')[0]
    df = ak.fund_etf_spot_em()
    df['代码'] = df['代码'].astype(str)
    hit = df[df['代码'] == code]

    if len(hit) > 0:
        return pd.DataFrame([{
            'ts_code': ts_code,
            'trade_date': str(hit.iloc[0]['数据日期'])[:10].replace('-', ''),
            'fd_share': float(hit.iloc[0]['最新份额']) / 10000,  # 转为万份
            'source': 'eastmoney_fund_etf_spot_em'
        }])
    return pd.DataFrame()
```

2. **修改函数** `fetch_fund_share()`：
   - 主源：citydata（历史数据完整）
   - 备用源：东方财富（当天数据补充）
   - 当 citydata 最新日期 < end_date 时，调用东方财富补充

**Fallback 触发约束**：
- 东方财富返回的 `数据日期` 必须在 `[start_date, end_date]` 区间内
- 返回日期必须大于 citydata 最新日期才追加
- 若东方财富日期等于已有日期，只覆盖同日期或跳过，不能生成重复记录
- fallback 只补一条最新份额，不用于历史区间回填

3. **记录来源**：
   - 在 `fund_share.csv` 中增加 `source` 字段
   - 或在日志/审计文件中记录来源

4. **Schema 兼容策略**：
   - 旧记录 `source` 默认填 `citydata_fund_share`
   - `DataFetcher.get_fund_share()` 不依赖 `source` 字段计算，避免破坏 S1
   - `append_to_file()` 合并时确保新旧列对齐

**实施状态**：✅ 已实施

**验证方法**：
```bash
uv run python -m wb.update_data
grep "589720.SH" data/raw/fund_share.csv | tail -3
# 预期：包含最新可得日期，来源可追溯
```

### 方案 B：更新流程增加 159567.SZ（优先级：中）

**目标**：保证 raw 层数据完整

**修改内容**：
修改 `wb/update_data.py`，在 ETF 列表中增加 159567.SZ

**实施状态**：✅ 已实施

**验证方法**：
```bash
uv run python -m wb.update_data
grep "159567" data/raw/fund_daily.csv | tail -3
```

### 方案 C：S3 模块拆分（优先级：中）

**目标**：S1、S2、S3 职责清晰，数据流向明确

**修改内容**：
1. 创建 `s3/` 目录
2. 迁移 AI 风格相关代码
3. 在 `s2/` 保留兼容层

**实施状态**：✅ 已实施

**验证方法**：
```bash
uv run python -m s3.generate_report
cat s3/output/daily_report.md
```

---

## 五、原型验证结果

> **说明**：以下测试验证的是"方案技术可行性"，实际代码尚未落地。

### 5.1 S1 更新流程原型验证

**验证内容**：`fetch_fund_daily` 函数能否正确获取 159567.SZ 的数据

**验证代码**：
```python
from wb.update_data import fetch_fund_daily
df = fetch_fund_daily('159567.SZ', '20260615', '20260622')
print(df['trade_date'].max())  # 输出: 20260622
```

**验证结果**：
- ✅ 返回 5 行数据
- ✅ 最新日期 20260622
- ✅ 数据格式正确

**结论**：`fetch_fund_daily` 函数无需修改，只需在 `update_fund_daily_incremental()` 中增加 159567.SZ 到 ETF 列表

### 5.2 S3 独立运行原型验证

**验证内容**：AI 风格报告模块能否独立运行

**依赖分析**：
| 文件 | S2 依赖 | 可独立迁移 |
|------|---------|-----------|
| `style_rotation.py` | 无 | ✅ 是 |
| `ai_biotech_validation.py` | `s2.style_rotation` | ✅ 是（一起迁移） |
| `generate_ai_style_report.py` | `s2.*` 三个模块 | ✅ 是（一起迁移） |
| `s1_reader.py` | 无 | ✅ 是（可复制或共享） |

**验证代码**：
```python
from s2.generate_ai_style_report import generate_ai_style_report
output_path = generate_ai_style_report(...)
# 输出: ✅ 生成成功，报告 71 行
```

**验证结果**：
- ✅ style_rotation 模块独立运行成功
- ✅ 完整报告生成成功
- ✅ 输出路径正确

**结论**：S3 可以顺利拆分，需采用兼容迁移方式

### 5.3 数据日期字段原型验证

**验证内容**：IndicatorResult 增加 `data_date` 字段后的效果

**验证代码**：
```python
@dataclass
class IndicatorResultV2:
    ...
    data_date: str  # 新增字段

result = IndicatorResultV2(
    code='S1-01',
    trade_date='20260622',
    data_date='20260618',  # 实际数据日期
    ...
)
```

**验证结果**：
- ✅ JSON 输出正确包含 `data_date`
- ✅ 报告表格可以显示数据日期
- ✅ 可以检测日期不一致并警告

**结论**：实现方案可行，需要在每个指标计算时获取数据的最新日期

---

## 六、实施步骤

### 第一阶段：数据日期披露

**目标**：报告日期与数据日期不一致时，明确披露

**修改文件**：
1. `wb/indicators/base.py` - 增加 `data_date` 字段
2. `wb/indicators/s1_01_capital_flow.py` - 获取份额数据日期
3. `wb/indicators/s1_02_share_change.py` - 获取份额数据日期
4. `wb/generate_report.py` - 在日报中显示数据日期

**验收标准**：
- `cat data/indicators/20260622.json | grep data_date` 可以看到每个指标的数据日期
- `docs/daily_report.md` 能区分报告日期与实际数据日期

### 第二阶段：份额数据备用源

**目标**：解决当天份额数据缺失问题

**修改文件**：
1. `wb/update_data.py` - 新增 `fetch_fund_share_em()` 函数
2. `wb/update_data.py` - 修改 `fetch_fund_share()` 增加东方财富 fallback

**验收标准**：
- `grep "589720.SH" data/raw/fund_share.csv | tail -3` 包含最新可得日期
- 来源可追溯（日志或 source 字段）

### 第三阶段：完善数据更新

**目标**：保证 raw 层数据完整

**修改文件**：
1. `wb/update_data.py` - 在第 326 行附近增加 159567.SZ

**具体修改**：
```python
# 原来
for ts_code in [ETF_CODE, BENCHMARK_CODE]:

# 修改为
for ts_code in [ETF_CODE, BENCHMARK_CODE, "159567.SZ"]:
```

**验收标准**：
- `grep "159567" data/raw/fund_daily.csv | tail -1` 显示最新可得交易日

**附带修改**：修正 `docs/indicators.md` 中 S1-05 的数据源说明
- 错误：`hk_daily`
- 正确：`daily`

### 第四阶段：S3 模块拆分

**目标**：S1、S2、S3 职责清晰

**迁移文件**：
| 原位置 | 新位置 |
|--------|--------|
| `s2/style_rotation.py` | `s3/style_rotation.py` |
| `s2/ai_biotech_validation.py` | `s3/validation.py` |
| `s2/generate_ai_style_report.py` | `s3/generate_report.py` |
| `s2/style_config.json` | `s3/config.json` |
| `s2/ai_core_versions.json` | `s3/versions.json` |
| `s2/s1_reader.py` | `s3/s1_reader.py`（复制） |

**新建文件**：
- `s3/__init__.py`
- `s3/daily_flow.py`（独立入口）
- `s3/README.md`

**迁移策略**：兼容迁移
1. 新建 `s3/`，复制并调整 AI 风格相关模块
2. 在 `s2/` 保留兼容 wrapper，转发到 `s3`
3. 待测试和调用方全部切到 `s3` 后，再删除 `s2` 兼容层

**验收标准**：
- `uv run python -m s3.generate_report` 可独立运行并生成报告
- 原有 S2 测试通过，旧的 `s2.*` import 不立即失效

### 第五阶段：补充数据血缘元数据

**目标**：完善数据追溯能力

**新增字段**：
| 字段 | 含义 |
|------|------|
| `trade_date` | 报告或计算口径日期 |
| `data_date` | 指标实际使用数据的最大日期 |
| `source_file` | 本地数据文件路径或数据表 |
| `source_name` | citydata、tencent_fqkline、local_csv 等 |
| `fetched_at` | 外部数据抓取时间 |
| `data_status` | latest、stale、missing、fallback 等 |

---

## 七、验收清单

### 实施前验证（已完成）

| 测试项 | 测试方法 | 结果 | 时间 |
|--------|----------|------|------|
| citydata fund_daily API | 调用接口获取 589720/159557/159567 | ✅ 正常 | 2026-06-22 |
| citydata fund_share API | 调用接口获取 589720 份额 | ✅ 正常 | 2026-06-22 |
| 东方财富 fund_etf_spot_em | 调用接口获取当天份额 | ✅ 正常 | 2026-06-22 |
| 本地数据状态检查 | 检查各文件最新日期 | ✅ 已记录 | 2026-06-22 |
| S1 指标计算逻辑 | 计算 S1-01/S1-02 值 | ✅ 正确 | 2026-06-22 |
| fetch_fund_daily 159567 | 测试获取 159567.SZ 数据 | ✅ 成功 | 2026-06-22 |
| style_rotation 独立运行 | 调用 calculate_style_analysis | ✅ 成功 | 2026-06-22 |
| AI 风格报告生成 | 调用 generate_ai_style_report | ✅ 成功 | 2026-06-22 |
| data_date 字段方案 | 模拟测试 | ✅ 可行 | 2026-06-22 |

### 实施后验证（待执行）

| 验证项 | 验证命令 | 预期结果 |
|--------|----------|----------|
| S1 指标 JSON 含 data_date | `cat data/indicators/*.json \| grep data_date` | 包含 data_date 字段 |
| S1 日报显示数据日期 | `head -15 docs/daily_report.md` | 包含"数据日期"行 |
| 份额数据含东方财富来源 | `grep "589720.SH" data/raw/fund_share.csv \| tail -3` | 包含最新日期，来源可追溯 |
| 159567 数据更新 | `grep "159567" data/raw/fund_daily.csv \| tail -1` | 日期 = 最新交易日 |
| S3 独立运行 | `uv run python -m s3.generate_report` | 无报错，生成报告 |
| S2 测试不失败 | `uv run pytest s2/tests/` | 全部通过 |

### 综合验收命令

```bash
# 数据更新
uv run python -m wb.update_data

# 指标计算
uv run python -m wb.calculate_indicators 20260622

# 报告生成
uv run python -m wb.generate_report

# 验证 data_date
grep "data_date" data/indicators/20260622.json

# 验证份额来源
grep "589720.SH" data/raw/fund_share.csv | tail -3

# 验证 159567 raw 层
grep "159567.SZ" data/raw/fund_daily.csv | tail -3

# 验证 S2 测试
uv run pytest s2/tests/
```

---

## 八、风险与回滚

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 修改 update_data.py 导致更新失败 | 低 | 中 | 已测试 fetch_fund_daily，逻辑正确 |
| S3 拆分后 import 路径错误 | 中 | 低 | 保持 s2 目录文件，逐步迁移 |
| data_date 字段计算错误 | 低 | 中 | 先在 S1-01/S1-02 测试，再推广 |
| S2 调用 S3 迁移后的模块报错 | 中 | 低 | 在 s2 中保留兼容性 import |

**回滚方案**：
- 所有修改前先 git commit 当前状态
- 分阶段提交，每个阶段独立可回滚
- S3 拆分不删除 s2 中的原文件，先并存运行

**实施前检查**：
```bash
git status --short
git diff --stat
```

**代码与数据分离原则**：
- 代码改造与数据刷新文件分开提交
- 若不提交，也至少在实施记录中列出本次代码改造涉及文件
- 不把大批输出文件变化和核心代码改造混在一个提交里

---

## 九、S2 代码 vs 智能体职责分界

### 9.1 核心区分原则

| 类型 | 判断标准 | 实现方式 | 原因 |
|------|---------|---------|------|
| **行情数据** | 有成熟 API | 代码自动抓取 | 数据结构化、来源稳定 |
| **事件数据** | 需要判断力 | 智能体查证 | 需要真实性、重要性判断 |
| **计算数据** | 可从已有数据推导 | 代码自动计算 | 纯逻辑运算 |

### 9.2 代码负责的数据（自动）

| 数据类型 | 数据源 | 函数/模块 | 输出文件 |
|---------|--------|----------|----------|
| A股股票行情 | akshare → citydata | `s2/build_data_layer.py` | `data/raw/daily.csv` |
| ETF 行情 | akshare → tencent → citydata | `s2/hk_observation.py` | `data/processed/market_daily.csv` |
| 港股个股行情 | tencent.hkfqkline | `s2/hk_observation.py` | `s2/data/hk_daily.csv` |
| 海外 ETF/指数 | yahoo_chart | `s2/build_data_layer.py` | `data/processed/macro_market_daily.csv` |
| 事件后收益 | 从行情计算 | `s2/build_data_layer.py` | `s2/data/clinical_trade_returns.csv` |
| 数据审计 | 多源汇总 | `s2/build_data_layer.py` | `s2/output/data_audit/market_data_audit.csv` |

**代码能做的**：
- ✅ 调用 API 获取结构化数据
- ✅ 数据格式转换、清洗
- ✅ 从已有数据计算衍生指标
- ✅ 自动降级（主源失败 → 备用源）
- ✅ 写入 CSV 文件

**代码不能做的**：
- ❌ 判断新闻是否真实
- ❌ 判断事件是否重要
- ❌ 从非结构化文本提取复杂字段
- ❌ 去重去伪（同一事件多个报道）

### 9.3 智能体负责的数据（需判断力）

| 数据类型 | 文件 | 需要的判断力 | 当前状态 |
|---------|------|-------------|----------|
| BD 事件 | `s2/data/bd_events.csv` | 真实性、金额重要性、来源可靠性 | 滞后 18 天 |
| 临床事件 | `s2/data/clinical_events.csv` | 数据质量、阶段重要性 | 滞后 17 天 |
| 审批事件 | `s2/data/regulatory_events.csv` | 审批级别、市场影响 | 滞后 18 天 |
| 业绩事件 | `s2/data/earnings_events.csv` | 超预期程度、核心指标 | 滞后 42 天 |
| 政策风险 | `s2/data/policy_risk_events.csv` | 影响范围、实施概率 | 滞后 14 天 |
| 一致预期 | `s2/data/earnings_consensus.csv` | 数据源选择、口径一致性 | 全部 missing |
| 商业化兑现 | `s2/data/commercialization_metrics.csv` | 指标定义、数据完整性 | 滞后 14 天 |
| 龙头池 | `s2/data/leader_pool.csv` | 公司选择、权重分配 | 手动维护 |

**智能体能做的**：
- ✅ 从多个新闻源发现事件
- ✅ 判断事件是否重要（基于背景知识）
- ✅ 验证信息来源可靠性
- ✅ 提取非结构化文本中的字段
- ✅ 去重合并同一事件的多个报道

**智能体需要人类提供的**：
- 背景知识（龙头公司、金额阈值、重要性标准）
- 验证方式（运行报告生成检查）
- 数据写入接口（`append_events()` 函数）

### 9.4 协作流程

```
┌─────────────────────────────────────────────────────────────────┐
│                        S2 数据流                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │ 代码自动抓取  │    │ 智能体查证   │    │ 代码自动计算  │      │
│  │              │    │              │    │              │      │
│  │ • 行情数据   │    │ • BD 事件    │    │ • 事件后收益 │      │
│  │ • 港股数据   │    │ • 临床事件   │    │ • 评分计算   │      │
│  │ • 宏观数据   │    │ • 审批事件   │    │ • 报告生成   │      │
│  │              │    │ • 政策风险   │    │              │      │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘      │
│         │                   │                   │              │
│         ▼                   ▼                   ▼              │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   s2/data/*.csv                          │   │
│  │              (事件库 + 行情数据)                          │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            │                                   │
│                            ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              s2/generate_s2_report.py                    │   │
│  │                  (代码自动生成报告)                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 9.5 为什么事件数据需要智能体？

**BD 事件示例**：

假设有一条新闻：
> "辉瑞与信达生物达成战略合作，首付款 12 亿美元"

**代码能做的**：
- ❌ 无法判断这条新闻是否值得记录
- ❌ 无法判断 12 亿美元是否"重要"
- ❌ 无法验证新闻来源是否可靠
- ❌ 无法区分这是 BD 交易还是普通合作

**智能体能做的**：
- ✅ 根据背景知识判断：信达是龙头公司，值得关注
- ✅ 根据金额阈值判断：首付款 12 亿美元 > 5000 万美元，重要
- ✅ 根据来源判断：辉瑞官网 > 行业媒体 > 普通新闻
- ✅ 提取字段：公司、金额、阶段、伙伴、权益范围

**关键差异**：

| 维度 | 代码 | 智能体 |
|------|------|--------|
| 处理对象 | 结构化数据 | 非结构化信息 |
| 判断能力 | 无（执行预设规则） | 有（基于背景知识） |
| 灵活性 | 低（固定逻辑） | 高（适应新情况） |
| 适用场景 | API 数据 | 新闻、公告、报告 |

### 9.6 代码中的明确分工

**`s2/build_data_layer.py:631-633`**：

```python
# 代码自动抓取：A股股票、ETF、港股个股、海外ETF/指数/宏观行情、事件后收益计算、market_data_audit。
# 需要人工/智能体查证：BD事件、临床事件、审批事件、公司财务字段、商业化兑现、一致预期、政策风险事件。
```

### 9.7 当前问题

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 事件库滞后 17-42 天 | 智能体任务设计不合理 | 用 Agent 思维重新设计（见第十一章） |
| 一致预期全部 missing | 未接入数据源 | 接入可靠数据源或明确标注不可用 |
| 龙头池未更新 | 依赖手动维护 | 智能体定期更新或保持手动 |

---

## 十、S1-S2-S3 数据关系

### 10.1 模块职责总览

| 模块 | 职责 | 输入 | 输出 | 是否需要智能体 |
|------|------|------|------|---------------|
| **S1** | 资金面观察 | ETF 份额、价格 | `data/indicators/*.json` | 否 |
| **S2** | 产业验证 | S1数据 + 事件库 | `s2/output/reports/*.md` | 是（事件收集） |
| **S3** | AI 风格轮动 | S1数据 + 市场行情 | `s3/output/ai_style_report.md` | 否 |

### 10.2 数据流图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           数据流向                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────┐                                                       │
│  │  原始数据     │                                                       │
│  │              │                                                       │
│  │ • ETF份额    │                                                       │
│  │ • ETF价格    │                                                       │
│  │ • 行情数据   │                                                       │
│  └──────┬───────┘                                                       │
│         │                                                               │
│         ▼                                                               │
│  ┌──────────────┐     ┌──────────────┐                                 │
│  │     S1       │────▶│ data/        │                                 │
│  │  资金面观察   │     │ indicators/  │                                 │
│  │              │     │ *.json       │                                 │
│  │ (代码计算)   │     └──────┬───────┘                                 │
│  └──────────────┘            │                                         │
│                              │                                         │
│              ┌───────────────┼───────────────┐                         │
│              │               │               │                         │
│              ▼               ▼               ▼                         │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐               │
│  │     S2       │   │     S3       │   │   事件库     │               │
│  │  产业验证    │   │ AI风格轮动   │   │              │               │
│  │              │   │              │   │ bd_events    │               │
│  │ (代码+智能体)│   │ (代码计算)   │   │ clinical_    │               │
│  │              │   │              │   │ regulatory_  │               │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘               │
│         │                  │                  │                        │
│         │                  │                  │                        │
│         ▼                  ▼                  ▼                        │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐               │
│  │ S2 日报      │   │ S3 日报      │   │ 智能体写入   │               │
│  │ s2/output/   │   │ s3/output/   │   │              │               │
│  └──────────────┘   └──────────────┘   └──────────────┘               │
│                                                                         │
│  S2 与 S3 之间无直接依赖                                                │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 10.3 S1 → S2 数据依赖

**S2 读取 S1 数据**：

```python
# s2/s1_reader.py
from s2.s1_reader import load_latest_s1

# S2 报告中使用 S1 数据：
latest_s1, recent_s1 = load_latest_s1(indicators_dir)
```

**S2 使用 S1 数据的场景**：

| 场景 | 用途 |
|------|------|
| 报告头部 | 显示 S1 指标状态 |
| 综合评分 | S1 分数 + S2 分数计算综合判断 |
| 反证分析 | S1 与 S2 信号冲突时的判断 |
| 趋势分析 | 近期 S1 指标变化趋势 |

### 10.4 S1 → S3 数据依赖

**S3 读取 S1 数据**：

```python
# s2/generate_ai_style_report.py (迁移后为 s3/)
from s2.s1_reader import load_latest_s1

latest_s1, _ = load_latest_s1(indicators_dir)
```

**S3 使用 S1 数据的场景**：

| 场景 | 用途 |
|------|------|
| 风格判断 | 结合 S1 资金面信号 |
| 报告头部 | 显示 S1 指标摘要 |

### 10.5 S2 与 S3 的关系

**S2 和 S3 之间无直接依赖**：

| 关系 | 说明 |
|------|------|
| S2 → S3 | ❌ 无依赖 |
| S3 → S2 | ❌ 无依赖 |
| 共同依赖 | S1 数据 |

**为什么 S2 和 S3 要分开？**

| 模块 | 关注点 | 数据来源 |
|------|--------|---------|
| S2 | 产业基本面验证 | 事件库（需要智能体） |
| S3 | 市场风格轮动 | 行情数据（代码计算） |

两者逻辑完全独立，只是都依赖 S1 的资金面信号。

### 10.6 统一入口

` s2/daily_report_flow.py` 按顺序执行：

```python
STEPS = [
    Step("wb.daily_flow", "更新S1数据、指标和S1日报"),
    Step("s2.update_market_data", "刷新HK_observation缓存"),
    Step("s2.build_data_layer", "构建S2数据层"),
    Step("s2.generate_s2_report", "生成S2产业验证日报"),
    Step("s2.generate_ai_style_report", "生成AI风格日报"),  # 将迁移到 s3
]
```

**执行顺序**：
1. S1 先计算（产生 `data/indicators/*.json`）
2. S2 和 S3 都读取 S1 结果
3. S2 和 S3 独立生成报告

### 10.7 数据一致性保障

`_validate_outputs()` 检查：

```python
# 检查 S2 报告日期是否与 S1 对齐
if f"**报告日期**: {report_date}" not in s2_text:
    raise SystemExit(f"S2报告日期未对齐最新S1日期")

# 检查 S2 报告是否引用了最新 S1
if f"S1指标已更新到 {latest_s1.trade_date}" not in s2_text:
    raise SystemExit(f"S2报告内S1状态未对齐")
```

---

## 十一、S2 智能体任务设计（Agent 思维）

### 11.1 问题回顾

**S2 事件数据现状**：

| 数据类型 | 最后更新 | 滞后天数 |
|---------|----------|----------|
| BD 事件 | Jun 4 | 18 天 |
| 临床事件 | Jun 5 | 17 天 |
| 审批事件 | Jun 4 | 18 天 |
| 业绩事件 | May 11 | 42 天 |
| 一致预期 | 全部 missing | - |

**为什么智能体"全部 Miss"？**

传统做法把智能体当爬虫用：
```
步骤 1：去 FierceBiotech 搜索 China
步骤 2：提取公司、金额、日期
步骤 3：用 append_events() 写入
```

这不是在用 Agent，是在用它模拟代码。

### 11.2 Agent 设计原则（来自研究）

| 传统做法 | Agent 思维 |
|---------|-----------|
| 给步骤：步骤1、步骤2、步骤3 | 给目标：让智能体自己规划 |
| 告诉它怎么做 | 让它自己想怎么做 |
| 执行模板 | 自主探索 |
| 把智能体当代码用 | 把智能体当实习生用 |

**关键原则**：

1. **给目标，不是给步骤**
   - 告诉智能体"追踪创新药行业动态，重要的记下来"
   - 不是"去网站A搜索关键词B，提取字段C"

2. **给背景知识，让智能体自己判断**
   - 龙头公司有哪些
   - 金额阈值是多少
   - 什么类型的事件重要

3. **给验证方式，让智能体自我检查**
   - 运行报告生成验证
   - 检查输出是否正确

4. **Context Window 是核心约束**
   - 使用 subagent 处理会淹没主对话的任务
   - 保持指令简洁

5. **验证机制让智能体"可以走开"**
   - 给测试/构建/检查命令
   - 智能体可以自我验证，减少人工监管频率

### 11.3 S2 事件收集智能体任务

**任务描述**：

```markdown
你是创新药投资研究员，负责追踪可能影响 159567 创新药 ETF 的事件。

## 目标

每天发现并记录重要的行业事件，写入 s2/data/ 目录下的事件库。

## 背景知识

### 龙头公司
- 恒瑞医药 (600276.SH)
- 信达生物 (01801.HK)
- 百济神州 (688235.SH / BGNE.US)
- 翰森制药 (3692.HK)
- 荣昌生物 (9995.HK)
- 云顶新耀 (1952.HK)
- 诺诚健华 (9969.HK)
- 海思科 (002653.SZ)
- 三生制药 (1530.HK)

### 关键事件类型
1. **BD 交易**：license-in/out、战略合作、商业化许可
2. **临床数据**：Phase II/III 数据读出、会议报告（ASCO、ESMO等）
3. **监管审批**：NDA/BLA 受理、获批、CDE 公示
4. **政策风险**：BIOSECURE、医保目录调整

### 重要性判断
- BD 交易：首付款 > 5000 万美元值得记录
- 临床数据：Phase II 以上，主要终点达到
- 监管审批：NDA/BLA 级别
- 政策风险：可能影响整个行业

### 来源可靠性
- Tier 1：公司官方 IR、监管机构公告（NMPA、FDA）
- Tier 2：权威行业媒体（FierceBiotech、Endpoints News）
- Tier 3：其他媒体报道

## 你需要自己决定

1. **去哪里找信息**
   - 公司官网 IR 页面
   - 行业媒体网站
   - 监管机构公告
   - 学术会议摘要

2. **什么信息值得记录**
   - 重要性判断
   - 相关性判断（是否影响 159567 成分股）

3. **如何验证信息可靠性**
   - 交叉验证
   - 来源可靠性评估

4. **如何组织数据**
   - 字段填充
   - 去重逻辑

## 验证方式

完成后运行：
```bash
uv run python -m s2.generate_s2_report
```

检查事件是否正确显示在报告中。

## 输出位置

事件写入：
- `s2/data/bd_events.csv` - BD 交易事件
- `s2/data/clinical_events.csv` - 临床数据事件
- `s2/data/regulatory_events.csv` - 监管审批事件
- `s2/data/policy_risk_events.csv` - 政策风险事件

可用工具：
```python
from s2.event_store import append_events
append_events(path, [event_dict])
```
```

### 11.4 与传统做法的对比

| 维度 | 传统做法 | Agent 思维 |
|------|---------|-----------|
| 指令风格 | 步骤化、代码化 | 目标导向、背景丰富 |
| 执行方式 | 执行模板 | 自主探索规划 |
| 判断能力 | 预设规则 | 基于背景知识判断 |
| 灵活性 | 低（固定路径） | 高（自主决策） |
| 适用场景 | 结构化任务 | 需要判断力的任务 |

### 11.5 实施建议

1. **创建智能体任务文件**
   - 文件：`s2/agent_task.md`
   - 内容：上述任务描述

2. **保持事件库接口可用**
   - `append_events()` 函数已存在
   - 字段规范已定义

3. **验证机制**
   - 报告生成是天然验证
   - 智能体可以自我检查

### 11.6 Orchestrator-Workers 模式

对于更复杂的智能体任务，可采用 Orchestrator-Workers 模式：

> "For dynamic research tasks, use the orchestrator-workers pattern where a central LLM dynamically breaks down tasks, delegates them to worker LLMs, and synthesizes their results."

**适用场景**：
- 需要多个数据源的信息收集
- 子任务可以并行执行
- 最终结果需要综合多个来源

**关键点**：子任务是**动态决定**的，不是预设的。
