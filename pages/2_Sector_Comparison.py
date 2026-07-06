import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.aggregation import sector_metrics
from src.config import METRIC_COLUMNS, METRIC_LABELS
from src.data_loader import load_demo_articles


df = load_demo_articles()
sector_df = sector_metrics(df)

st.title("板块比较")
st.caption("比较 11 个板块的 demo 六维指标。后续阶段会加入正式聚合权重。")

selected_sectors = st.multiselect(
    "选择要叠加到雷达图的板块",
    options=sector_df["sector"].tolist(),
    default=sector_df["sector"].head(3).tolist(),
)

fig = go.Figure()
labels = [METRIC_LABELS[column] for column in METRIC_COLUMNS]
for sector in selected_sectors:
    row = sector_df[sector_df["sector"] == sector].iloc[0]
    values = [float(row[column]) for column in METRIC_COLUMNS]
    fig.add_trace(
        go.Scatterpolar(
            r=values + values[:1],
            theta=labels + labels[:1],
            fill="toself",
            name=sector,
        )
    )
fig.update_layout(
    title="Sector Radar Comparison",
    polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
    height=460,
)
st.plotly_chart(fig, use_container_width=True)

st.subheader("Sector Heatmap")
heatmap_df = sector_df.set_index("sector")[METRIC_COLUMNS].rename(columns=METRIC_LABELS)
heatmap_fig = px.imshow(
    heatmap_df,
    text_auto=".1f",
    aspect="auto",
    color_continuous_scale="RdYlGn",
)
heatmap_fig.update_layout(height=430)
st.plotly_chart(heatmap_fig, use_container_width=True)

col1, col2, col3, col4, col5 = st.columns(5)
col1.dataframe(sector_df.nlargest(5, "optimism")[["sector", "optimism"]], hide_index=True)
col2.dataframe(sector_df.nlargest(5, "fear")[["sector", "fear"]], hide_index=True)
col3.dataframe(sector_df.nlargest(5, "uncertainty")[["sector", "uncertainty"]], hide_index=True)
col4.dataframe(sector_df.nlargest(5, "disagreement_input")[["sector", "disagreement_input"]], hide_index=True)
col5.dataframe(sector_df.nlargest(5, "risk_intensity")[["sector", "risk_intensity"]], hide_index=True)

st.subheader("板块指标表")
display_df = sector_df.rename(columns={"sector": "Sector", **METRIC_LABELS})
st.dataframe(display_df, use_container_width=True, hide_index=True)
