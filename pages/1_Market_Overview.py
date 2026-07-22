import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.aggregation import market_metrics, sector_metrics
from src.brief_generator import read_latest_brief
from src.config import (
    DISCLAIMER,
    DRIVER_MIN_EVENTS,
    DRIVER_WINDOW_HOURS,
    METRIC_COLUMNS,
    METRIC_LABELS,
    WORKING_SET_DAYS,
)
from src.driver_analysis import top_driver_articles
from src.rss_sources import distinct_value_count
from src.ui_helpers import (
    METRIC_ACCENT_COLORS,
    apply_radar_theme,
    load_selected_articles,
    markdown_article_link,
    metric_bar_chart,
    render_sector_heatmap,
)


def render_radar(scores: dict[str, float], title: str) -> None:
    labels = [METRIC_LABELS[column] for column in METRIC_COLUMNS]
    values = [float(scores.get(column, 0)) for column in METRIC_COLUMNS]
    values_closed = values + values[:1]
    labels_closed = labels + labels[:1]
    fig = go.Figure(
        data=[
            go.Scatterpolar(
                r=values_closed,
                theta=labels_closed,
                fill="toself",
                name="Market-level metrics",
                mode="lines+markers+text",
                text=[f"{v:.0f}" for v in values_closed],
                textposition="top center",
                marker=dict(size=6),
            )
        ]
    )
    style = apply_radar_theme(fig, title, height=430)
    fig.update_traces(textfont=dict(size=11, color=style["point_label"]))
    st.plotly_chart(fig, use_container_width=True, theme=None)


def fmt_time(value: object) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M UTC")


def fmt_time_short(value: object) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return pd.Timestamp(value).strftime("%m-%d %H:%M")


def fmt_iso_short(value: object) -> str:
    try:
        return pd.Timestamp(str(value)).strftime("%m-%d %H:%M")
    except (ValueError, TypeError):
        return str(value or "")


def render_driver_events(drivers: pd.DataFrame) -> None:
    if drivers.empty:
        st.info("No driver events to show in the current window.")
        return

    for rank, row in enumerate(drivers.to_dict("records"), start=1):
        with st.container(border=True):
            st.markdown(
                f"##### {rank}. {markdown_article_link(row.get('title'), row.get('url'))}"
            )
            source_count = int(float(row.get("source_count", 0) or 0))
            article_count = int(float(row.get("event_article_count", 1) or 1))
            boost_label = " \u00b7 coverage boost applied" if bool(row.get("coverage_boost_applied")) else ""
            macro_label = " \u00b7 macro guaranteed" if bool(row.get("macro_guaranteed")) else ""
            st.caption(
                f"{row.get('sector', 'Unmapped')} \u00b7 {row.get('topic', '')} \u00b7 "
                f"Sentiment Score {float(row.get('driver_score', 0) or 0):.1f} \u00b7 {source_count} outlets"
                f"{boost_label}{macro_label}"
            )
            st.write(str(row.get("driver_reason", "")))

            if article_count > 1:
                other_media_count = max(0, source_count - 1)
                media_label = (
                    f"{other_media_count} other outlets covered this"
                    if other_media_count
                    else f"{article_count - 1} other reprint(s) of this story"
                )
                with st.expander(f"{media_label} \u00b7 view all {article_count} articles in this cluster"):
                    for article in row.get("event_articles", []):
                        st.markdown(
                            f"- {markdown_article_link(article.get('title'), article.get('url'))}  "
                            f"  {article.get('publisher', '') or article.get('source', '')} \u00b7 "
                            f"{fmt_time(article.get('published_at'))}"
                        )
        st.write("")


df, source_mode = load_selected_articles()
market_scores = market_metrics(df, data_source=source_mode)
sector_df = sector_metrics(df, data_source=source_mode)
latest_brief = read_latest_brief()
brief_meta = latest_brief.get("metadata", {}) if isinstance(latest_brief.get("metadata"), dict) else {}
brief_content = str(latest_brief.get("content", "") or "")

data_updated_at = df["collected_at"].max() if "collected_at" in df else pd.NaT
brief_generated_at = brief_meta.get("generated_at_local") or brief_meta.get("generated_at") or ""
summary_source = brief_meta.get("summary_source", "Rule template")
brief_model_id = brief_meta.get("model_id", "")
if summary_source == "AI generated":
    model_label = f" \u00b7 model {brief_model_id}" if brief_model_id else ""
    brief_source_label = f"AI generated{model_label} \u00b7 brief time {brief_generated_at}"
else:
    brief_source_label = f"Rule template \u00b7 brief time {brief_generated_at or 'not yet generated'}"

st.title("Market Overview")
st.caption("Fetching can run multiple times/day; the LLM brief defaults to once/day. This page only reads the already-generated latest_brief.md.")
st.caption(f"Current data source: {source_mode}")
st.warning(DISCLAIMER)

metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
metric_col1.metric("Articles in window", f"{len(df):,}")
metric_col2.metric(
    "Publishers covered",
    f"{distinct_value_count(df['publisher'] if 'publisher' in df else df.get('source', []), df.get('source', [])):,}",
)
metric_col3.metric("Data window", f"last {WORKING_SET_DAYS} days")
metric_col4.metric(
    "Data updated at",
    fmt_time_short(data_updated_at),
    help=f"Full timestamp: {fmt_time(data_updated_at)}; refreshes with every fetch.",
)

left_col, right_col = st.columns([1.05, 0.95])
with left_col:
    render_radar(market_scores, "Overall Market Sentiment Radar")
    st.subheader("Market-Level Six-Dimension Scores")
    market_score_values = {
        METRIC_LABELS[column]: round(float(market_scores[column]), 1) for column in METRIC_COLUMNS
    }
    st.plotly_chart(
        metric_bar_chart(
            market_score_values,
            color=[METRIC_ACCENT_COLORS[column] for column in METRIC_COLUMNS],
            height=260,
        ),
        use_container_width=True,
        theme=None,
    )

with right_col:
    st.subheader("Daily Market Brief")
    st.caption(brief_source_label)
    if brief_content:
        snapshot_id = str(brief_meta.get("data_snapshot_id", ""))
        brief_article_count = snapshot_id.split("|")[-1] if snapshot_id.count("|") >= 2 else ""
        window_label = (
            f"{fmt_iso_short(brief_meta.get('data_window_start'))} \u2013 "
            f"{fmt_iso_short(brief_meta.get('data_window_end'))} UTC"
        )
        count_label = f"{brief_article_count} articles" if brief_article_count else "articles in window at generation time"
        st.info(
            f"This brief is based on {count_label} (window {window_label}), "
            f"generated at {fmt_iso_short(brief_generated_at)}; "
            f"the rest of this page reflects the current live window ({len(df):,} articles), "
            "so numbers may differ from the brief."
        )
    with st.container(height=600, border=True):
        if brief_content:
            st.markdown(brief_content)
        else:
            st.info(
                "No latest_brief.md yet. The fetch pipeline generates it automatically at the daily "
                "generation time; you can also confirm a manual regeneration in the sidebar."
            )

st.subheader("Sector Heatmap")
heatmap_mode = st.radio(
    "Heatmap color mode",
    options=["Cross-sectional (relative)", "Absolute 0-100 scale"],
    horizontal=True,
    key="market_heatmap_color_mode",
)
render_sector_heatmap(
    sector_df,
    color_mode="relative" if heatmap_mode == "Cross-sectional (relative)" else "absolute",
)

driver_title = st.empty()
driver_window_mode = st.radio(
    "Driver event window",
    options=["Last 48 hours", "Last 30 days"],
    horizontal=True,
    key="market_driver_window",
)
requested_driver_window = (
    DRIVER_WINDOW_HOURS if driver_window_mode == "Last 48 hours" else WORKING_SET_DAYS * 24
)
drivers = top_driver_articles(
    df,
    limit=5,
    window_hours=requested_driver_window,
    min_events=DRIVER_MIN_EVENTS,
)
if driver_window_mode == "Last 48 hours":
    actual_driver_window = int(drivers.attrs.get("driver_window_hours", DRIVER_WINDOW_HOURS))
    driver_window_label = f"last {actual_driver_window} hours"
else:
    driver_window_label = f"last {WORKING_SET_DAYS} days"
driver_title.subheader(f"Top Market Drivers ({driver_window_label})")
render_driver_events(drivers)
