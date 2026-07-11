import pandas as pd
import streamlit as st

from src.config import CSV_EXPORT_ENCODING
from src.evaluation import (
    annotation_template,
    coverage_summary_table,
    evaluate_annotations,
    formula_article_examples,
    formula_metric_comparison,
    formula_rank_changes,
    formula_sector_outputs,
    output_distribution,
)
from src.ui_helpers import load_selected_articles


df, source_mode = load_selected_articles()

st.title("评估")
st.caption(
    "提供覆盖统计、输出分布、Baseline vs Enhanced 对比和人工标注 CSV 接口；"
    "正式消融与敏感性分析留到第二冲刺。"
)
st.caption(f"当前数据源：{source_mode}")

st.subheader("覆盖统计")
st.dataframe(coverage_summary_table(df), use_container_width=True, hide_index=True)

st.subheader("输出分布")
distribution = output_distribution(df)
st.dataframe(distribution.round(4), use_container_width=True, hide_index=True)

st.subheader("Baseline vs Enhanced 对比")
baseline_sector, enhanced_sector = formula_sector_outputs(df, source_mode)

st.markdown("**六维板块分布**")
metric_comparison = formula_metric_comparison(baseline_sector, enhanced_sector)
st.dataframe(metric_comparison.round(2), use_container_width=True, hide_index=True)

st.markdown("**各维度排名变化最大的板块**")
rank_changes = formula_rank_changes(
    df,
    baseline_sector,
    enhanced_sector,
    source_mode,
)
st.dataframe(rank_changes.round(2), use_container_width=True, hide_index=True)

st.markdown("**具体新闻两套分数对照**")
article_examples = formula_article_examples(df, limit=3)
st.dataframe(article_examples.round(2), use_container_width=True, hide_index=True)

st.subheader("人工标注 CSV 接口")
template = annotation_template(df)
st.download_button(
    "下载标注模板 CSV",
    data=template.to_csv(index=False).encode(CSV_EXPORT_ENCODING),
    file_name="annotation_template.csv",
    mime="text/csv",
)

uploaded_file = st.file_uploader(
    "上传已标注 CSV",
    type=["csv"],
    help="至少包含 article_id；可选标注列：label_sentiment、label_sector、label_risk_category。",
)
if uploaded_file is not None:
    annotations = pd.read_csv(uploaded_file)
    metrics = evaluate_annotations(df, annotations)
    st.dataframe(metrics, use_container_width=True, hide_index=True)
