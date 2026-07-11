import pandas as pd
import streamlit as st

from src.driver_analysis import collapse_articles_by_event
from src.ui_helpers import load_selected_articles, url_column_config


st.title("文章浏览器")
st.caption("当前显示已处理新闻；agg_weight 是聚合权重，不等同于板块级关注度。")

option_col1, option_col2 = st.columns(2)
with option_col1:
    load_all_history = st.checkbox(
        "加载全部历史", value=False, help="默认仅加载近 30 天工作集；勾选后读取全部累计历史。"
    )
with option_col2:
    group_by_event = st.checkbox(
        "按事件分组", value=False, help="每个 event_id 只显示 agg_weight 最高的代表文章。"
    )

df, source_mode = load_selected_articles(load_all_history=load_all_history)
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

NO_RISK_LABEL = "无风险"


def risk_set(value: object) -> frozenset[str]:
    """risk_category 允许分号多标签和空值；空值归入"无风险"筛选项。"""
    parts = frozenset(part.strip() for part in str(value or "").split(";") if part.strip())
    return parts if parts else frozenset({NO_RISK_LABEL})


time_filtered["_risk_set"] = time_filtered["risk_category"].map(risk_set)

source_options = sorted(time_filtered["source"].dropna().unique().tolist())
sector_options = sorted(time_filtered["sector"].dropna().unique().tolist())
risk_options = sorted(set().union(*time_filtered["_risk_set"]) if len(time_filtered) else set())

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

selected_risk_set = set(selected_risks)
filtered_articles = time_filtered[
    time_filtered["source"].isin(selected_sources)
    & time_filtered["sector"].isin(selected_sectors)
    & time_filtered["_risk_set"].map(lambda risks: bool(risks & selected_risk_set))
].copy()
filtered_articles = filtered_articles.drop(columns=["_risk_set"])

filtered = collapse_articles_by_event(filtered_articles) if group_by_event else filtered_articles

if sort_mode == "sentiment_score 从高到低":
    filtered = filtered.sort_values("sentiment_score", ascending=False)
elif sort_mode == "sentiment_score 从低到高":
    filtered = filtered.sort_values("sentiment_score", ascending=True)
else:
    filtered = filtered.sort_values("risk_intensity", ascending=False)

display_columns = [
    "title",
    "event_id",
    "source",
    "publisher",
    "source_count",
    "published_at",
    "sector",
    "topic",
    "tickers",
    "sentiment_score",
    "optimism",
    "fear",
    "uncertainty",
    "agg_weight",
    "source_weight",
    "content_level",
    "rescored",
    "risk_category",
    "risk_intensity",
    "evidence_sentence",
    "url",
]
if group_by_event:
    display_columns.insert(2, "event_article_count")

metric_label = "筛选后事件数量" if group_by_event else "筛选后新闻数量"
st.metric(metric_label, len(filtered))
if group_by_event:
    st.caption(f"这些事件共包含 {len(filtered_articles)} 篇独立新闻；分组仅影响展示。")
number_column_config = {
    "sentiment_score": st.column_config.NumberColumn(format="%.3f"),
    "optimism": st.column_config.NumberColumn(format="%.1f"),
    "fear": st.column_config.NumberColumn(format="%.1f"),
    "uncertainty": st.column_config.NumberColumn(format="%.1f"),
    "risk_intensity": st.column_config.NumberColumn(format="%.1f"),
    "agg_weight": st.column_config.NumberColumn(format="%.4f"),
    "source_weight": st.column_config.NumberColumn(format="%.2f"),
}
st.dataframe(
    filtered[display_columns],
    use_container_width=True,
    hide_index=True,
    column_config={**url_column_config(), **number_column_config},
)
