"""
指标日报生成脚本

生成横轴按指标、纵轴按日期的 Markdown 表格
"""
import json
import pandas as pd
from pathlib import Path
from datetime import datetime

# 数据目录
DATA_DIR = Path(__file__).parent.parent / "data"
INDICATORS_DIR = DATA_DIR / "indicators"

# 指标定义
INDICATOR_NAMES = {
    "S1-01": "资金回流",
    "S1-02": "份额变化",
    "S1-03": "相对强度",
    "S1-04": "成交放大",
    "S1-05": "广度修复",
    "S1-06": "龙头先行",
}

INDICATOR_WEIGHTS = {
    "S1-01": 0.22,
    "S1-02": 0.18,
    "S1-03": 0.20,
    "S1-04": 0.14,
    "S1-05": 0.14,
    "S1-06": 0.12,
}


def get_expectation_icon(level: str) -> str:
    """获取预期等级图标"""
    icons = {
        "超预期": "🟢",
        "符合预期": "🟡",
        "低于预期": "🔴",
    }
    return icons.get(level, "⚪")


def format_value(code: str, value: float) -> str:
    """格式化指标值"""
    if code == "S1-04":
        return f"{value:.2f}x"
    else:
        return f"{value:.2%}"


def generate_report() -> str:
    """生成 Markdown 报告"""

    # 读取所有指标数据
    records = []
    for filepath in sorted(INDICATORS_DIR.glob("*.json")):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        record = {"日期": data["trade_date"]}
        for ind in data["indicator_results"]:
            record[ind["code"]] = ind["value"]
            record[f"{ind['code']}_预期"] = ind["expectation"]
            # 收集数据日期
            if ind.get("data_date"):
                record[f"{ind['code']}_数据日期"] = ind["data_date"]
        record["综合得分"] = data["total_score"]
        record["预期等级"] = data["expectation_level"]

        # 检查数据日期是否一致
        data_dates = set()
        for ind in data["indicator_results"]:
            if ind.get("data_date"):
                data_dates.add(ind["data_date"])
        if data_dates and len(data_dates) == 1:
            record["数据日期"] = data_dates.pop()
        elif data_dates:
            record["数据日期"] = max(data_dates)  # 取最滞后的日期
        else:
            record["数据日期"] = ""

        records.append(record)

    if not records:
        return "# 指标日报\n\n暂无数据"

    df = pd.DataFrame(records)
    df["日期"] = pd.to_datetime(df["日期"], format="%Y%m%d").dt.strftime("%Y-%m-%d")
    # 格式化数据日期
    if "数据日期" in df.columns:
        df["数据日期"] = df["数据日期"].apply(
            lambda x: pd.to_datetime(str(x), format="%Y%m%d").strftime("%Y-%m-%d")
            if x and len(str(x)) == 8 else x
        )
    df = df.sort_values("日期", ascending=False)

    # 构建 Markdown
    lines = []
    lines.append("# 创新药投资阶段评价 - 指标日报")
    lines.append("")
    lines.append(f"**标的**: 589720.SH | **更新时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    # 显示最新记录的数据日期信息
    if len(df) > 0:
        latest_row = df.iloc[0]
        if latest_row.get("数据日期") and latest_row["数据日期"]:
            report_date = latest_row["日期"]
            data_date = latest_row["数据日期"]
            if report_date != data_date:
                lines.append(f"⚠️ **数据日期**: {data_date}（报告日期 {report_date}，份额数据滞后）")
            else:
                lines.append(f"**数据日期**: {data_date}（与报告日期一致）")
    lines.append("")

    # 表格1：指标值
    lines.append("## 指标数值")
    lines.append("")

    # 表头
    header = "| 日期 | S1-01 | S1-02 | S1-03 | S1-04 | S1-05 | S1-06 | 综合得分 | 预期等级 |"
    separator = "|------|-------|-------|-------|-------|-------|-------|----------|----------|"
    lines.append(header)
    lines.append(separator)

    # 数据行
    for _, row in df.iterrows():
        date_str = row["日期"]
        values = []
        for code in ["S1-01", "S1-02", "S1-03", "S1-04", "S1-05", "S1-06"]:
            val = row.get(code, 0)
            exp = row.get(f"{code}_预期", "未知")
            icon = get_expectation_icon(exp)
            formatted = format_value(code, val)
            values.append(f"{formatted} {icon}")

        score = row["综合得分"]
        level = row["预期等级"]
        level_icon = get_expectation_icon(level)

        line = f"| {date_str} | {' | '.join(values)} | {score:.2f} | {level_icon} {level} |"
        lines.append(line)

    lines.append("")

    # 图例
    lines.append("**图例**: 🟢 超预期 | 🟡 符合预期 | 🔴 低于预期")
    lines.append("")

    # 表格2：指标说明
    lines.append("## 指标说明")
    lines.append("")
    lines.append("| 指标 | 名称 | 权重 | 说明 |")
    lines.append("|------|------|------|------|")
    lines.append("| S1-01 | 资金回流连续性 | 22% | 近10日份额增加天数占比，≥70%超预期 |")
    lines.append("| S1-02 | ETF份额变化 | 18% | 近10日份额变化率，≥3%超预期 |")
    lines.append("| S1-03 | ETF相对强度 | 20% | 589720收益-159557收益，≥5%超预期 |")
    lines.append("| S1-04 | 成交放大持续性 | 14% | 5日均/20日均成交额，≥1.5x超预期 |")
    lines.append("| S1-05 | 板块广度修复 | 14% | 成分股站上20日均线占比，≥60%超预期 |")
    lines.append("| S1-06 | 龙头先行强度 | 12% | 龙头组合收益-ETF收益，≥5%超预期 |")
    lines.append("")

    # 表格3：评分规则
    lines.append("## 评分规则")
    lines.append("")
    lines.append("| 综合得分 | 预期等级 |")
    lines.append("|----------|----------|")
    lines.append("| ≥0.80 | 超预期 🟢 |")
    lines.append("| 0.60-0.80 | 符合预期 🟡 |")
    lines.append("| 0.40-0.60 | 低于预期 🔴 |")
    lines.append("| <0.40 | 严重低于预期 |")
    lines.append("")

    # 最近趋势
    lines.append("## 最近趋势")
    lines.append("")

    if len(df) >= 2:
        latest = df.iloc[0]
        prev = df.iloc[1]
        change = latest["综合得分"] - prev["综合得分"]
        change_str = f"{'+' if change >= 0 else ''}{change:.2f}"

        lines.append(f"- **最新得分**: {latest['综合得分']:.2f} ({change_str})")
        lines.append(f"- **预期等级**: {latest['预期等级']}")

        # 找出表现最好和最差的指标
        best_code = None
        worst_code = None
        best_val = -999
        worst_val = 999

        for code in ["S1-01", "S1-02", "S1-03", "S1-04", "S1-05", "S1-06"]:
            val = latest.get(code, 0)
            exp = latest.get(f"{code}_预期", "")
            if exp == "超预期" and val > best_val:
                best_val = val
                best_code = code
            if exp == "低于预期" and val < worst_val:
                worst_val = val
                worst_code = code

        if best_code:
            lines.append(f"- **表现最好**: {best_code} {INDICATOR_NAMES.get(best_code, '')} (超预期)")
        if worst_code:
            lines.append(f"- **需关注**: {worst_code} {INDICATOR_NAMES.get(worst_code, '')} (低于预期)")

    lines.append("")

    # 数据统计
    lines.append("## 数据统计")
    lines.append("")
    lines.append(f"- 数据天数: {len(df)}")
    lines.append(f"- 日期范围: {df['日期'].min()} ~ {df['日期'].max()}")
    lines.append("")

    return "\n".join(lines)


def save_report():
    """保存报告到文件"""
    report = generate_report()

    # 保存到 docs 目录
    output_path = DATA_DIR.parent / "docs" / "daily_report.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"报告已保存到: {output_path}")
    return output_path


if __name__ == "__main__":
    path = save_report()
    print(f"\n{'='*50}")
    print("报告内容预览:")
    print("="*50)
    print(generate_report())