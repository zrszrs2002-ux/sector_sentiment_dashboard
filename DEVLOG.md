# DEVLOG

## 2026-07-06 21:58

- 阶段名称 / 本次操作目标：第一阶段项目骨架搭建
- 具体做了什么：检查当前目录，确认工作区下尚无 `sector_sentiment_dashboard` 项目；确认本机 Python 版本为 3.12.7，Streamlit 尚未安装；创建项目目录结构；创建 `requirements.txt`、`requirements-full.txt`、`README.md`、`app.py`、`data/demo_articles.csv`、`data/processed_articles.csv`、`src/` 模块占位文件和四个 Streamlit 页面文件。选择 `streamlit==1.58.0`，采用 `st.Page` + `st.navigation` 组织多页面应用。
- 遇到的问题和解决方案：默认 `python` 指向 Windows Python Manager，在沙箱内执行时出现权限拒绝；已改用本机 Python 3.12 完整路径并通过只读权限检查确认版本。当前 Streamlit 未安装，因此本阶段不直接启动应用，先给出安装和运行命令。
- 当前项目状态：项目骨架已创建；安装依赖后可通过 `pip install -r requirements.txt` 和 `streamlit run app.py` 打开 demo 页面框架。
- 下一步计划：等待用户确认后，第二阶段扩展 demo 数据到 100-150 条，并实现数据加载、UTC 时间处理、去重标记和基础预处理流程。

## 2026-07-07 00:17

- 阶段名称 / 本次操作目标：第二阶段数据层增强
- 具体做了什么：新增 `src/demo_data_generator.py`，用固定模板生成 132 条 demo 财经新闻，覆盖 11 个板块，每个板块 12 条，发布时间分布在 2026-06-07 至 2026-07-07 的 UTC 时间范围内；完善 `src/preprocessing.py`，实现 UTC 时间标准化、URL 去重、标题精确去重和高相似标题转载识别；把文章字段清单集中移动到 `src/config.py`；更新 `src/data_loader.py`，新增 `load_articles()` 统一入口，优先读取 `data/processed_articles.csv`；更新四个页面文件，使 dashboard 默认使用处理后的文章数据；重新生成 `data/demo_articles.csv` 和 `data/processed_articles.csv`。
- 遇到的问题和解决方案：初版相似标题阈值过宽，模板化标题导致大量新闻被误判为重复；随后调整标题生成模板，并在预处理里增加“前缀词一致 + 相似度阈值”的保守判断，最终得到 102 条唯一新闻、19 条高相似转载新闻、11 条明显重复新闻。
- 当前项目状态：第二阶段数据层已完成；`processed_articles.csv` 共 132 条，覆盖 11 个板块，时间字段已统一为 UTC ISO 8601 格式。代码已通过 Python 3.12 语法编译检查。安装依赖后可运行：`pip install -r requirements.txt`，然后执行 `streamlit run app.py`。
- 下一步计划：等待用户确认后，第三阶段实现公司/ticker/板块映射、topic/risk 规则词典和词典情绪模型 fallback，为后续正式六维指标计算做准备。

## 2026-07-07 00:17

- 阶段名称 / 本次操作目标：第二阶段 README 状态同步
- 具体做了什么：更新 `README.md`，把项目状态从第一阶段小型 demo 框架同步为第二阶段数据层增强状态，补充 132 条 demo 新闻、`processed_articles.csv`、UTC 时间范围和基础去重说明。
- 遇到的问题和解决方案：无。
- 当前项目状态：README 与当前代码和数据状态一致；dashboard 仍按 `streamlit run app.py` 启动。
- 下一步计划：等待用户确认后进入第三阶段，补充映射、词典和情绪 fallback。

## 2026-07-07 01:05

- 阶段名称 / 本次操作目标：第三阶段规则识别与词典情绪 fallback
- 具体做了什么：新增 `data/dictionaries/company_sector_mapping.json`、`topic_keywords.json`、`risk_keywords.json`、`sentiment_lexicon.json` 四份独立 JSON 词典；完善 `src/mapping.py`，实现公司别名、ticker 和板块关键词映射；完善 `src/topic_risk_tagger.py`，实现 topic、risk_category 和风险证据句识别；完善 `src/sentiment_model.py`，实现离线词典情绪模型 fallback，并按句子聚合为文章级情绪概率；完善 `src/scoring.py`，根据 fallback 情绪概率和风险严重度生成单篇新闻基础六维分数；新增 `src/article_pipeline.py`，把预处理、映射、标签、情绪和评分串成处理流水线；更新 `src/demo_data_generator.py`，使生成 demo 数据后自动调用第三阶段处理流水线；刷新 `data/processed_articles.csv`；更新 `README.md` 到第三阶段状态。
- 遇到的问题和解决方案：首次复查发现 topic 词典仍有 16 条落到 `general market sentiment`，说明主题关键词覆盖不足；随后补充 streaming margins、pricing power、drug pipeline、capital spending、cash flow、tenant demand、copper prices 等 demo 中实际出现的主题规则，兜底 topic 降到 2 条。当前没有调用 Hugging Face 模型，原因是课程 demo 需要无网络可运行，先采用词典 fallback。
- 当前项目状态：`processed_articles.csv` 共 132 条；11 个板块全部覆盖，每个板块 12 条；未映射板块数量为 0；所有文章都有 companies 和 tickers；风险类别覆盖 10 类；去重权重分布为 102 条唯一新闻、19 条高相似转载、11 条明显重复。
- 下一步计划：等待用户确认后进入第四阶段，实现正式聚合层：新闻权重 `time_weight * relevance_weight * dedup_factor`、板块级六维雷达、市场级六维雷达、Top Drivers、Top Positive/Negative/Risk News 和 evidence sentence 聚合。

## 2026-07-07 01:31

- 阶段名称 / 本次操作目标：第四阶段六维指标正式聚合
- 具体做了什么：修正 `src/config.py` 中的雷达指标字段，把板块级指标改为 `optimism`、`fear`、`uncertainty`、`attention`、`disagreement`、`risk_intensity`；在 `src/scoring.py` 中新增 `p_positive`、`p_neutral`、`p_negative`、`relevance_weight`、`time_weight`、`agg_weight` 字段，并将 `agg_weight` 定义为 `time_weight * relevance_weight * dedup_factor`；重写 `src/aggregation.py`，实现 Optimism/Fear/Uncertainty 的加权平均、Disagreement 的 `sentiment_score` 加权标准差、Attention 的近 7 天板块新闻量横向 min-max、Risk Intensity 的 `0.7 * 加权平均 + 0.3 * P90`；市场级雷达采用 11 个板块等权平均；更新四个 dashboard 页面中对旧字段和旧说明的引用；重新生成 `data/processed_articles.csv`；更新 `README.md` 说明正式聚合公式。
- 遇到的问题和解决方案：用户指出旧版 `aggregation.py` 对 `disagreement_input` 求均值会得到平均情绪而不是分歧度，且旧版把 `time_weight * relevance_weight` 当成 Attention，导致关注度语义错误。本阶段已把聚合权重命名为 `agg_weight` 并和 Attention 指标彻底分离。文章级 `risk_intensity` 与提示词第六节的方向一致，即基于风险标签和严重度权重映射到 0-100；但当前 baseline 额外加入了负向情绪压力和不确定性压力，理由是词典 fallback 没有 FinBERT 那样稳定的风险置信度，加入情绪压力可以让风险新闻在 demo 中更可区分。后续如有人工标注数据，应校准这部分权重。
- 当前项目状态：`processed_articles.csv` 共 132 条，并已包含独立的 `agg_weight` 字段。聚合验证结果：板块级 Disagreement 范围为 9.4 到 29.5，没有负数；板块级 Attention 范围为 0 到 100，板块间已拉开差距；市场级雷达采用板块等权平均。
- 下一步计划：等待用户确认后进入第五阶段，建议实现 Top Drivers 聚合解释、Top Positive/Negative/Risk News 展示强化、evaluation 脚本/页面，以及可选真实新闻导入入口。

## 2026-07-07 05:08

- 阶段名称 / 本次操作目标：第四阶段 Attention 归一化优化与字段说明更正
- 具体做了什么：根据用户反馈优化 `src/aggregation.py` 中的 Attention 计算方法：近 7 天窗口内不再使用原始新闻条数，而是按板块汇总 `agg_weight` 得到加权新闻量；归一化不再使用 min-max，而改为 `100 * (rank - 0.5) / 板块数` 的排名分位数，并列时取平均排名。更新 `src/config.py`，在 `ATTENTION_WINDOW_DAYS` 旁补充 TODO，说明当前方法是跨板块横截面近似，真实新闻积累 30 天以上后应切换为每个板块相对自身历史分布的 ECDF 分位数。更新 `README.md` 数据字典，准确说明 `attention_weight`、`disagreement_input` 和 `agg_weight`。
- 遇到的问题和解决方案：用户指出上一轮 Attention 使用原始条数 min-max 会在 demo 数据中形成 0/33.3/66.7/100 档位，并导致多个板块并列 100，容易误导；已改为加权新闻量和排名分位数。另更正上一轮汇报中的不准确表述：`attention_weight` 当前确实为保留字段且恒为 0，但 `disagreement_input` 不是 0，而是 `sentiment_score` 的逐行副本；聚合代码当前直接读取 `sentiment_score` 计算加权标准差。
- 当前项目状态：聚合代码和文档说明已更新；待执行最终编译检查和 Attention 数值验证。
- 下一步计划：运行语法检查与聚合验证，确认 11 个板块的 Attention 无 0.0、无大面积并列 100，并暂停等待用户确认。

## 2026-07-07 05:09

- 阶段名称 / 本次操作目标：Attention 优化验证
- 具体做了什么：运行 Python 3.12 语法编译检查，并直接调用 `sector_metrics()` 验证 11 个板块的 Attention、Disagreement 和窗口加权新闻量输出。
- 遇到的问题和解决方案：无新的代码错误。`rg` 在当前沙箱中因权限被拒绝，已改用直接读取关键文件和 Python 聚合验证完成检查。
- 当前项目状态：编译检查通过。Attention 取值范围为 4.545 到 95.455，11 个板块均为不同取值，0.0 数量为 0，100 数量为 0；Disagreement 仍保持 0-100 内且无负数。
- 下一步计划：暂停等待用户确认，再进入下一阶段。

## 2026-07-07 05:25

- 阶段名称 / 本次操作目标：新增真实新闻 RSS 抓取模块
- 具体做了什么：将 `src/news_collector.py` 从占位模块改为真实 RSS 抓取模块，使用 `feedparser` 解析 Yahoo Finance 按 ticker 的 RSS、CNBC Top News RSS 和 MarketWatch Top Stories RSS；每个 feed 独立 try/except，设置 User-Agent 和超时；只读取标题、摘要、URL、发布时间和来源，不抓新闻原文页面；新增 `data/raw_articles.csv` 累积保存 RSS 原始新闻，新增 `data/real_processed_articles.csv` 保存真实新闻经过现有预处理、去重、映射、标签、情绪和评分流水线后的结果；更新 `src/data_loader.py` 支持“Demo 数据 / 真实新闻”两种数据源；更新 `app.py`，在 sidebar 添加数据源开关和“抓取最新新闻”按钮；新增 `src/ui_helpers.py`，统一处理真实新闻为空提示和 URL 可点击列；更新四个页面，使真实新闻模式下可读取 RSS 处理结果，并将 URL 列显示为可点击链接；更新 `README.md`，说明 RSS 数据源、命令行抓取方式、累积存储和趋势图稀疏是预期行为。
- 遇到的问题和解决方案：真实 RSS 数据通常只覆盖最近几天，30 天趋势需要连续多日运行抓取积累，因此短期真实新闻模式下趋势图可能稀疏；已在 README 中说明。Reuters RSS 未使用，因为该服务已停止。为了避免反爬和版权问题，第一版不抓取新闻正文页面，`content` 使用 RSS 摘要填充。若全部 RSS 源失败，UI 会给出中文提示，并保留 Demo 数据作为兜底。
- 当前项目状态：代码已接入真实新闻抓取入口；`raw_articles.csv` 和 `real_processed_articles.csv` 已创建表头，等待首次抓取填充。由于当前执行环境网络受限，本条记录先记录实现完成，随后进行编译检查；实际抓取可在本地通过 sidebar 按钮或 `python -m src.news_collector` 运行。
- 下一步计划：执行语法编译检查；如果依赖和网络可用，再运行 `python -m src.news_collector` 做真实抓取验证。

## 2026-07-07 05:28

- 阶段名称 / 本次操作目标：RSS 抓取实测与映射修正
- 具体做了什么：先试抓 Yahoo Finance 的 NVDA RSS，成功解析 20 条；随后运行完整 `python -m src.news_collector`，45 个 feed 全部成功，解析 890 条，本次新增 702 条，`raw_articles.csv` 累计 702 条，`real_processed_articles.csv` 生成 702 条。复查真实数据后发现单字母 ticker（如 `T`、`C`、`O`）如果大小写不敏感匹配，可能误伤普通文本；已修改 `src/mapping.py`，公司别名仍大小写不敏感，ticker 匹配改为大小写敏感，并基于已有 `raw_articles.csv` 重新生成 `real_processed_articles.csv`。
- 遇到的问题和解决方案：真实市场级 RSS 中有少量新闻无法映射到 11 个板块，当前保留为 `Unmapped` 并在文章浏览器中展示；板块雷达仍只聚合 11 个目标板块。真实新闻聚合验证显示 702 条新闻、URL 非空且以 http 开头的记录为 702 条；板块覆盖完整，另有 15 条 `Unmapped` 市场级新闻。
- 当前项目状态：编译检查通过。真实新闻模式可用；真实数据板块分布包括 Technology 166 条、Communication Services 64 条、Consumer Discretionary 66 条、Financials 62 条等；Attention 无 0 值，URL 列可点击。
- 下一步计划：暂停等待用户确认；后续可继续优化市场级/宏观新闻如何影响市场总览，或增加 evaluation 页面。

## 2026-07-07 05:45

- 阶段名称 / 本次操作目标：修复板块详情页 Key evidence sentences 中 `title` 与 `evidence_sentence` 大量重复的问题
- 具体做了什么：用户在对话中指出“Key evidence sentences 这里，`title` 和 `evidence_sentence` 显示的都是一样的，这是不是有问题？”，并附上板块详情页截图；截图中 Key evidence sentences 表格的两列分别为 `title` 和 `evidence_sentence`，多行内容几乎完全相同，例如新闻标题被原样显示为证据句。根据该反馈检查 `pages/3_Sector_Detail.py`、`src/article_pipeline.py`、`src/sentiment_model.py`、`src/topic_risk_tagger.py` 和真实新闻 CSV，确认页面只是直接展示两列，问题来自处理管线生成的 `evidence_sentence`。修改 `src/article_pipeline.py`，新增 `normalize_evidence_text()`、`article_parts()`、`article_body_text()`、`strip_title_from_evidence()`、`first_body_sentence()` 和 `choose_evidence_sentence()` 等辅助逻辑，使证据句优先从 `summary/content` 中选择，并在候选句开头重复标题时剥离标题；只有正文和摘要没有可用信息时才回退到 `title`。随后基于现有 demo 与 RSS raw 数据重新生成 `data/processed_articles.csv` 和 `data/real_processed_articles.csv`。
- 遇到的问题和解决方案：`rg` 在当前沙箱中被拒绝访问，已改用 PowerShell `Select-String` 和定向读取关键文件完成定位；默认 `python` 和本机 Python 3.12 在沙箱内也被权限拒绝，已通过授权执行本机 Python 完成 `py_compile` 语法检查和 CSV 重新生成。真实 RSS 数据中仍有 2 条 `title == summary == content` 的记录，因此这 2 条无法提取非标题证据句，保留标题作为合理兜底。
- 当前项目状态：`src/article_pipeline.py` 已更新证据句选择逻辑；语法检查通过。重新生成后，`real_processed_articles.csv` 共 705 条，其中 `title == evidence_sentence` 从 526 条降到 2 条；`processed_articles.csv` 的 demo 数据中 `title == evidence_sentence` 为 0 条。项目安装依赖后可运行；运行方式是在项目根目录执行 `streamlit run app.py`，然后在侧边栏选择 Demo 数据或真实新闻数据，刷新页面后应能看到 Key evidence sentences 中两列明显区分。
- 下一步计划：如后续继续优化真实新闻质量，可考虑接入更完整的正文抽取或来源摘要清洗，以减少 RSS 摘要本身过短、重复标题或被截断导致的兜底情况。
