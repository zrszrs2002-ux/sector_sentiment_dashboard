import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.aggregation import sector_metrics
from src.config import METRIC_COLUMNS, METRIC_LABELS
from src.daily_snapshots import load_sector_snapshots
from src.ui_helpers import load_selected_articles, url_column_config


def split_values(series: pd.Series) -> pd.Series:
    values: list[str] = []
    for item in series.dropna().astype(str):
        values.extend([part.strip() for part in item.split(";") if part.strip()])
    return pd.Series(values)


def metric_table_from_row(row: pd.Series, value_label: str) -> list[dict[str, float | str]]:
    return [
        {"指标": METRIC_LABELS[column], value_label: round(float(row.get(column, 0) or 0), 1)}
        for column in METRIC_COLUMNS
    ]


df, source_mode = load_selected_articles()
sector_df = sector_metrics(df, data_source=source_mode)

st.title("板块详情")
st.caption(f"当前数据源：{source_mode}")
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

st.subheader("板块趋势")
trend_days = st.radio("趋势窗口", [7, 30], index=1, horizontal=True)
snapshot_df = load_sector_snapshots(source_mode)
snapshot_trend = snapshot_df[snapshot_df["sector"].astype(str).eq(str(selected_sector))].copy()
if not snapshot_trend.empty:
    snapshot_trend["snapshot_date"] = pd.to_datetime(snapshot_trend["snapshot_date"], errors="coerce").dt.date
    snapshot_trend = snapshot_trend.dropna(subset=["snapshot_date"]).sort_values("snapshot_date")
    max_snapshot_date = snapshot_trend["snapshot_date"].max()
    min_snapshot_date = (pd.Timestamp(max_snapshot_date) - pd.Timedelta(days=trend_days - 1)).date()
    snapshot_trend = snapshot_trend[snapshot_trend["snapshot_date"] >= min_snapshot_date]

snapshot_day_count = int(snapshot_trend["snapshot_date"].nunique()) if not snapshot_trend.empty else 0
if snapshot_day_count < 2:
    st.info(f"已积累 {snapshot_day_count} 天快照，趋势图需至少 2 天数据")
    if snapshot_day_count:
        latest_snapshot = snapshot_trend.sort_values("snapshot_date").iloc[-1]
        st.dataframe(
            metric_table_from_row(latest_snapshot, "当日快照值"),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.dataframe(
            metric_table_from_row(sector_row, "当前工作集数值"),
            use_container_width=True,
            hide_index=True,
        )
else:
    plot_df = snapshot_trend.copy()
    plot_df["snapshot_date_label"] = pd.to_datetime(plot_df["snapshot_date"]).dt.strftime("%m-%d")
    date_order = plot_df["snapshot_date_label"].drop_duplicates().tolist()
    plot_df = plot_df.rename(columns=METRIC_LABELS)
    chinese_metric_columns = [METRIC_LABELS[column] for column in METRIC_COLUMNS]
    trend_fig = px.line(
        plot_df,
        x="snapshot_date_label",
        y=chinese_metric_columns,
        markers=True,
        category_orders={"snapshot_date_label": date_order},
        title="基于每日聚合快照的六维趋势",
    )
    trend_fig.update_traces(mode="lines+markers")
    trend_fig.update_xaxes(type="category")
    trend_fig.update_layout(legend_title_text="指标", xaxis_title="快照日期", yaxis_title="分数（0-100）")
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

news_column_config = {
    **url_column_config(),
    "sentiment_score": st.column_config.NumberColumn("情绪分", format="%.3f"),
}

st.subheader("Top positive news")
st.dataframe(
    sector_articles.sort_values("sentiment_score", ascending=False)[
        ["title", "sentiment_score", "evidence_sentence", "url"]
    ],
    use_container_width=True,
    hide_index=True,
    column_config=news_column_config,
)

st.subheader("Top negative news")
st.dataframe(
    sector_articles.sort_values("sentiment_score")[
        ["title", "sentiment_score", "evidence_sentence", "url"]
    ],
    use_container_width=True,
    hide_index=True,
    column_config=news_column_config,
)

st.subheader("Key evidence sentences")
st.dataframe(
    sector_articles[["title", "evidence_sentence"]],
    use_container_width=True,
    hide_index=True,
)
