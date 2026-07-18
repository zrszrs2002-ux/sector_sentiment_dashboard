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

## 2026-07-11 05:04

- 阶段名称 / 本次操作目标：每日市场简报从数值播报升级为分析解读
- 数据包增强：`src/brief_builder.py` 将市场分数、前日差值、板块排名和异动指标统一保留一位小数；新增主题分布 Top 5、11 个板块的正负面新闻计数、最正面/最负面新闻各 Top 3（标题、板块、证据句）。新增市场指标近 7 日位置标签，只有存在 7 个独立日快照时才写入；当前真实数据只有 2 天快照，因此该字段按设计省略。风险类别计数显式转换为整数，避免 NumPy 整数在 JSON 中降级为字符串。
- 提示词升级：`src/llm_summary.py` 的运行时系统提示词改为“资深市场舆情分析师，为同事撰写次日晨读的深度简报”，保留严格接地、不预测价格、不给建议，明确允许指标定性解读、事件与板块关联解释、跨新闻主题归纳。输出结构改为核心观点、市场全景、板块与事件深读、风险与明日关注点、数据范围说明与免责声明，篇幅 600-900 字；禁止内部字段名和裸数字罗列。输出预算提高到 3200 token，避免推理消耗导致正文为空。
- 数字密度加固：提示词要求市场全景至少两段、每段不超过 4 个阿拉伯数字；同时仅对 AI 输出增加确定性段落拆分，按中文句号、问号、感叹号和分号在数字超限前换段，不改写任何词句。规则模板函数及无 key/API 失败降级路径不经过该处理，行为保持不变。
- 真实生成与验证：基于当前真实新闻 24 小时窗口生成 AI 简报；最终样稿覆盖 420 条新闻、3 个来源。第一次 AI 草稿用于发现数字密度问题；收紧提示词后的第二次请求返回空文本，系统按设计降级规则模板；提高输出预算后的最终请求成功生成 AI 简报并写入 `data/latest_brief.md` 与 `data/briefs/2026-07-11.md`。最终正文 692 个中文字符，每段最多 4 个数字，禁用内部词命中 0。增强数据包、7 日冷启动条件、规则模板兼容和 `compileall` 均验证通过。

## 2026-07-11 05:35

- 阶段名称 / 本次操作目标：深度简报篇幅扩展、模型候选链与实际模型署名
- 篇幅与重心：将 AI 晨读正文要求从 600-900 字替换为 900-1200 字，并要求“板块与事件深读”占全文约一半；只展开关注度、风险或情绪突出的 3-5 个板块，每个板块用 2-4 句说明指标水平、具体驱动新闻及二者印证关系，不重要板块不为凑数量罗列。输出预算由 3200 提高到 4600 token，以容纳更完整的板块分析和模型推理。
- 模型候选链：`config.py` 新增有序候选 `LLM_MODEL_BRIEF_CANDIDATES = ["gpt-5.6-terra", "gpt-5.5"]`。`_resolve_brief_model()` 每次读取账户模型清单并返回第一个可用候选，打印实际选择或前序候选不可用原因；全部不可用时才抛错进入规则模板。离线 fake client 已覆盖 Terra 优先、回落 5.5、全部不可用三种路径。
- 模型署名：AI 结果新增 `model_id`，`brief_generator.py` 将实际模型写入 `latest_brief.md` 和日期归档的 front matter，并在函数结果中返回；规则模板的 `model_id` 为空，元数据不写该字段。Market Overview 标题下方按“AI 生成 · 模型 ID · 简报时间”显示，规则模板仅显示来源和时间。README 同步候选链、篇幅与署名说明。
- 真实生成与验收：真实账户本次模型清单已包含 `gpt-5.6-terra`，因此候选链实际选择 Terra，而不是回落 5.5；最新简报和 `data/briefs/2026-07-11.md` 均写入 `model_id: gpt-5.6-terra`。基于当前 24 小时真实新闻窗口生成最终晨读，覆盖 404 条新闻、3 个来源；正文 1126 个中文字符，板块深读占 46.8%，每段最多 4 个数字，禁用内部字段命中 0。模拟规则模板生成确认不会写入模型元数据；`compileall` 与 `git diff --check` 通过。

## 2026-07-11 05:55

- 阶段名称 / 本次操作目标：模型候选链加固（灰度清单抖动与限流处理）
- 选择策略更正：上一条 DEVLOG 中“由 `_resolve_brief_model()` 读取清单后选择”的实现已被本次替换。`models.list()` 现在仅输出候选是否出现在账户清单中的参考信息；即使清单调用失败或未列出 Terra，也会按 `gpt-5.6-terra → gpt-5.5` 顺序直接尝试 Responses API，以真实生成请求结果作为可用性判断。
- 降级与重试：首选模型首次返回 429 时等待 `LLM_CANDIDATE_RATE_LIMIT_RETRY_SECONDS = 5` 秒并重试一次；再次失败才切换下一候选。模型不存在、无权限、429、容量或服务暂不可用会进入下一候选；其他错误直接进入规则模板，避免对明显的全局参数错误重复请求。所有候选失败后才走既有规则模板降级，管线不抛出外部 API 异常。
- 可追溯日志：每次生成均记录 `models.list` 参考、尝试模型、尝试次数、成功/失败分类、最终模型和选择原因；同一单行日志通过 `model_selection_log` 写入 `latest_brief.md` 与 `data/briefs/YYYY-MM-DD.md` front matter。无 key、LLM 关闭或 SDK 不可用时也记录“未发起请求”和规则模板原因；AI 页面署名仍只显示实际成功模型。
- 离线验证：fake OpenAI client 覆盖“清单无 Terra 但直呼成功”“Terra 连续两次 429 后切换 5.5”“模型不存在/无权限/503 容量错误后切换”“`models.list` 自身失败不阻断”“两候选均失败回退规则模板”。确认 429 调用顺序为 `Terra → 等待 5 秒 → Terra → 5.5`，等待仅一次，元数据日志保持单行；测试未发起真实 API 请求。

## 2026-07-11 07:30

- 阶段名称 / 本次操作目标：同事件折叠（事件级聚类）
- 聚类核心：新增 `src/event_clustering.py`，先按发布时间不超过 48 小时和 ticker 交集生成候选对；无 ticker 的 Unmapped 新闻允许比较，但使用更严格阈值。相似度通过独立 `SimilarityIndex` 接口注入，默认 `sentence-transformers/all-MiniLM-L6-v2` 归一化句向量余弦相似度（阈值 `0.72`，Unmapped `0.82`），模型或依赖不可用时自动回退内容词 Jaccard（阈值 `0.40`，Unmapped `0.55`）。向量只对候选对涉及的文章在内存中现算，不持久化。
- 数据与增量：processed schema 新增 `event_id`、`source_count`。并查集形成事件簇后，以簇内 `agg_weight` 最高文章的 `article_id` 作为全簇 `event_id`，并统计不同 RSS 来源数；单篇簇使用自身 ID。全量管线在文章评分后聚类；增量管线预先复用已有事件成员，只以新增文章驱动二分时间窗查询，比较“新增↔附近已有”和“新增↔新增”。历史数据缺少 `event_id` 时自动执行一次全量迁移。真实数据无新增测试候选对/向量数均为 0，总耗时约 0.007 秒。
- 依赖分层：按本阶段最新要求恢复 `requirements-full.txt`，固定 `sentence-transformers==5.6.0`，由本地 `setup_env.py` 在保留 GPU torch 后读取；云端 `requirements.txt` 不加入该依赖，构成 FinBERT + lexical 事件聚类路径。本机安装后确认复用 `torch 2.12.1+cu130` 和 RTX 4080 SUPER，embedding 实际运行设备为 CUDA；模拟模型异常可自动回退 lexical。
- 展示层：Top Drivers 改为每个事件一行，代表文章为最高 `agg_weight` 文章，簇级 `driver_score` 取簇内最大值；`source_count >= 3` 时仅对展示分数乘 `EVENT_COVERAGE_BOOST = 1.15`。多篇簇显示“另有 N 家媒体报道”并可展开全部可点击文章。Article Explorer 新增 `event_id` 列和“按事件分组”开关，分组后增加事件文章数与来源数。每日简报数据包的 Top Drivers 同步使用事件折叠结果。
- 六维边界：未修改 `dedup_factor`、`agg_weight` 或聚合公式。将聚类前备份与写回后的 2,037 条真实新闻按 `article_id` 对齐，`agg_weight`、`dedup_factor`、11 板块六维表和市场六维 dict 全部逐值一致。独立报道继续各自贡献 Attention/情绪；是否簇内降权仍留到第二冲刺。
- 真实数据结果：embedding 全量运行得到 1,716 个事件簇，其中多篇簇 172 个（占全部簇 10.02%），493 篇新闻进入多篇簇（文章覆盖率 24.20%），最大簇 25 篇。Apple/Broadcom 合作的 20 条标题明确归入同一主簇 `rss-9d53d9cf9bbfd98a`，该簇共 25 篇、覆盖 Yahoo Finance RSS 与 CNBC 两个来源。Demo 132 篇均为单篇簇。
- 引擎对比：同批 2,037 条数据用 lexical dry-run 得到 1,996 个簇、多篇簇 29 个、70 篇进入多篇簇（覆盖率 3.44%），比 embedding 多 280 个簇，说明 lexical 明显更保守。清晰的 embedding-only 合并包括 Apple/Broadcom 芯片合作、Microsoft 裁员 4,800 人并重组 Xbox、Tesla Robotaxi 扩展至 Miami；这些标题词面差异较大，lexical 未合并。
- 人工抽查：使用固定随机种子 5720 抽取 5 个 embedding 多篇簇。SK Hynix 美国上市/与 Micron 差距、Citigroup Q2 财报预览、7-Eleven 起诉 Nike 三簇语义一致；McDonald’s 当日上涨/长期机会/Russell 指数调整，以及 Wix 小盘软件推荐/估值回报两簇属于疑似不同事件误合并。按需求保留 `0.72` 配置值并在 README 标注 TODO，没有为美化结果暗调阈值。
- 验证：事件/增量/覆盖加成合成数据契约测试通过；`compileall` 通过；Streamlit AppTest 验证 Market Overview 无异常且生成多篇事件展开器，Article Explorer 分组态无异常并包含 `event_id`、`event_article_count`、`source_count`。本阶段尚未提交，等待验收确认。

## 2026-07-11 08:39

- 阶段名称 / 本次操作目标：六维指标增强版计算（PDF 第 6/9.2 节部分 enhanced）
- 单公式与权重组：`src/scoring.py` 和 `src/aggregation.py` 只保留一套公式实现，调用方通过 `BASELINE_WEIGHTS` / `ENHANCED_WEIGHTS` 传入完整权重组；`ACTIVE_WEIGHTS` 当前指向 enhanced。Baseline 的 Optimism/Fear 为 `1/0/0`，Uncertainty 为 `0.6/0.4/0`，Disagreement 为 `1/0`；Enhanced 对应 `0.7/0.2/0.1`、`0.4/0.3/0.3`、`0.5/0.5`。Risk Intensity 两组仍同为 `0.7*mean + 0.3*P90`，本批未改。
- 词典与组件：新增 `growth_keywords.json`（33 项）、`shock_keywords.json`（33 项）、`stance_keywords.json`（bullish/bearish 各 20 项）和公共句级归一化函数 `min(命中句数/总句数*3, 1)`。从 University of Notre Dame 的 Loughran-McDonald Master Dictionary 2026-03 版提取 297 个当前有效 Uncertainty 词，与原有 5 项合并去重后共 302 项；README 已补官方来源和 Loughran & McDonald (2011) 引用。
- 文章级结果保全：processed schema 新增 `b_bull`、`b_bear`、`g_growth`、`s_shock`、`k_unc`、`entropy_norm`。文章级 Optimism/Fear/Uncertainty 使用增强公式写入 ACTIVE 结果；FinBERT 三概率与六个组件同时持久化，因此任意权重组都可由 CSV 纯算术重算，不需要再次运行模型或词典匹配。增量管线遇到旧 processed 记录时会复用已有 FinBERT 概率补齐组件。
- 板块级增强：Disagreement 改为 `100*(0.5*加权标准差 + 0.5*PolarityMix)`，其中 `PolarityMix=2*min(PosShare,NegShare)`、情绪阈值为 `0.15`，少于 2 条保持 0。Attention 保留 7 天加权新闻量横截面排名冷启动；某板块历史达到 30 天后自动切换自身历史 `0.7*新闻量ECDF + 0.3*增长率ECDF`，并输出中文日志。当前真实历史只有 1 个已完成日，故两套公式均走冷启动路径。
- 快照双写：`sector_daily_scores.csv` / `market_daily_scores.csv` 新增 `formula_version`；每日分别 upsert baseline/enhanced 两套结果，旧历史行补标 baseline。板块快照同时持久化 `attention_volume`；迁移时旧行用 `article_count` 补齐，不再保留 `nan`。趋势图与简报加载器默认只读取 `ACTIVE_FORMULA_VERSION`。
- Evaluation 页面：新增 Baseline vs Enhanced 六维均值/标准差/范围表、每维排名变化最大的 3 个板块及组件原因、跨板块的具体新闻两套分数与变化值；输出分布同步加入六个组件字段。正式消融、显著性和敏感性分析仍留到第二冲刺。
- 真实数据重跑：使用本地 GPU FinBERT 与 CUDA embedding 对 Demo 132 条、真实新闻 2,088 条全量重跑，处理错误 0。真实数据非零组件覆盖：`b_bull=78`、`b_bear=29`、`g_growth=361`、`s_shock=60`、`k_unc=656` 条。
- 六维 Baseline→Enhanced：板块均值分别为 Optimism `36.49→27.86`、Fear `19.90→14.46`、Uncertainty `48.95→42.57`、Attention `50.00→50.00`、Disagreement `49.64→46.67`、Risk Intensity `75.98→75.98`。范围分别为 Optimism `31.91-40.64→25.03-30.35`、Fear `11.37-27.96→9.17-20.28`、Uncertainty `41.11-54.34→36.67-48.82`、Attention `4.55-95.45` 不变、Disagreement `39.13-61.51→32.74-60.38`、Risk `72.98-77.34` 不变。前三项均值下降主要来自 FinBERT 主概率权重下调，增强组件改变的是相对排序和事件敏感度，不保证所有新闻绝对分数上升。
- 排名变化：Optimism 最大变化为 Real Estate `9→7`、Healthcare `4→3`、Industrials `3→4`；Fear 为 Financials `6→5`、Consumer Staples `5→6`、Energy 保持第 1；Uncertainty 为 Communication Services `7→3`、Materials `4→8`、Healthcare `5→9`；Disagreement 为 Consumer Staples `9→6`、Consumer Discretionary `5→3`、Industrials `3→5`。Attention 因历史不足 30 天排名不变，Risk 因本批公式不变而排名不变。
- 方向性抽查：成长样例 `Shopify reinstated...Buy rating...growth outlook` 命中 `growth/expansion/buy rating`，Optimism `55.10→68.57`；`3M...Growth Trends Improving...` 命中 `growth/upside/buy rating`，`35.50→49.85`。冲击样例 `Cramer Just Turned Bearish...` 命中 `crash/bearish`，Fear `43.70→60.59`；`3 AI Chip Stocks to Buy as the Sell-Off Continues` 命中 `sell-off`，`2.10→11.47`。四条净变化方向均符合设计。
- 验证：新增 5 个标准库回归测试，覆盖文章公式、句级归一化、LM 合并、Disagreement、Risk 不变、旧 Attention 历史兼容和快照双写，全部通过。`compileall`、`git diff --check`、全部词典 JSON 解析通过；真实数据契约确认六个组件均在 0-1、两套板块六维均在 0-100、当天真实快照为 22 个板块行和 2 个市场行。随机 200 条由 CSV 重算 ACTIVE 文章分数最大差异 0.08，仅来自持久化小数位舍入。Streamlit AppTest 验证 Market Overview、Sector Comparison、Sector Detail、Evaluation 无异常，简报/趋势读取到的均为 enhanced 快照。
- 当前项目状态：本阶段实现与验证完成，尚未提交，等待用户验收确认后按流程执行 `git add -A` 并以本阶段名称提交。

## 2026-07-11 18:05

- 阶段名称 / 本次操作目标：六维指标增强版计算二次完整性审计与补交
- 审计原因：上一轮完成后 Git 提交曾被 Codex 审批额度限制阻断，用户要求先确认该阶段没有因额度耗尽而中断，再继续第二冲刺。
- 重新核对：直接审计 Git 索引中的独立阶段快照，确认 growth/shock/stance 与 302 项不确定性词典、两套完整权重组、六个持久化组件、增强版 Optimism/Fear/Uncertainty、PolarityMix Disagreement、30 天 Attention ECDF 切换、快照双写、ACTIVE 版本过滤、Evaluation 对照和 README 公式均已进入暂存快照。
- 重新运行：增强指标专属 5 个测试全部通过；真实 processed 共 2,088 条、处理错误 0，六个组件全在 0-1。随机 200 条由 CSV 纯算术复算 ACTIVE 文章分数的最大差异为 0.08，仅来自持久化舍入；baseline/enhanced 两套板块和市场六维均在 0-100。最新真实快照确认有 22 个板块行、2 个市场行，并同时包含 baseline/enhanced，`attention_volume` 无空值。
- 提交结果：确认阶段完整后提交为 `5e63439`，提交信息为“六维指标增强版计算（PDF 第 6/9.2 节部分 enhanced）”。本次二次审计未发现遗漏或半完成实现。

## 2026-07-11 18:20

- 阶段名称 / 本次操作目标：模型评估工具链（第二冲刺第一批）
- 分层盲标：新增 `scripts/sample_for_annotation.py`，从 `raw_articles.csv` 与 `real_processed_articles.csv` 按 `article_id` 一一对齐，以预测 sector × FinBERT 三分类做确定性轮询均衡抽样；容量不足的小层取尽后自动把余量分配给其他层。默认样本数 300、随机种子 5720，参数与路径集中在 config，并提供 CLI 覆盖。
- 正式样本：从 2,088 条候选中生成 `data/annotation/annotation_blind.csv` 和 `annotation_key.csv` 各 300 条，raw 未匹配数为 0。36 个交叉层全部覆盖，每层 3-9 条；Utilities-negative 原始容量只有 3 条，因此该层全部入样。blind 精确只有 11 个规定字段，标签列全空、ID 唯一，不含 sector、风险、证据句、情绪概率、置信度或任何 `predicted_*` 字段；key 与 blind 的 article_id 集合完全一致。
- 标注规范：新增 `docs/annotation_guide.md`，说明三类情绪、正负混合/纯事实/股价波动边界、10 类风险、证据句标准与格式。为解决 blind 文件不展示预测却要求 `sector_ok/evidence_ok` 的契约矛盾，采用两遍流程：主标注者第一遍只做情绪和风险并锁定；评估负责人第二遍保管私有 key，只完成板块和证据句对账，不修改第一遍标签。
- 指标引擎：扩展 `src/evaluation.py`，实现情绪 Accuracy、逐类 P/R/F1、Macro F1、3×3 混淆矩阵；同一标注集上的全中性基线、现有词典 fallback、FinBERT 三方对比；板块映射 Accuracy；风险多标签逐类 P/R/F1 与 10 类等权 Macro F1；证据句 Precision；10 桶 FinBERT 可靠性数据与标准多分类 Brier score。非空但非法标签、重复 ID、空 ID、key 未匹配 ID 会明确报错，不静默丢样本。
- 词典对比：在 `sentiment_model.py` 增加强制词典入口，复用现有 fallback 的句级打分，同时保持与 FinBERT 完全相同的分句、置信度加权文章聚合和证据逻辑，没有另写近似词典公式。
- 错误分析：所有 FinBERT 情绪误判按 article_id、标题、真实标签、预测标签和置信度写入 `data/annotation/sentiment_errors.csv`；相同内容不会重复写入或制造备份。Evaluation 页面支持按真实/预测标签过滤并下载筛选结果。
- 页面：Evaluation 顶部明确本页只评估分类层，六维敏感性/消融另行实现；加入三方对比表、可切换引擎的混淆矩阵热力图、逐类指标、Brier、可靠性曲线、板块/风险/证据指标和错误浏览。原六维对照保留在折叠的“描述性对照（非稳健性验证）”区块。页面后台读取私有 key，但不渲染或提供下载。
- 30 条假标注验证：构造 negative/neutral/positive 各 10 条，FinBERT 每类故意错 2 条。手算与程序一致：混淆矩阵每类对角线 8、环形误判 2，故 Accuracy=`24/30=0.8`，每类 P/R/F1 与 Macro F1 均为 0.8；全中性基线 Accuracy=`10/30=1/3`、Macro F1=`1/6`；词典引擎在定向测试文本上为 1.0。第二个手算核对：正确样本概率 `[0.8,0.1,0.1]` 的 Brier 为 0.06，错误样本为 1.46，`(24*0.06+6*1.46)/30=0.34`，与程序一致。另验证板块 Accuracy 0.9、证据句 Precision 0.8、风险 Macro F1 0.24、误判 CSV 6 行。
- 遇到的问题和修复：首次文件级测试发现 Pandas 将 `0/1` 读成整数，旧布尔归一化把整数 0 当作空值；修正为先判断 NaN、再直接字符串化。修复后全部 8 个标准库测试通过。
- 页面与静态验证：Evaluation 空白冷启动和 30 条已标注完整状态 AppTest 均通过，页面指标显示 FinBERT Accuracy 0.800、Macro F1 0.800、Brier 0.340；`compileall` 与 `git diff --check` 通过。运行时代码未新增 Windows 路径或凭据。
- 当前项目状态：本阶段实现、正式抽样和验证已完成，尚未提交，等待用户验收确认后按阶段流程提交。

## 2026-07-11 20:55

- 阶段名称 / 本次操作目标：P0 信号质量修复（风险强度失效 + 事件聚类过度合并）。本批只修信号计算、数据与说明，未调整 UI 样式。
- Risk Intensity：移除未知风险默认严重度和 macro 默认兜底；未命中风险时类别为空、强度为 0。风险标签改为分号存储的多标签，每类复用公共句级关键词密度 `r_k=min(命中句子数/总句子数*3,1)`，文章公式统一为 `100*clip(sum((v_k/5)*r_k),0,1)`。情绪/不确定性压力开关保持默认关闭，严重度上限与密度系数集中到 config 并标注待校准。
- 词典修复：macro risk 删除 `macro` 等泛化单词，只保留 recession、stagflation、hard landing、inflation shock 等强信号；inflation、economic slowdown、consumer weakness 等弱信号必须同文命中至少 2 个不同词。主题词典新增 AI infrastructure spending、chip supply deal、streaming、EV demand、bank earnings、drug approval、dividend、share buyback、analyst rating、space economy、corporate restructuring 等细分主题。
- 公共实现：新增 `src/keyword_matching.py`，集中维护边界化关键词匹配、不同命中词去重和句级密度归一化；增强六维组件与风险标签共同调用，避免两套近似公式。新增 `tests/test_signal_quality.py` 覆盖无风险为 0、单个/两个 macro 弱词、多标签精确求和、72 小时链式阻断、极性护栏和分号来源计数。
- 聚类护栏：config 新增 `EVENT_MAX_SPAN_HOURS=72` 和 `EVENT_POLARITY_GUARD_THRESHOLD=0.30`。并查集在每次合并前检查两簇合并后的最早/最晚发布时间，超过 72 小时拒绝；一正一负跨越阈值的文章在相似度计算前禁止连边。`source_count` 按分号/竖线拆分后去重，Top Drivers 不再用过期持久化计数覆盖当前真实来源数。
- 快照连续性：新增 `PIPELINE_REVISION="r2"`，板块/市场快照增加 `pipeline_revision`；旧行自动补 `r1`，本次重跑新增 22 条板块 r2 行和 2 条市场 r2 行。README 数据字典说明该字段用于解释趋势中的公式修订断点。
- 全量重跑：使用本地 CUDA FinBERT 与 CUDA sentence-transformers 对 2,154 条真实新闻完整重跑，处理错误 0。新 Risk Intensity 均值 9.7203、标准差 22.6524，中位数 0、P90 40、范围 0-100；无风险 1,760 条，持久化后一共有 20 个不同取值，不再只有 40/60/80/100 四档。
- 分布变化：macro risk 从 1,718 条降到 5 条；其余主要类别为 valuation 167、commodity 67、interest rate 64、earnings 51。general market sentiment 从 1,504 条降到 1,028 条；Technology 内从 285 降到 181，降幅约 36.5%，新增 dividend、analyst rating、AI demand、space economy、streaming、AI infrastructure spending 等可解释类别。
- 聚类结果：事件簇从 1,794 增至 1,818，多篇簇 178 个；最大簇从 26 降到 16，最大时间跨度精确受限为 72 小时，超过 72 小时的簇由 10 个降为 0。Apple/Broadcom 核心合作报道仍形成 16 篇主簇（51.324 小时、Yahoo/CNBC 两个真实来源）；较晚批次按跨度拆为 9 篇和 1 篇。原 Meta 14 篇混合簇拆成 13 篇非强负向簇与 1 篇强负向单篇；13 篇簇的 `source_count=3`，实际来源确为 Yahoo Finance、CNBC、MarketWatch，不是 ticker feed 重复计数。
- 人工抽查：固定种子 5720 的 5 个多篇簇中，Exxon/Chevron 对比 2 篇、Chevron 技术许可 3 篇、Chevron/Alinta 供气协议 2 篇语义一致；Chevron 4 篇推荐/数据中心叙事和 Microsoft 6 篇成本削减/Copilot/投资/估值叙事仍疑似同公司不同事件误合并。该残余问题需要后续引入簇代表一致性或 complete-link 约束评估，本批按批准范围只实现时间跨度与强极性护栏，未暗调 embedding 阈值。
- 验证：新增 `scripts/validate_p0_signal_quality.py`，可直接从 Git HEAD 读取 r1 CSV 并与当前 r2 做可重复对比；14 个标准库测试、`compileall`、词典 JSON 解析与 `git diff --check` 全部通过。当前阶段尚未提交，等待用户验收后再按流程提交。

## 2026-07-11 21:11

- 验收与提交：用户确认 P0 信号质量修复验收通过，批准按阶段流程执行 `git add -A` 并以本阶段名称提交。
- 延期事项 1：Chevron 与 Microsoft 的混叙事簇已登记，complete-link 或簇代表一致性约束留待后续批次，本批不继续修改事件聚类。
- 延期事项 2：macro risk 词表暂不继续手工调节；待人工标注评估给出 precision/recall，尤其是召回率后，再依据数据调整强弱词和触发门槛。

## 2026-07-11 21:51

- 阶段名称 / 本次操作目标：数据源扩展与选择性正文抓取。RSS 配置外置、真实出版方、来源质量权重、Trafilatura 正文缓存和 r3 快照连续性在同一批落地。
- RSS 外置与实测：新增 `data/rss_sources.json` 和严格配置加载器，运行时代码不再硬编码 Yahoo/CNBC/MarketWatch URL。最终启用 20 个源：Yahoo ticker template；CNBC Top/Markets/Technology/Economy/Earnings/Business；MarketWatch Top/Real-time/Market Pulse；Google News Business/Markets；Nasdaq Markets/Earnings；Benzinga Markets；Motley Fool；Investing.com Stock Market News；Fortune；Business Insider；NYT Business。最终实跑 62 个具体 feed（其中 Yahoo 43 个 ticker），全部成功，解析 1,285 条。
- 候选淘汰：Motley Fool 旧入口首测短暂为 0 条、复测恢复 50 条后纳入；其 `/a/feeds/foolwatch` 入口持续 401。Fortune Finance 为 404；WSJ Markets 虽返回 20 条，但发布时间全部停在 2025-01-27，按陈旧失效排除。Nasdaq Technology、Benzinga root 和 Business Insider custom/all 可解析但与已选源高度重复，未重复收录。
- Publisher：从 RSS entry 的 `source/publisher/dc_publisher` 依次提取真实出版方，缺失时回退 feed 名；重复 URL+标题会合并 publisher。事件 `source_count`、Top Driver 覆盖加成、市场总览“覆盖出版方数”、简报覆盖和 Evaluation 覆盖统一改为 publisher 口径，并对 Demo/旧空值逐行回退 source。历史 entry 未保存出版方时保留 feed 名是预期迁移限制。
- 来源权重：`agg_weight` 改为 `time_weight * relevance_weight * dedup_factor * source_weight`。权重从外置 JSON 读取，取值覆盖 `0.8/0.85/0.9/0.95/1.0`；跨 feed 合并取最大权重。2,535 条最终 processed 数据按持久化小数复算的最大绝对误差为 `6e-7`。权重是待人工标注校准的来源类型先验。
- 选择性正文：新增 `src/fulltext_fetcher.py` 和 `trafilatura==2.1.0`。候选限定为 UTC 当日的 Top Driver、`|sentiment_score|>=0.5`、`risk_intensity>=60` 或多篇事件代表，按优先级排序并每轮最多 30 篇；请求间隔至少 1 秒、超时 10 秒、单篇失败不重试。付费墙/聚合跳转源由配置禁止正文。缓存同时记录成功正文和失败尝试，article_id、URL、规范化标题任一已缓存即不再请求。
- 正文数据契约：新增 `body_text/content_level/rescored`；`content` 继续等于 RSS 摘要。成功正文批量重跑 FinBERT、证据句、风险、主题与文章评分，并在简报 Top Driver 中优先采用同事件 fulltext 证据句。页面代码不引用 `body_text`，Article Explorer 只显示 publisher、权重和正文级别标记。
- 真实运行：首轮 19 源解析 1,265 条、新增 338 条，正文 30 次请求成功 26、失败 4，RSS 27.0 秒、正文 41.4 秒、总计 85.5 秒。加入 Motley Fool 后最终 20 源解析 1,285 条、新增 24 条，正文缓存排除首轮对象后仅剩 11 个候选，成功 10、失败 1，RSS 31.1 秒、正文 15.3 秒、总计 60.4 秒。两轮合计正文成功 36/41（87.8%），平均正文长度 4,030 字符；最终 raw/processed 各 2,535 条。
- 摘要/正文样例：`Palo Alto Networks May Need a Breather...` 从 `-0.782` 变为 `0.385`，新证据句为 “Guidance implied $3.35 billion...” ；`3 Phenomenal Artificial Intelligence...` 从 `-0.963` 变为 `0.090`，证据句转为 TSMC 市场地位与执行；`Oil Prices Are Plunging...` 从 `-0.917` 变为 `0.030`，证据句转为对大盘涨势基础的审慎判断。三个例子表明标题/短摘要的极性可能被正文语境显著修正。
- r3 连续性：`PIPELINE_REVISION` 升为 `r3`，原因是源结构和来源权重会改变新闻量、Attention 与所有加权指标。快照 upsert 主键补入 `pipeline_revision`，并从已提交 P0 数据恢复同日 r2；当前板块快照 `r1/r2/r3=66/22/22`，市场快照 `6/2/2`，同日修订不再互相覆盖。
- 验证状态：现有 14 项测试和新增 6 项来源/正文测试分别已通过；两轮真实抓取、JSON 解析、CSV schema、正文不展示、`content==summary`、publisher 非空、Linux 运行路径和 `git diff --check` 均已验证。最后一次合并后的全套测试复跑因 Codex 本地执行额度在 23:16 前受限而未执行，需额度恢复后补跑；这不是测试失败，当前阶段保持未提交。

## 2026-07-11 23:41

- 最终验证补跑：执行额度恢复后完成 `python -m compileall -q src pages scripts tests` 和完整 `unittest discover`；21 项测试全部通过，覆盖原有六维/评估/P0 回归，以及本阶段 RSS 外置配置、publisher 回退、source_weight 算术、正文候选缓存与去重、付费墙禁抓、简报优先 fulltext 证据和 r2/r3 同日快照并存。
- 当前项目状态：本阶段代码、真实数据、README、DEVLOG 和验证均已完成；按要求保持未提交，暂停等待用户验收。

## 2026-07-11 23:43

- 页面与数据终验：重新运行 `scripts/validate_data_source_extension.py`，确认 20 源、2,535 条 processed、36 条 fulltext/rescored、来源权重误差 `6e-7` 和 r1/r2/r3 快照数量不变；Market Overview 与 Article Explorer 的 Streamlit AppTest 均为 0 异常。Streamlit 仅报告项目原有 `use_container_width` 弃用提醒，不影响本阶段功能。

## 2026-07-12 01:43

- 阶段名称 / 本次操作目标：正文重打分信号稀释修复补丁。正式六维与排序口径恢复为标题+摘要，正文只保留并行评估信号、标签补充和高质量证据句。
- 正式评分口径：sentiment_score、三类 p_*、Optimism、Fear、Uncertainty 统一由摘要批次计算；全句平均对长文本存在中性稀释，因此正文不再覆盖聚合与排序字段。
- 正文并行口径：processed schema 新增 sentiment_score_fulltext、p_positive_fulltext、p_neutral_fulltext、p_negative_fulltext，仅供第二阶段“摘要版 vs 正文版”标注评估，不参与排序或聚合。
- 正文保留价值：证据句优先正文风险句和正文高信号情绪句；风险类别取摘要/正文并集且强度取较大值；主题仅在摘要落入 general market sentiment 兜底时由正文补充细分类，摘要已有具体主题不会被覆盖。
- 数据迁移：关闭网络抓取，以本地 GPU FinBERT 对 36 篇已缓存正文执行摘要/正文双批次重算；36 篇全部成功，2,535 条 processed 历史记录完整保留。
- 验证：摘要 |s| 均值从错误正文口径的 0.211250 恢复为 0.470806，与迁移前缓存抓取时分布完全一致；正文并行 |s| 均值保留 0.211250，四个并行列 36/36 完整，34/36 证据句可直接定位到正文。

## 2026-07-12 02:54

- 阶段名称 / 本次操作目标：P1 UI 与展示修复批（9 项）。本阶段由主对话助手 Claude 直接执行（非 Codex）。
- 具体做了什么：1) 新增 `src/ui_helpers.py::render_sector_heatmap()`，市场总览与板块比较共用：六个维度按方向独立着色（乐观度高=绿、恐惧度/不确定性/分歧度/风险强度高=红反转色阶、关注度用蓝色系中性热度），色阶统一固定 0-100，附配色说明 caption；两页原 px.imshow 单色阶热力图移除。2) 市场总览"数据更新时间"指标卡改为 MM-DD HH:MM 短格式，完整 UTC 时间移入 help 提示。3) 板块比较"板块指标表"统一 1 位小数、新闻数取整、表头汉化并固定列序；六个排名速览表（新增"关注度最高"补足六维）以 2 行 × 3 列布局展示并加中文标题。4) 每日简报卡片顶部新增 st.info 窗口说明：简报所基于的新闻条数（取自 data_snapshot_id）、数据窗口起止、生成时间，并注明与页面实时窗口数字可能不同。5) 板块详情趋势图图例、图例标题、坐标轴标题全部汉化（复用 METRIC_LABELS）；正负新闻表情绪分改 3 位小数格式。6) Top Drivers 理由文案去实现细节：移除"事件分数乘以 1.15"表述，媒体覆盖加成改为"获 N 家媒体共同报道，重要性上调"，理由模板集中在 `src/driver_analysis.py`。7) 文章浏览器两个开关移至页面标题之下的选项行；数值列增加格式配置（0-100 指标 1 位小数、情绪分 3 位、权重 4 位）。8) 乱码项核查结论：存量数据 0 条 U+FFFD、0 条 cp1252 伪码，此前审计所见"It??s"为 GBK 控制台渲染 U+2019 的显示假象，故不执行存量迁移；在 `src/preprocessing.py` 新增 `repair_mojibake()` 并接入 `news_collector.strip_html()` 作为对未来编码异常源的防御。
- 额外修复（目检发现的连锁 bug）：P0 之后 82% 文章 risk_category 为空，文章浏览器风险筛选用 isin 精确匹配导致空标签文章被静默排除（2478 条只显示 448 条）；重写为集合匹配：risk_category 按分号拆分为标签集，空集归入"无风险"选项，任一选中标签命中即保留。修复后默认全选显示 2478 条。
- 遇到的问题和解决方案：本机终端为 GBK 编码，直接打印含弯引号文本会 UnicodeEncodeError/显示为乱码，改用 `python -X utf8` 与 ascii() 转义核查，确认数据本身干净。
- 当前项目状态：compileall 通过；21 项单元测试全部通过；本地 Streamlit 五页逐页目检通过（热力图双页配色、指标卡、排名表标题、简报窗口说明、趋势图例、浏览器布局与筛选计数均符合预期）。本阶段未提交。
- 下一步计划：等待用户验收；验收后可提交，随后进入整体页面复查与人工标注阶段。
## 2026-07-12 05:52

- 阶段名称 / 本次操作目标：评估页盲标 CSV 一键下载补丁。把原先需要手动运行 `scripts/sample_for_annotation.py` 的流程接入 Streamlit Evaluation 页面。
- 页面能力：新增抽样条数和随机种子控件，点击“生成/刷新盲标样本”会复用既有分层抽样逻辑，同步刷新 `annotation_blind.csv` 与私有 `annotation_key.csv`；已有盲标文件时页面直接显示“下载待标注 CSV”按钮。
- 盲标边界：下载给标注者的 CSV 仍只含 article_id、title、summary、content、url、published_at 和待填标签列；对账 key 放入折叠区并提示不得提供给标注者。
- 验证：`pages/5_Evaluation.py` 与抽样脚本 py_compile 通过；临时目录烟测生成 5 条样本，盲标列不含任何 predict 字段；`git diff --check -- pages/5_Evaluation.py` 通过。

## 2026-07-12 19:55

- 阶段名称 / 本次操作目标：评估页标注流程页面化（去掉命令行步骤）。
- 抽样内核：新增 `src/annotation_sampling.py`，将分层抽样、盲标/私有 key 安全写入和已填写标签计数收敛为可复用函数；`scripts/sample_for_annotation.py` 保留为调用相同内核的命令行薄壳。`config.py` 新增固定的 `ANNOTATION_SAMPLE_SEED = 5720`，保留旧常量别名以兼容已有调用。
- 页面流程：`pages/5_Evaluation.py` 改为“获取盲标样本 → 离线填写 → 上传与结果”三步布局。仅点击“生成 300 条盲标样本”才会生成文件；下载采用 UTF-8-SIG。页面同时提供标注手册下载，明确 `annotation_key.csv` 仅供后台对账且不再提供任何下载入口。
- 重抽样护栏：检测到四类标签列已有填写时，显示已填写单元格数与备份提示；必须勾选“我确认放弃...”后生成按钮才解除禁用。`notes` 不计入已填写标注数。
- 验证：`py_compile` 通过；真实页面 AppTest 0 异常且页面加载前后 `annotation_blind.csv` 修改时间不变；隔离 AppTest 中 3 个已填标签时按钮初始禁用、勾选后解锁；临时 3 条假标注可得 3 条情绪评估、三方对比与混淆矩阵输入；21 项单元测试全部通过。
## 2026-07-12 20:10

- 小补丁：盲标 CSV 的 `url` 列支持 Excel 一键跳转。`src/annotation_sampling.py` 对 HTTP/HTTPS URL 生成 `HYPERLINK()` 公式，显示“打开原文”；空值、非 URL 值和已格式化公式保持原样。`pages/5_Evaluation.py` 的下载路径也会执行同一格式化，因此已存在的旧盲标样本无需重新抽样即可下载为可点击链接。
- 文档与验证：标注手册补充 `url` 只读及点击说明；抽样契约测试新增超链接断言。已验证公式 Unicode 显示文本为“打开原文”、重复格式化不嵌套、页面 AppTest 0 异常并仍显示盲标 CSV/手册两个下载入口。
## 2026-07-13 06:10

- 阶段名称 / 本次操作目标：评估页抽样参数控件与盲标批次元数据持久化。
- 具体做了什么：在 Evaluation 页面“步骤 1：获取盲标样本”恢复“抽样条数”和“随机种子”控件，默认分别读取 `ANNOTATION_SAMPLE_SIZE=300` 和 `ANNOTATION_SAMPLE_SEED=5720`，点击生成时将两项参数传入既有确定性分层抽样。新增 `data/annotation/annotation_meta.json`，持久化当前批次实际条数、种子、UTC 生成时间和 article_id 指纹；blind/key 写入后以原子替换方式写入元数据。页面从该文件读取，并在指纹和条数与当前 blind CSV 对账成功后才显示“当前样本种子”和生成时间，应用重启不会误显示输入框默认值。README 与标注手册同步说明页面可配置种子，报告应以 metadata 中最终批次种子为准。
- 历史批次迁移与验收：在临时目录按 5720 重建当前 300 条真实新闻盲标，article_id 顺序与历史 `annotation_blind.csv` 精确一致后，才为当前批次写入 metadata；生成时间使用该 blind 文件原始 mtime `2026-07-12T11:18:58.346933+00:00`。真实新闻池验证 `5720 → 1234 → 5720`：1234 的 article_id 集合不同，恢复 5720 后按顺序精确复现。Streamlit AppTest 0 异常，确认两个控件存在且无 session 加载时显示持久化种子 5720。
- 验证：`python -m compileall -q src pages app.py` 通过；完整 `python -m unittest discover -s tests` 运行 21 项、全部通过；`python -m unittest discover` 默认未进入 tests 目录而显示 0 项，故不作为验收结果。
- 当前项目状态：本阶段实现、历史批次 metadata、文档和验证均完成，尚未提交，等待用户验收后按阶段名称提交。
## 2026-07-13 06:40

- 阶段名称 / 本次操作目标：市场总览 Top Market Drivers 时效窗口修复。
- 具体做了什么：在 `config.py` 新增 `DRIVER_WINDOW_HOURS = 48` 与 `DRIVER_MIN_EVENTS = 5`。`top_driver_articles()` 新增可选时间窗口路径：先按发布时间筛选，再做事件折叠与排序；市场总览显式启用该路径，窗口内少于 5 个事件时依次从 48 小时扩至 72、168 小时，返回结果通过 DataFrame attrs 携带实际窗口。市场总览标题改为 `Top Market Drivers（近 N 小时）`，如实标注实际使用窗口。README 说明页面从 48 小时起步、新闻荒自动扩窗；每日简报保持既有 24 小时数据包与调用逻辑不变，因此两者窗口不同是预期设计。
- 边界与测试：`driver_score` 公式、六维聚合、brief_builder 与 fulltext 候选逻辑均未改。新增两项回归：5 天前高风险新闻在明确 48 小时窗口中被排除；48 小时只有 2 个事件时自动扩到 72 小时并纳入 5 个事件。`compileall` 通过；完整 `unittest discover -s tests` 共 23 项通过。真实市场总览工作集 2,914 条，实际使用 48 小时，5 个 Top Drivers 均不早于窗口下界；Market Overview AppTest 0 异常且标题显示 `Top Market Drivers（近 48 小时）`。
- 当前项目状态：本阶段实现、文档与验证完成，尚未提交，等待用户验收后按阶段名称提交。
## 2026-07-13 07:00

- 阶段名称 / 本次操作目标：Top Market Drivers 窗口切换与宏观保底排序修复。
- 具体做了什么：市场总览在 Top Market Drivers 标题下加入横向 radio：“近 48 小时”（默认）与“近 30 天”。两种模式复用 `top_driver_articles()` 的同一筛选、事件折叠和排序路径：48 小时模式保留 48→72→168 小时自动扩窗；30 天模式传入 `WORKING_SET_DAYS * 24 = 720`，候选窗口只有 720 小时，故不扩窗且标题显示“近 30 天”。页面以占位标题先占据 radio 上方位置、再在 radio 状态确定后填入实际窗口，解决 AppTest 切换重跑时序问题。
- 宏观保底修复：Unmapped 宏观事件仍保证入选，但不再固定置顶。若它未自然进入前 5，则替换最低普通事件，随后所有入选事件按 `driver_score` 降序重排；仅此类保障性入选记录标记 `macro_guaranteed=True`，页面元信息显示“宏观保底”。README 同步两窗口语义和宏观按分数落位规则；driver_score、六维聚合、简报 24 小时逻辑和正文候选逻辑未改。
- 验证：新增 30 天不扩窗、宏观保底仍入列且最低分落第 5 位/最终分数降序两项回归（并保留上一轮旧高风险过滤与扩窗测试）。`compileall` 通过；完整 `unittest discover -s tests` 共 25 项通过。AppTest 验证默认 48 小时切换至 30 天 0 异常，标题同步为 `Top Market Drivers（近 30 天）`。真实工作集验证短窗 5 条使用 48 小时、长窗 5 条固定 720 小时，均满足窗口时间边界和分数降序；两种模式当前各有 1 条宏观保底事件。
- 当前项目状态：本阶段的时效窗口修复与本次窗口切换/宏观排序增量均已完成，尚未提交，等待用户验收后按阶段名称提交。
## 2026-07-13 07:45

- 阶段名称 / 本次操作目标：Tier-A：六维公式优化第一批 + 热力图相对化展示。
- Fear 与方向门控：新增 `panic_keywords.json`，Fear 的 persisted `s_shock` 改只读市场恐慌/避险反应词；`shock_keywords.json` 保留风险事件审计分组但不再进入 Fear。新增 `positive_direction_blockers.json`，同句同时命中 growth/bullish 与 slow/slowing/misses/cut/weak/decline 等反向修饰时不计正向组件。真实样例验证：Costco 的“growth…slowdown”、McDonald’s 的“Overweight rating…reduced”、GE/Lockheed 的“growth…lower”均保留原文但 `g_growth/b_bull=0`。
- Risk 与 Disagreement：文章级 Risk 默认改为 `RISK_COMBINE="noisy_or"` 的有界联合，`sum` 作为消融开关保留；板块 Risk 先按 event_id 取最高 agg_weight 代表，使用加权 P90。Disagreement 默认改为无阈值的加权成对绝对情绪距离，旧 `legacy_std_mix`/PolarityMix 保留为 config 消融开关。Risk、Fear 语义和公式说明已同步 README/Evaluation。
- 快照与热力图：`PIPELINE_REVISION` 升为 r4；sector snapshot 新增 `event_count`、`publisher_count`，r1-r3 历史行保留空值，今日 r4 两个数据源/两套公式共 44 行均完整。市场总览与板块比较的热力图默认按维度内板块 min-max 相对位置上色，数字/hover 仍显示原始分，并提供“绝对 0-100 定标”切换。
- 全量重跑与验证：Demo 全量处理 132 条，真实新闻全量处理 2,976 条，CUDA embedding 聚类成功。真实跨板块 std r3→r4：Optimism `2.1196→2.1574`、Fear `3.3836→3.3343`、Uncertainty `2.8536→2.8536`、Attention `28.7480→28.7480`、Disagreement `9.2288→3.6529`、Risk `7.1401→6.9608`。Risk 分布为 `0:2462, 0-5:8, 5-20:28, 20-40:212, 40-60:173, 60-80:52, 80-100:41`。Fear–Risk 排名相关性 `-0.3545→-0.3727`，绝对值略增 0.0182，未出现预期下降，已如实记录，未为追逐该统计量额外调参。
- 验证与验收：`compileall` 通过；完整 `unittest discover -s tests` 27 项通过；市场总览与板块比较 AppTest 的相对/绝对热力图切换均无异常。Playwright 前置检查发现本机缺少 npx，未绕过技能执行浏览器截图；用户已用其他工具完成两种模式的视觉核对并验收通过。
- 当前项目状态：Tier-A 完成，等待按阶段名称提交。

## 2026-07-13 07:56

- Tier-A 验收补记：外部浏览器已核对市场总览与板块比较两页热力图的“横截面相对 / 绝对 0-100”两种模式；相对模式逐列分化正常，绝对模式与旧行为一致，caption 会随模式正确切换。按验收结论跳过本地 Playwright 截图步骤。
- Fear–Risk 解耦口径修正：文章级 Pearson 相关性为 `0.034`（`n=2,976`），接近独立，可作为解耦成功的有效验证；11 个板块的排名相关性样本过小，不再作为验收指标，原先“预期下降”的要求作废。
- 分歧度解释补记：跨板块 std 从 `9.2288` 降至 `3.6529` 是移除 PolarityMix 后的可预期代价；旧 `legacy_std_mix` 公式仍由 config 开关保留，供第二阶段消融对比。
- 当前项目状态：Tier-A 已通过验收，准备按阶段名称提交。

## 2026-07-19 04:50

- 阶段名称 / 本次操作目标：人工标注完成：300 条盲标合并与归一化。
- 具体做了什么：300 条盲标已由标注者在 Excel 中完成，并经外部修复合并回 `data/annotation/annotation_blind.csv`；同时保留 `annotation_manual_raw.csv` 作为标注者原始填写审计文件及对应备份。人工标注文件未在本阶段清理、格式化、重新生成或重新抽样。
- 验证：合并后的盲标 article_id 指纹与 `annotation_meta.json` 校验通过。
- 当前项目状态：人工标注成果已整理完毕，待阶段验收后按阶段名称提交；`sentiment_errors.csv` 为评估管线衍生输出，本阶段排除并保持未跟踪状态。

## 2026-07-19 06:58

- 阶段名称 / 本次操作目标：阶段 1.5 范围收缩为仅色阶按模式区分（用户验收决定）。
- 具体做了什么：先用 `git restore` 将原未提交阶段 1.5 的文字选色、gamma、色带压缩、caption、测试与文档改动全部恢复到 `9cb340c`；随后仅将 `_HEATMAP_COLOR_SCALES` 拆为 relative/absolute 两套命名色阶，并让 `render_sector_heatmap` 按 `color_mode` 取色。相对模式使用 `Greens / Blues / RdYlGn_r`；绝对模式使用 `Greens / Reds / Blues / RdYlGn_r`，Fear 高值保持红色方向。保留 HEAD 的 `texttemplate`、`textfont={"size": 11}`、hover、caption 与线性定标，不另加对比度映射算法。
- 验证：`python -m compileall -q src pages app.py` 通过；`python -m unittest discover -s tests` 共 28 项全部通过；AppTest 实际打开市场总览与板块比较两页，并分别验证“横截面相对 / 绝对 0-100 定标”，四次渲染均为 0 exception。仅出现既有 `use_container_width` 弃用警告。
- 当前项目状态：阶段 1.5 收缩版代码、轻量结构测试、README 与验证均完成，等待用户验收后按阶段名称提交；外部抓取产生的数据、缓存、快照、备份，以及 `.claude/`、`sentiment_errors.csv` 均保持原样并排除在本阶段之外。

## 2026-07-19 07:40

- 阶段名称 / 本次操作目标：相对模式单色渐变色带压缩（外部直接修改，非 Codex 会话产出）。
- 具体做了什么：在阶段 1.5 收缩版基础上，`src/ui_helpers.py` 新增 `_SEQUENTIAL_SCALES`（Greens/Blues/Reds）与 `_SEQUENTIAL_BAND=(20.0, 85.0)`；`heatmap_color_values` 增加 `sequential` 参数，相对模式下单色渐变列的色带行程线性压缩到 [20, 85]，避免最低板块渲染成近白、最高接近纯黑；发散色阶（RdYlGn_r）与绝对模式完全不变。`render_sector_heatmap` 按该列色阶是否单色渐变传入 `sequential`。texttemplate、textfont、hover、caption 均未改动。
- 验证：`python -m compileall -q src pages app.py` 通过；`python -m unittest discover -s tests` 共 29 项全部通过（新增 1 项覆盖色带压缩端点、平值与绝对模式不受影响）。浏览器实测：乐观度列最浅格由近白 rgb(247,252,245) 变为可见浅绿 rgb(194,231,187)，最深格由近黑变为 rgb(7,115,49)；关注度同步收窄；恐惧度等 RdYlGn_r 列仍为全程饱和色。数据双簇（22-24 与 28.6-30.3）的色差仍可辨识，为真实分布信息。
- 当前项目状态：与阶段 1.5 收缩版一并等待用户验收后按阶段名称提交。

## 2026-07-19 07:43

- 阶段名称 / 本次操作目标：简报历史快照多版本选择修复。
- 具体做了什么：修复真实新闻简报在 UTC 日期边界回看 `2026-07-12` 快照时，同一板块同时存在 r3/r4 两行而使 `.loc[sector]` 返回 DataFrame、后续 Series 参与 `or 0` 抛出歧义异常的问题。新增统一快照选择逻辑：每个键优先采用当前 `PIPELINE_REVISION`，缺失时按 `snapshot_timestamp` 取最新行；市场级上一期采用相同规则，`_sector_movers()` 入口再做防御性唯一化。历史 r3/r4 快照数据完整保留，未清理或重写。
- 验证：新增 2 项回归测试覆盖板块 r3/r4 优先选择、无当前版本时最新时间回退、市场级同日多版本选择及 movers 标量差值；当前真实数据上一期从 22 行收敛为 11 个唯一 r4 板块，`build_brief_payload()` 成功返回 5 个唯一 movers；完整 `generate_daily_brief(force=True)` 调用链在 Mock LLM/写入下返回 generated，无 API 调用、无 data 写入。`python -m compileall -q src pages app.py` 通过，完整 unittest 31 项全部通过。
- 当前项目状态：简报生成的 Series truth-value 异常已修复，代码、测试和真实数据调用链验证完成，等待用户验收后按阶段名称提交；外部抓取数据、缓存、快照、备份、`.claude/` 与 `sentiment_errors.csv` 均保持原样并排除在本阶段之外。

## 2026-07-19 07:54

- 阶段名称 / 本次操作目标：阶段 1：盲标读取 dtype 修复。
- 具体做了什么：评估页上传与默认盲标 CSV 的读取，以及 `evaluate_annotation_files()` 对盲标文件的读取，均显式使用 `dtype=str`，避免含空值的二元标签列被 pandas 推断为 float；`annotation_key.csv` 保持原读取方式。`normalize_binary_label()` 同时接受 `"1.0"` / `"0.0"` 作为合法真/假值，形成双保险。新增临时 CSV 往返回归测试，覆盖 `"1"`、`"0"` 与空值混合列，并断言评估不抛异常、有效样本数正确。
- 验证：`python -m compileall -q src pages app.py` 通过；`python -m unittest discover -s tests` 共 32 项全部通过。真实 300 条盲标评估成功，对齐 300 条、情绪有效 299 条，三方对比 3 组、混淆矩阵 3 个、校准分箱 7 个均有数据；风险有效样本 187 条，正常生成 140 条 `sentiment_errors.csv` 衍生记录。Evaluation 页 AppTest 为 0 exception、0 error，三方对比表、混淆矩阵与校准区块均成功渲染。
- 当前项目状态：阶段 1 代码、回归测试、真实标注评估与页面验证均已完成，等待用户验收后按阶段名称提交；人工标注原始文件未修改，外部抓取数据、缓存、快照、备份及 `.claude/` 保持在本阶段提交之外，`sentiment_errors.csv` 作为评估管线衍生输出随本阶段纳入。
