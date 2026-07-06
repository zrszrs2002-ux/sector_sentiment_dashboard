import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.aggregation import sector_metrics
from src.config import METRIC_COLUMNS, METRIC_LABELS
from src.data_loader import load_demo_articles


def split_values(series: pd.Series) -> pd.Series:
    values: list[str] = []
    for item in series.dropna().astype(str):
        values.extend([part.strip() for part in item.split(";") if part.strip()])
    return pd.Series(values)


df = load_demo_articles()
sector_df = sector_metrics(df)

st.title("板块详情")
selected_sector = st.selectbox("选择板块", options=sector_df["sector"].tolist())
sector_articles = df[df["sector"] == selected_sector].copy()
sector_row = sector_df[sector_df["sector"] == selected_sector].iloc[0]

labels = [METRIC_LABELS[column] for column in METRIC_COLUMNS]
values = [float(sector_row[column]) for column in METRIC_COLUMNS]
fig = go.Figure(
    data=[
        go.Scatterpolar(
            r=values + values[:1],
            theta=labels + labels[:1],
            fill="toself",
            name=selected_sector,
        )
    ]
)
fig.update_layout(
    title=f"{selected_sector} 六维雷达图",
    polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
    height=430,
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("过去 30 天趋势图框架")
trend = (
    sector_articles.assign(published_date=sector_articles["published_at"].dt.date)
    .groupby("published_date", as_index=False)[["sentiment_score", "risk_intensity"]]
    .mean()
)
if len(trend) >= 2:
    trend_fig = px.line(
        trend,
        x="published_date",
        y=["sentiment_score", "risk_intensity"],
        markers=True,
    )
else:
    trend_fig = px.scatter(
        trend,
        x="published_date",
        y="sentiment_score",
        title="当前小型 demo 每个板块只有 1 条新闻，完整趋势会在第二阶段扩展数据后展示。",
    )
st.plotly_chart(trend_fig, use_container_width=True)

col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("Top mentioned companies")
    companies = split_values(sector_articles["companies"]).value_counts().reset_index()
    companies.columns = ["company", "count"]
    st.dataframe(companies, use_container_width=True, hide_index=True)

with col2:
    st.subheader("Top topics")
    topics = sector_articles["topic"].value_counts().reset_index()
    topics.columns = ["topic", "count"]
    st.dataframe(topics, use_container_width=True, hide_index=True)

with col3:
    st.subheader("Top risk categories")
    risks = sector_articles["risk_category"].value_counts().reset_index()
    risks.columns = ["risk_category", "count"]
    st.dataframe(risks, use_container_width=True, hide_index=True)

st.subheader("Top positive news")
st.dataframe(
    sector_articles.sort_values("sentiment_score", ascending=False)[
        ["title", "sentiment_score", "evidence_sentence", "url"]
    ],
    use_container_width=True,
    hide_index=True,
)

st.subheader("Top negative news")
st.dataframe(
    sector_articles.sort_values("sentiment_score")[
        ["title", "sentiment_score", "evidence_sentence", "url"]
    ],
    use_container_width=True,
    hide_index=True,
)

st.subheader("Key evidence sentences")
st.dataframe(
    sector_articles[["title", "evidence_sentence"]],
    use_container_width=True,
    hide_index=True,
)
