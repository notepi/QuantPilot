# API 端点说明

## 启动服务

```bash
uv run python -m wb.api_server
```

默认端口：8000

## 端点列表

| 端点 | 方法 | 说明 |
|------|------|------|
| `/` | GET | 服务信息 |
| `/health` | GET | 健康检查 |
| `/indicators` | GET | 指标定义列表 |
| `/indicators/latest` | GET | 最新指标结果 |
| `/indicators/{trade_date}` | GET | 指定日期结果 |
| `/indicators/history` | GET | 可用日期列表 |
| `/calculate` | GET | 实时计算（不保存） |
| `/calculate` | POST | 计算并保存 |

## 示例

```bash
# 获取最新结果
curl http://localhost:8000/indicators/latest

# 获取指定日期
curl http://localhost:8000/indicators/20260327

# 实时计算
curl http://localhost:8000/calculate

# 计算并保存
curl -X POST http://localhost:8000/calculate
```

## 响应格式

```json
{
  "phase": "第一阶段",
  "trade_date": "20260327",
  "total_score": 0.56,
  "expectation_level": "低于预期",
  "indicator_results": [...],
  "summary": "综合得分 0.56..."
}
```