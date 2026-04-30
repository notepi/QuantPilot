# 数据更新优化计划

## 目标
避免一天内多次调用 hk_daily 接口导致超限（每天10次限制）

## 背景
- 官方 Tushare hk_daily 接口限制：每分钟2次，每天10次
- 当前 update_hk_daily() 每次运行都会请求接口
- 用户可能因调试、测试等原因一天内多次运行 update_data.py

## 实现方案

### 方案：检查本地数据是否已是最新

在 `update_hk_daily()` 前检查：
1. 本地 `hk_daily.csv` 是否存在
2. 最新数据日期是否 >= 今天
3. 如果已是最新，跳过请求

### 修改文件
`wb/update_data.py`

### 代码逻辑

```python
def should_update_hk_daily() -> bool:
    """检查是否需要更新港股数据"""
    filepath = DATA_DIR / "hk_daily.csv"

    # 文件不存在，需要更新
    if not filepath.exists():
        return True

    # 检查最新日期
    df = pd.read_csv(filepath)
    df["trade_date"] = df["trade_date"].astype(str)
    latest_date = df["trade_date"].max()

    # 获取今天日期
    from datetime import datetime
    today = datetime.now().strftime("%Y%m%d")

    # 如果最新数据 >= 今天，跳过更新
    if latest_date >= today:
        print(f"  hk_daily 数据已是最新 ({latest_date})，跳过更新")
        return False

    return True


def update_hk_daily():
    """更新港股日线数据"""
    print("更新 hk_daily...")

    # 检查是否需要更新
    if not should_update_hk_daily():
        return None

    print("  警告：hk_daily 接口限制每分钟2次，每天10次")

    # ... 原有请求逻辑 ...
```

### 优化点

1. **交易日判断**：如果是非交易日（周末/节假日），检查最新数据是否 >= 最近交易日
2. **强制更新参数**：保留 `--force` 参数允许强制更新

## 验证方式

```bash
# 第一次运行（数据不存在或过期）
uv run python -m wb.update_data
# 输出：正在请求 hk_daily 数据...

# 第二次运行（数据已是最新）
uv run python -m wb.update_data
# 输出：hk_daily 数据已是最新 (20260330)，跳过更新

# 强制更新
uv run python -m wb.update_data --force
# 输出：强制更新 hk_daily...
```

## 实施步骤

1. 在 `update_data.py` 添加 `should_update_hk_daily()` 函数
2. 修改 `update_hk_daily()` 调用检查函数
3. 添加 `--force` 命令行参数支持
4. 测试验证