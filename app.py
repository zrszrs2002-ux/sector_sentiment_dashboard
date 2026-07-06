from pathlib import Path

import streamlit as st

from src.config import DISCLAIMER
from src.data_loader import DEMO_DATA_LABEL, REAL_DATA_LABEL
from src.news_collector import collect_rss_news


BASE_DIR = Path(__file__).resolve().parent

st.set_page_config(
    page_title="自动化板块级金融舆情雷达系统",
    layout="wide",
)

st.sidebar.title("板块级金融舆情雷达")
st.sidebar.caption("第一冲刺 MVP 框架")
st.sidebar.info(DISCLAIMER)

st.sidebar.radio(
    "数据源",
    [DEMO_DATA_LABEL, REAL_DATA_LABEL],
    key="data_source_mode",
    help="Demo 数据可离线运行；真实新闻来自 RSS，需要先抓取。",
)

if st.sidebar.button("抓取最新新闻", type="primary"):
    with st.spinner("正在抓取 RSS 新闻并刷新真实新闻数据..."):
        try:
            result = collect_rss_news()
        except Exception as exc:  # noqa: BLE001 - UI 层需要给中文错误提示
            st.sidebar.error(f"RSS 抓取失败：{exc}")
        else:
            if result["all_failed"] and result["processed_count"] == 0:
                st.sidebar.warning(result["message"])
            else:
                st.sidebar.success(
                    "抓取完成："
                    f"新增 {result['new_record_count']} 条，"
                    f"真实新闻累计 {result['processed_count']} 条。"
                )
            if result["failures"]:
                with st.sidebar.expander("部分 RSS 源失败"):
                    for failure in result["failures"][:8]:
                        st.write(f"{failure['source']}: {failure['error']}")

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
