import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.config import (
    ANNOTATION_BLIND_PATH,
    ANNOTATION_ERRORS_PATH,
    ANNOTATION_KEY_PATH,
    ANNOTATION_RANDOM_SEED,
    ANNOTATION_SAMPLE_SIZE,
    CSV_EXPORT_ENCODING,
    RAW_ARTICLES_PATH,
    REAL_PROCESSED_ARTICLES_PATH,
)
from scripts.sample_for_annotation import build_annotation_files
from src.evaluation import (
    SENTIMENT_LABELS,
    coverage_summary_table,
    evaluate_model_annotations,
    formula_article_examples,
    formula_metric_comparison,
    formula_rank_changes,
    formula_sector_outputs,
    output_distribution,
)
from src.ui_helpers import load_selected_articles


def read_csv_file(source) -> pd.DataFrame:
    return pd.read_csv(source, encoding="utf-8-sig")


def csv_download_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode(CSV_EXPORT_ENCODING)


def render_confusion_matrix(matrix: pd.DataFrame, title: str) -> None:
    figure = px.imshow(
        matrix,
        text_auto="d",
        color_continuous_scale="Blues",
        labels={"x": "预测标签", "y": "真实标签", "color": "样本数"},
        title=title,
        aspect="auto",
    )
    figure.update_layout(height=390)
    st.plotly_chart(figure, use_container_width=True)


def render_reliability_curve(reliability: pd.DataFrame) -> None:
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=[0, 1],
            y=[0, 1],
            mode="lines",
            name="理想校准",
            line={"dash": "dash", "color": "#777"},
        )
    )
    figure.add_trace(
        go.Scatter(
            x=reliability["mean_confidence"],
            y=reliability["accuracy"],
            mode="lines+markers",
            name="FinBERT",
            text=[f"样本数 {count}" for count in reliability["count"]],
            hovertemplate="平均置信度 %{x:.3f}<br>准确率 %{y:.3f}<br>%{text}<extra></extra>",
        )
    )
    figure.update_layout(
        title="FinBERT 可靠性曲线",
        xaxis_title="分桶平均置信度",
        yaxis_title="分桶准确率",
        xaxis={"range": [0, 1]},
        yaxis={"range": [0, 1]},
        height=390,
    )
    st.plotly_chart(figure, use_container_width=True)


df, source_mode = load_selected_articles()

st.title("评估")
st.info(
    "本页评估文章分类层：情绪、板块映射、风险标签、证据句与 FinBERT 校准。"
    "六维指标层的稳健性验证（敏感性分析与消融实验）另行实现。"
)
st.caption(f"当前数据源：{source_mode}")
st.caption("上方分类评估固定读取 annotation 文件；当前数据源只影响页面底部的数据诊断区块。")

st.subheader("人工标注评估")
st.caption(
    "可直接在页面生成并下载待标注的 annotation_blind.csv；"
    "annotation_key.csv 会同步保存，仅供本页后台对账，不提供给标注者。"
)

st.markdown("**盲标样本生成与下载**")
sample_col1, sample_col2, sample_col3 = st.columns([0.9, 0.9, 1.4])
sample_size = sample_col1.number_input(
    "抽样条数",
    min_value=1,
    max_value=5000,
    value=ANNOTATION_SAMPLE_SIZE,
    step=50,
)
sample_seed = sample_col2.number_input(
    "随机种子",
    min_value=0,
    max_value=999999999,
    value=ANNOTATION_RANDOM_SEED,
    step=1,
)
sample_col3.caption(
    "重新生成会刷新 data/annotation 下的盲标文件和对账 key；"
    "已有标注进行中时，请先下载当前版本留档。"
)

generated_blind = st.session_state.get("generated_annotation_blind")
generated_key = st.session_state.get("generated_annotation_key")
if st.button("生成/刷新盲标样本", type="primary"):
    try:
        generated_blind, generated_key = build_annotation_files(
            RAW_ARTICLES_PATH,
            REAL_PROCESSED_ARTICLES_PATH,
            ANNOTATION_BLIND_PATH.parent,
            sample_size=int(sample_size),
            seed=int(sample_seed),
        )
    except (FileNotFoundError, OSError, UnicodeDecodeError, ValueError, pd.errors.ParserError) as exc:
        st.error(f"盲标样本生成失败：{exc}")
    else:
        st.session_state["generated_annotation_blind"] = generated_blind
        st.session_state["generated_annotation_key"] = generated_key
        st.success(
            f"已生成 {len(generated_blind)} 条盲标样本，并同步刷新 annotation_key.csv。"
        )

download_blind = generated_blind
download_key = generated_key
if download_blind is None and ANNOTATION_BLIND_PATH.exists():
    try:
        download_blind = read_csv_file(ANNOTATION_BLIND_PATH)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        st.warning(f"当前盲标文件读取失败，暂不能下载：{exc}")
if download_key is None and ANNOTATION_KEY_PATH.exists():
    try:
        download_key = read_csv_file(ANNOTATION_KEY_PATH)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        st.warning(f"当前对账 key 读取失败：{exc}")

download_col1, download_col2 = st.columns([1, 1])
with download_col1:
    if isinstance(download_blind, pd.DataFrame) and not download_blind.empty:
        st.download_button(
            "下载待标注 CSV",
            data=csv_download_bytes(download_blind),
            file_name="annotation_blind.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.caption(f"当前可下载 {len(download_blind)} 条盲标样本。")
    else:
        st.info("尚无盲标样本，请先点击上方按钮生成。")
with download_col2:
    with st.expander("内部对账 key 下载"):
        st.warning("annotation_key.csv 含模型预测列，只能由评估者保存，不能给标注者。")
        if isinstance(download_key, pd.DataFrame) and not download_key.empty:
            st.download_button(
                "下载 annotation_key.csv",
                data=csv_download_bytes(download_key),
                file_name="annotation_key.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            st.info("暂无可下载的对账 key。")

uploaded_file = st.file_uploader(
    "上传已填写的 annotation_blind.csv（留空则读取 data/annotation/annotation_blind.csv）",
    type=["csv"],
)

annotations = pd.DataFrame()
annotation_key = pd.DataFrame()
if uploaded_file is not None:
    try:
        annotations = read_csv_file(uploaded_file)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        st.error(f"标注 CSV 读取失败：{exc}")
elif ANNOTATION_BLIND_PATH.exists():
    try:
        annotations = read_csv_file(ANNOTATION_BLIND_PATH)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        st.error(f"默认盲标文件读取失败：{exc}")

if ANNOTATION_KEY_PATH.exists():
    try:
        annotation_key = read_csv_file(ANNOTATION_KEY_PATH)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        st.error(f"annotation_key 读取失败：{exc}")

if annotations.empty or annotation_key.empty:
    st.info("尚无可评估的盲标文件与对账 key，请先在上方生成盲标样本。")
else:
    label_columns = [
        "label_sentiment",
        "label_sector_ok",
        "label_risk_categories",
        "label_evidence_ok",
    ]
    completed_cells = sum(
        int(annotations.get(column, pd.Series(dtype=str)).fillna("").astype(str).str.strip().ne("").sum())
        for column in label_columns
    )
    st.caption(
        f"已载入 {len(annotations)} 条盲标样本；四类标签共填写 {completed_cells} 个单元格。"
    )
    try:
        result = evaluate_model_annotations(
            annotations,
            annotation_key,
            error_output_path=ANNOTATION_ERRORS_PATH,
        )
    except ValueError as exc:
        st.error(f"标注数据校验失败：{exc}")
    else:
        if result["sentiment_labelled_count"] == 0:
            st.info("当前尚未填写有效情绪标签；填写后将显示三方对比、混淆矩阵与校准结果。")
        else:
            metric_a, metric_b, metric_c, metric_d = st.columns(4)
            finbert_report = result["sentiment_reports"]["FinBERT"]
            metric_a.metric("情绪标注数", result["sentiment_labelled_count"])
            metric_b.metric("FinBERT Accuracy", f"{finbert_report['accuracy']:.3f}")
            metric_c.metric("FinBERT Macro F1", f"{finbert_report['macro_f1']:.3f}")
            metric_d.metric("Brier Score", f"{result['calibration']['brier_score']:.3f}")

            st.markdown("**全中性基线 / 词典引擎 / FinBERT**")
            st.dataframe(
                result["sentiment_comparison"].round(4),
                use_container_width=True,
                hide_index=True,
            )

            engine = st.selectbox(
                "混淆矩阵与分类指标引擎",
                options=list(result["sentiment_reports"]),
                index=2,
            )
            selected_report = result["sentiment_reports"][engine]
            left, right = st.columns([0.9, 1.1])
            with left:
                st.dataframe(
                    selected_report["per_class"].round(4),
                    use_container_width=True,
                    hide_index=True,
                )
            with right:
                render_confusion_matrix(
                    selected_report["confusion_matrix"],
                    f"{engine} 3×3 混淆矩阵",
                )

            reliability = result["calibration"]["reliability"]
            if not reliability.empty:
                render_reliability_curve(reliability)
                st.dataframe(
                    reliability.round(4),
                    use_container_width=True,
                    hide_index=True,
                )

        st.markdown("**板块、风险与证据句**")
        sector_metric, evidence_metric = st.columns(2)
        sector_value = (
            f"{result['sector_mapping']['accuracy']:.3f}"
            if result["sector_mapping"]["sample_count"]
            else "暂无"
        )
        evidence_value = (
            f"{result['evidence']['precision']:.3f}"
            if result["evidence"]["sample_count"]
            else "暂无"
        )
        sector_metric.metric(
            "板块映射 Accuracy",
            sector_value,
            help=f"有效标注 {result['sector_mapping']['sample_count']} 条",
        )
        evidence_metric.metric(
            "证据句 Precision",
            evidence_value,
            help=f"有效标注 {result['evidence']['sample_count']} 条",
        )
        if not result["risk"]["per_class"].empty:
            st.caption(
                f"风险多标签 Macro F1：{result['risk']['macro_f1']:.3f}；"
                f"有效标注 {result['risk']['sample_count']} 条。"
            )
            st.dataframe(
                result["risk"]["per_class"].round(4),
                use_container_width=True,
                hide_index=True,
            )

        errors = result["sentiment_errors"]
        st.markdown("**情绪误判样本**")
        if errors.empty:
            st.info("当前没有 FinBERT 情绪误判样本，或尚无有效情绪标注。")
        else:
            filter_col1, filter_col2 = st.columns(2)
            true_filter = filter_col1.multiselect(
                "真实标签",
                SENTIMENT_LABELS,
                default=SENTIMENT_LABELS,
            )
            predicted_filter = filter_col2.multiselect(
                "预测标签",
                SENTIMENT_LABELS,
                default=SENTIMENT_LABELS,
            )
            filtered_errors = errors[
                errors["true_sentiment"].isin(true_filter)
                & errors["predicted_sentiment"].isin(predicted_filter)
            ]
            st.dataframe(
                filtered_errors.round(4),
                use_container_width=True,
                hide_index=True,
            )
            st.download_button(
                "下载筛选后的误判 CSV",
                data=filtered_errors.to_csv(index=False).encode(CSV_EXPORT_ENCODING),
                file_name="sentiment_errors_filtered.csv",
                mime="text/csv",
            )
            st.caption(f"完整错误清单已写入 {ANNOTATION_ERRORS_PATH}")

st.divider()
with st.expander("现有数据诊断与六维公式描述性对照（非稳健性验证）"):
    st.markdown("**覆盖统计**")
    st.dataframe(coverage_summary_table(df), use_container_width=True, hide_index=True)

    st.markdown("**输出分布**")
    st.dataframe(output_distribution(df).round(4), use_container_width=True, hide_index=True)

    baseline_sector, enhanced_sector = formula_sector_outputs(df, source_mode)
    st.markdown("**Baseline vs Enhanced 六维板块分布**")
    st.dataframe(
        formula_metric_comparison(baseline_sector, enhanced_sector).round(2),
        use_container_width=True,
        hide_index=True,
    )
    st.markdown("**排名变化最大的板块**")
    st.dataframe(
        formula_rank_changes(df, baseline_sector, enhanced_sector, source_mode).round(2),
        use_container_width=True,
        hide_index=True,
    )
    st.markdown("**具体新闻两套分数对照**")
    st.dataframe(
        formula_article_examples(df, limit=3).round(2),
        use_container_width=True,
        hide_index=True,
    )
