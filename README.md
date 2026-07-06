# AI-powered Sector Sentiment Intelligence Dashboard

中文名：自动化板块级金融舆情雷达系统

## 1. 项目简介

本项目是一个课程展示用的 Streamlit dashboard，目标是把财经新闻中的公司、ticker、板块、主题、情绪和风险信号整理成板块级与市场级的六维舆情雷达。

当前已完成第一冲刺的第四阶段，并新增 RSS 真实新闻抓取能力：项目骨架、页面导航、132 条可复现 demo 新闻、RSS 抓取、UTC 时间标准化、基础去重、公司/ticker/板块映射、topic/risk 规则词典、离线词典情绪模型 fallback，以及正式板块级/市场级六维聚合已经就绪。FinBERT 推理和评估模块将在后续阶段逐步补齐。

免责声明：本系统仅用于教育和研究演示，不构成投资建议。

## 2. 功能列表

- 市场总览：展示市场级六维指标、demo 新闻数量、来源数量、板块热力图和规则摘要。
- 板块比较：展示 11 个 GICS 风格板块的六维指标对比。
- 板块详情：按单个板块查看雷达图、趋势框架、重点公司、主题和证据句。
- 文章浏览器：查看 demo 新闻列表，并支持基础筛选和排序。
- RSS 新闻抓取：侧边栏可切换“Demo 数据 / 真实新闻”，并可点击“抓取最新新闻”更新真实 RSS 数据。
- 后续计划：完善 Top Drivers 解释、评估脚本、可选 RSS/CSV 数据接入和 FinBERT 接口。

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

当前阶段支持两类数据源：

1. Demo 数据：本地生成，不依赖网络，作为兜底。
2. 真实新闻：通过 RSS 抓取，默认使用 Yahoo Finance 按 ticker 的 RSS、CNBC Top News RSS、MarketWatch Top Stories RSS。不使用 Reuters RSS，因为该服务已停止。

RSS 第一版只读取标题、摘要、URL、发布时间和来源；`content` 字段使用摘要填充，不抓取新闻原文页面，避免反爬、登录限制和版权问题。

RSS 地址示例：

- Yahoo Finance ticker RSS：`https://feeds.finance.yahoo.com/rss/2.0/headline?s=NVDA&region=US&lang=en-US`
- CNBC Top News RSS：`https://www.cnbc.com/id/100003114/device/rss/rss.html`
- MarketWatch Top Stories RSS：`https://feeds.marketwatch.com/marketwatch/topstories`

- `data/demo_articles.csv`：132 条原始 demo 新闻。
- `data/processed_articles.csv`：经过 UTC 时间标准化、基础去重、公司映射、主题/风险标签、词典情绪 fallback 和聚合权重字段处理后的 demo 新闻。
- `data/raw_articles.csv`：RSS 抓取得到的真实新闻原始累积数据。多次运行会追加新新闻，不覆盖历史。
- `data/real_processed_articles.csv`：真实新闻经过现有预处理、去重、映射、标签、情绪和评分流水线后的结果。
- `data/dictionaries/company_sector_mapping.json`：公司、ticker、别名与板块映射。
- `data/dictionaries/topic_keywords.json`：主题关键词词典。
- `data/dictionaries/risk_keywords.json`：风险类别关键词词典。
- `data/dictionaries/sentiment_lexicon.json`：离线 fallback 情绪词典。

数据覆盖 11 个板块，每个板块 12 条新闻，发布时间分布在 2026-06-07 至 2026-07-07 的 UTC 时间范围内。当前去重策略包括 URL 去重、标题精确去重和保守的标题高相似转载识别。后续阶段会保留可选 RSS/API 抓取模块。

RSS 只覆盖最近几天的新闻，30 天趋势需要连续多日运行抓取来积累。短期内真实新闻模式下趋势图比较稀疏，这是预期行为。

数据字典补充：

- `attention_weight`：保留字段，当前恒为 0。关注度在板块层由新闻量计算，文章层无实际含义。
- `disagreement_input`：`sentiment_score` 的逐行副本，作为板块分歧度加权标准差的输入留档；当前聚合代码实际直接读取 `sentiment_score`。
- `agg_weight`：聚合权重，计算为 `time_weight * relevance_weight * dedup_factor`，用于加权平均和加权标准差。

## 5. 六维指标解释

- Optimism 乐观度：新闻中正向概率或正向信号强度。
- Fear 恐惧度：新闻中负向概率或风险担忧强度。
- Uncertainty 不确定性：中性概率与概率熵的组合。
- Attention 关注度：板块层指标，使用近 7 天窗口内该板块加权新闻量在 11 个板块中的排名分位数，公式为 `100 * (rank - 0.5) / 板块数`，并列时取平均排名。它不是单篇新闻的时间衰减权重。
- Disagreement 分歧度：板块层指标，使用板块内 `sentiment_score` 的加权标准差，计算为 `100 * clip(weighted_std, 0, 1)`；板块内新闻少于 2 条时记为 0。
- Risk Intensity 风险强度：风险类别严重度与新闻风险信号的综合分数。

当前 demo CSV 中的单篇新闻分数由 `src/sentiment_model.py` 的词典情绪 fallback、`src/topic_risk_tagger.py` 的风险标签和 `src/scoring.py` 的基础公式生成。单篇新闻聚合权重独立保存为 `agg_weight = time_weight * relevance_weight * dedup_factor`，避免与 Attention 概念混用。

板块级聚合由 `src/aggregation.py` 完成：

- Optimism / Fear / Uncertainty：使用 `agg_weight` 做加权平均。
- Disagreement：使用 `sentiment_score` 的加权标准差。
- Attention：使用近 7 天板块加权新闻量的横向排名分位数。当前这是没有长期历史数据时的横截面近似；等真实新闻积累超过 30 天后，应切换为每个板块相对自身历史新闻量分布的 ECDF 分位数，以避免低估 Utilities、Materials 等天然新闻较少的板块。
- Risk Intensity：使用 `0.7 * 加权平均风险强度 + 0.3 * P90 风险强度`；样本不足时用平均值替代 P90。

市场级雷达采用 11 个板块等权平均，而不是新闻量加权。这样可以避免 demo 数据或真实新闻流量过度集中在少数高曝光板块时，市场总览被单一板块主导。

## 6. 如何本地运行

建议在项目目录下创建虚拟环境后安装依赖：

```bash
cd sector_sentiment_dashboard
pip install -r requirements.txt
streamlit run app.py
```

命令行抓取真实 RSS 新闻：

```bash
python -m src.news_collector
```

也可以在 Streamlit 侧边栏点击“抓取最新新闻”。真实新闻模式下如果数据为空，页面会提示先抓取或切换回 Demo 数据。

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

- 当前 demo 数据是模板生成的课程展示数据，还不能代表真实市场新闻覆盖。
- 当前使用离线词典情绪模型 fallback，还不是 FinBERT 输出。
- 当前文章级 risk_intensity 是 baseline 公式：以风险类别严重度为主体，并加入负向情绪压力和不确定性压力；它不是人工标注校准后的最终风险模型。
- 当前不提供投资建议，也不用于实时交易。
- 真实新闻抓取、长文本分句、证据句提取和模型评估会在后续阶段实现。

## 10. 免责声明

本系统仅用于教育和研究演示，不构成投资建议。

## 11. 未来改进方向

- 接入可选 FinBERT/Hugging Face 推理接口。
- 增加 evaluation 脚本和人工标注 CSV 接口。
- 增加可选 RSS 新闻抓取和 CSV 上传。
