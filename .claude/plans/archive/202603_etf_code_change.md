# 标的代码修改计划

## 背景

用户需要将主标的从 **159567.SZ**（港股创新药ETF）改为 **589720.SH**。基准 ETF **159557.SZ** 保持不变。

**重要变更**: 所有数据接口统一使用 **citydata 代理**，不再使用官方 Tushare API。

## 修改范围

| 类别 | 文件数 | 说明 |
|------|--------|------|
| Excel 文档 | 1 | 使用 openpyxl 批量替换 |
| Python 代码 | 7 | ETF_CODE 常量 + 注释 + 接口统一 |
| Markdown 文档 | 1 | indicators.md |
| 数据文件 | 清空 | 删除旧数据重新抓取 |

---

## 步骤一：修改 Excel 文档

**文件**: [创新药_第一阶段_v2_claude.xlsx](docs/创新药_第一阶段_v2_claude.xlsx)

创建临时脚本处理：
```python
from openpyxl import load_workbook

wb = load_workbook("docs/创新药_第一阶段_v2_claude.xlsx")
for sheet in wb.worksheets:
    for row in sheet.iter_rows():
        for cell in row:
            if cell.value and isinstance(cell.value, str):
                cell.value = cell.value.replace("159567", "589720")
                cell.value = cell.value.replace("159567.SZ", "589720.SH")
wb.save("docs/创新药_第一阶段_v2_claude.xlsx")
```

---

## 步骤二：修改 Python 代码

### 2.1 [wb/update_data.py](wb/update_data.py)（关键修改）

**接口统一为 citydata**:
- 移除 `import tushare as ts` 和 `TUSHARE_TOKEN` 使用
- 港股数据改用 citydata 代理的 `hk_daily` 接口
- 移除 `should_update_hk_daily()` 缓存检查（citydata 无限制）
- 移除接口限制警告

**ETF 代码修改**（5处）:

| 行号 | 修改内容 |
|------|----------|
| 23 | 注释 `159567成分股` → `589720成分股` |
| 70 | `ts_code="159567.SZ"` → `ts_code="589720.SH"` |
| 92 | 注释 `159567和159557` → `589720和159557` |
| 94 | `["159567.SZ", "159557.SZ"]` → `["589720.SH", "159557.SZ"]` |
| 119 | `ts_code="159567.SZ"` → `ts_code="589720.SH"` |

**港股接口改用 citydata**:

| 原代码 | 修改后 |
|--------|--------|
| `import tushare as ts` | 移除（只用 citydata） |
| `token = os.getenv("TUSHARE_TOKEN")` | 移除 |
| `pro = ts.pro_api(token)` | `pro = citydata_pro_api()` |
| `should_update_hk_daily()` 检查 | 移除（citydata 无限制） |
| 警告 "每分钟2次，每天10次" | 移除 |

**重要**: HK_STOCKS 龙头组合（第24-31行）需在获取新 ETF 持仓后重新定义。

### 2.2 指标文件（6个文件，各修改 ETF_CODE）

| 文件 | 行号 | 修改 |
|------|------|------|
| [s1_01_capital_flow.py](wb/indicators/s1_01_capital_flow.py) | 27 | `ETF_CODE = "589720.SH"` + 注释 |
| [s1_02_share_change.py](wb/indicators/s1_02_share_change.py) | 27 | `ETF_CODE = "589720.SH"` + 注释 |
| [s1_03_relative_strength.py](wb/indicators/s1_03_relative_strength.py) | 27 | `ETF_CODE = "589720.SH"`（BENCHMARK_CODE 保持不变）+ 注释 |
| [s1_04_volume_ratio.py](wb/indicators/s1_04_volume_ratio.py) | 26 | `ETF_CODE = "589720.SH"` + 注释 |
| [s1_05_breadth_repair.py](wb/indicators/s1_05_breadth_repair.py) | 27 | `ETF_CODE = "589720.SH"` + 注释 |
| [s1_06_leader_strength.py](wb/indicators/s1_06_leader_strength.py) | 34 | `ETF_CODE = "589720.SH"` + 注释 |

### 2.3 [s1_06_leader_strength.py](wb/indicators/s1_06_leader_strength.py) 龙头组合

**关键**: 需要根据新 ETF 的成分股重新定义：
- `LEADER_STOCKS`（第38-44行）
- `LEADER_WEIGHTS`（第47行）

处理流程：
1. 先运行 `update_data.py` 获取 fund_portfolio.csv
2. 检查新 ETF 成分股类型（港股/A股）
3. 更新龙头组合代码和权重

---

## 步骤三：修改 Markdown 文档

**文件**: [docs/indicators.md](docs/indicators.md)

| 行号 | 修改内容 |
|------|----------|
| 8 | `S1-02 159567份额变化率` → `S1-02 589720份额变化率` |
| 9 | `159567收益-159557收益` → `589720收益-159557收益` |
| 12 | `龙头组合收益-159567收益` → `龙头组合收益-589720收益` |

---

## 步骤四：清空数据重新抓取

```bash
# 删除旧数据
rm -f data/raw/*.csv
rm -f data/indicators/*.json

# 抓取新数据
uv run python -m wb.update_data

# 检查成分股，更新龙头组合代码
# 计算指标
uv run python -m wb.calculate_indicators
```

---

## 步骤五：验证

1. 检查数据文件包含 589720
2. 运行指标计算无报错
3. 启动 API 服务测试端点

```bash
uv run python -m wb.api_server
curl http://localhost:8000/indicators/latest
```

---

## 注意事项

1. **接口统一**: 所有数据接口使用 citydata 代理，无限制
   - fund_share, fund_daily, fund_portfolio: citydata 代理（无限制）
   - hk_daily: 改用 citydata 代理（无限制，不再用官方 Tushare）

2. **新 ETF 成分股类型**: 589720.SH 的成分股可能是港股或A股，需确认后调整数据源
   - 港股：继续使用 hk_daily 接口（通过 citydata）
   - A股：需改用 A股日线接口（daily）

3. **基准ETF**: 159557.SZ 保持不变，无需修改

4. **简化代码**: 移除官方 Tushare 相关代码和限制检查