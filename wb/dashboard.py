"""
创新药投资阶段评价量化系统 - 可视化界面

使用 Streamlit 构建
基于 创新药_第一阶段_v2_claude.xlsx 设计
"""
import json
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import streamlit as st

# 数据目录
DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
INDICATORS_DIR = DATA_DIR / "indicators"

# ETF代码
ETF_CODE = "589720.SH"
ETF_NAME = "创新药ETF"
BENCHMARK_CODE = "159557.SZ"

# 指标定义（按角色分类）
CORE_INDICATORS = {
    "S1-01": "资金回流连续性",
    "S1-02": "ETF份额变化",
    "S1-03": "ETF相对强度",
}
CONFIRM_INDICATORS = {
    "S1-04": "成交放大持续性",
}
SUPPORT_INDICATORS = {
    "S1-05": "板块广度修复",
    "S1-06": "龙头先行强度",
}
ALL_INDICATORS = {**CORE_INDICATORS, **CONFIRM_INDICATORS, **SUPPORT_INDICATORS}


# ==================== 数据加载函数 ====================

@st.cache_data
def load_all_indicators() -> pd.DataFrame:
    """加载所有指标数据"""
    if not INDICATORS_DIR.exists():
        return pd.DataFrame()

    records = []
    for filepath in sorted(INDICATORS_DIR.glob("*.json"), reverse=True):
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        record = {
            "trade_date": data["trade_date"],
            "total_score": data["total_score"],
            "expectation_level": data["expectation_level"],
        }

        for indicator in data["indicator_results"]:
            record[indicator["code"]] = indicator["value"]
            record[f"{indicator['code']}_expectation"] = indicator["expectation"]

        records.append(record)

    df = pd.DataFrame(records)
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    df = df.sort_values("trade_date")

    return df


@st.cache_data
def load_fund_daily() -> pd.DataFrame:
    """加载ETF日线数据"""
    filepath = RAW_DIR / "fund_daily.csv"
    if not filepath.exists():
        return pd.DataFrame()
    df = pd.read_csv(filepath)
    df["trade_date"] = pd.to_datetime(df["trade_date"].astype(str), format="%Y%m%d")
    return df


@st.cache_data
def load_fund_share() -> pd.DataFrame:
    """加载ETF份额数据"""
    filepath = RAW_DIR / "fund_share.csv"
    if not filepath.exists():
        return pd.DataFrame()
    df = pd.read_csv(filepath)
    df["trade_date"] = pd.to_datetime(df["trade_date"].astype(str), format="%Y%m%d")
    return df


@st.cache_data
def load_daily() -> pd.DataFrame:
    """加载A股成分股日线数据"""
    filepath = RAW_DIR / "daily.csv"
    if not filepath.exists():
        return pd.DataFrame()
    df = pd.read_csv(filepath)
    df["trade_date"] = pd.to_datetime(df["trade_date"].astype(str), format="%Y%m%d")
    return df


@st.cache_data
def load_portfolio() -> pd.DataFrame:
    """加载ETF持仓数据"""
    filepath = RAW_DIR / "fund_portfolio.csv"
    if not filepath.exists():
        return pd.DataFrame()
    df = pd.read_csv(filepath)
    return df


# ==================== 辅助函数 ====================

def get_expectation_color(level: str) -> str:
    """获取预期等级颜色"""
    colors = {
        "超预期": "🟢",
        "符合预期": "🟡",
        "低于预期": "🔴",
    }
    return colors.get(level, "⚪")


def get_expectation_bg(level: str) -> str:
    """获取预期等级背景色"""
    colors = {
        "超预期": "rgba(0,200,0,0.2)",
        "符合预期": "rgba(255,165,0,0.2)",
        "低于预期": "rgba(255,0,0,0.2)",
    }
    return colors.get(level, "rgba(128,128,128,0.2)")


# ==================== 页面模块 ====================

def show_overview(df_indicators: pd.DataFrame):
    """综合概览 - 回答"当前是否值得参与" """
    st.header("📊 综合概览")
    st.caption("第一阶段：预期重定价（1-3月）- 市场是否从'不信'转向'愿意先信一点'")

    if df_indicators.empty:
        st.error("未找到指标数据，请先运行 `python -m wb.calculate_indicators history 30`")
        return

    latest = df_indicators.iloc[-1]

    # ===== 顶部状态栏 =====
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("最新日期", latest["trade_date"].strftime("%Y-%m-%d"))

    with col2:
        delta = latest['total_score'] - df_indicators.iloc[-2]['total_score'] if len(df_indicators) > 1 else 0
        st.metric("综合得分", f"{latest['total_score']:.2f}", delta=f"{delta:+.2f}")

    with col3:
        st.metric("预期等级", f"{get_expectation_color(latest['expectation_level'])} {latest['expectation_level']}")

    with col4:
        st.metric("数据天数", len(df_indicators))

    st.divider()

    # ===== 核心指标卡片 =====
    st.subheader("核心指标")
    st.caption("判断是否'连续回来'，不是单日脉冲")

    cols = st.columns(3)
    for i, (code, name) in enumerate(CORE_INDICATORS.items()):
        with cols[i]:
            value = latest.get(code, 0)
            exp = latest.get(f"{code}_expectation", "未知")
            bg_color = get_expectation_bg(exp)

            st.markdown(
                f"""
                <div style='background-color:{bg_color}; padding:15px; border-radius:10px;'>
                    <h4>{code}</h4>
                    <p style='font-size:24px; font-weight:bold;'>{value:.2%}</p>
                    <p>{get_expectation_color(exp)} {exp}</p>
                    <p style='font-size:12px; color:gray;'>{name}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.divider()

    # ===== 确认指标 + 支撑指标 =====
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("确认指标")
        st.caption("验证修复是否持续放量")
        for code, name in CONFIRM_INDICATORS.items():
            value = latest.get(code, 0)
            exp = latest.get(f"{code}_expectation", "未知")
            st.metric(f"{code} {name}", f"{value:.2f}x", f"{exp}")

    with col_right:
        st.subheader("支撑指标")
        st.caption("验证是否扩散到更多个股")
        for code, name in SUPPORT_INDICATORS.items():
            value = latest.get(code, 0)
            exp = latest.get(f"{code}_expectation", "未知")
            st.metric(f"{code} {name}", f"{value:.2%}", f"{exp}")

    st.divider()

    # ===== 得分趋势图 =====
    st.subheader("综合得分趋势")

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df_indicators["trade_date"],
        y=df_indicators["total_score"],
        mode="lines+markers",
        name="综合得分",
        line=dict(color="#1f77b4", width=2),
        marker=dict(size=8),
        hovertemplate="日期: %{x|%Y-%m-%d}<br>得分: %{y:.2f}<extra></extra>",
    ))

    # 阈值线
    fig.add_hline(y=0.80, line_dash="dash", line_color="green",
                  annotation_text="超预期 (≥0.80)", annotation_position="right")
    fig.add_hline(y=0.60, line_dash="dash", line_color="orange",
                  annotation_text="符合预期 (0.60-0.80)", annotation_position="right")
    fig.add_hline(y=0.40, line_dash="dash", line_color="red",
                  annotation_text="低于预期 (<0.40)", annotation_position="right")

    fig.update_layout(
        height=350,
        xaxis_title="日期",
        yaxis_title="得分",
        yaxis_range=[0, 1],
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)


def show_etf_market(df_fund_daily: pd.DataFrame, df_fund_share: pd.DataFrame):
    """ETF行情 - 回答"标的本身表现如何" """
    st.header("📈 ETF行情")
    st.caption(f"标的: {ETF_CODE} | 基准: {BENCHMARK_CODE}")

    if df_fund_daily.empty:
        st.error("未找到ETF日线数据")
        return

    # 筛选数据
    etf_data = df_fund_daily[df_fund_daily["ts_code"] == ETF_CODE].sort_values("trade_date")
    benchmark_data = df_fund_daily[df_fund_daily["ts_code"] == BENCHMARK_CODE].sort_values("trade_date")

    if etf_data.empty:
        st.error(f"未找到 {ETF_CODE} 数据")
        return

    latest = etf_data.iloc[-1]

    # ===== 关键数据卡片 =====
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("最新价", f"{latest['close']:.3f}")

    with col2:
        pct_chg = latest['pct_chg']
        st.metric("涨跌幅", f"{pct_chg:+.2f}%")

    with col3:
        st.metric("成交额(万)", f"{latest['amount']:.0f}")

    with col4:
        if not df_fund_share.empty:
            share_data = df_fund_share[df_fund_share["ts_code"] == ETF_CODE].sort_values("trade_date")
            if not share_data.empty:
                share_latest = share_data.iloc[-1]
                share_prev = share_data.iloc[-2] if len(share_data) > 1 else share_latest
                share_chg = (share_latest['fd_share'] - share_prev['fd_share']) / share_prev['fd_share'] * 100
                st.metric("份额(万份)", f"{share_latest['fd_share']:.0f}", delta=f"{share_chg:+.2f}%")
            else:
                st.metric("份额", "无数据")
        else:
            st.metric("份额", "无数据")

    # ===== 成交放大倍数 =====
    if len(etf_data) >= 20:
        avg_5d = etf_data["amount"].tail(5).mean()
        avg_20d = etf_data["amount"].tail(20).mean()
        volume_ratio = avg_5d / avg_20d if avg_20d > 0 else 0

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("5日均成交(万)", f"{avg_5d:.0f}")
        with col2:
            st.metric("20日均成交(万)", f"{avg_20d:.0f}")
        with col3:
            ratio_color = "green" if volume_ratio >= 1.5 else "orange" if volume_ratio >= 1.1 else "red"
            st.metric("成交放大倍数", f"{volume_ratio:.2f}x")
            if volume_ratio >= 1.5:
                st.success("持续放量 ✓")
            elif volume_ratio >= 1.1:
                st.info("温和放量")
            else:
                st.warning("缩量")

    st.divider()

    # ===== 价格走势图 =====
    st.subheader("价格走势")
    st.caption(f"{ETF_CODE} vs {BENCHMARK_CODE} (基准)")

    fig = go.Figure()

    # ETF价格
    fig.add_trace(go.Scatter(
        x=etf_data["trade_date"],
        y=etf_data["close"],
        mode="lines",
        name=ETF_CODE,
        line=dict(color="#1f77b4", width=2),
    ))

    # 基准价格（归一化）
    if not benchmark_data.empty:
        base_close = benchmark_data["close"].iloc[0]
        etf_base = etf_data["close"].iloc[0]
        benchmark_data = benchmark_data.copy()
        benchmark_data["norm_close"] = benchmark_data["close"] / base_close * etf_base

        fig.add_trace(go.Scatter(
            x=benchmark_data["trade_date"],
            y=benchmark_data["norm_close"],
            mode="lines",
            name=f"{BENCHMARK_CODE} (归一化)",
            line=dict(color="#ff7f0e", width=1, dash="dash"),
        ))

    fig.update_layout(
        height=350,
        xaxis_title="日期",
        yaxis_title="价格",
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)

    # ===== 成交额柱状图 =====
    st.subheader("成交额变化")

    fig2 = go.Figure()

    # 成交额柱状图
    fig2.add_trace(go.Bar(
        x=etf_data["trade_date"].tail(20),
        y=etf_data["amount"].tail(20),
        name="成交额",
        marker_color="#2ca02c",
    ))

    # 5日均线
    if len(etf_data) >= 5:
        etf_tail = etf_data.tail(20).copy()
        etf_tail["ma5"] = etf_tail["amount"].rolling(5).mean()
        fig2.add_trace(go.Scatter(
            x=etf_tail["trade_date"],
            y=etf_tail["ma5"],
            mode="lines",
            name="5日均",
            line=dict(color="red", width=2),
        ))

    fig2.update_layout(
        height=250,
        xaxis_title="日期",
        yaxis_title="成交额(万元)",
    )

    st.plotly_chart(fig2, use_container_width=True)

    # ===== 份额变化图 =====
    if not df_fund_share.empty:
        st.subheader("份额变化")

        share_data = df_fund_share[df_fund_share["ts_code"] == ETF_CODE].sort_values("trade_date")

        if not share_data.empty:
            fig3 = go.Figure()

            fig3.add_trace(go.Scatter(
                x=share_data["trade_date"],
                y=share_data["fd_share"],
                mode="lines+markers",
                name="份额",
                line=dict(color="#9467bd", width=2),
            ))

            fig3.update_layout(
                height=250,
                xaxis_title="日期",
                yaxis_title="份额(万份)",
            )

            st.plotly_chart(fig3, use_container_width=True)


def show_holdings(df_daily: pd.DataFrame, df_portfolio: pd.DataFrame):
    """成分股详情 - 回答"龙头和成分股表现如何" """
    st.header("🏢 成分股详情")
    st.caption("S1-06 龙头先行强度 - 龙头是否强于ETF")

    if df_portfolio.empty:
        st.error("未找到持仓数据")
        return

    # 获取最新报告期持仓
    latest_period = df_portfolio["end_date"].max()
    holdings = df_portfolio[df_portfolio["end_date"] == latest_period].copy()
    holdings = holdings.sort_values("stk_mkv_ratio", ascending=False)

    st.info(f"报告期: {latest_period} | 成分股数量: {len(holdings)}")

    # 获取最新价格数据
    if df_daily.empty:
        st.error("未找到成分股日线数据")
        return

    latest_date = df_daily["trade_date"].max()
    latest_prices = df_daily[df_daily["trade_date"] == latest_date][["ts_code", "close", "pct_chg"]]

    # 合并持仓和价格
    holdings = holdings.merge(
        latest_prices,
        left_on="symbol",
        right_on="ts_code",
        how="left"
    )

    # ===== 龙头组合表现 =====
    st.subheader("龙头组合（前五大持仓）")

    top5 = holdings.head(5)

    # 计算龙头组合收益
    top5_returns = []
    for _, row in top5.iterrows():
        if pd.notna(row['pct_chg']):
            top5_returns.append(row['pct_chg'])

    if top5_returns:
        leader_avg_return = np.mean(top5_returns)

        # 获取ETF当日涨跌
        df_fund = load_fund_daily()
        etf_latest = df_fund[df_fund["ts_code"] == ETF_CODE].sort_values("trade_date").iloc[-1]
        etf_return = etf_latest['pct_chg']

        leader_strength = leader_avg_return - etf_return

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("龙头组合涨跌", f"{leader_avg_return:+.2f}%")
        with col2:
            st.metric(f"{ETF_CODE}涨跌", f"{etf_return:+.2f}%")
        with col3:
            color = "green" if leader_strength > 0 else "red"
            st.metric("龙头先行强度", f"{leader_strength:+.2f}%")
            if leader_strength > 0:
                st.success("龙头强于ETF ✓")
            else:
                st.warning("龙头弱于ETF")

    # 龙头详情
    cols = st.columns(5)
    for i, (_, row) in enumerate(top5.iterrows()):
        with cols[i]:
            pct = row['pct_chg'] if pd.notna(row['pct_chg']) else 0
            color = "green" if pct > 0 else "red" if pct < 0 else "gray"
            st.metric(
                row['symbol'],
                f"{row['close']:.2f}" if pd.notna(row['close']) else "-",
                f"{pct:+.2f}%",
            )
            st.caption(f"权重: {row['stk_mkv_ratio']:.2f}%")

    st.divider()

    # ===== 全部持仓表格 =====
    st.subheader("全部持仓")

    display_df = holdings[["symbol", "stk_mkv_ratio", "close", "pct_chg"]].copy()
    display_df.columns = ["代码", "权重(%)", "最新价", "涨跌幅(%)"]
    display_df["权重(%)"] = display_df["权重(%)"].round(2)
    display_df["涨跌幅(%)"] = display_df["涨跌幅(%)"].round(2)

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
    )


def show_breadth(df_daily: pd.DataFrame, df_portfolio: pd.DataFrame, df_indicators: pd.DataFrame):
    """广度指标 - 回答"修复是否扩散到更多个股" """
    st.header("📊 广度指标")

    # ===== 顶部核心结论 =====
    if not df_indicators.empty:
        latest = df_indicators.iloc[-1]
        s1_05_value = latest.get("S1-05", 0)
        s1_05_exp = latest.get("S1-05_expectation", "未知")
        exp_icon = get_expectation_color(s1_05_exp)

        st.markdown(f"### S1-05 板块广度修复：{s1_05_value:.1%} {exp_icon}")
        st.caption(f"预期等级：{s1_05_exp} | 阈值：≥60%超预期，35%-60%符合预期，<35%低于预期")
    else:
        st.error("未找到指标数据")
        return

    if df_daily.empty or df_portfolio.empty:
        st.error("数据不足")
        return

    # 获取成分股列表
    latest_period = df_portfolio["end_date"].max()
    holdings = df_portfolio[df_portfolio["end_date"] == latest_period]["symbol"].tolist()

    # 获取最新交易日数据
    latest_date = df_daily["trade_date"].max()
    latest_data = df_daily[(df_daily["trade_date"] == latest_date) & (df_daily["ts_code"].isin(holdings))].copy()

    # 计算均线突破
    ma_results = []
    above_count = 0
    below_count = 0

    for symbol in holdings:
        stock_data = df_daily[df_daily["ts_code"] == symbol].sort_values("trade_date").tail(30)
        if len(stock_data) >= 20:
            ma20 = stock_data["close"].tail(20).mean()
            latest_close = stock_data["close"].iloc[-1]
            pct_chg = stock_data["pct_chg"].iloc[-1]
            above = latest_close > ma20

            if above:
                above_count += 1
            else:
                below_count += 1

            ma_results.append({
                "代码": symbol,
                "最新价": round(latest_close, 2),
                "涨跌幅(%)": round(pct_chg, 2),
                "MA20": round(ma20, 2),
                "状态": "站上 🟢" if above else "跌破 🔴",
            })

    total_stocks = above_count + below_count
    above_ratio = above_count / total_stocks if total_stocks > 0 else 0

    # ===== 核心结论 =====
    st.divider()

    # 判断结论
    up = len(latest_data[latest_data["pct_chg"] > 0])
    down = len(latest_data[latest_data["pct_chg"] < 0])

    if above_ratio >= 0.6 and down > up:
        conclusion = "板块中期趋势向上，但短期有回调"
        conclusion_color = "🟡"
    elif above_ratio >= 0.6:
        conclusion = "板块趋势向上，个股普涨"
        conclusion_color = "🟢"
    elif above_ratio >= 0.35:
        conclusion = "板块趋势分化，部分个股走弱"
        conclusion_color = "🟡"
    else:
        conclusion = "板块趋势走弱，多数个股下跌"
        conclusion_color = "🔴"

    st.markdown(f"### {conclusion_color} 结论：{conclusion}")

    # ===== 两列布局：趋势位置 vs 今日表现 =====
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 趋势位置（20日均线）")
        st.caption("衡量中期趋势：价格在20日均线之上=趋势向上")

        st.metric("站上均线", f"{above_count}/{total_stocks}", f"{above_ratio:.1%}")

        # 进度条
        st.progress(above_ratio)

        # 预期判断
        if above_ratio >= 0.6:
            st.success("超预期 (≥60%) - 大部分个股趋势向上")
        elif above_ratio >= 0.35:
            st.info("符合预期 (35%-60%) - 趋势分化")
        else:
            st.warning("低于预期 (<35%) - 大部分个股趋势走弱")

    with col2:
        st.subheader("📊 今日表现")
        st.caption("衡量短期情绪：今日涨跌情况")

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("上涨", up, f"{up/total_stocks*100:.0f}%")
        with col_b:
            st.metric("下跌", down, f"{down/total_stocks*100:.0f}%")
        with col_c:
            st.metric("平盘", total_stocks - up - down)

        # 饼图
        fig = go.Figure(go.Pie(
            labels=["上涨", "下跌"],
            values=[up, down],
            marker_colors=["#2ca02c", "#d62728"],
            hole=0.4,
            textinfo="label+percent",
        ))
        fig.update_layout(height=200, margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig, use_container_width=True)

    # ===== 解读 =====
    st.divider()
    st.subheader("📖 解读")

    if above_ratio >= 0.6 and down > up:
        st.info(f"""
        **中期趋势向上，短期有回调**

        - {above_ratio:.0%}的成分股站上20日均线，说明中期趋势仍向上
        - 但今日{down}只下跌，占比{down/total_stocks*100:.0f}%，说明短期有回调压力
        - 这种情况通常是：之前涨幅较大，即使今日回调价格仍高于均线
        """)
    elif above_ratio >= 0.6:
        st.success(f"""
        **趋势向上，个股普涨**

        - {above_ratio:.0%}的成分股站上20日均线，中期趋势向上
        - 今日{up}只上涨，占比{up/total_stocks*100:.0f}%，短期情绪乐观
        """)
    elif above_ratio >= 0.35:
        st.warning(f"""
        **趋势分化**

        - 仅{above_ratio:.0%}站上均线，部分个股趋势走弱
        - 需要关注是否继续恶化
        """)
    else:
        st.error(f"""
        **趋势走弱**

        - 仅{above_ratio:.0%}站上均线，大部分个股趋势向下
        - 需要谨慎
        """)

    # ===== 详细数据 =====
    st.divider()
    with st.expander("📋 查看详细数据"):
        st.subheader("个股均线明细")

        ma_df = pd.DataFrame(ma_results)
        st.dataframe(ma_df, hide_index=True, use_container_width=True)

        st.subheader("个股强弱排名")

        ranked = latest_data.sort_values("pct_chg", ascending=False)

        col1, col2 = st.columns(2)

        with col1:
            st.write("**涨幅前10**")
            top10 = ranked.head(10)[["ts_code", "pct_chg"]].copy()
            top10["pct_chg"] = top10["pct_chg"].round(2)
            top10.columns = ["代码", "涨跌幅(%)"]
            st.dataframe(top10, hide_index=True, use_container_width=True)

        with col2:
            st.write("**跌幅前10**")
            bottom10 = ranked.tail(10)[["ts_code", "pct_chg"]].copy()
            bottom10["pct_chg"] = bottom10["pct_chg"].round(2)
            bottom10.columns = ["代码", "涨跌幅(%)"]
            st.dataframe(bottom10, hide_index=True, use_container_width=True)


def show_radar(df_indicators: pd.DataFrame):
    """指标雷达 - 综合评估6项指标"""
    st.header("🎯 指标雷达")
    st.caption("六边形雷达图 - 看强项和弱项")

    if df_indicators.empty:
        st.error("未找到指标数据")
        return

    latest = df_indicators.iloc[-1]

    # ===== 雷达图 =====
    categories = []
    values = []

    for code, name in ALL_INDICATORS.items():
        categories.append(f"{code}\n{name}")
        val = latest.get(code, 0)
        # 归一化处理
        if code == "S1-04":
            # 成交放大比值：1.5为超预期，2.0为上限
            values.append(min(val / 2.0, 1.0))
        else:
            # 比例值：直接使用，限制在0-1
            values.append(min(max(val, 0), 1.0))

    # 闭合
    values.append(values[0])

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=values,
        theta=categories + [categories[0]],
        fill='toself',
        name='当前值',
        line_color='#1f77b4',
        opacity=0.7,
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 1]),
        ),
        showlegend=False,
        height=450,
    )

    st.plotly_chart(fig, use_container_width=True)

    # ===== 指标详情表格 =====
    st.subheader("指标详情")

    detail_data = []
    for code, name in ALL_INDICATORS.items():
        val = latest.get(code, 0)
        exp = latest.get(f"{code}_expectation", "未知")

        # 格式化数值
        if code == "S1-04":
            val_str = f"{val:.2f}x"
        else:
            val_str = f"{val:.2%}"

        detail_data.append({
            "指标": f"{code} {name}",
            "数值": val_str,
            "预期": f"{get_expectation_color(exp)} {exp}",
        })

    st.dataframe(pd.DataFrame(detail_data), hide_index=True, use_container_width=True)

    # ===== 权重说明 =====
    st.caption("权重分配：S1-01(22%) S1-02(18%) S1-03(20%) S1-04(14%) S1-05(14%) S1-06(12%)")


# ==================== 主函数 ====================

def main():
    st.set_page_config(
        page_title="创新药投资阶段评价",
        page_icon="💊",
        layout="wide",
    )

    st.title("💊 创新药投资阶段评价量化系统")
    st.markdown(f"**标的**: {ETF_CODE} ({ETF_NAME}) | **基准**: {BENCHMARK_CODE} | **阶段**: 第一阶段（预期重定价）")

    # 手动刷新按钮
    if st.button("🔄 刷新数据", type="secondary"):
        st.cache_data.clear()
        st.rerun()

    st.divider()

    # 加载数据
    df_indicators = load_all_indicators()
    df_fund_daily = load_fund_daily()
    df_fund_share = load_fund_share()
    df_daily = load_daily()
    df_portfolio = load_portfolio()

    # Tab 页面
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 综合概览",
        "📈 ETF行情",
        "🏢 成分股详情",
        "📊 广度指标",
        "🎯 指标雷达",
    ])

    with tab1:
        show_overview(df_indicators)

    with tab2:
        show_etf_market(df_fund_daily, df_fund_share)

    with tab3:
        show_holdings(df_daily, df_portfolio)

    with tab4:
        show_breadth(df_daily, df_portfolio, df_indicators)

    with tab5:
        show_radar(df_indicators)


if __name__ == "__main__":
    main()