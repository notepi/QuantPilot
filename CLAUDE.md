# 创新药投资阶段评价量化系统

## 背景

量化评价创新药ETF投资阶段。
- 标的: 589720.SH
- 基准: 159557.SZ
- 当前阶段: 第一阶段（预期重定价）

## 协作流程

严格按以下顺序执行：
1. 用户定任务
2. Claude 做 plan → 写入 `.claude/plans/active/`
3. 用户确认 plan
4. Claude 执行
5. 测试验证
6. **用户确认测试通过后**，Claude 才能修改 CLAUDE.md
7. plan 归档到 `.claude/plans/archive/`

## 操作

见 [docs/usage.md](docs/usage.md)

## 数据接口

统一使用 citydata 代理，配置 `.env`:
```
CITYDATA_TOKEN=xxx
```

## 文档索引

- docs/file_structure.md - 项目文件目录结构
- docs/usage.md - 命令使用指南（每日流程、回测、API、界面）
- docs/indicators.md - 指标定义与阈值（S1-01~S1-06 口径说明）
- docs/daily_report.md - 指标日报（横轴指标，纵轴日期）
- docs/dashboard_prd.md - 可视化界面PRD（5模块设计）
- docs/创新药_第一阶段_v2_claude.xlsx - 指标详细定义（业务口径）
- .claude/plans/archive/ - 历史开发计划