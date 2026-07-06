import pandas as pd


def demo_coverage_summary(df: pd.DataFrame) -> dict[str, int]:
    """第一阶段评估占位：统计 demo 数据覆盖情况。"""
    return {
        "新闻数量": int(len(df)),
        "来源数量": int(df["source"].nunique()) if "source" in df else 0,
        "板块覆盖数量": int(df["sector"].nunique()) if "sector" in df else 0,
    }
