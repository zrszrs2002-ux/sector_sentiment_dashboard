from pathlib import Path

import streamlit as st

from src.config import DISCLAIMER


BASE_DIR = Path(__file__).resolve().parent

st.set_page_config(
    page_title="自动化板块级金融舆情雷达系统",
    layout="wide",
)

st.sidebar.title("板块级金融舆情雷达")
st.sidebar.caption("第一冲刺 MVP 框架")
st.sidebar.info(DISCLAIMER)

pages = {
    "核心仪表盘": [
        st.Page(
            BASE_DIR / "pages" / "1_Market_Overview.py",
            title="市场总览",
            icon=":material/dashboard:",
            default=True,
        ),
        st.Page(
            BASE_DIR / "pages" / "2_Sector_Comparison.py",
            title="板块比较",
            icon=":material/analytics:",
        ),
        st.Page(
            BASE_DIR / "pages" / "3_Sector_Detail.py",
            title="板块详情",
            icon=":material/troubleshoot:",
        ),
        st.Page(
            BASE_DIR / "pages" / "4_Article_Explorer.py",
            title="文章浏览器",
            icon=":material/article:",
        ),
    ],
}

selected_page = st.navigation(pages, expanded=True)
selected_page.run()
