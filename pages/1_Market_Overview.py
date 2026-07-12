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
from src.ui_helpers import load_selected_articles, render_sector_heatmap


def render_radar(scores: dict[str, float], title: str) -> None:
    labels = [METRIC_LABELS[column] for column in METRIC_COLUMNS]
    values = [float(scores.get(column, 0)) for column in METRIC_COLUMNS]
    fig = go.Figure(
        data=[
            go.Scatterpolar(
                r=values + values[:1],
                theta=labels + labels[:1],
                fill="toself",
                name="市场级指标",
            )
        ]
    )
    fig.update_layout(
        title=title,
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=False,
        height=430,
    )
    st.plotly_chart(fig, use_container_width=True)


def fmt_time(value: object) -> str:
    if value is None or pd.isna(value):
        return "暂无"
    return pd.Timestamp(value).strftime("%Y-%m-%d %H:%M UTC")


def fmt_time_short(value: object) -> str:
    if value is None or pd.isna(value):
        return "暂无"
    return pd.Timestamp(value).strftime("%m-%d %H:%M")


def fmt_iso_short(value: object) -> str:
    try:
        return pd.Timestamp(str(value)).strftime("%m-%d %H:%M")
    except (ValueError, TypeError):
        return str(value or "")


def markdown_article_link(title: object, url: object) -> str:
    label = str(title or "无标题").replace("[", "\\[").replace("]", "\\]")
    href = str(url or "").strip()
    return f"[{label}]({href})" if href.startswith(("http://", "https://")) else label


def render_driver_events(drivers: pd.DataFrame) -> None:
    if drivers.empty:
        st.info("当前窗口暂无可展示的驱动事件。")
        return

    for rank, row in enumerate(drivers.to_dict("records"), start=1):
        st.markdown(f"**{rank}. {markdown_article_link(row.get('title'), row.get('url'))}**")
        source_count = int(float(row.get("source_count", 0) or 0))
        article_count = int(float(row.get("event_article_count", 1) or 1))
        boost_label = " · 已应用媒体覆盖加成" if bool(row.get("coverage_boost_applied")) else ""
        macro_label = " · 宏观保底" if bool(row.get("macro_guaranteed")) else ""
        st.caption(
            f"{row.get('sector', 'Unmapped')} · {row.get('topic', '')} · "
            f"事件分数 {float(row.get('driver_score', 0) or 0):.1f} · {source_count} 家媒体"
            f"{boost_label}{macro_label}"
        )
        st.write(str(row.get("driver_reason", "")))

        if article_count > 1:
            other_media_count = max(0, source_count - 1)
            media_label = (
                f"另有 {other_media_count} 家媒体报道"
                if other_media_count
                else f"另有 {article_count - 1} 篇同源报道"
            )
            with st.expander(f"{media_label} · 查看簇内全部 {article_count} 篇"):
                for article in row.get("event_articles", []):
                    st.markdown(
                        f"- {markdown_article_link(article.get('title'), article.get('url'))}  "
                        f"  {article.get('publisher', '') or article.get('source', '')} · "
                        f"{fmt_time(article.get('published_at'))}"
                    )
        st.divider()


df, source_mode = load_selected_articles()
market_scores = market_metrics(df, data_source=source_mode)
sector_df = sector_metrics(df, data_source=source_mode)
latest_brief = read_latest_brief()
brief_meta = latest_brief.get("metadata", {}) if isinstance(latest_brief.get("metadata"), dict) else {}
brief_content = str(latest_brief.get("content", "") or "")

data_updated_at = df["collected_at"].max() if "collected_at" in df else pd.NaT
brief_generated_at = brief_meta.get("generated_at_local") or brief_meta.get("generated_at") or ""
summary_source = brief_meta.get("summary_source", "规则模板")
brief_model_id = brief_meta.get("model_id", "")
if summary_source == "AI 生成":
    model_label = f" · 模型 {brief_model_id}" if brief_model_id else ""
    brief_source_label = f"AI 生成{model_label} · 简报时间 {brief_generated_at}"
else:
    brief_source_label = f"规则模板 · 简报时间 {brief_generated_at or '尚未生成'}"

st.title("市场总览")
st.caption("抓取可多次/天，LLM 简报默认一次/天；页面只读取已生成的 latest_brief.md。")
st.caption(f"当前数据源：{source_mode}")
st.warning(DISCLAIMER)

metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
metric_col1.metric("窗口内新闻数", f"{len(df):,}")
metric_col2.metric(
    "覆盖出版方数",
    f"{distinct_value_count(df['publisher'] if 'publisher' in df else df.get('source', []), df.get('source', [])):,}",
)
metric_col3.metric("数据窗口", f"近 {WORKING_SET_DAYS} 天")
metric_col4.metric(
    "数据更新时间",
    fmt_time_short(data_updated_at),
    help=f"完整时间：{fmt_time(data_updated_at)}，随每次抓取刷新。",
)

left_col, right_col = st.columns([1.05, 0.95])
with left_col:
    render_radar(market_scores, "Overall Market Sentiment Radar")
    st.subheader("市场级六维分数")
    score_rows = [
        {"指标": METRIC_LABELS[column], "分数": round(float(market_scores[column]), 1)}
        for column in METRIC_COLUMNS
    ]
    st.dataframe(score_rows, use_container_width=True, hide_index=True)

with right_col:
    st.subheader("每日市场简报")
    st.caption(brief_source_label)
    if brief_content:
        snapshot_id = str(brief_meta.get("data_snapshot_id", ""))
        brief_article_count = snapshot_id.split("|")[-1] if snapshot_id.count("|") >= 2 else ""
        window_label = (
            f"{fmt_iso_short(brief_meta.get('data_window_start'))} – "
            f"{fmt_iso_short(brief_meta.get('data_window_end'))} UTC"
        )
        count_label = f"{brief_article_count} 条新闻" if brief_article_count else "生成时窗口内新闻"
        st.info(
            f"本简报基于 {count_label}（窗口 {window_label}），"
            f"生成于 {fmt_iso_short(brief_generated_at)}；"
            f"页面其余指标为当前实时窗口（{len(df):,} 条），数字可能与简报不同。"
        )
    with st.container(height=600, border=True):
        if brief_content:
            st.markdown(brief_content)
        else:
            st.info("暂无 latest_brief.md。抓取管线会在每日生成时刻后自动生成；也可以在侧边栏手动确认重新生成。")

st.subheader("Sector Heatmap")
render_sector_heatmap(sector_df)

driver_title = st.empty()
driver_window_mode = st.radio(
    "驱动事件窗口",
    options=["近 48 小时", "近 30 天"],
    horizontal=True,
    key="market_driver_window",
)
requested_driver_window = (
    DRIVER_WINDOW_HOURS if driver_window_mode == "近 48 小时" else WORKING_SET_DAYS * 24
)
drivers = top_driver_articles(
    df,
    limit=5,
    window_hours=requested_driver_window,
    min_events=DRIVER_MIN_EVENTS,
)
if driver_window_mode == "近 48 小时":
    actual_driver_window = int(drivers.attrs.get("driver_window_hours", DRIVER_WINDOW_HOURS))
    driver_window_label = f"近 {actual_driver_window} 小时"
else:
    driver_window_label = f"近 {WORKING_SET_DAYS} 天"
driver_title.subheader(f"Top Market Drivers（{driver_window_label}）")
render_driver_events(drivers)
