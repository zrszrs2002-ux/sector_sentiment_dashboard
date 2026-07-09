import pandas as pd
import streamlit as st

from src.config import CSV_EXPORT_ENCODING
from src.evaluation import (
    annotation_template,
    coverage_summary_table,
    evaluate_annotations,
    output_distribution,
)
from src.ui_helpers import load_selected_articles


df, source_mode = load_selected_articles()

st.title("评估")
st.caption("当前只提供覆盖统计、输出分布和人工标注 CSV 指标接口；消融和敏感性分析留到第二冲刺。")
st.caption(f"当前数据源：{source_mode}")

st.subheader("覆盖统计")
st.dataframe(coverage_summary_table(df), use_container_width=True, hide_index=True)

st.subheader("输出分布")
distribution = output_distribution(df)
st.dataframe(distribution.round(4), use_container_width=True, hide_index=True)

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
