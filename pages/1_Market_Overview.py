import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.aggregation import market_metrics, sector_metrics
from src.brief_generator import read_latest_brief
from src.config import DISCLAIMER, METRIC_COLUMNS, METRIC_LABELS, WORKING_SET_DAYS
from src.driver_analysis import top_driver_articles
from src.ui_helpers import load_selected_articles, url_column_config


def render_radar(scores: dict[str, float], title: str) -> None:
    labels = [METRIC_LABELS[column] for column in METRIC_COLUMNS]
    values = [float(scores.get(column, 0)) for column in METRIC_COLUMNS]
    fig = go.Figure(
        data=[
            go.Scatterpolar(
                r=values + values[:1],
                theta=labels + labels[:1],
                fill="toself",
                name="市场级指标",
            )
        ]
    )
    fig.update_layout(
        title=title,
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False,
        height=430,
    )
    st.plotly_chart(fig, use_container_width=True)


def fmt_time(value: object) -> str:
    if value is None or pd.isna(value):
        return "暂无"
    return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M UTC")


df, source_mode = load_selected_articles()
market_scores = market_metrics(df)
sector_df = sector_metrics(df)
latest_brief = read_latest_brief()
brief_meta = latest_brief.get("metadata", {}) if isinstance(latest_brief.get("metadata"), dict) else {}
brief_content = str(latest_brief.get("content", "") or "")

data_updated_at = df["collected_at"].max() if "collected_at" in df else pd.NaT
brief_generated_at = brief_meta.get("generated_at_local") or brief_meta.get("generated_at") or ""
summary_source = brief_meta.get("summary_source", "规则模板")
brief_model_id = brief_meta.get("model_id", "")
if summary_source == "AI 生成":
    model_label = f" · 模型 {brief_model_id}" if brief_model_id else ""
    brief_source_label = f"AI 生成{model_label} · 简报时间 {brief_generated_at}"
else:
    brief_source_label = f"规则模板 · 简报时间 {brief_generated_at or '尚未生成'}"

st.title("市场总览")
st.caption("抓取可多次/天，LLM 简报默认一次/天；页面只读取已生成的 latest_brief.md。")
st.caption(f"当前数据源：{source_mode}")
st.warning(DISCLAIMER)

metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
metric_col1.metric("窗口内新闻数", f"{len(df):,}")
metric_col2.metric("覆盖来源数", f"{df['source'].nunique():,}")
metric_col3.metric("数据窗口", f"近 {WORKING_SET_DAYS} 天")
metric_col4.metric("数据更新时间", fmt_time(data_updated_at))

left_col, right_col = st.columns([1.05, 0.95])
with left_col:
    render_radar(market_scores, "Overall Market Sentiment Radar")
    st.subheader("市场级六维分数")
    score_rows = [
        {"指标": METRIC_LABELS[column], "分数": round(float(market_scores[column]), 1)}
        for column in METRIC_COLUMNS
    ]
    st.dataframe(score_rows, use_container_width=True, hide_index=True)

with right_col:
    st.subheader("每日市场简报")
    st.caption(brief_source_label)
    with st.container(height=600, border=True):
        if brief_content:
            st.markdown(brief_content)
        else:
            st.info("暂无 latest_brief.md。抓取管线会在每日生成时刻后自动生成；也可以在侧边栏手动确认重新生成。")

st.subheader("Sector Heatmap")
heatmap_df = sector_df.set_index("sector")[METRIC_COLUMNS].rename(columns=METRIC_LABELS)
fig = px.imshow(
    heatmap_df,
    text_auto=".1f",
    aspect="auto",
    color_continuous_scale="RdYlGn",
)
fig.update_layout(height=430)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Top Market Drivers")
driver_columns = [
    "title",
    "sector",
    "topic",
    "risk_category",
    "driver_score",
    "risk_intensity",
    "driver_reason",
    "evidence_sentence",
    "url",
]
drivers = top_driver_articles(df, limit=5).reindex(columns=driver_columns)
st.dataframe(drivers, use_container_width=True, hide_index=True, column_config=url_column_config())
