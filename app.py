"""
校园WiFi体验保障 - Streamlit 前端 Demo
参考 Juniper Mist AI / Marvis AI 的无线网络智能运维
"""
import os
import sys
import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# 添加项目根路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import OUTPUT_DIR, WEAK_RSSI_THRESHOLD, MIN_VISIBLE_AP, RSSI_GOOD, RSSI_MEDIUM, DATA_PATH
from llm_diagnosis import diagnose_with_llm, simulate_diagnosis, WIFI_KNOWLEDGE_BASE

st.set_page_config(
    page_title="校园WiFi体验保障",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============ 缓存数据加载 ============
@st.cache_data
def load_all_data():
    """加载预处理后的数据"""
    all_path = os.path.join(OUTPUT_DIR, "all_points_annotated.csv")
    weak_path = os.path.join(OUTPUT_DIR, "weak_points.csv")
    stats_path = os.path.join(OUTPUT_DIR, "building_stats.csv")

    if not os.path.exists(all_path):
        # 首次运行，执行数据处理
        from data_processor import process_all
        _, weak_points, building_stats, _ = process_all()
        df_all = pd.read_csv(all_path)
    else:
        df_all = pd.read_csv(all_path)
        weak_points = pd.read_csv(weak_path)
        building_stats = pd.read_csv(stats_path)

    return df_all, weak_points, building_stats


# ============ 侧边栏 ============
def render_sidebar(df_all, building_stats):
    st.sidebar.title("📡 校园WiFi体验保障")
    st.sidebar.markdown("---")

    # 筛选
    st.sidebar.header("🔍 筛选条件")

    buildings = sorted(df_all["BUILDINGID"].dropna().unique().astype(int))
    selected_building = st.sidebar.selectbox("选择楼栋", ["全部"] + [f"楼栋 {b}" for b in buildings])

    if selected_building == "全部":
        available_floors = sorted(df_all["FLOOR"].dropna().unique().astype(int))
    else:
        bid = int(selected_building.replace("楼栋 ", ""))
        available_floors = sorted(df_all[df_all["BUILDINGID"] == bid]["FLOOR"].dropna().unique().astype(int))

    selected_floor = st.sidebar.selectbox("选择楼层", ["全部"] + [f"{f}楼" for f in available_floors])

    # 质量筛选
    st.sidebar.markdown("---")
    quality_filter = st.sidebar.multiselect(
        "信号质量",
        ["good", "medium", "poor"],
        default=["medium", "poor"],
        format_func=lambda x: {"good": "🟢 优秀", "medium": "🟡 中等", "poor": "🔴 差"}[x]
    )

    st.sidebar.markdown("---")
    st.sidebar.metric("总采样点", f"{len(df_all):,}")
    st.sidebar.metric("弱覆盖告警", f"{len(df_all[df_all['is_anomaly'] == True]):,}")

    # 楼层覆盖评分
    st.sidebar.markdown("---")
    st.sidebar.subheader("📊 楼层覆盖评分")
    worst_floors = building_stats.nlargest(5, "weak_ratio")[
        ["BUILDINGID", "FLOOR", "weak_ratio", "avg_max_rssi"]
    ]
    for _, row in worst_floors.iterrows():
        color = "🔴" if row["weak_ratio"] > 50 else "🟡"
        st.sidebar.write(
            f"{color} B{int(row['BUILDINGID'])}-F{int(row['FLOOR'])}: "
            f"{row['weak_ratio']:.0f}%弱覆盖 | RSSI {row['avg_max_rssi']:.0f}"
        )

    return selected_building, selected_floor, quality_filter


# ============ 数据过滤 ============
def filter_data(df_all, building, floor, quality):
    df = df_all.copy()

    if building != "全部":
        bid = int(building.replace("楼栋 ", ""))
        df = df[df["BUILDINGID"] == bid]
    if floor != "全部":
        fid = int(floor.replace("楼", ""))
        df = df[df["FLOOR"] == fid]
    if quality:
        df = df[df["signal_quality"].isin(quality)]

    return df


# ============ 可视化 ============
def render_heatmap(df):
    """楼层热力图"""
    fig = px.scatter(
        df,
        x="LONGITUDE",
        y="LATITUDE",
        color="signal_quality",
        color_discrete_map={"good": "#00CC66", "medium": "#FFB347", "poor": "#FF4444", "none": "#CCCCCC"},
        size="visible_ap_count",
        size_max=8,
        hover_data={
            "max_rssi": ":.0f",
            "avg_rssi": ":.0f",
            "visible_ap_count": True,
            "signal_quality": True,
            "LONGITUDE": False,
            "LATITUDE": False,
        },
        opacity=0.7,
        height=500,
        title="WiFi 信号覆盖热力图（颜色=质量，大小=可见AP数）",
    )
    fig.update_layout(
        xaxis_title="经度 (Longitude)",
        yaxis_title="纬度 (Latitude)",
        legend_title="信号质量",
    )
    return fig


def render_ap_histogram(df):
    """可见AP数分布直方图"""
    fig = px.histogram(
        df,
        x="visible_ap_count",
        color="signal_quality",
        color_discrete_map={"good": "#00CC66", "medium": "#FFB347", "poor": "#FF4444", "none": "#CCCCCC"},
        nbins=30,
        height=350,
        title="可见 AP 数量分布",
    )
    fig.add_vline(x=MIN_VISIBLE_AP, line_dash="dash", line_color="red",
                  annotation_text=f"阈值={MIN_VISIBLE_AP}")
    return fig


def render_rssi_distribution(df):
    """RSSI 分布"""
    fig = px.histogram(
        df[df["max_rssi"].notna()],
        x="max_rssi",
        nbins=40,
        height=350,
        title="最强信号 (max_rssi) 分布",
    )
    fig.add_vline(x=RSSI_GOOD, line_dash="dash", line_color="green",
                  annotation_text=f"Good ≥ {RSSI_GOOD}")
    fig.add_vline(x=RSSI_MEDIUM, line_dash="dash", line_color="red",
                  annotation_text=f"Poor < {RSSI_MEDIUM}")
    return fig


# ============ LLM 诊断 ============
def render_diagnosis(weak_points, building_stats):
    st.markdown("---")
    st.header("🤖 AI 排障助手")

    if st.button("🚀 生成诊断报告", type="primary", width='stretch'):
        with st.spinner("AI 正在分析弱覆盖数据..."):
            result = simulate_diagnosis(weak_points, building_stats)

        # 总体评估
        st.success("✅ 诊断完成")
        st.info(result["overall_assessment"])

        # 诊断卡片
        st.subheader("📋 弱覆盖诊断详情")
        cols = st.columns(3)
        for i, analysis in enumerate(result.get("anomaly_analysis", [])[:12]):
            with cols[i % 3]:
                with st.container(border=True):
                    risk_color = {"high": "🔴", "medium": "🟡", "low": "🟢"}
                    st.markdown(f"**{risk_color.get(analysis['risk_level'], '⚪')} {analysis['affected_area']}**")
                    st.caption(f"风险等级: **{analysis['risk_level'].upper()}**")
                    st.write(f"**原因:** {analysis['possible_cause']}")
                    st.write(f"**证据:** {analysis['evidence']}")
                    with st.expander("🔧 排查步骤"):
                        for step in analysis.get("next_steps", []):
                            st.write(step)
                    with st.expander("👤 用户说明"):
                        st.write(analysis.get("user_message", ""))
                    with st.expander("❓ 不确定性"):
                        st.write(analysis.get("uncertainty", ""))
                        st.write("**需要补充数据:**", analysis.get("needed_data", ""))

        # 摘要报告
        st.subheader("📄 诊断摘要报告")
        st.code(result.get("summary_report", ""), language=None)

        # JSON 导出
        st.download_button(
            "📥 下载诊断 JSON",
            json.dumps(result, ensure_ascii=False, indent=2),
            "diagnosis_report.json",
            "application/json",
        )


# ============ 主页面 ============
def main():
    st.title("📡 校园 WiFi 体验保障与 LLM 运维助手")
    st.caption("参考 HPE Juniper Networking Mist AI / Marvis AI · 基于 UJIIndoorLoc 数据集")

    # 加载数据
    with st.spinner("正在加载数据..."):
        df_all, weak_points, building_stats = load_all_data()

    # 侧边栏
    selected_building, selected_floor, quality_filter = render_sidebar(df_all, building_stats)

    # 过滤
    df_filtered = filter_data(df_all, selected_building, selected_floor, quality_filter)
    st.success(f"当前显示: **{len(df_filtered):,}** 个采样点")

    # 指标卡片
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        good_pct = (df_filtered["signal_quality"] == "good").mean() * 100
        st.metric("🟢 信号优秀", f"{good_pct:.0f}%")
    with col2:
        medium_pct = (df_filtered["signal_quality"] == "medium").mean() * 100
        st.metric("🟡 信号中等", f"{medium_pct:.0f}%")
    with col3:
        poor_pct = (df_filtered["signal_quality"] == "poor").mean() * 100
        st.metric("🔴 信号差", f"{poor_pct:.0f}%")
    with col4:
        avg_ap = df_filtered["visible_ap_count"].mean()
        st.metric("📶 平均可见AP", f"{avg_ap:.1f}")

    # 热力图
    st.markdown("---")
    st.subheader("🗺️ WiFi 覆盖热力图")
    if len(df_filtered) > 5000:
        st.warning(f"点数过多 ({len(df_filtered)})，显示前 5000 个点")
        df_plot = df_filtered.sample(5000, random_state=42) if len(df_filtered) > 5000 else df_filtered
    else:
        df_plot = df_filtered
    st.plotly_chart(render_heatmap(df_plot), width='stretch')

    # 统计图表
    col_l, col_r = st.columns(2)
    with col_l:
        st.plotly_chart(render_ap_histogram(df_filtered), width='stretch')
    with col_r:
        st.plotly_chart(render_rssi_distribution(df_filtered), width='stretch')

    # 弱覆盖告警表格
    st.markdown("---")
    st.subheader("🚨 弱覆盖告警点")

    weak_filtered = df_filtered[df_filtered["is_anomaly"] == True]
    if len(weak_filtered) > 0:
        st.warning(f"发现 **{len(weak_filtered)}** 个弱覆盖点位")
        show_cols = ["BUILDINGID", "FLOOR", "LONGITUDE", "LATITUDE",
                     "max_rssi", "avg_rssi", "visible_ap_count", "risk_level", "is_weak_rssi", "is_few_ap"]
        st.dataframe(
            weak_filtered[show_cols].head(50).style.format({
                "max_rssi": "{:.0f}", "avg_rssi": "{:.0f}",
                "LONGITUDE": "{:.2f}", "LATITUDE": "{:.2f}",
            }),
            width='stretch',
        )
        st.caption(f"共 {len(weak_filtered)} 条，显示前 50 条")
    else:
        st.success("当前筛选条件下无弱覆盖告警")

    # LLM 诊断
    if len(weak_points) > 0:
        render_diagnosis(weak_points, building_stats)

    # 知识库浏览
    st.markdown("---")
    with st.expander("📚 WiFi 排障知识库"):
        st.markdown(WIFI_KNOWLEDGE_BASE)

    # 数据集信息
    st.markdown("---")
    st.subheader("📊 数据集信息")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write(f"**数据来源:** UJIIndoorLoc")
        st.write(f"**原始采样点:** {len(df_all):,}")
    with col2:
        st.write(f"**AP 数量:** 520 (WAP001-WAP520)")
        st.write(f"**楼栋数:** {df_all['BUILDINGID'].nunique():.0f}")
    with col3:
        st.write(f"**楼层范围:** {df_all['FLOOR'].min():.0f} - {df_all['FLOOR'].max():.0f}")
        st.write(f"**弱覆盖点:** {len(weak_points):,}")

    # 页脚
    st.markdown("---")
    st.caption("© 2026 FDE 无线网络智能运维培训 · 场景4 · 校园WiFi体验保障与LLM运维助手")


if __name__ == "__main__":
    main()
