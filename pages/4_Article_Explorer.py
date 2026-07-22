import pandas as pd
import streamlit as st

from src.driver_analysis import collapse_articles_by_event
from src.ui_helpers import (
    load_selected_articles,
    markdown_article_link,
    sentiment_badge_markdown,
    url_column_config,
)


st.title("Article Explorer")
st.caption("Showing processed news. agg_weight is the aggregation weight and is not the same as sector-level attention.")

option_col1, option_col2 = st.columns(2)
with option_col1:
    load_all_history = st.checkbox(
        "Load full history", value=False, help="Only the last-30-day working set loads by default; check this to read the full accumulated history."
    )
with option_col2:
    group_by_event = st.checkbox(
        "Group by event", value=False, help="Show only the highest agg_weight representative article per event_id."
    )

df, source_mode = load_selected_articles(load_all_history=load_all_history)
st.caption(f"Current data source: {source_mode}")

valid_times = df["published_at"].dropna()
time_filtered = df.copy()
if not valid_times.empty:
    min_date = valid_times.min().date()
    max_date = valid_times.max().date()
    selected_date_range = st.date_input(
        "Publish date range",
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

NO_RISK_LABEL = "No risk"


def risk_set(value: object) -> frozenset[str]:
    """risk_category allows semicolon-separated multi-labels and blanks; blanks fall
    under the "No risk" filter option."""
    parts = frozenset(part.strip() for part in str(value or "").split(";") if part.strip())
    return parts if parts else frozenset({NO_RISK_LABEL})


time_filtered["_risk_set"] = time_filtered["risk_category"].map(risk_set)

source_options = sorted(time_filtered["source"].dropna().unique().tolist())
sector_options = sorted(time_filtered["sector"].dropna().unique().tolist())
risk_options = sorted(set().union(*time_filtered["_risk_set"]) if len(time_filtered) else set())

col1, col2, col3 = st.columns(3)
with col1:
    selected_sources = st.multiselect("News source", source_options, default=source_options)
with col2:
    selected_sectors = st.multiselect("Sector", sector_options, default=sector_options)
with col3:
    selected_risks = st.multiselect("Risk category", risk_options, default=risk_options)

sort_mode = st.radio(
    "Sort by",
    ["sentiment_score: high to low", "sentiment_score: low to high", "risk_intensity: high to low"],
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

if sort_mode == "sentiment_score: high to low":
    filtered = filtered.sort_values("sentiment_score", ascending=False)
elif sort_mode == "sentiment_score: low to high":
    filtered = filtered.sort_values("sentiment_score", ascending=True)
else:
    filtered = filtered.sort_values("risk_intensity", ascending=False)

metric_label = "Events after filtering" if group_by_event else "Articles after filtering"
st.metric(metric_label, len(filtered))
if group_by_event:
    st.caption(f"These events contain {len(filtered_articles)} individual articles in total; grouping only affects display.")

detail_columns = [
    "event_id",
    "source",
    "publisher",
    "source_count",
    "published_at",
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
    "risk_intensity",
    "evidence_sentence",
]
if group_by_event:
    detail_columns.insert(1, "event_article_count")
detail_number_format = {
    "sentiment_score": "{:.3f}",
    "optimism": "{:.1f}",
    "fear": "{:.1f}",
    "uncertainty": "{:.1f}",
    "risk_intensity": "{:.1f}",
    "agg_weight": "{:.4f}",
    "source_weight": "{:.2f}",
}

view_mode = st.radio(
    "Result view",
    ["Card view (clickable titles)", "Full table"],
    horizontal=True,
    key="article_explorer_view_mode",
)

if view_mode == "Card view (clickable titles)":
    max_cards = 50
    cards_to_show = filtered.head(max_cards)
    if len(filtered) > max_cards:
        st.caption(f"{len(filtered)} total; card view shows the first {max_cards}. To see everything, switch to \u201cFull table\u201d or narrow down with the filters.")
    for _, row in cards_to_show.iterrows():
        with st.container(border=True):
            st.markdown(f"##### {markdown_article_link(row.get('title'), row.get('url'))}")
            badge_col1, badge_col2, badge_col3 = st.columns([1, 1, 1.4])
            with badge_col1:
                st.markdown(f"\U0001f3f7\ufe0f **Sector** \u00b7 {row.get('sector', '') or 'Unmapped'}")
            with badge_col2:
                risk_label = str(row.get("risk_category") or "") or NO_RISK_LABEL
                st.markdown(f"\u26a0\ufe0f **Risk category** \u00b7 {risk_label}")
            with badge_col3:
                st.markdown(sentiment_badge_markdown(row.get("sentiment_score")), unsafe_allow_html=True)
            with st.expander("View all fields"):
                for column in detail_columns:
                    if column not in row:
                        continue
                    value = row.get(column)
                    if column in detail_number_format:
                        try:
                            value = detail_number_format[column].format(float(value))
                        except (TypeError, ValueError):
                            pass
                    st.write(f"**{column}**: {value}")
else:
    display_columns = ["title", "sector", "risk_category", *detail_columns, "url"]
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
