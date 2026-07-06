import streamlit as st

from src.data_loader import DEMO_DATA_LABEL, REAL_DATA_LABEL, load_articles


def load_selected_articles():
    """按侧边栏数据源选择加载文章，并处理真实新闻为空的情况。"""
    source_mode = st.session_state.get("data_source_mode", DEMO_DATA_LABEL)
    df = load_articles(source_mode=source_mode)
    if df.empty and source_mode == REAL_DATA_LABEL:
        st.warning("真实新闻数据为空。请先在左侧点击“抓取最新新闻”，或切换到 Demo 数据。")
        st.stop()
    return df, source_mode


def url_column_config(label: str = "链接") -> dict:
    return {"url": st.column_config.LinkColumn(label, display_text="打开")}
