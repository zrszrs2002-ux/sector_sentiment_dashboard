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
st.markdown("### 步骤 1：获取盲标样本")
st.caption(
    "点击按钮后才会按 sector × FinBERT 情绪分层抽样；"
    "页面加载或交互重跑不会自动重抽。"
)


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
    value=ANNOTATION_SAMPLE_SEED,
    step=1,
)
sample_col3.caption(
    "同一新闻池使用相同条数和种子会精确复现同一批样本；"
    "生成后会将实际条数、种子和时间写入 annotation_meta.json。"
)

existing_blind = pd.DataFrame()
completed_cells = 0
sample_metadata = read_annotation_metadata(ANNOTATION_META_PATH)
if ANNOTATION_BLIND_PATH.exists():
    try:
        existing_blind = read_csv_file(ANNOTATION_BLIND_PATH)
        completed_cells = completed_annotation_cells(existing_blind)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        st.warning(f"现有盲标文件读取失败，暂不提供重抽样：{exc}")

replacement_confirmed = True
if completed_cells:
    st.warning(
        f"当前 annotation_blind.csv 已有 {completed_cells} 个已填写标注。"
        "重新生成会替换该文件和私有对账 key；现有安全写入机制会先保留备份。"
    )
    replacement_confirmed = st.checkbox(
        f"我确认放弃已填写的 {completed_cells} 个标注并重新抽样",
        key="confirm_annotation_resample",
    )
else:
    st.caption("当前没有已填写标签，可直接生成或刷新空白盲标样本。")

if st.button(
    f"生成 {int(sample_size)} 条盲标样本",
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
        st.error(f"盲标样本生成失败：{exc}")
    else:
        st.session_state["generated_annotation_blind"] = generated_blind
        existing_blind = generated_blind
        completed_cells = 0
        sample_metadata = read_annotation_metadata(ANNOTATION_META_PATH)
        st.success(
            f"已生成 {len(generated_blind)} 条盲标样本并同步写入 annotation_key.csv 与 annotation_meta.json。"
        )

session_blind = st.session_state.get("generated_annotation_blind")
download_blind = session_blind if isinstance(session_blind, pd.DataFrame) else existing_blind

download_col, guide_col = st.columns(2)
with download_col:
    if not download_blind.empty:
        st.download_button(
            "下载待标注 CSV",
            data=csv_download_bytes(download_blind),
            file_name="annotation_blind.csv",
            mime="text/csv",
            use_container_width=True,
        )
        if annotation_metadata_matches_blind(sample_metadata, download_blind):
            st.caption(
                "当前持久化样本："
                f"{sample_metadata['sample_size']} 条 · "
                f"当前样本种子：{sample_metadata['seed']} · "
                f"生成时间：{sample_metadata['generated_at']}"
            )
        else:
            st.warning(
                "当前盲标文件缺少或未通过 annotation_meta.json 对账；"
                "请在确认无须保留现有标注后重新生成样本。"
            )
    else:
        st.info("尚无盲标样本，请先点击上方按钮生成。")
with guide_col:
    if ANNOTATION_GUIDE_PATH.exists():
        st.download_button(
            "下载标注手册",
            data=ANNOTATION_GUIDE_PATH.read_bytes(),
            file_name="annotation_guide.md",
            mime="text/markdown",
            use_container_width=True,
        )
    else:
        st.warning("未找到 docs/annotation_guide.md。")
st.caption("annotation_key.csv 仅供后台对账，基于盲标原则，页面不提供下载入口。")
st.markdown("### 步骤 2：离线填写")
st.markdown(
    "- `label_sentiment` 仅填 `positive`、`neutral` 或 `negative`。\n"
    "- `label_sector_ok` 填 `1`（归属正确）或 `0`（归属错误）；不确定可留空。\n"
    "- `label_risk_categories` 可填多个英文风险标签并用 `;` 分隔；无明确风险填 `none`。\n"
    "- `label_evidence_ok` 填 `1` 或 `0`；边界判断和理由写入 `notes`。"
)

st.markdown("### 步骤 3：上传与结果")

uploaded_file = st.file_uploader(
    "上传已填写的 annotation_blind.csv（留空则读取 data/annotation/annotation_blind.csv）",
    type=["csv"],
)
annotations = pd.DataFrame()
annotation_key = pd.DataFrame()
if uploaded_file is not None:
    try:
        annotations = read_csv_file(uploaded_file, dtype=str)
    except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
        st.error(f"标注 CSV 读取失败：{exc}")
elif ANNOTATION_BLIND_PATH.exists():
    try:
        annotations = read_csv_file(ANNOTATION_BLIND_PATH, dtype=str)
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
            "证据句 Top-1 一致率",
            evidence_value,
            help=(
                "本批 label_evidence_ok 由标注者独立选取的证据句与模型证据句"
                "自动匹配生成（规范化后互相包含，或相似度 ≥ 0.85）；"
                "该指标衡量双方选中同一句的比率，是比标注手册“可接受率”"
                "更严格的保守下界。"
                f"有效标注 {result['evidence']['sample_count']} 条。"
            ),
        )
        if not result["risk"]["per_class"].empty:
            st.caption(
                f"风险多标签 Macro F1：{result['risk']['macro_f1']:.3f}；"
                "本批标注中风险列空白按缺失处理（不等于 none）；"
                f"有效样本 {result['risk']['sample_count']} 条。"
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

st.divider()
st.subheader("权重敏感性分析")
st.caption(
    "固定读取 data/real_processed_articles.csv 的全部真实新闻，"
    "复用已持久化情绪概率、公式组件与正式 sector_metrics 聚合路径；"
    "不会使用 Demo 数据，也不会重新运行 FinBERT。"
)

try:
    sensitivity_results = load_sensitivity_results()
except ValueError as exc:
    sensitivity_results = pd.DataFrame()
    st.warning(str(exc))

if st.button("运行权重敏感性分析", key="run_weight_sensitivity"):
    with st.spinner("正在对 Enhanced 权重逐维、逐分量执行 OAT 扰动..."):
        try:
            sensitivity_results = run_sensitivity_analysis()
        except (OSError, ValueError) as exc:
            st.error(f"权重敏感性分析失败：{exc}")
        else:
            st.success(
                f"权重敏感性分析完成，结果已写入 {SENSITIVITY_ANALYSIS_PATH}"
            )

if sensitivity_results.empty:
    st.info("尚无持久化敏感性分析结果；点击上方按钮后才会开始计算。")
else:
    generated_at = str(sensitivity_results["generated_at"].iloc[0])
    formula_version = str(sensitivity_results["formula_version"].iloc[0])
    data_source = str(sensitivity_results["data_source"].iloc[0])
    st.caption(
        f"生成时间：{generated_at} · 公式版本：{formula_version} · "
        f"数据源：{data_source}"
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
                "target_dimension": "维度",
                "target_component": "扰动分量",
                "perturbation_factor": "扰动因子",
                "original_weight": "默认权重",
                "perturbed_weight": "重归一化后目标权重",
                "mean_daily_spearman": "日均 Spearman",
                "mean_absolute_score_change": "分数平均绝对变化",
                "mean_daily_top3_jaccard": "日均 Top-3 Jaccard",
                "day_count": "日期数",
                "sector_day_count": "sector-day 数",
            }
        ).round(4),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("**每维度最敏感分量**")
    st.dataframe(
        most_sensitive_components(sensitivity_results).rename(
            columns={
                "dimension": "维度",
                "most_sensitive_component": "最敏感分量",
                "worst_factor": "最大变化对应因子",
                "minimum_daily_spearman": "最低日均 Spearman",
                "maximum_score_change": "最大分数平均绝对变化",
                "minimum_top3_jaccard": "最低日均 Top-3 Jaccard",
            }
        ).round(4),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "解读口径：扰动 ±20%~50% 下排名相关性保持高位，"
        "说明结论对专家先验权重的具体取值稳健；"
        "因子 0 为额外消融，不计入该区间解读。"
    )
