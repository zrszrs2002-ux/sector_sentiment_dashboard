import hmac
import os
from pathlib import Path

import streamlit as st


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

st.set_page_config(
    page_title="Automated Sector Financial Sentiment Radar",
    layout="wide",
)

from src.config import DISCLAIMER, get_demo_pin
from src.data_loader import DEMO_DATA_LABEL, REAL_DATA_LABEL, has_real_articles
from src.brief_generator import generate_daily_brief
from src.news_collector import collect_rss_news
from src.sentiment_model import sentiment_backend_status


BASE_DIR = Path(__file__).resolve().parent

st.sidebar.title("Sector Financial Sentiment Radar")
st.sidebar.caption("Public financial news sentiment monitoring tool")
st.sidebar.info(DISCLAIMER)
st.sidebar.caption(sentiment_backend_status())

real_available = has_real_articles()
source_options = [REAL_DATA_LABEL, DEMO_DATA_LABEL]
if "data_source_mode" not in st.session_state:
    st.session_state["data_source_mode"] = REAL_DATA_LABEL if real_available else DEMO_DATA_LABEL
if st.session_state["data_source_mode"] not in source_options:
    st.session_state["data_source_mode"] = REAL_DATA_LABEL if real_available else DEMO_DATA_LABEL
if not real_available and st.session_state["data_source_mode"] == REAL_DATA_LABEL:
    st.session_state["data_source_mode"] = DEMO_DATA_LABEL
if not real_available:
    st.sidebar.warning(
        "Real news data is empty or unreadable, so Demo data is used by default. "
        "Click \u201cFetch latest news\u201d and then switch to real news."
    )

st.sidebar.radio(
    "Data source",
    source_options,
    index=source_options.index(st.session_state["data_source_mode"]),
    key="data_source_mode",
    help="Real news comes from RSS and is the primary data source; Demo data is only "
    "for offline fallback and testing.",
)

if st.sidebar.button("Fetch latest news", type="primary"):
    with st.spinner("Fetching RSS news and refreshing real news data..."):
        try:
            result = collect_rss_news()
        except Exception as exc:  # noqa: BLE001 - UI layer needs a readable error message
            st.sidebar.error(f"RSS fetch failed: {exc}")
        else:
            if result["all_failed"] and result["processed_count"] == 0:
                st.sidebar.warning(result["message"])
            else:
                st.sidebar.success(
                    "Fetch complete: "
                    f"{result['new_record_count']} new, "
                    f"{result['merged_context_count']} merged duplicate contexts, "
                    f"{result['processed_count']} real news articles in total."
                )
            if result["failures"]:
                with st.sidebar.expander("Some RSS sources failed"):
                    for failure in result["failures"][:8]:
                        st.write(f"{failure['source']}: {failure['error']}")
            if result.get("brief_result"):
                st.sidebar.caption(f"Brief gate: {result['brief_result'].get('message', '')}")
            if result.get("raw_size_warning"):
                st.sidebar.warning(result["raw_size_warning"])

if st.sidebar.button("Regenerate brief now"):
    st.session_state["confirm_force_brief"] = True

if st.session_state.get("confirm_force_brief"):
    st.sidebar.warning(
        "Confirming will bypass the daily gate and call the brief generation pipeline; "
        "if OPENAI_API_KEY is available this may incur API costs."
    )
    demo_pin = get_demo_pin()
    pin_matches = True
    if demo_pin:
        entered_pin = st.sidebar.text_input("Access PIN", type="password", key="force_brief_pin")
        pin_matches = hmac.compare_digest(entered_pin, demo_pin)
    if st.sidebar.button("Confirm generation (may incur costs)"):
        if demo_pin and not pin_matches:
            st.sidebar.error("Incorrect access PIN; brief generation was not called.")
        else:
            with st.spinner("Regenerating the daily market brief..."):
                result = generate_daily_brief(
                    source_mode=st.session_state.get("data_source_mode", REAL_DATA_LABEL),
                    force=True,
                )
            st.session_state["confirm_force_brief"] = False
            if result.get("status") == "generated":
                st.sidebar.success(result.get("message", "Brief generated."))
            else:
                st.sidebar.warning(result.get("message", "Brief was not generated."))
    if st.sidebar.button("Cancel regeneration"):
        st.session_state["confirm_force_brief"] = False

pages = {
    "Core Dashboard": [
        st.Page(
            BASE_DIR / "pages" / "1_Market_Overview.py",
            title="Market Overview",
            icon=":material/dashboard:",
            default=True,
        ),
        st.Page(
            BASE_DIR / "pages" / "2_Sector_Comparison.py",
            title="Sector Comparison",
            icon=":material/analytics:",
        ),
        st.Page(
            BASE_DIR / "pages" / "3_Sector_Detail.py",
            title="Sector Detail",
            icon=":material/troubleshoot:",
        ),
        st.Page(
            BASE_DIR / "pages" / "4_Article_Explorer.py",
            title="Article Explorer",
            icon=":material/article:",
        ),
        st.Page(
            BASE_DIR / "pages" / "5_Evaluation.py",
            title="Evaluation",
            icon=":material/fact_check:",
        ),
    ],
}

selected_page = st.navigation(pages, expanded=True)
selected_page.run()
