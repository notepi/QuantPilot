# 数据源切换：citydata 代理 → tushare 直连

## 背景

当前系统通过 `citydata.club` 代理访问 tushare 数据，现需切换为直接连接 tushare 官方 API。

## 当前架构

1. **wb/tushare_proxy.py** - 通过 `https://tushare.citydata.club` 代理访问
2. **s2/citydata_client.py** - S2 模块专用，也通过 citydata 代理
3. **.env** - 包含 `CITYDATA_TOKEN` 和 `tushare` token

## 目标架构

直接使用 tushare 官方 SDK：
```python
import tushare as ts
pro = ts.pro_api(token)
```

## 执行步骤

### 1. 修改 .env 文件
- 将 `tushare=9988804f...` 改为 `TUSHARE_TOKEN=9988804f...`
- 保留 `CITYDATA_TOKEN` 作为备用（可选）

### 2. 修改 wb/tushare_proxy.py
- 移除 citydata 代理逻辑
- 直接使用 tushare SDK
- 保持 `pro_api()` 接口不变（业务代码零改动）

### 3. 修改 s2/citydata_client.py
- 同样切换到 tushare SDK
- 或者复用 `wb/tushare_proxy.py`

### 4. 验证
- 运行 S1 数据更新测试
- 运行 S2 数据更新测试
- 确保所有数据接口正常工作

## 风险评估

- **低风险**：只是数据源切换，不改变业务逻辑
- **兼容性**：保持 `pro_api()` 接口不变，所有业务代码无需修改
- **回滚**：如有问题可快速切回 citydata 代理

## 预期结果

- 数据更新流程正常运行
- S1/S2/S3 报告生成正常
- 无需修改业务代码
