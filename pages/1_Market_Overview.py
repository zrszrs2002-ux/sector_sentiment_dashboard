import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.aggregation import market_metrics, sector_metrics, top_articles
from src.config import DISCLAIMER, METRIC_COLUMNS, METRIC_LABELS
from src.llm_summary import generate_market_brief
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


df, source_mode = load_selected_articles()
market_scores = market_metrics(df)
sector_df = sector_metrics(df)

top_sector = sector_df.sort_values("optimism", ascending=False).iloc[0]["sector"]
risk_sector = sector_df.sort_values("risk_intensity", ascending=False).iloc[0]["sector"]

st.title("市场总览")
st.caption("第四阶段已启用正式板块级聚合：新闻权重、分歧度、关注度和风险强度按规范计算。")
st.caption(f"当前数据源：{source_mode}")
st.warning(DISCLAIMER)

metric_col1, metric_col2, metric_col3 = st.columns(3)
metric_col1.metric("今日分析新闻数量", len(df))
metric_col2.metric("覆盖新闻源数量", df["source"].nunique())
metric_col3.metric("更新时间 UTC", df["collected_at"].max().strftime("%Y-%m-%d %H:%M"))

left_col, right_col = st.columns([1.05, 0.95])
with left_col:
    render_radar(market_scores, "Overall Market Sentiment Radar")

with right_col:
    st.subheader("AI-generated Market Brief")
    st.info(generate_market_brief(market_scores, top_sector, risk_sector))
    st.subheader("市场级六维分数")
    score_rows = [
        {"指标": METRIC_LABELS[column], "分数": round(market_scores[column], 1)}
        for column in METRIC_COLUMNS
    ]
    st.dataframe(score_rows, use_container_width=True, hide_index=True)

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
drivers = top_articles(df, "risk_intensity", limit=5)[
    ["title", "sector", "topic", "risk_category", "risk_intensity", "evidence_sentence", "url"]
]
st.dataframe(drivers, use_container_width=True, hide_index=True, column_config=url_column_config())
