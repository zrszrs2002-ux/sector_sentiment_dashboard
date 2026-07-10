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
## 2026-07-08 22:24

- 阶段名称 / 本次操作目标：阶段 4.5 实战化一致性修复
- 具体做了什么：按用户确认范围完成 P0 五项、默认真实新闻优先和两项新增检查。统一 `src/config.py` 中的正式免责声明；把 RSS User-Agent、RSS URL、超时、单 feed 条数、标题相似阈值、Risk Intensity 情绪压力开关等参数集中到 config。`preprocessing.py` 不再把坏时间静默改成当前时间，而是记录 `time_parse_error`，并将 CSV 写入改为临时文件写入、备份旧文件、原子替换。`article_pipeline.py` 改为逐条新闻 try/except，坏记录写入 `data/error_records.csv` 并以低权重降级，不中断整批。词典加载增加最小兜底，避免 JSON 缺失或损坏时应用直接崩溃。`scoring.py` 将文章级 Risk Intensity 恢复为默认纯风险标签严重度映射；早期负向情绪压力/不确定性压力已放到 `RISK_USE_SENTIMENT_PRESSURE` 开关后，默认关闭，原因是会与 Fear/Uncertainty 维度耦合。
- RSS 与数据源修复：`news_collector.py` 不再硬编码 RSS 参数；重复 URL+标题的 raw 新闻不再直接丢弃后续 feed 语境，而是合并 `tickers`、`companies` 和 `source`。如果重复新闻来自不同板块 ticker，则清空单一 `sector` fallback，避免先抓到的 feed 主导归属；处理流水线会用正文加合并后的 raw tickers/companies 重新做公司实体映射。`app.py` 改为真实新闻文件非空时默认真实新闻，真实数据为空或不可读时回落 Demo 并提示；sidebar 文案改为实战工具定位。
- 文档更新：重写 `README.md` 的项目定位、免责声明、数据来源、数据安全、错误记录、RSS 覆盖限制、数据字典和六维指标说明；明确 Demo 只是离线兜底和测试脚手架，RSS 只覆盖最近几天新闻，30 天趋势需要连续运行抓取积累。更正 Risk Intensity 当前实现说明，说明市场级雷达采用 11 个板块等权平均。
- 遇到的问题和解决方案：终端默认显示中文时有编码乱码，已改用 `Get-Content -Encoding UTF8` 读取关键文件并用 ASCII 锚点打补丁。Streamlit 不允许在 widget 创建后修改同名 session state，因此抓取按钮成功后不强行改 radio 状态，而是在页面初始加载阶段实现真实新闻优先。为了验证数据但避免重复联网，本轮只基于现有 `raw_articles.csv` 重跑处理流水线，没有再次抓取 RSS。
- 当前项目状态：已重新生成 `data/demo_articles.csv`、`data/processed_articles.csv`、`data/real_processed_articles.csv`，并新增 `data/error_records.csv` 与 `data/backups/`。验证结果：Demo processed 132 条，真实 processed 705 条；Demo/真实 processed 均无缺列；错误记录 0 条；真实数据 `time_parse_error` 和 `processing_error` 非空数量均为 0；`has_real_articles()` 为 True；默认 `macro risk` 中性情绪下 Risk Intensity 为 80.0，证明默认纯风险标签公式生效；真实新闻板块 Attention 范围为 4.545 到 95.455，11 个板块均为不同取值且无 0/100；Disagreement 范围为 8.444 到 25.089，无负数；重复 raw 合并测试中 AAPL/MSFT/JPM 语境被合并，跨板块时 `sector` 清空。
- 下一步计划：阶段 4.5 到此暂停，等待用户确认后再进入 P1。P1 顺序应先做 FinBERT 可选 wrapper；评估模块只做覆盖统计、输出分布和人工标注 CSV 指标接口；macro overlay 限定为 Unmapped 宏观新闻进入 Market Brief 和 Top Drivers，不重构聚合层。
## 2026-07-08 22:39

- 阶段名称 / 本次操作目标：4.5.1 小补丁与 P1 第一轮实战增强
- 具体做了什么：修复 `src/news_collector.py` 中 RSS 发布时间兜底仍然静默的问题，`parsed_time_to_utc()` 现在解析失败或缺失时使用该条记录的 `collected_at`，并在 `time_parse_error` 写入 `published_at: missing/unparseable in RSS; fallback=collected_at`。在 `src/config.py` 新增 `BACKUP_RETENTION_COUNT = 10`，`write_article_csv()` 备份后会按源文件清理 `data/backups/`，每个源文件只保留最近 10 份备份。
- P1 FinBERT wrapper：在 `src/sentiment_model.py` 增加可选 FinBERT 单句推理 wrapper，默认模型为 `ProsusAI/finbert`，使用 CPU，默认只读取本地缓存；依赖或模型不可用时自动回退词典模型，并在命令行/侧边栏给中文提示。保持 `score_sentence()` 为唯一替换点，`analyze_article_sentiment()` 的分句聚合和证据句逻辑未改变。`requirements-full.txt` 改为 CPU 版 PyTorch 依赖。
- P1 页面与评估：在 `pages/4_Article_Explorer.py` 增加发布时间范围筛选；新增 `pages/5_Evaluation.py`，提供覆盖统计、输出分布、人工标注 CSV 模板下载和准确率计算接口。评估模块只做最简版，未做消融或敏感性分析。
- P1 Top Drivers 与 macro overlay：新增 `src/driver_analysis.py`，在展示层计算 `driver_score` 和 `driver_reason`，不改变六维聚合。`pages/1_Market_Overview.py` 改用新的 Top Drivers，并确保至少 1 条 `Unmapped` 宏观/市场级新闻可进入 Top Drivers；`src/llm_summary.py` 的 Market Brief 会提示 Unmapped 宏观新闻数量和代表新闻。
- 遇到的问题和解决方案：当前本机 Python 环境缺少 `torch`，验证时 FinBERT wrapper 按预期输出中文提示“FinBERT 依赖不可用（No module named 'torch'），已回退到词典情绪模型。”并继续处理数据。第一次 Top Drivers 抽查发现宏观新闻可能被排序挤出，随后修正为先保留最高分 Unmapped 新闻，再用常规 driver 补齐。验证过程中没有联网抓取新的 RSS，只基于现有 `raw_articles.csv` 重跑处理流水线。
- 当前项目状态：重新生成 Demo processed 132 条、真实 processed 705 条，错误记录 0 条。编译检查通过。抽查结果：RSS 发布时间缺失测试返回 `collected_at` 且错误标记正确；备份保留配置为 10，当前各源文件备份数均小于 10；覆盖统计字段完整，输出分布 10 行，人工标注接口返回 3 类指标；真实数据中 Unmapped 宏观新闻 15 条，Top Drivers 5 条中包含 1 条 Unmapped 新闻。
- 下一步计划：P1 已完成当前确认范围的第一轮实现；后续可继续细化 FinBERT 模型缓存/下载说明、评估标注规范和更完整的驱动因子解释。
## 2026-07-09 00:41

- 阶段名称 / 本次操作目标：FinBERT 正式启用与批量推理修正
- 具体做了什么：在 `src/config.py` 新增 `SENTIMENT_DEVICE = "auto"` 和 `FINBERT_BATCH_SIZE = 32`；`src/sentiment_model.py` 改为设备自适应，`auto` 在 `torch.cuda.is_available()` 为 True 时使用 CUDA，并在侧边栏显示 `当前情绪引擎：FinBERT (cuda)`。将 FinBERT 推理从逐句调用升级为跨文章收集句子后按批推理，再回填文章级聚合；`score_sentence()` 保留兼容入口，文章级分句聚合和证据句逻辑保持原有语义。
- 标签映射修正：FinBERT 概率映射完全基于 `model.config.id2label` 动态解析，启动时构建 `label_to_index` 并执行映射测试。当前实际映射为 `{'positive': 0, 'negative': 1, 'neutral': 2}`，避免了把 `p_negative` 和 `p_neutral` 按直觉顺序静默互换的风险。
- 依赖说明更新：`requirements-full.txt` 更新为 `transformers==5.13.0` 与 `torch==2.12.1+cpu`，并在文件顶部注明本地已安装 GPU 版 torch 时不要运行该文件，以免被 CPU 版覆盖。README 补充 `SENTIMENT_DEVICE`、`FINBERT_BATCH_SIZE` 和动态标签映射说明。
- 数据重跑与验证：使用本地 Python 3.12 环境（`torch 2.12.1+cu130`、`transformers 5.13.0`、CUDA 可用、`ProsusAI/finbert` 已缓存）重新生成 `data/demo_articles.csv`、`data/processed_articles.csv` 和 `data/real_processed_articles.csv`；真实新闻仍为 705 条，Demo 为 132 条，`data/error_records.csv` 为 0 条。编译检查通过。
- 分布变化：词典模型基线下真实新闻 `sentiment_score` 均值 0.0234、中位数 0.0000、P10 -0.1000、P90 0.2280；FinBERT 后均值 0.1469、中位数 0.1360、P10 -0.5526、P90 0.8410，说明 FinBERT 输出更有区分度和极性。Demo `sentiment_score` 均值从 -0.1126 变为 0.0905，中位数从 -0.1435 变为 0.1775。
- 证据句抽查：抽取同 5 条真实新闻对比，FinBERT 后情绪概率明显更有区分度；证据句选择整体保持基于摘要/正文的可解释句子。示例：`Duke Energy...investment...` 从词典中性变为强正向 `sentiment_score=0.844`，证据句仍指向“investing in American suppliers...support customer value...”；`SpaceX Nasdaq-100 inclusion...options pricing` 从词典中性变为强负向 `sentiment_score=-0.955`，证据句仍为 options trading/liquidity 相关句。`Jim Cramer...Blackstone` 的证据句从过短的 `Blackstone Inc.` 改为更有上下文的摘要句，但仍含 RSS 截断符 `[…]`，说明证据句质量仍受 RSS 摘要质量限制。
## 2026-07-09 00:49

- 阶段名称 / 本次操作目标：新增自适应环境安装脚本
- 具体做了什么：在项目根目录新增 `setup_env.py`，脚本使用 `nvidia-smi` 探测 NVIDIA GPU；探测成功时安装 `torch==2.12.1` 的 cu130 版本，探测失败或无 `nvidia-smi` 时回退安装 `torch==2.12.1+cpu`；若已检测到本地 GPU 版 torch，则跳过 torch 安装，避免覆盖现有 GPU 环境。随后脚本安装 `requirements.txt` 和 `transformers==5.13.0`，最后自检并用中文打印 torch 版本、CUDA 可用性、设备名称和结论。
- 文档更新：`requirements-full.txt` 顶部注释改为“供 Streamlit Community Cloud 等无 GPU 云端部署使用；本地安装请运行 python setup_env.py，会自动选择 CPU/GPU 版本”。`README.md` 的本地运行章节改为推荐 `python setup_env.py`，云端部署章节说明使用 `requirements-full.txt`。
- 遇到的问题和解决方案：用户要求脚本保持 50 行左右，初版偏长，随后压缩为 62 行的简单实现。为避免破坏当前已验证的 GPU torch 环境，本轮没有执行安装脚本，只执行 `python -m py_compile setup_env.py` 做语法检查。
- 当前项目状态：`setup_env.py` 语法检查通过；现有 FinBERT/GPU 环境未被覆盖。

## 2026-07-10 01:12

- 阶段名称 / 本次操作目标：修复 data 目录 CSV 在中文 Windows Excel 双击打开时弯引号和特殊字符显示为乱码的问题
- 具体做了什么：用户指出 data 目录下 CSV 以无 BOM UTF-8 写出，中文 Windows Excel 双击打开时会按 GBK 误读，导致标题中的弯引号显示为 `鈥檛` 等乱码；要求将项目中所有 CSV 写出编码统一为 `utf-8-sig`，包括 `write_article_csv`、`error_records.csv`、评估页标注模板下载和 demo 数据生成器等写出点。为此在 `src/config.py` 新增 `CSV_EXPORT_ENCODING = "utf-8-sig"`；在 `src/preprocessing.py` 中把统一 CSV writer 的 `temp_path.open(..., encoding=...)` 改为使用该常量；在 `pages/5_Evaluation.py` 中把人工标注模板下载的 `to_csv(...).encode(...)` 改为使用同一个常量。复扫后确认 demo 数据生成器、真实新闻处理、`processed_articles.csv`、`real_processed_articles.csv` 和 `error_records.csv` 都通过统一 writer 写出；同时扫描 `data/**/*.csv`，给 `data/backups` 中历史无 BOM 备份 CSV 仅补充 BOM 字节，不解析或改写字段内容。
- 遇到的问题和解决方案：`rg` 在当前环境中仍被权限拒绝，已改用 PowerShell `Select-String` 定位 CSV 写出点；本机 Python 3.12 在沙箱内直接执行被拒绝，已通过授权执行完成数据重跑和语法检查；第一次重生成 `real_processed_articles.csv` 时遇到 Windows `PermissionError`，原因是目标文件正被其他进程占用，等待锁释放后重新运行成功；PowerShell 直接匹配弯引号时出现解析问题，改用 Unicode 码点验证 `U+2019` 等特殊字符。
- 当前项目状态：`src/config.py`、`src/preprocessing.py` 和 `pages/5_Evaluation.py` 已完成编码统一；`data/demo_articles.csv`、`data/processed_articles.csv`、`data/raw_articles.csv`、`data/real_processed_articles.csv` 和 `data/error_records.csv` 均已重新写出并验证前三字节为 `EF BB BF`。全量扫描 `data` 目录下 34 个 `.csv` 文件，均已带 UTF-8 BOM。抽查真实新闻标题 `Doesn’t`，弯引号为正确的 `U+2019`，不是 `鈥檛` 乱码。相关 Python 文件已通过 `py_compile` 语法检查。项目安装依赖后可运行；运行方式是在项目根目录执行 `streamlit run app.py`，在侧边栏选择 Demo 数据或真实新闻数据后查看页面，CSV 文件可直接用 Excel 双击打开。
- 下一步计划：如后续新增任何 CSV 导出入口，应继续复用 `CSV_EXPORT_ENCODING` 或 `write_article_csv()`，避免重新出现无 BOM UTF-8 被 Excel 误读的问题。

## 2026-07-10 02:05

- 阶段名称 / 本次操作目标：LLM 每日市场简报、每日快照与一天多次抓取的增量处理
- 具体做了什么：新增 `data/sector_daily_scores.csv`、`data/market_daily_scores.csv` 的每日快照写入逻辑；每次全量或增量处理完成后按 UTC 日期 upsert 当天板块级/市场级六维分数，同日重跑覆盖当天行，历史行不动。新增 `src/daily_snapshots.py`、`src/brief_builder.py` 和 `src/brief_generator.py`，构建过去 24 小时简报数据包，包含市场六维分数、前一日差值、板块排名、异动板块、Top 5 Drivers、风险类别 Top 5、Unmapped 宏观标题和覆盖统计。`src/llm_summary.py` 改造为 Anthropic SDK + 规则模板降级链，模型配置为 `claude-opus-4-8`，API key 从 `ANTHROPIC_API_KEY` 读取，失败时打印中文日志并回退规则模板。`src/news_collector.py` 抓取后改用 `process_articles_incremental()`，只对新增 `article_id` 运行映射/标签/情绪/评分，历史结果复用，并输出“本次新增 N 条，复用 M 条”；处理完成后调用每日简报门闸，未到生成时刻或今日已生成则跳过。
- 页面与调度：Market Overview 改为只读取 `data/latest_brief.md`，显示“数据更新于”和“简报生成于”两个时间戳，不在 Streamlit 渲染路径调用 LLM；侧边栏新增“立即重新生成简报”二次确认按钮，确认文案说明可能产生 API 费用。Sector Detail 趋势图优先读取每日快照，提供 7/30 天窗口；Article Explorer 新增“加载全部历史”选项，其余页面默认 `WORKING_SET_DAYS = 30` 工作集。新增 `scripts/setup_schedule.ps1`，用于注册每 4 小时运行 `python -m src.news_collector` 的 Windows 计划任务。
- 存储分层：`raw_articles.csv` 继续永久保留，不自动清理；文件超过 `RAW_SQLITE_WARNING_MB = 50` 时仅输出建议迁移 SQLite 的中文日志。每日快照不受工作集窗口影响，永久累积。简报写入 `data/latest_brief.md`，并按日期归档到 `data/briefs/`。
- 遇到的问题和解决方案：旧中文文件在 PowerShell 输出中仍显示为乱码，为避免误伤旧内容，本轮多数旧文件采用窄锚点补丁；页面 1 和页面 3 体量较小，直接用 UTF-8 中文重写以提升可读性。Anthropic SDK 是可选运行依赖，已加入 `requirements.txt`，但代码仍保留 import/API 失败回退，避免无 key 或无网络时阻断抓取。
- 当前项目状态：代码已接入每日快照、增量处理、简报门闸、LLM/规则降级、页面只读简报和任务计划脚本；下一步需要运行语法检查、基于现有 demo/真实 processed 数据刷新快照，并在无 API key 情况下验证规则模板可写入 `latest_brief.md`。

## 2026-07-10 02:58

- 阶段名称 / 本次操作目标：每日简报与增量处理验证
- 具体做了什么：运行 Python 3.12 `compileall` 语法检查，覆盖 `src`、`pages`、`app.py` 和 `setup_env.py`，检查通过。基于现有 `processed_articles.csv` 写入 Demo 每日快照；对 `raw_articles.csv` / `real_processed_articles.csv` 运行 `process_articles_incremental()`，本次新增 0 条，复用 1201 条，处理后总计 1201 条。显式清空 `ANTHROPIC_API_KEY` 后强制生成一次简报，验证无 key 时会回退规则模板并写入 `data/latest_brief.md` 与 `data/briefs/2026-07-10.md`。检查 `data/sector_daily_scores.csv` 当前 22 行（Demo/真实新闻各 11 个板块），`data/market_daily_scores.csv` 当前 2 行（Demo/真实新闻各 1 行）。验证 `maybe_generate_daily_brief()` 在当前本地时间未到 8:00 时会跳过生成；验证 `scripts/setup_schedule.ps1` 可被 PowerShell 解析。
- 当前项目状态：本轮功能验证通过。由于验证时刻早于本地 8:00，`latest_brief.md` 是一次手动强制生成的规则模板简报；后续有 `ANTHROPIC_API_KEY` 时可通过侧边栏确认按钮重新生成 AI 简报。

## 2026-07-10 03:17

- 阶段名称 / 本次操作目标：简报阶段收尾补丁（UI 与冷启动修复）
- 具体做了什么：重构 Market Overview 排版，顶部改为 4 张 `st.metric` 指标卡（窗口内新闻数、覆盖来源数、数据窗口、数据更新时间）；左列改为市场雷达图 + 市场级六维分数表上下排列；右列每日简报放入 `st.container(height=600, border=True)` 固定高度滚动容器，避免长简报撑开整页；Sector Heatmap 和 Top Drivers 保持下方通栏。Sector Detail 趋势图改为快照天数至少 2 天才画 `lines+markers` 折线图，快照日期轴使用分类轴，避免 Plotly 自动缩放到亚秒级刻度；快照不足 2 天时显示“已积累 N 天快照，趋势图需至少 2 天数据”并展示当日数值表格。
- 简报模板修复：`generate_rule_brief_from_payload()` 不再输出“较前一日暂无”；当前一日快照不存在时，差值子句整体省略，并在数据覆盖说明中写入“暂无前一日对比基准，异动对比将于明日起可用”。
- 验证结果：Python `compileall` 通过；当前 Streamlit 版本 1.58.0 支持 `st.container(height=..., border=...)`；无 API key 情况下强制生成规则模板简报成功，确认 `latest_brief.md` 不含“较前一日暂无”，且包含数据覆盖基准说明。当前真实新闻样例板块快照天数为 1，因此趋势页会走冷启动提示 + 当日数值表格路径。
- 时区核查：`brief_generator._local_now()` 使用 `datetime.now().astimezone()`，即系统本地时区；本机返回 `澳大利亚东部标准时间`，UTC offset 为 `+10:00`。`BRIEF_GENERATION_HOUR_LOCAL = 8` 的 scheduled time 由同一个 aware datetime `replace(hour=8, ...)` 生成，因此门闸按系统本地 08:00 触发，不会因为 UTC/本地时间混用提前或滞后触发。当前核查时刻为 `2026-07-10T03:16:55+10:00`，门闸判断为未过 08:00。

## 2026-07-10 03:35

- 阶段名称 / 本次操作目标：每日简报 LLM 供应商切换到 OpenAI API
- 具体做了什么：`src/llm_summary.py` 从 Anthropic SDK 改为 OpenAI 官方 Python SDK，API key 改从 `OPENAI_API_KEY` 读取，并使用 Responses API 传入既有接地系统提示词和 JSON 数据包。新增 `LLM_MODEL_BRIEF`、`LLM_MODEL_SECTOR_SUMMARY`、`LLM_MODEL_CHAT` 三个按任务配置项；当前简报期望模型为 `gpt-5.6-terra`，保留 `LLM_MODEL` 作为兼容别名。每次生成前先调用 `client.models.list()`，仅当精确模型 ID 出现在账户实际返回列表中时才调用生成接口；不匹配时输出中文原因并回退规则模板，不会将猜测的模型 ID 发给 API。原有门闸、规则降级、接地提示词、免责声明补全、文件归档和页面只读设计保持不变。
- 依赖与文档：`requirements.txt` 用 `openai>=1.66.0,<2.0.0` 替换 Anthropic 依赖；README 的环境变量和模型校验说明同步改为 OpenAI；侧边栏强制生成确认文案改为 `OPENAI_API_KEY`。
- 验证说明：当前 Python 环境未安装 OpenAI SDK，且未检测到 `OPENAI_API_KEY`，因此无法在本次环境中实际调用 `/v1/models` 获得账户模型 ID。代码会在后续有 key 的首次生成前执行该校验；若 `gpt-5.6-terra` 不在返回列表中，将安全回退并提示用 API 实际返回的 ID 更新 `LLM_MODEL_BRIEF`。已运行 `compileall`，并以离线 Fake OpenAI client 验证：无 key 时规则降级；模型可用时调用顺序严格为 `models.list()` 后 `responses.create()`；模型不在清单中时不会调用生成接口。

## 2026-07-10 07:07

- 阶段名称 / 本次操作目标：OpenAI 简报模型 ID 修正
- 具体做了什么：根据账户实测的 `models.list()` 结果，将 `LLM_MODEL_BRIEF` 改为当前可用的 `gpt-5.5`，并让兼容配置 `LLM_MODEL` 同步指向该值。保留现有模型清单校验、Responses API、门闸和规则模板降级逻辑不变；模型不可用时的提示改为根据当前配置动态显示对应模型家族。账户获得权限后可将 `LLM_MODEL_BRIEF` 切回 `gpt-5.6-terra`。

## 2026-07-11 02:21

- 阶段名称 / 本次操作目标：Streamlit Community Cloud CPU FinBERT 完整部署改造
- 依赖与本地保护：将 `requirements.txt` 改为云端完整清单，加入 PyTorch CPU index、`torch==2.12.1+cpu` 和 `transformers==5.13.0`，保留现有应用依赖；删除废弃的 `requirements-full.txt`。由于新的完整清单会覆盖本地 GPU torch，`setup_env.py` 改为读取该清单后过滤 CPU torch、transformers 和云端 index，再安装其余依赖并按本机 GPU/CPU 情况单独安装 ML 依赖。
- 配置与启动：`FINBERT_LOCAL_FILES_ONLY` 和 `FINBERT_BATCH_SIZE` 改为环境变量配置，本地默认仍为 `1` 和 `32`，云端可设为 `0` 和 `8`；`SENTIMENT_DEVICE` 保持 `auto`。新增 `DEMO_PIN` 环境变量。`app.py` 在导入 `src.config` 前将 Streamlit Secrets 逐项桥接到环境变量，本地没有 Secrets 文件时静默跳过；启动顺序保持 `st.set_page_config()` 最先执行。
- 页面保护与模型体验：云端允许下载且 FinBERT 尚未加载时，用“首次启动正在下载 FinBERT 模型（约 440MB），请稍候…” spinner 包裹首次加载；现有模型加载异常捕获继续回退词典模型。`DEMO_PIN` 非空时，侧边栏强制重新生成简报需要输入正确口令，错误口令不会进入 `generate_daily_brief()`；为空时保持本地原行为。
- 文档与云端限制：README 改为 Community Cloud 使用根目录 `requirements.txt`，列出 `OPENAI_API_KEY`、`FINBERT_LOCAL_FILES_ONLY="0"`、`FINBERT_BATCH_SIZE="8"`、`DEMO_PIN` 四项 Secrets，说明首次模型下载耗时、CPU 推理较慢、加载失败降级，以及容器文件系统和模型缓存易失；公开演示基准数据以仓库提交为准。
- 验证结果：`compileall` 通过；依赖逐行结构和 `setup_env.py` 过滤器检查通过；云端环境值与本地默认值检查通过；AST 检查确认 Secrets 桥接发生在配置导入前，错误 PIN 分支不会调用简报生成；本地无 Secrets 文件的异常类型可被静默处理。运行时代码 `src/`、`pages/`、`app.py` 的 Windows 盘符、`python.exe`、PowerShell、`cmd.exe`、`nvidia-smi`、`.ps1` 扫描命中数为 0，云端 Linux 运行路径不依赖 Windows 专属路径或命令。本轮未安装云端 CPU requirements，避免覆盖已验证的本地 GPU torch。

## 2026-07-11 03:11

- 阶段名称 / 本次操作目标：FinBERT 两段式加载与云端缓存未命中根治补丁
- 模型加载：`load_finbert_resources()` 不再依赖预先判定的布尔开关，而是始终先以 `local_files_only=True` 读取缓存；仅在确认缓存未命中时才以 `local_files_only=False` 重试。Streamlit 运行上下文中的第二段下载由 `st.spinner("首次启动正在下载 FinBERT 模型（约 440MB），请稍候…")` 包裹，命令行运行则打印同一提示；下载或其他加载错误仍由原有外层异常处理回退词典模型。`FINBERT_LOCAL_FILES_ONLY` 默认改为 `auto`，仅显式设为 `1`（以及等价真值）时启用严格离线并禁止第二段重试。
- 版本与鉴权：根据 Hugging Face 官方 `ProsusAI/finbert` main 历史锁定 `FINBERT_REVISION = "4556d13015211d73dccd3fdd39d39232506f3e43"`；tokenizer 和分类模型的缓存读取、联网下载均传入同一 revision。新增惰性 `HF_TOKEN` 读取，非空时传给两个 `from_pretrained()`，未配置时不传 `token` 参数，保持原行为。
- Secrets 与惰性配置：`app.py` 在 `st.set_page_config()` 和所有 `src.*` 导入前完成 `st.secrets → os.environ.setdefault` 桥接。检查 `config.py` 全部 `os.getenv` 后，将 FinBERT 加载模式、批大小、`DEMO_PIN` 和 `HF_TOKEN` 全部改为调用时读取；OpenAI key 原本已在简报调用时读取。这样即使配置模块较早导入，桥接后的 Secrets 仍不会因模块级常量定型而失效。
- 文档：README 改为说明默认两段式加载、严格离线开关、可选 `HF_TOKEN` 和固定 revision；云端 Secrets 示例删除不再需要的 `FINBERT_LOCAL_FILES_ONLY="0"`。
- 验证结果：`compileall` 通过；离线 fake loader 验证缓存命中不下载、缓存未命中按本地/联网顺序重试、spinner 只包裹第二段、严格离线禁止重试、`HF_TOKEN` 可选且 revision 在两段保持一致；模拟下载失败确认回退词典模型。AST 检查确认 Secrets 桥接早于页面配置和所有 `src` 导入，`config.py` 无模块级 `os.getenv` 求值。Windows 专属运行路径扫描为 0，凭据模式扫描为 0。本轮未进行真实联网下载，等待 Streamlit Cloud Reboot 实测。
