import plotly.graph_objects as go
import streamlit as st

from src.aggregation import sector_metrics
from src.config import METRIC_COLUMNS, METRIC_LABELS
from src.ui_helpers import load_selected_articles, render_sector_heatmap


df, source_mode = load_selected_articles()
sector_df = sector_metrics(df, data_source=source_mode)

st.title("板块比较")
st.caption(
    "比较 11 个板块的增强版六维指标；关注度在历史不足 30 天时使用横截面排名分位数，"
    "积累充足后自动切换自身历史 ECDF；分歧度融合加权情绪标准差与正负极性混合度。"
)
st.caption(f"当前数据源：{source_mode}")

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
render_sector_heatmap(sector_df)

st.subheader("板块排名速览")
ranking_specs = [
    ("optimism", "最乐观板块"),
    ("fear", "恐惧度最高"),
    ("uncertainty", "不确定性最高"),
    ("attention", "关注度最高"),
    ("disagreement", "分歧度最高"),
    ("risk_intensity", "风险强度最高"),
]
ranking_rows = [st.columns(3), st.columns(3)]
for index, (metric_column, ranking_title) in enumerate(ranking_specs):
    with ranking_rows[index // 3][index % 3]:
        st.markdown(f"**{ranking_title}**")
        ranking_table = sector_df.nlargest(5, metric_column)[["sector", metric_column]].copy()
        ranking_table[metric_column] = ranking_table[metric_column].astype(float).round(1)
        ranking_table.columns = ["板块", METRIC_LABELS[metric_column]]
        st.dataframe(ranking_table, hide_index=True, use_container_width=True)

st.subheader("板块指标表")
display_df = sector_df.copy()
for metric_column in METRIC_COLUMNS:
    display_df[metric_column] = display_df[metric_column].astype(float).round(1)
if "article_count" in display_df:
    display_df["article_count"] = display_df["article_count"].astype(int)
ordered_columns = [column for column in ["sector", "article_count", *METRIC_COLUMNS] if column in display_df]
display_df = display_df[ordered_columns].rename(
    columns={"sector": "板块", "article_count": "新闻数", **METRIC_LABELS}
)
st.dataframe(display_df, use_container_width=True, hide_index=True)
