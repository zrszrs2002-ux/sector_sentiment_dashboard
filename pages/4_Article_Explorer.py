import pandas as pd
import streamlit as st

from src.ui_helpers import load_selected_articles, url_column_config


load_all_history = st.checkbox("加载全部历史", value=False, help="默认仅加载近 30 天工作集；勾选后读取全部累计历史。")
df, source_mode = load_selected_articles(load_all_history=load_all_history)

st.title("文章浏览器")
st.caption("当前显示已处理新闻；agg_weight 是聚合权重，不等同于板块级关注度。")
st.caption(f"当前数据源：{source_mode}")

valid_times = df["published_at"].dropna()
time_filtered = df.copy()
if not valid_times.empty:
    min_date = valid_times.min().date()
    max_date = valid_times.max().date()
    selected_date_range = st.date_input(
        "发布时间范围",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if isinstance(selected_date_range, tuple) and len(selected_date_range) == 2:
        start_date, end_date = selected_date_range
        start_ts = pd.Timestamp(start_date, tz="UTC")
        end_ts = pd.Timestamp(end_date, tz="UTC") + pd.Timedelta(days=1)
        time_filtered = df[(df["published_at"] >= start_ts) & (df["published_at"] < end_ts)].copy()
    else:
        selected_date = selected_date_range
        start_ts = pd.Timestamp(selected_date, tz="UTC")
        end_ts = start_ts + pd.Timedelta(days=1)
        time_filtered = df[(df["published_at"] >= start_ts) & (df["published_at"] < end_ts)].copy()

source_options = sorted(time_filtered["source"].dropna().unique().tolist())
sector_options = sorted(time_filtered["sector"].dropna().unique().tolist())
risk_options = sorted(time_filtered["risk_category"].dropna().unique().tolist())

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

filtered = time_filtered[
    time_filtered["source"].isin(selected_sources)
    & time_filtered["sector"].isin(selected_sectors)
    & time_filtered["risk_category"].isin(selected_risks)
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
