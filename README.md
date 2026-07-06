# AI-powered Sector Sentiment Intelligence Dashboard

中文名：自动化板块级金融舆情雷达系统

## 1. 项目简介

本项目是一个课程展示用的 Streamlit dashboard，目标是把财经新闻中的公司、ticker、板块、主题、情绪和风险信号整理成板块级与市场级的六维舆情雷达。

当前是第一冲刺的第一阶段：先搭建可运行的项目骨架、页面导航和 demo 数据展示框架。完整的新闻处理流水线、FinBERT 推理、规则词典、聚合算法和评估模块将在后续阶段逐步补齐。

免责声明：本系统仅用于教育和研究演示，不构成投资建议。

## 2. 功能列表

- 市场总览：展示市场级六维指标、demo 新闻数量、来源数量、板块热力图和规则摘要。
- 板块比较：展示 11 个 GICS 风格板块的六维指标对比。
- 板块详情：按单个板块查看雷达图、趋势框架、重点公司、主题和证据句。
- 文章浏览器：查看 demo 新闻列表，并支持基础筛选和排序。
- 后续计划：接入 100-150 条 demo 新闻、词典标签、情绪模型 fallback、聚合层和评估脚本。

## 3. 系统架构

第一版采用轻量本地架构：

```text
demo CSV / 可选 RSS / 可选 CSV 上传
        ↓
数据加载与预处理
        ↓
公司与板块映射、主题与风险标签、情绪识别
        ↓
单篇新闻结构化输出
        ↓
板块级与市场级六维聚合
        ↓
Streamlit + Plotly dashboard
```

页面组织方式：使用 `streamlit==1.58.0`，并采用 Streamlit 官方当前推荐的 `st.Page` + `st.navigation` 方式组织多页面应用。这样 `app.py` 作为统一入口和页面路由，`pages/` 下的文件负责各功能页。

## 4. 数据来源说明

当前阶段只使用 `data/demo_articles.csv` 中的小型演示数据，覆盖 11 个板块，每个板块 1 条新闻，用于验证页面框架是否能打开。

后续阶段会扩展为 100-150 条过去 30 天内的 demo 新闻，并保留可选 RSS/API 抓取模块。所有时间字段将统一转换并保存为 UTC 时间。

## 5. 六维指标解释

- Optimism 乐观度：新闻中正向概率或正向信号强度。
- Fear 恐惧度：新闻中负向概率或风险担忧强度。
- Uncertainty 不确定性：中性概率与概率熵的组合。
- Attention 关注度：板块新闻量、时间权重和相关性权重的综合信号。
- Disagreement 分歧度：板块内情绪分数差异。
- Risk Intensity 风险强度：风险类别严重度与新闻风险信号的综合分数。

当前 demo CSV 中的六维分数是手工示例值，只用于页面展示。后续会由 `src/scoring.py` 和 `src/aggregation.py` 统一计算。

## 6. 如何本地运行

建议在项目目录下创建虚拟环境后安装依赖：

```bash
cd sector_sentiment_dashboard
pip install -r requirements.txt
streamlit run app.py
```

如果 Windows 默认 `python` 被 Python Manager 拦截，可以改用本机 Python 3.12 的完整路径创建环境或执行 pip。

## 7. 如何部署到 Streamlit Community Cloud

1. 将项目推送到 GitHub 仓库。
2. 在 Streamlit Community Cloud 新建应用。
3. 入口文件选择 `sector_sentiment_dashboard/app.py`。
4. Python 版本选择 3.12。
5. 默认只安装 `requirements.txt`，先运行 demo 模式。

## 8. 环境变量/API key 设置

当前阶段不需要 API key。

后续如果接入 OpenAI、Gemini 或其他 LLM 摘要服务，建议使用环境变量保存密钥，例如：

```bash
OPENAI_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here
```

没有 API key 时，系统必须继续使用规则模板生成中文摘要。

## 9. 项目限制

- 当前 demo 数据量很小，还不能代表真实市场新闻覆盖。
- 当前六维指标是示例值，不是完整模型输出。
- 当前没有启用 FinBERT 或 Hugging Face 模型。
- 当前不提供投资建议，也不用于实时交易。
- 真实新闻抓取、去重、长文本分句、证据句提取和模型评估会在后续阶段实现。

## 10. 免责声明

本系统仅用于教育和研究演示，不构成投资建议。

## 11. 未来改进方向

- 扩展 demo 数据到 100-150 条，覆盖过去 30 天。
- 增加公司/ticker/板块映射词典。
- 增加 topic 与 risk_category 的 JSON 或 YAML 规则词典。
- 实现词典情绪模型 fallback，并预留 FinBERT 推理接口。
- 实现单篇新闻、板块级和市场级聚合算法。
- 增加 evaluation 脚本和人工标注 CSV 接口。
- 增加可选 RSS 新闻抓取和 CSV 上传。
