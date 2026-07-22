import pandas as pd
import plotly.express as px
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

# 六维指标的语义主色，用于柱状图 / 排行榜等可视化，与热力图配色保持一致的直觉：
# 绿=乐观，红=警惕类（恐惧/不确定/分歧/风险），蓝=关注度。
METRIC_ACCENT_COLORS = {
    "optimism": "#3fb950",
    "fear": "#e5534b",
    "uncertainty": "#e0883f",
    "attention": "#4098e6",
    "disagreement": "#c76ae0",
    "risk_intensity": "#f2495c",
}


def get_theme_mode() -> str:
    """返回当前应使用的图表配色模式：'light' 或 'dark'。
    读取 Streamlit 原生的 System/Light/Dark 主题开关（右上角"⋮"菜单）；
    如果检测失败（例如刚切换主题的瞬间），默认按 dark 处理。"""
    try:
        theme_type = st.context.theme.type
    except Exception:
        theme_type = None
    return theme_type if theme_type in ("light", "dark") else "dark"


def shorten_label(text: object, max_len: int = 16) -> str:
    """过长的坐标轴文字用省略号截短，避免超出边距导致被硬裁切；完整文字保留在 hover 中。"""
    label = str(text or "")
    return label if len(label) <= max_len else label[: max_len - 1].rstrip() + "…"


def radar_style(theme_mode: str | None = None) -> dict:
    """雷达图配色：随亮/暗主题切换，避免深色模式白底、浅色模式黑字看不清的问题。"""
    mode = theme_mode or get_theme_mode()
    if mode == "light":
        return {
            "bg": "rgba(90,100,120,0.07)",
            "grid": "rgba(70,74,84,0.35)",
            "line": "rgba(70,74,84,0.55)",
            "radial_tick": "rgba(35,38,46,0.95)",
            "angular_tick": "rgba(20,22,28,0.98)",
            "title": "#14161c",
            "point_label": "rgba(20,95,210,0.95)",
            "legend_text": "rgba(20,22,28,0.92)",
        }
    return {
        "bg": "rgba(120,120,130,0.18)",
        "grid": "rgba(180,180,180,0.55)",
        "line": "rgba(180,180,180,0.65)",
        "radial_tick": "#FFFFFF",
        "angular_tick": "#FFFFFF",
        "title": "#FFFFFF",
        "point_label": "#FFFFFF",
        "legend_text": "#FFFFFF",
    }


def apply_radar_theme(
    fig: go.Figure,
    title: str,
    theme_mode: str | None = None,
    radial_tick_size: int = 15,
    angular_tick_size: int = 16,
    height: int = 430,
) -> dict:
    """统一应用雷达图配色/字号，返回使用的样式字典（供设置数据点标注颜色使用）。"""
    style = radar_style(theme_mode)
    fig.update_layout(
        title=dict(text=title, font=dict(color=style["title"], size=18)),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=style["angular_tick"]),
        polar=dict(
            bgcolor=style["bg"],
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                gridcolor=style["grid"],
                gridwidth=1.5,
                linecolor=style["line"],
                linewidth=1.5,
                tickfont=dict(size=radial_tick_size, color=style["radial_tick"]),
            ),
            angularaxis=dict(
                tickfont=dict(size=angular_tick_size, color=style["angular_tick"]),
                gridcolor=style["grid"],
                gridwidth=1.5,
                linecolor=style["line"],
                linewidth=1.5,
            ),
        ),
        legend=dict(font=dict(color=style["legend_text"])),
        height=height,
        margin=dict(t=60, b=30, l=40, r=40),
    )
    return style


def apply_chart_theme(fig: go.Figure, theme_mode: str | None = None) -> None:
    """给普通 bar/line 等图表套用随主题自适应的透明背景与文字/网格颜色。"""
    mode = theme_mode or get_theme_mode()
    text_color = "rgba(230,230,230,0.95)" if mode == "dark" else "rgba(25,28,34,0.92)"
    grid_color = "rgba(255,255,255,0.12)" if mode == "dark" else "rgba(0,0,0,0.08)"
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=text_color),
        xaxis=dict(gridcolor=grid_color, zerolinecolor=grid_color),
        yaxis=dict(gridcolor=grid_color, zerolinecolor=grid_color),
        legend=dict(font=dict(color=text_color)),
    )


def markdown_article_link(title: object, url: object) -> str:
    """把标题渲染为可点击跳转的 Markdown 链接；无有效链接时退化为纯文本。"""
    label = str(title or "Untitled").replace("[", "\\[").replace("]", "\\]")
    href = str(url or "").strip()
    return f"[{label}]({href})" if href.startswith(("http://", "https://")) else label


def sentiment_badge_markdown(score: object, precision: int = 3) -> str:
    """情绪分徽章：正=绿色，负=红色，接近 0=灰色，用于卡片/列表中直观展示。"""
    try:
        value = float(score)
    except (TypeError, ValueError):
        return "`Sentiment N/A`"
    if value > 0.05:
        color = "#3fb950"
    elif value < -0.05:
        color = "#e5534b"
    else:
        color = "#8a8f98"
    return f"<span style='color:{color}; font-weight:600;'>● Sentiment {value:+.{precision}f}</span>"


def metric_bar_chart(
    values_by_label: dict[str, float],
    color: str | list[str] = "#4098e6",
    height: int = 260,
    value_range: tuple[float, float] = (0, 100),
) -> go.Figure:
    """通用横向条形图：用于把单行/单列的数据表转成一眼可读的柱状可视化。
    color 可传单一颜色（所有柱同色）或与 values_by_label 等长的颜色列表（逐条配色）。"""
    full_labels = list(values_by_label.keys())
    labels = [shorten_label(label, 18) for label in full_labels]
    values = [float(v) for v in values_by_label.values()]
    bar_colors = color if isinstance(color, list) else [color] * len(labels)
    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker=dict(color=bar_colors, line=dict(width=0)),
            text=[f"{v:.1f}" for v in values],
            textposition="outside",
            cliponaxis=False,
            customdata=full_labels,
            hovertemplate="%{customdata}: %{x:.1f}<extra></extra>",
        )
    )
    fig.update_layout(
        height=height,
        margin=dict(t=10, b=36, l=10, r=30),
        xaxis=dict(range=[value_range[0], value_range[1] * 1.12], title=None, automargin=True),
        yaxis=dict(autorange="reversed", title=None, automargin=True),
        showlegend=False,
    )
    apply_chart_theme(fig)
    return fig


def count_bar_chart(counts: pd.Series, color: str, height: int = 300, top_n: int = 8) -> go.Figure:
    """value_counts() 结果的横向条形图：截取前 top_n 项，最多的排最上面；坐标轴文字不截断。"""
    top_counts = counts.head(top_n).iloc[::-1]
    full_labels = top_counts.index.astype(str).tolist()
    short_labels = [shorten_label(label, 18) for label in full_labels]
    fig = go.Figure(
        go.Bar(
            x=top_counts.values,
            y=short_labels,
            orientation="h",
            marker=dict(color=color, line=dict(width=0)),
            text=top_counts.values,
            textposition="outside",
            cliponaxis=False,
            customdata=full_labels,
            hovertemplate="%{customdata}: %{x}<extra></extra>",
        )
    )
    fig.update_layout(
        height=height,
        margin=dict(t=10, b=36, l=10, r=30),
        xaxis=dict(title=None, automargin=True),
        yaxis=dict(title=None, automargin=True),
        showlegend=False,
    )
    apply_chart_theme(fig)
    return fig


def compact_subheader(text: str, size_rem: float = 1.15) -> None:
    """Smaller, single-line subheader for side-by-side columns where the default
    st.subheader font size can wrap onto two lines and break horizontal alignment."""
    st.markdown(
        f"<div style='font-size:{size_rem}rem; font-weight:700; white-space:nowrap; "
        "overflow:hidden; text-overflow:ellipsis; margin:0 0 0.3rem 0;'>"
        f"{text}</div>",
        unsafe_allow_html=True,
    )


def load_selected_articles(load_all_history: bool = False):
    """按侧边栏数据源选择加载文章，并处理真实新闻为空的情况。"""
    source_mode = st.session_state.get("data_source_mode", REAL_DATA_LABEL)
    df = load_articles(source_mode=source_mode, load_all_history=load_all_history)
    if df.empty and source_mode == REAL_DATA_LABEL:
        st.warning(
            "Real news data is empty or failed to load; falling back to Demo data. "
            "Click \u201cFetch latest news\u201d in the sidebar to refresh real news."
        )
        df = load_articles(source_mode=DEMO_DATA_LABEL, load_all_history=load_all_history)
        source_mode = DEMO_DATA_LABEL
        if df.empty:
            st.error("Demo data is also empty. Please regenerate the demo data or check the data directory.")
            st.stop()
    return df, source_mode


def url_column_config(label: str = "Link") -> dict:
    return {"url": st.column_config.LinkColumn(label, display_text="Open")}


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
        raise ValueError(f"Unsupported heatmap color mode: {color_mode}")
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
                hovertemplate=f"%{{y}} \u00b7 {METRIC_LABELS[column]}: %{{customdata:.1f}}<extra></extra>",
            ),
            row=1,
            col=idx,
        )
    fig.update_yaxes(autorange="reversed", automargin=True)
    # Show the metric name below each column so the dimension is visible without hovering.
    fig.update_xaxes(side="bottom", showticklabels=True, tickfont=dict(size=13), automargin=True)
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=10, b=34))
    apply_chart_theme(fig)
    st.plotly_chart(fig, use_container_width=True, theme=None)
    if color_mode == "relative":
        st.caption(
            "Color legend: color shows each sector's relative position within that "
            "dimension across all 11 sectors; cell numbers are raw scores. "
            "Green = high optimism; red = high fear, uncertainty, disagreement, or risk "
            "intensity; blue = high attention. Once daily snapshots exceed 30 days, this "
            "will upgrade to a percentile view relative to each sector's own history."
        )
    else:
        st.caption(
            "Color legend: both color and numbers are scaled on an absolute 0-100 basis. "
            "Green = high optimism; red = high fear, uncertainty, disagreement, or risk "
            "intensity; blue = high attention. Once daily snapshots exceed 30 days, this "
            "will upgrade to a percentile view relative to each sector's own history."
        )