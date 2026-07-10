import hmac
import os
from pathlib import Path

import streamlit as st


st.set_page_config(
    page_title="自动化板块级金融舆情雷达系统",
    layout="wide",
)


def bridge_streamlit_secrets() -> None:
    try:
        for key, value in st.secrets.items():
            os.environ.setdefault(str(key), str(value))
    except FileNotFoundError:
        return
    except Exception as exc:  # Streamlit uses its own missing-secrets exception.
        if exc.__class__.__name__ == "StreamlitSecretNotFoundError":
            return
        raise


bridge_streamlit_secrets()

from src.config import DEMO_PIN, DISCLAIMER, FINBERT_LOCAL_FILES_ONLY
from src.data_loader import DEMO_DATA_LABEL, REAL_DATA_LABEL, has_real_articles
from src.brief_generator import generate_daily_brief
from src.news_collector import collect_rss_news
from src.sentiment_model import load_finbert_resources, sentiment_backend_status


BASE_DIR = Path(__file__).resolve().parent

st.sidebar.title("板块级金融舆情雷达")
st.sidebar.caption("公开财经新闻舆情监测工具")
st.sidebar.info(DISCLAIMER)
if not FINBERT_LOCAL_FILES_ONLY and load_finbert_resources.cache_info().currsize == 0:
    with st.spinner("首次启动正在下载 FinBERT 模型（约 440MB），请稍候…"):
        sentiment_status = sentiment_backend_status()
else:
    sentiment_status = sentiment_backend_status()
st.sidebar.caption(sentiment_status)

real_available = has_real_articles()
source_options = [REAL_DATA_LABEL, DEMO_DATA_LABEL]
if "data_source_mode" not in st.session_state:
    st.session_state["data_source_mode"] = REAL_DATA_LABEL if real_available else DEMO_DATA_LABEL
if st.session_state["data_source_mode"] not in source_options:
    st.session_state["data_source_mode"] = REAL_DATA_LABEL if real_available else DEMO_DATA_LABEL
if not real_available and st.session_state["data_source_mode"] == REAL_DATA_LABEL:
    st.session_state["data_source_mode"] = DEMO_DATA_LABEL
if not real_available:
    st.sidebar.warning("真实新闻数据为空或不可读，已默认使用 Demo 数据。请点击“抓取最新新闻”后切换真实新闻。")

st.sidebar.radio(
    "数据源",
    source_options,
    index=source_options.index(st.session_state["data_source_mode"]),
    key="data_source_mode",
    help="真实新闻来自 RSS，是主要数据源；Demo 数据仅用于离线兜底和测试。",
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
                    f"合并重复语境 {result['merged_context_count']} 条，"
                    f"真实新闻累计 {result['processed_count']} 条。"
                )
            if result["failures"]:
                with st.sidebar.expander("部分 RSS 源失败"):
                    for failure in result["failures"][:8]:
                        st.write(f"{failure['source']}: {failure['error']}")
            if result.get("brief_result"):
                st.sidebar.caption(f"简报门闸：{result['brief_result'].get('message', '')}")
            if result.get("raw_size_warning"):
                st.sidebar.warning(result["raw_size_warning"])

if st.sidebar.button("立即重新生成简报"):
    st.session_state["confirm_force_brief"] = True

if st.session_state.get("confirm_force_brief"):
    st.sidebar.warning("确认后会无视每日门闸并调用简报生成流程；若 OPENAI_API_KEY 可用，可能产生 API 费用。")
    pin_matches = True
    if DEMO_PIN:
        entered_pin = st.sidebar.text_input("访问口令", type="password", key="force_brief_pin")
        pin_matches = hmac.compare_digest(entered_pin, DEMO_PIN)
    if st.sidebar.button("确认生成（可能产生费用）"):
        if DEMO_PIN and not pin_matches:
            st.sidebar.error("访问口令不正确，未调用简报生成接口。")
        else:
            with st.spinner("正在重新生成每日市场简报..."):
                result = generate_daily_brief(
                    source_mode=st.session_state.get("data_source_mode", REAL_DATA_LABEL),
                    force=True,
                )
            st.session_state["confirm_force_brief"] = False
            if result.get("status") == "generated":
                st.sidebar.success(result.get("message", "简报已生成。"))
            else:
                st.sidebar.warning(result.get("message", "简报未生成。"))
    if st.sidebar.button("取消重新生成"):
        st.session_state["confirm_force_brief"] = False

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
        st.Page(
            BASE_DIR / "pages" / "5_Evaluation.py",
            title="评估",
            icon=":material/fact_check:",
        ),
    ],
}

selected_page = st.navigation(pages, expanded=True)
selected_page.run()
