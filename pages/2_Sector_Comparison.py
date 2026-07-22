import plotly.graph_objects as go
import streamlit as st

from src.aggregation import sector_metrics
from src.config import METRIC_COLUMNS, METRIC_LABELS
from src.ui_helpers import (
    METRIC_ACCENT_COLORS,
    apply_radar_theme,
    load_selected_articles,
    metric_bar_chart,
    render_sector_heatmap,
)


df, source_mode = load_selected_articles()
sector_df = sector_metrics(df, data_source=source_mode)

st.title("Sector Comparison")
st.caption(
    "Compares the enhanced six-dimension metrics across 11 sectors; Attention uses "
    "cross-sectional rank percentiles when history is under 30 days and automatically "
    "switches to its own historical ECDF once enough data accumulates; Disagreement blends "
    "weighted sentiment standard deviation with positive/negative polarity mix."
)
st.caption(f"Current data source: {source_mode}")

selected_sectors = st.multiselect(
    "Select sectors to overlay on the radar chart",
    options=sector_df["sector"].tolist(),
    default=sector_df["sector"].head(3).tolist(),
)

fig = go.Figure()
labels = [METRIC_LABELS[column] for column in METRIC_COLUMNS]
labels_closed = labels + labels[:1]
for sector in selected_sectors:
    row = sector_df[sector_df["sector"] == sector].iloc[0]
    values = [float(row[column]) for column in METRIC_COLUMNS]
    values_closed = values + values[:1]
    fig.add_trace(
        go.Scatterpolar(
            r=values_closed,
            theta=labels_closed,
            fill="toself",
            name=sector,
            mode="lines+markers+text",
            text=[f"{v:.0f}" for v in values_closed],
            textposition="top center",
            textfont=dict(size=10),
            marker=dict(size=5),
        )
    )
apply_radar_theme(fig, "Sector Radar Comparison", height=460)
st.plotly_chart(fig, use_container_width=True, theme=None)

st.subheader("Sector Heatmap")
heatmap_mode = st.radio(
    "Heatmap color mode",
    options=["Cross-sectional (relative)", "Absolute 0-100 scale"],
    horizontal=True,
    key="comparison_heatmap_color_mode",
)
render_sector_heatmap(
    sector_df,
    color_mode="relative" if heatmap_mode == "Cross-sectional (relative)" else "absolute",
)

st.subheader("Sector Rankings at a Glance")
ranking_specs = [
    ("optimism", "Most optimistic sectors"),
    ("fear", "Highest fear"),
    ("uncertainty", "Highest uncertainty"),
    ("attention", "Highest attention"),
    ("disagreement", "Highest disagreement"),
    ("risk_intensity", "Highest risk intensity"),
]
ranking_rows = [st.columns(3), st.columns(3)]
for index, (metric_column, ranking_title) in enumerate(ranking_specs):
    with ranking_rows[index // 3][index % 3]:
        st.markdown(f"**{ranking_title}**")
        ranking_table = sector_df.nlargest(5, metric_column)[["sector", metric_column]].copy()
        ranking_values = {
            str(row["sector"]): round(float(row[metric_column]), 1)
            for _, row in ranking_table.iterrows()
        }
        st.plotly_chart(
            metric_bar_chart(
                ranking_values,
                color=METRIC_ACCENT_COLORS[metric_column],
                height=190,
            ),
            use_container_width=True,
            theme=None,
        )

st.subheader("Sector Metrics Table")
display_df = sector_df.copy()
for metric_column in METRIC_COLUMNS:
    display_df[metric_column] = display_df[metric_column].astype(float).round(1)
if "article_count" in display_df:
    display_df["article_count"] = display_df["article_count"].astype(int)
ordered_columns = [column for column in ["sector", "article_count", *METRIC_COLUMNS] if column in display_df]
display_df = display_df[ordered_columns].rename(
    columns={"sector": "Sector", "article_count": "Articles", **METRIC_LABELS}
)
metric_progress_config = {
    METRIC_LABELS[column]: st.column_config.ProgressColumn(
        METRIC_LABELS[column], min_value=0, max_value=100, format="%.1f"
    )
    for column in METRIC_COLUMNS
}
st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    column_config=metric_progress_config,
)
