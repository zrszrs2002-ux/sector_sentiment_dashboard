import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from src.config import METRIC_COLUMNS, METRIC_LABELS
from src.data_loader import DEMO_DATA_LABEL, REAL_DATA_LABEL, load_articles

# 热力图按模式和指标语义着色：绿=乐观，红系=警惕型指标，蓝=关注度。
_HEATMAP_COLOR_SCALES = {
    "relative": {
        "optimism": "Greens",
        "fear": "RdYlGn_r",
        "uncertainty": "RdYlGn_r",
        "attention": "Blues",
        "disagreement": "RdYlGn_r",
        "risk_intensity": "RdYlGn_r",
    },
    "absolute": {
        "optimism": "Greens",
        "fear": "Reds",
        "uncertainty": "RdYlGn_r",
        "attention": "Blues",
        "disagreement": "RdYlGn_r",
        "risk_intensity": "RdYlGn_r",
    },
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


# 单色渐变色阶的端点接近纯白/纯黑，相对模式 min-max 会把最低板块钉在近白端造成刺眼断层；
# 压缩色带行程让浅端保持可见的浅色。发散色阶（RdYlGn_r）两端为饱和色，不需要压缩。
_SEQUENTIAL_SCALES = frozenset({"Greens", "Blues", "Reds"})
_SEQUENTIAL_BAND = (20.0, 85.0)


def heatmap_color_values(
    values: pd.Series, color_mode: str = "relative", sequential: bool = False
) -> pd.Series:
    """Return 0-100 color positions while preserving raw values for labels."""
    raw = pd.to_numeric(values, errors="coerce").fillna(0.0).astype(float)
    if color_mode == "absolute":
        return raw.clip(0.0, 100.0)
    if color_mode != "relative":
        raise ValueError(f"不支持的热力图上色模式：{color_mode}")
    minimum = float(raw.min()) if len(raw) else 0.0
    maximum = float(raw.max()) if len(raw) else 0.0
    if maximum <= minimum:
        positions = pd.Series(50.0, index=raw.index)
    else:
        positions = (raw - minimum) / (maximum - minimum) * 100.0
    if sequential:
        lower, upper = _SEQUENTIAL_BAND
        positions = lower + positions * (upper - lower) / 100.0
    return positions


def render_sector_heatmap(
    sector_df: pd.DataFrame,
    height: int = 430,
    color_mode: str = "relative",
) -> None:
    """Render raw scores with either cross-sectional or absolute color scaling."""
    sectors = sector_df["sector"].astype(str).tolist()
    fig = make_subplots(
        rows=1,
        cols=len(METRIC_COLUMNS),
        shared_yaxes=True,
        horizontal_spacing=0.006,
    )
    for idx, column in enumerate(METRIC_COLUMNS, start=1):
        raw_values = pd.to_numeric(sector_df[column], errors="coerce").fillna(0.0)
        colorscale = _HEATMAP_COLOR_SCALES[color_mode][column]
        color_values = heatmap_color_values(
            raw_values, color_mode, sequential=colorscale in _SEQUENTIAL_SCALES
        )
        fig.add_trace(
            go.Heatmap(
                z=[[float(value)] for value in color_values],
                x=[METRIC_LABELS[column]],
                y=sectors,
                zmin=0,
                zmax=100,
                colorscale=colorscale,
                showscale=False,
                text=[[f"{float(value):.1f}"] for value in raw_values],
                texttemplate="%{text}",
                textfont={"size": 11},
                customdata=[[float(value)] for value in raw_values],
                hovertemplate=f"%{{y}} · {METRIC_LABELS[column]}：%{{customdata:.1f}}<extra></extra>",
            ),
            row=1,
            col=idx,
        )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=24, b=10))
    st.plotly_chart(fig, use_container_width=True)
    if color_mode == "relative":
        st.caption(
            "配色说明：颜色表示该维度内 11 个板块的相对位置，单元格数字为原始分；"
            "乐观度高=绿，恐惧度、不确定性、分歧度、风险强度高=红，关注度高=蓝。"
            "历史快照满 30 天后，将升级为相对自身历史的分位展示。"
        )
    else:
        st.caption(
            "配色说明：颜色与数字均按绝对 0–100 分定标；乐观度高=绿，"
            "恐惧度、不确定性、分歧度、风险强度高=红，关注度高=蓝。"
            "历史快照满 30 天后，将升级为相对自身历史的分位展示。"
        )