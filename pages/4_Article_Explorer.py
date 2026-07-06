import streamlit as st

from src.ui_helpers import load_selected_articles, url_column_config


df, source_mode = load_selected_articles()

st.title("文章浏览器")
st.caption("当前显示已处理新闻；agg_weight 是聚合权重，不等同于板块级关注度。")
st.caption(f"当前数据源：{source_mode}")

source_options = sorted(df["source"].dropna().unique().tolist())
sector_options = sorted(df["sector"].dropna().unique().tolist())
risk_options = sorted(df["risk_category"].dropna().unique().tolist())

col1, col2, col3 = st.columns(3)
with col1:
    selected_sources = st.multiselect("新闻源", source_options, default=source_options)
with col2:
    selected_sectors = st.multiselect("板块", sector_options, default=sector_options)
with col3:
    selected_risks = st.multiselect("风险类别", risk_options, default=risk_options)

sort_mode = st.radio(
    "排序方式",
    ["sentiment_score 从高到低", "sentiment_score 从低到高", "risk_intensity 从高到低"],
    horizontal=True,
)

filtered = df[
    df["source"].isin(selected_sources)
    & df["sector"].isin(selected_sectors)
    & df["risk_category"].isin(selected_risks)
].copy()

if sort_mode == "sentiment_score 从高到低":
    filtered = filtered.sort_values("sentiment_score", ascending=False)
elif sort_mode == "sentiment_score 从低到高":
    filtered = filtered.sort_values("sentiment_score", ascending=True)
else:
    filtered = filtered.sort_values("risk_intensity", ascending=False)

display_columns = [
    "title",
    "source",
    "published_at",
    "sector",
    "topic",
    "tickers",
    "sentiment_score",
    "optimism",
    "fear",
    "uncertainty",
    "agg_weight",
    "risk_category",
    "risk_intensity",
    "evidence_sentence",
    "url",
]

st.metric("筛选后新闻数量", len(filtered))
st.dataframe(
    filtered[display_columns],
    use_container_width=True,
    hide_index=True,
    column_config=url_column_config(),
)
