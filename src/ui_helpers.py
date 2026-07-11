import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.config import METRIC_COLUMNS, METRIC_LABELS
from src.data_loader import DEMO_DATA_LABEL, REAL_DATA_LABEL, load_articles

# 热力图按指标方向着色：正向指标高=绿；负向指标高=红；关注度是中性热度，用蓝色系。
_HEATMAP_COLOR_SCALES = {
    "optimism": "RdYlGn",
    "fear": "RdYlGn_r",
    "uncertainty": "RdYlGn_r",
    "attention": "Blues",
    "disagreement": "RdYlGn_r",
    "risk_intensity": "RdYlGn_r",
}


def load_selected_articles(load_all_history: bool = False):
    """按侧边栏数据源选择加载文章，并处理真实新闻为空的情况。"""
    source_mode = st.session_state.get("data_source_mode", REAL_DATA_LABEL)
    df = load_articles(source_mode=source_mode, load_all_history=load_all_history)
    if df.empty and source_mode == REAL_DATA_LABEL:
        st.warning("真实新闻数据为空或读取失败，已回落到 Demo 数据。请先在左侧点击“抓取最新新闻”刷新真实新闻。")
        df = load_articles(source_mode=DEMO_DATA_LABEL, load_all_history=load_all_history)
        source_mode = DEMO_DATA_LABEL
        if df.empty:
            st.error("Demo 数据也为空，请先重新生成 demo 数据或检查 data 目录。")
            st.stop()
    return df, source_mode


def url_column_config(label: str = "链接") -> dict:
    return {"url": st.column_config.LinkColumn(label, display_text="打开")}


def render_sector_heatmap(sector_df: pd.DataFrame, height: int = 430) -> None:
    """按维度方向着色的板块六维热力图（市场总览与板块比较共用）。

    单一色阶无法表达"高恐惧是坏事、高乐观是好事"的语义差异，因此每个维度
    使用独立子图和独立色阶；色阶范围统一固定 0-100，保证跨维度可比。
    """
    sectors = sector_df["sector"].astype(str).tolist()
    fig = make_subplots(
        rows=1,
        cols=len(METRIC_COLUMNS),
        shared_yaxes=True,
        horizontal_spacing=0.006,
    )
    for idx, column in enumerate(METRIC_COLUMNS, start=1):
        values = pd.to_numeric(sector_df[column], errors="coerce").fillna(0).round(1).tolist()
        fig.add_trace(
            go.Heatmap(
                z=[[value] for value in values],
                x=[METRIC_LABELS[column]],
                y=sectors,
                zmin=0,
                zmax=100,
                colorscale=_HEATMAP_COLOR_SCALES[column],
                showscale=False,
                text=[[f"{value:.1f}"] for value in values],
                texttemplate="%{text}",
                textfont={"size": 11},
                hovertemplate=f"%{{y}} · {METRIC_LABELS[column]}：%{{z:.1f}}<extra></extra>",
            ),
            row=1,
            col=idx,
        )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=24, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "配色说明：乐观度越高越绿；恐惧度、不确定性、分歧度、风险强度越高越红；"
        "关注度为中性热度指标，蓝色越深表示媒体关注越高。所有色阶固定 0-100。"
    )
