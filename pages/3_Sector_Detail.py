import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.aggregation import sector_metrics
from src.config import METRIC_COLUMNS, METRIC_LABELS
from src.daily_snapshots import load_sector_snapshots
from src.ui_helpers import (
    apply_chart_theme,
    apply_radar_theme,
    compact_subheader,
    count_bar_chart,
    load_selected_articles,
    markdown_article_link,
    sentiment_badge_markdown,
)


def split_values(series: pd.Series) -> pd.Series:
    values: list[str] = []
    for item in series.dropna().astype(str):
        values.extend([part.strip() for part in item.split(";") if part.strip()])
    return pd.Series(values)


def metric_table_from_row(row: pd.Series, value_label: str) -> list[dict[str, float | str]]:
    return [
        {"Metric": METRIC_LABELS[column], value_label: round(float(row.get(column, 0) or 0), 1)}
        for column in METRIC_COLUMNS
    ]


def _render_news_card(row: pd.Series) -> None:
    with st.container(border=True):
        st.markdown(f"**{markdown_article_link(row.get('title'), row.get('url'))}**")
        st.markdown(sentiment_badge_markdown(row.get("sentiment_score")), unsafe_allow_html=True)
        evidence = str(row.get("evidence_sentence") or "").strip()
        if evidence:
            st.caption(evidence)


def render_news_cards(articles: pd.DataFrame, visible_count: int = 5) -> None:
    """News cards with clickable titles and a colored sentiment badge; only the first
    visible_count are shown by default, the rest are tucked into an expander so a long
    list doesn't take over the page."""
    if articles.empty:
        st.info("No news under the current filter.")
        return
    rows = list(articles.iterrows())
    for _, row in rows[:visible_count]:
        _render_news_card(row)
    remaining = rows[visible_count:]
    if remaining:
        with st.expander(f"Show {len(remaining)} more"):
            for _, row in remaining:
                _render_news_card(row)


df, source_mode = load_selected_articles()
sector_df = sector_metrics(df, data_source=source_mode)

st.title("Sector Detail")
st.caption(f"Current data source: {source_mode}")
selected_sector = st.selectbox("Select sector", options=sector_df["sector"].tolist())
sector_articles = df[df["sector"] == selected_sector].copy()
sector_row = sector_df[sector_df["sector"] == selected_sector].iloc[0]

labels = [METRIC_LABELS[column] for column in METRIC_COLUMNS]
values = [float(sector_row[column]) for column in METRIC_COLUMNS]
values_closed = values + values[:1]
labels_closed = labels + labels[:1]
fig = go.Figure(
    data=[
        go.Scatterpolar(
            r=values_closed,
            theta=labels_closed,
            fill="toself",
            name=selected_sector,
            mode="lines+markers+text",
            text=[f"{v:.0f}" for v in values_closed],
            textposition="top center",
            marker=dict(size=6),
        )
    ]
)
style = apply_radar_theme(fig, f"{selected_sector} Six-Dimension Radar", height=430)
fig.update_traces(textfont=dict(size=11, color=style["point_label"]))
st.plotly_chart(fig, use_container_width=True, theme=None)

st.subheader("Sector Trend")
trend_days = st.radio("Trend window", [7, 30], index=1, horizontal=True)
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
    st.info(f"{snapshot_day_count} day(s) of snapshots collected so far; the trend chart needs at least 2 days of data")
    if snapshot_day_count:
        latest_snapshot = snapshot_trend.sort_values("snapshot_date").iloc[-1]
        st.dataframe(
            metric_table_from_row(latest_snapshot, "Latest snapshot value"),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.dataframe(
            metric_table_from_row(sector_row, "Current working-set value"),
            use_container_width=True,
            hide_index=True,
        )
else:
    plot_df = snapshot_trend.copy()
    plot_df["snapshot_date_label"] = pd.to_datetime(plot_df["snapshot_date"]).dt.strftime("%m-%d")
    date_order = plot_df["snapshot_date_label"].drop_duplicates().tolist()
    plot_df = plot_df.rename(columns=METRIC_LABELS)
    metric_display_columns = [METRIC_LABELS[column] for column in METRIC_COLUMNS]
    trend_fig = px.line(
        plot_df,
        x="snapshot_date_label",
        y=metric_display_columns,
        markers=True,
        category_orders={"snapshot_date_label": date_order},
        title="Six-Dimension Trend from Daily Aggregated Snapshots",
    )
    trend_fig.update_traces(mode="lines+markers")
    trend_fig.update_xaxes(type="category")
    trend_fig.update_layout(legend_title_text="Metric", xaxis_title="Snapshot date", yaxis_title="Score (0-100)")
    apply_chart_theme(trend_fig)
    st.plotly_chart(trend_fig, use_container_width=True, theme=None)

col1, col2, col3 = st.columns(3)
with col1:
    compact_subheader("Top mentioned companies")
    companies = split_values(sector_articles["companies"]).value_counts()
    st.plotly_chart(count_bar_chart(companies, color="#4098e6"), use_container_width=True, theme=None)

with col2:
    compact_subheader("Top topics")
    topics = sector_articles["topic"].value_counts()
    st.plotly_chart(count_bar_chart(topics, color="#c76ae0"), use_container_width=True, theme=None)

with col3:
    compact_subheader("Top risk categories")
    risks = sector_articles["risk_category"].value_counts()
    st.plotly_chart(count_bar_chart(risks, color="#f2495c"), use_container_width=True, theme=None)

st.subheader("Top positive news")
render_news_cards(sector_articles.sort_values("sentiment_score", ascending=False).head(20))

st.subheader("Top negative news")
render_news_cards(sector_articles.sort_values("sentiment_score").head(20))

st.subheader("Key evidence sentences")
st.dataframe(
    sector_articles[["title", "evidence_sentence"]],
    use_container_width=True,
    hide_index=True,
)
