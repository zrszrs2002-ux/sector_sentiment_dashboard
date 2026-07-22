import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.config import (
    ANNOTATION_BLIND_PATH,
    ANNOTATION_ERRORS_PATH,
    ANNOTATION_GUIDE_PATH,
    ANNOTATION_KEY_PATH,
    ANNOTATION_META_PATH,
    ANNOTATION_SAMPLE_SEED,
    ANNOTATION_SAMPLE_SIZE,
    CSV_EXPORT_ENCODING,
    RAW_ARTICLES_PATH,
    REAL_PROCESSED_ARTICLES_PATH,
    SENSITIVITY_ANALYSIS_PATH,
)
from src.annotation_sampling import (
    annotation_metadata_matches_blind,
    completed_annotation_cells,
    excel_hyperlink_formula,
    generate_annotation_samples,
    read_annotation_metadata,
)
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
from src.sensitivity_analysis import (
    load_sensitivity_results,
    most_sensitive_components,
    run_sensitivity_analysis,
)
from src.ui_helpers import load_selected_articles


def read_csv_file(source, *, dtype=None) -> pd.DataFrame:
    return pd.read_csv(source, encoding="utf-8-sig", dtype=dtype)


def csv_download_bytes(frame: pd.DataFrame) -> bytes:
    export = frame.copy()
    if "url" in export.columns:
        export["url"] = export["url"].map(excel_hyperlink_formula)
    return export.to_csv(index=False).encode(CSV_EXPORT_ENCODING)

def render_confusion_matrix(matrix: pd.DataFrame) -> None:
    figure = px.imshow(
        matrix,
        text_auto="d",
        color_continuous_scale="Blues",
        labels={"x": "Predicted label", "y": "True label", "color": "Sample count"},
        aspect="auto",
    )
    figure.update_layout(height=360, margin=dict(t=10))
    st.plotly_chart(figure, use_container_width=True)


def render_reliability_curve(reliability: pd.DataFrame) -> None:
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=[0, 1],
            y=[0, 1],
            mode="lines",
            name="Perfect calibration",
            line={"dash": "dash", "color": "#777"},
        )
    )
    figure.add_trace(
        go.Scatter(
            x=reliability["mean_confidence"],
            y=reliability["accuracy"],
            mode="lines+markers",
            name="FinBERT",
            text=[f"Sample count {count}" for count in reliability["count"]],
            hovertemplate="Mean confidence %{x:.3f}<br>Accuracy %{y:.3f}<br>%{text}<extra></extra>",
        )
    )
    figure.update_layout(
        title="FinBERT Reliability Curve",
        xaxis_title="Bin mean confidence",
        yaxis_title="Bin accuracy",
        xaxis={"range": [0, 1]},
        yaxis={"range": [0, 1]},
        height=390,
    )
    st.plotly_chart(figure, use_container_width=True)


df, source_mode = load_selected_articles()

st.title("Evaluation")
st.info(
    "This page evaluates the article classification layer: sentiment, sector mapping, risk "
    "labels, evidence sentences, and FinBERT calibration. Robustness checks for the "
    "six-dimension metric layer (sensitivity analysis and ablations) are implemented separately."
)
st.caption(f"Current data source: {source_mode}")
st.caption("The classification evaluation above always reads the annotation files; the current data source only affects the data diagnostics section at the bottom of the page.")

st.subheader("Human Annotation Evaluation")
st.markdown("### Step 1: Get a Blind Annotation Sample")
st.caption(
    "Stratified sampling by sector × FinBERT sentiment only runs when you click the button; "
    "page loads or interaction reruns never resample automatically."
)


sample_col1, sample_col2, sample_col3 = st.columns([0.9, 0.9, 1.4])
sample_size = sample_col1.number_input(
    "Sample size",
    min_value=1,
    max_value=5000,
    value=ANNOTATION_SAMPLE_SIZE,
    step=50,
)
sample_seed = sample_col2.number_input(
    "Random seed",
    min_value=0,
    max_value=999999999,
    value=ANNOTATION_SAMPLE_SEED,
    step=1,
)
sample_col3.caption(
    "The same article pool with the same size and seed will exactly reproduce the same "
    "sample; the actual size, seed, and timestamp are written to annotation_meta.json "
    "after generation."
)

existing_blind = pd.DataFrame()
completed_cells = 0
sample_metadata = read_annotation_metadata(ANNOTATION_META_PATH)
if ANNOTATION_BLIND_PATH.exists():
    try:
        existing_blind = read_csv_file(ANNOTATION_BLIND_PATH)
        completed_cells = completed_annotation_cells(existing_blind)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        st.warning(f"Failed to read the existing blind annotation file, so resampling is unavailable for now: {exc}")

replacement_confirmed = True
if completed_cells:
    st.warning(
        f"annotation_blind.csv currently has {completed_cells} filled-in labels. "
        "Regenerating will replace this file and the private reconciliation key; the "
        "existing safe-write mechanism keeps a backup first."
    )
    replacement_confirmed = st.checkbox(
        f"I confirm I want to discard the {completed_cells} filled-in labels and resample",
        key="confirm_annotation_resample",
    )
else:
    st.caption("No labels have been filled in yet, so you can generate or refresh a blank blind sample directly.")

if st.button(
    f"Generate {int(sample_size)} blind samples",
    type="primary",
    disabled=not replacement_confirmed,
):
    try:
        generated_blind, _ = generate_annotation_samples(
            RAW_ARTICLES_PATH,
            REAL_PROCESSED_ARTICLES_PATH,
            ANNOTATION_BLIND_PATH.parent,
            sample_size=int(sample_size),
            seed=int(sample_seed),
        )
    except (FileNotFoundError, OSError, UnicodeDecodeError, ValueError, pd.errors.ParserError) as exc:
        st.error(f"Failed to generate blind samples: {exc}")
    else:
        st.session_state["generated_annotation_blind"] = generated_blind
        existing_blind = generated_blind
        completed_cells = 0
        sample_metadata = read_annotation_metadata(ANNOTATION_META_PATH)
        st.success(
            f"Generated {len(generated_blind)} blind samples and wrote them to annotation_key.csv and annotation_meta.json."
        )

session_blind = st.session_state.get("generated_annotation_blind")
download_blind = session_blind if isinstance(session_blind, pd.DataFrame) else existing_blind

download_col, guide_col = st.columns(2)
with download_col:
    if not download_blind.empty:
        st.download_button(
            "Download CSV to annotate",
            data=csv_download_bytes(download_blind),
            file_name="annotation_blind.csv",
            mime="text/csv",
            use_container_width=True,
        )
        if annotation_metadata_matches_blind(sample_metadata, download_blind):
            st.caption(
                "Current persisted sample: "
                f"{sample_metadata['sample_size']} items · "
                f"seed: {sample_metadata['seed']} · "
                f"generated at: {sample_metadata['generated_at']}"
            )
        else:
            st.warning(
                "The current blind annotation file is missing or failed reconciliation against "
                "annotation_meta.json; please regenerate the sample once you confirm you don't "
                "need to keep the existing labels."
            )
    else:
        st.info("No blind samples yet; click the button above to generate them first.")
with guide_col:
    if ANNOTATION_GUIDE_PATH.exists():
        st.download_button(
            "Download annotation guide",
            data=ANNOTATION_GUIDE_PATH.read_bytes(),
            file_name="annotation_guide.md",
            mime="text/markdown",
            use_container_width=True,
        )
    else:
        st.warning("docs/annotation_guide.md was not found.")
st.caption("annotation_key.csv is for backend reconciliation only, in keeping with the blind-annotation principle; the page does not offer a download for it.")
st.markdown("### Step 2: Label Offline")
st.markdown(
    "- `label_sentiment`: only `positive`, `neutral`, or `negative`.\n"
    "- `label_sector_ok`: `1` (correctly mapped) or `0` (incorrectly mapped); leave blank if unsure.\n"
    "- `label_risk_categories`: one or more English risk labels separated by `;`; use `none` if there is no clear risk.\n"
    "- `label_evidence_ok`: `1` or `0`; put borderline judgment calls and reasoning in `notes`."
)

st.markdown("### Step 3: Upload and Results")

uploaded_file = st.file_uploader(
    "Upload a filled-in annotation_blind.csv (leave empty to read data/annotation/annotation_blind.csv)",
    type=["csv"],
)
annotations = pd.DataFrame()
annotation_key = pd.DataFrame()
if uploaded_file is not None:
    try:
        annotations = read_csv_file(uploaded_file, dtype=str)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        st.error(f"Failed to read the annotation CSV: {exc}")
elif ANNOTATION_BLIND_PATH.exists():
    try:
        annotations = read_csv_file(ANNOTATION_BLIND_PATH, dtype=str)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        st.error(f"Failed to read the default blind annotation file: {exc}")

if ANNOTATION_KEY_PATH.exists():
    try:
        annotation_key = read_csv_file(ANNOTATION_KEY_PATH)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        st.error(f"Failed to read annotation_key: {exc}")

if annotations.empty or annotation_key.empty:
    st.info("No blind annotation file or reconciliation key to evaluate yet; generate a blind sample above first.")
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
        f"Loaded {len(annotations)} blind samples; {completed_cells} cells filled in across the four label types."
    )
    try:
        result = evaluate_model_annotations(
            annotations,
            annotation_key,
            error_output_path=ANNOTATION_ERRORS_PATH,
        )
    except ValueError as exc:
        st.error(f"Annotation data validation failed: {exc}")
    else:
        if result["sentiment_labelled_count"] == 0:
            st.info("No valid sentiment labels have been filled in yet; once filled in, this will show the three-way comparison, confusion matrix, and calibration results.")
        else:
            metric_a, metric_b, metric_c, metric_d = st.columns(4)
            finbert_report = result["sentiment_reports"]["FinBERT"]
            metric_a.metric("Sentiment labels", result["sentiment_labelled_count"])
            metric_b.metric("FinBERT Accuracy", f"{finbert_report['accuracy']:.3f}")
            metric_c.metric("FinBERT Macro F1", f"{finbert_report['macro_f1']:.3f}")
            metric_d.metric("Brier Score", f"{result['calibration']['brier_score']:.3f}")

            st.markdown("**All-neutral baseline / Lexicon engine / FinBERT**")
            st.dataframe(
                result["sentiment_comparison"].round(4),
                use_container_width=True,
                hide_index=True,
            )

            engine = st.selectbox(
                "Engine for confusion matrix and classification metrics",
                options=list(result["sentiment_reports"]),
                index=2,
            )
            selected_report = result["sentiment_reports"][engine]
            left, right = st.columns([0.9, 1.1])
            with left:
                st.markdown("**Per-Class Metrics**")
                st.dataframe(
                    selected_report["per_class"].round(4),
                    use_container_width=True,
                    hide_index=True,
                )
            with right:
                st.markdown(f"**{engine} 3\u00d73 Confusion Matrix**")
                render_confusion_matrix(selected_report["confusion_matrix"])

            reliability = result["calibration"]["reliability"]
            if not reliability.empty:
                render_reliability_curve(reliability)
                st.dataframe(
                    reliability.round(4),
                    use_container_width=True,
                    hide_index=True,
                )

        st.markdown("**Sector, Risk, and Evidence Sentence**")
        sector_metric, evidence_metric = st.columns(2)
        sector_value = (
            f"{result['sector_mapping']['accuracy']:.3f}"
            if result["sector_mapping"]["sample_count"]
            else "N/A"
        )
        evidence_value = (
            f"{result['evidence']['precision']:.3f}"
            if result["evidence"]["sample_count"]
            else "N/A"
        )
        sector_metric.metric(
            "Sector Mapping Accuracy",
            sector_value,
            help=f"{result['sector_mapping']['sample_count']} valid labels",
        )
        evidence_metric.metric(
            "Evidence Sentence Top-1 Match Rate",
            evidence_value,
            help=(
                "For this batch, label_evidence_ok was auto-generated by matching the "
                "evidence sentence the annotator picked independently against the model's "
                "evidence sentence (mutually contains each other after normalization, or "
                "similarity ≥ 0.85); this metric measures the rate at which both sides pick "
                "the exact same sentence, a stricter conservative lower bound than the "
                "annotation guide's “acceptable rate.” "
                f"{result['evidence']['sample_count']} valid labels."
            ),
        )
        if not result["risk"]["per_class"].empty:
            st.caption(
                f"Risk multi-label Macro F1: {result['risk']['macro_f1']:.3f}; "
                "blank risk fields in this batch are treated as missing (not equal to none); "
                f"{result['risk']['sample_count']} valid samples."
            )
            st.dataframe(
                result["risk"]["per_class"].round(4),
                use_container_width=True,
                hide_index=True,
            )

        errors = result["sentiment_errors"]
        st.markdown("**Sentiment Misclassification Samples**")
        if errors.empty:
            st.info("No FinBERT sentiment misclassification samples, or no valid sentiment labels yet.")
        else:
            filter_col1, filter_col2 = st.columns(2)
            true_filter = filter_col1.multiselect(
                "True label",
                SENTIMENT_LABELS,
                default=SENTIMENT_LABELS,
            )
            predicted_filter = filter_col2.multiselect(
                "Predicted label",
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
                "Download filtered misclassification CSV",
                data=filtered_errors.to_csv(index=False).encode(CSV_EXPORT_ENCODING),
                file_name="sentiment_errors_filtered.csv",
                mime="text/csv",
            )
            st.caption(f"The full error list was written to {ANNOTATION_ERRORS_PATH}")

st.divider()
with st.expander("Current Data Diagnostics and Six-Dimension Formula Descriptive Comparison (not a robustness check)"):
    st.markdown("**Coverage Statistics**")
    st.dataframe(coverage_summary_table(df), use_container_width=True, hide_index=True)

    st.markdown("**Output Distribution**")
    st.dataframe(output_distribution(df).round(4), use_container_width=True, hide_index=True)

    baseline_sector, enhanced_sector = formula_sector_outputs(df, source_mode)
    st.markdown("**Baseline vs Enhanced Six-Dimension Sector Distribution**")
    st.dataframe(
        formula_metric_comparison(baseline_sector, enhanced_sector).round(2),
        use_container_width=True,
        hide_index=True,
    )
    st.markdown("**Sectors with the Largest Ranking Changes**")
    st.dataframe(
        formula_rank_changes(df, baseline_sector, enhanced_sector, source_mode).round(2),
        use_container_width=True,
        hide_index=True,
    )
    st.markdown("**Side-by-Side Scores for Individual Articles**")
    st.dataframe(
        formula_article_examples(df, limit=3).round(2),
        use_container_width=True,
        hide_index=True,
    )

st.divider()
st.subheader("Weight Sensitivity Analysis")
st.caption(
    "Always reads all real news from data/real_processed_articles.csv, reusing the "
    "persisted sentiment probabilities, formula components, and the production "
    "sector_metrics aggregation path; it never uses Demo data or reruns FinBERT."
)

try:
    sensitivity_results = load_sensitivity_results()
except ValueError as exc:
    sensitivity_results = pd.DataFrame()
    st.warning(str(exc))

if st.button("Run weight sensitivity analysis", key="run_weight_sensitivity"):
    with st.spinner("Running OAT perturbations on the Enhanced weights, dimension by dimension, component by component..."):
        try:
            sensitivity_results = run_sensitivity_analysis()
        except (OSError, ValueError) as exc:
            st.error(f"Weight sensitivity analysis failed: {exc}")
        else:
            st.success(
                f"Weight sensitivity analysis complete; results written to {SENSITIVITY_ANALYSIS_PATH}"
            )

if sensitivity_results.empty:
    st.info("No persisted sensitivity analysis results yet; click the button above to start the computation.")
else:
    generated_at = str(sensitivity_results["generated_at"].iloc[0])
    formula_version = str(sensitivity_results["formula_version"].iloc[0])
    data_source = str(sensitivity_results["data_source"].iloc[0])
    st.caption(
        f"Generated at: {generated_at} · Formula version: {formula_version} · "
        f"Data source: {data_source}"
    )
    result_columns = [
        "target_dimension",
        "target_component",
        "perturbation_factor",
        "original_weight",
        "perturbed_weight",
        "mean_daily_spearman",
        "mean_absolute_score_change",
        "mean_daily_top3_jaccard",
        "day_count",
        "sector_day_count",
    ]
    st.dataframe(
        sensitivity_results[result_columns].rename(
            columns={
                "target_dimension": "Dimension",
                "target_component": "Perturbed component",
                "perturbation_factor": "Perturbation factor",
                "original_weight": "Default weight",
                "perturbed_weight": "Renormalized target weight",
                "mean_daily_spearman": "Mean daily Spearman",
                "mean_absolute_score_change": "Mean absolute score change",
                "mean_daily_top3_jaccard": "Mean daily Top-3 Jaccard",
                "day_count": "Day count",
                "sector_day_count": "Sector-day count",
            }
        ).round(4),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("**Most Sensitive Component per Dimension**")
    st.dataframe(
        most_sensitive_components(sensitivity_results).rename(
            columns={
                "dimension": "Dimension",
                "most_sensitive_component": "Most sensitive component",
                "worst_factor": "Factor with the largest change",
                "minimum_daily_spearman": "Minimum mean daily Spearman",
                "maximum_score_change": "Maximum mean absolute score change",
                "minimum_top3_jaccard": "Minimum mean daily Top-3 Jaccard",
            }
        ).round(4),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "Reading guide: ranking correlation stays high under ±20%-50% perturbations, "
        "indicating the conclusions are robust to the exact values of the expert-prior "
        "weights; factor 0 is an extra ablation and is excluded from this range's reading."
    )
