# AI-powered Sector Sentiment Intelligence Dashboard

中文名：自动化板块级金融舆情雷达系统

## 1. 项目简介

本项目是一个面向日常跟踪的公开财经新闻舆情监测工具。系统从 RSS 财经新闻中提取标题、摘要、URL、发布时间、feed 来源与真实出版方，并只为高价值文章选择性提取正文用于模型分析；经过公司/ticker/板块映射、主题与风险标签、可选 FinBERT/词典情绪模型、事件级聚类和六维指标聚合后，在 Streamlit dashboard 中展示市场级和板块级舆情状态。

免责声明：本系统基于公开财经新闻自动分析市场舆情，结果仅供研究参考，不构成投资建议。投资有风险，决策需独立判断。

真实新闻是主要数据源；Demo 数据只作为离线兜底、测试脚手架和页面演示样本。当前版本提供 FinBERT 可选 wrapper；依赖或模型不可用时会回退到离线词典情绪 fallback，并在侧边栏/命令行给出中文提示。

## 2. 功能

- 市场总览：展示市场级六维指标、板块热力图、每日简报和按事件折叠的 Top Market Drivers；每个事件可展开查看全部报道。Unmapped 宏观新闻进入 Market Brief 和 Top Drivers，但不摊入板块聚合。
- 板块比较：比较 11 个 GICS 风格板块的 Optimism、Fear、Uncertainty、Attention、Disagreement、Risk Intensity。
- 板块详情：查看单板块雷达图、趋势框架、重点公司、主题、证据句和高风险新闻。
- 文章浏览器：查看处理后的新闻列表，支持发布时间、来源、板块、风险类别筛选及按 `event_id` 分组，URL 可点击跳转。
- 评估：提供 300 条分层盲标、全中性/词典/FinBERT 三方分类对比、混淆矩阵、风险与证据句指标、FinBERT 校准和错误样本分析；六维公式描述性对照保留为独立区块。
- RSS 抓取：20 个有效源由 `data/rss_sources.json` 外置管理，包括 Yahoo ticker 模板、CNBC 分类、MarketWatch 分类、Google News、Nasdaq、Benzinga、Motley Fool、Investing.com、Fortune、Business Insider 和 NYT Business；不使用已停止服务的 Reuters RSS。

## 3. 数据来源与存储

RSS 层只读取标题、摘要、URL、发布时间、feed 名和 entry 的 `source/publisher`。`publisher` 缺失时回退 feed 名。`content` 始终保留 RSS 摘要；系统只对当日高价值文章选择性抓取正文并写入 `body_text`，正文仅供模型分析，任何页面都不展示全文。MarketWatch、Google News、Fortune、Business Insider、NYT 等付费墙或聚合跳转源在配置中禁止正文请求，只收 headline feed。

当前 20 个启用源：Yahoo Finance ticker template；CNBC Top News、Markets、Technology、Economy、Earnings、Business；MarketWatch Top Stories、Real-time Headlines、Market Pulse；Google News Business、Markets；Nasdaq Markets、Earnings；Benzinga Markets；Motley Fool；Investing.com Stock Market News；Fortune；Business Insider；NYT Business。

主要数据文件：

- `data/raw_articles.csv`：RSS 抓取后的真实新闻原始累积数据。多次抓取会累积保存，重复 URL+标题会合并 ticker/company/source 语境。
- `data/rss_sources.json`：RSS 源、类型、启用状态、每源抓取上限、来源质量权重和正文许可策略。
- `data/real_processed_articles.csv`：真实新闻经过预处理、去重、映射、标签、情绪和评分后的结果。
- `data/fulltext_cache.json`：正文请求的永久缓存。成功正文与失败尝试都会留档；相同 article_id、URL 或规范化标题不再重复请求。
- `data/demo_articles.csv`：本地生成的 Demo 原始样本。
- `data/processed_articles.csv`：Demo 样本处理后的结果。
- `data/error_records.csv`：单条新闻处理失败时的降级记录，避免一条坏数据中断整批流水线。
- `data/sector_daily_scores.csv`：板块级每日快照；同日分别保存 `baseline` 和 `enhanced` 两个 `formula_version`，并用 `pipeline_revision` 标记语义修订；r4 起新增事件数与出版方数原料列。
- `data/market_daily_scores.csv`：市场级每日快照；与板块快照同步双写两套公式结果和管线修订号。
- `data/backups/`：CSV 写入前的自动备份目录。系统采用临时文件写入、备份旧文件、原子替换，降低数据被覆盖或写坏的风险；每个源文件默认保留最近 10 份备份。

RSS 通常只覆盖最近几天的新闻。30 天趋势需要连续多日运行抓取来积累，短期内真实新闻模式下趋势图稀疏是预期行为。

## 4. 数据字典补充

- `agg_weight`：聚合权重，计算为 `time_weight * relevance_weight * dedup_factor * source_weight`，用于加权平均和加权标准差。
- `source_weight`：来自 `rss_sources.json` 的来源质量先验。主流直接来源通常为 `1.0`，聚合器及较小来源为 `0.8-0.95`；重复新闻跨 feed 合并时取最大值。当前权重待人工标注后校准。
- `publisher`：RSS entry 的真实出版方；缺失时回退 feed 名。Google News 等聚合源可因此保留原始媒体口径。
- `event_id`：事件簇 ID，等于簇内 `agg_weight` 最高的代表文章 `article_id`；未与其他文章成簇时等于自身 `article_id`。
- `source_count`：事件簇内不同 `publisher` 数；同一 `event_id` 的所有文章记录相同值。
- `body_text`：Trafilatura 提取的正文，仅用于模型分析和离线评估，不在页面显示。
- `content_level`：`summary` 或 `fulltext`，用于第二冲刺比较摘要版与正文版信号。
- `rescored`：正文抓取后是否已重跑情绪、证据句、风险和主题管线。
- `pipeline_revision`：每日快照的数据管线语义修订号。`r1` 为早期管线，`r2` 为风险公式/聚类护栏，`r3` 为多源、publisher 与来源权重结构，`r4` 为 Fear/Risk/Disagreement Tier-A 公式与快照计数扩列；同日不同 revision 以复合主键并存，趋势断点可据此审计。
- `event_count` / `publisher_count`：板块每日快照的去重事件数与独立出版方数；r4 以前的历史行保留空值。从今日开始积累，供未来 Attention 三分量 ECDF 与相对自身历史分位展示使用。
- `b_bull` / `b_bear`：文章句子命中多头/空头立场词的归一化分数。
- `g_growth` / `s_shock`：文章句子命中成长主题/市场恐慌或避险反应词的归一化分数；`s_shock` 为兼容既有 CSV 的字段名，实际词源为 `panic_keywords.json`。
- `k_unc`：文章句子命中扩充后不确定性词典的归一化分数。
- `entropy_norm`：FinBERT 三分类概率熵除以 `log(3)` 后的 0-1 分数。
- `attention_weight`：保留字段，恒为 0。关注度在板块层由新闻量计算，文章层无实际含义。
- `disagreement_input`：`sentiment_score` 的逐行副本，作为板块分歧度输入留档；默认聚合直接用它计算加权成对绝对距离。
- `time_parse_error`：发布时间或采集时间解析失败时记录 fallback 原因。
- `processing_error`：单条新闻处理失败时记录异常摘要；该行会以低权重降级输出。

## 5. 六维指标

### 5.1 组件与词典

成长、恐慌、多空立场和不确定性组件共用句级匹配函数：`K = min(命中句子数 / 总句子数 * 3, 1)`。系数 `3` 由 `KEYWORD_SENTENCE_SCORE_MULTIPLIER` 配置。Fear 的 `S_shock` 改读 `panic_keywords.json`，只覆盖 panic selling、risk-off、flight to safety 等市场恐慌/避险反应；违约、调查、衰退等风险事件不再重复进入 Fear。`positive_direction_blockers.json` 会在同一句含 slows、misses、cut、weak、decline 等反向修饰词时阻断 growth/bullish 命中。`shock_keywords.json` 保留风险事件分组供词典审计，不再用于 Fear。

不确定性词表在原有词表上合并了 University of Notre Dame 发布的 [Loughran-McDonald Master Dictionary](https://sraf.nd.edu/loughranmcdonald-master-dictionary/) 中当前有效的 Uncertainty 类词。引用：Loughran, T. and McDonald, B. (2011), [When Is a Liability Not a Liability? Textual Analysis, Dictionaries, and 10-Ks](https://ssrn.com/abstract=1331573), *Journal of Finance*, 66(1), 35-65。当前合并后 `k_unc` 使用 302 个去重词条。

### 5.2 文章级公式

令 `p_pos/p_neu/p_neg` 为 FinBERT 概率，`H_norm = -sum(p * log(p)) / log(3)`。当前 `ACTIVE_WEIGHTS` 指向 Enhanced：

- Optimism：`100 * clip(0.7*p_pos + 0.2*B_bull + 0.1*G_growth, 0, 1)`。
- Fear：`100 * clip(0.7*p_neg + 0.2*B_bear + 0.1*S_panic, 0, 1)`；技术语义收窄为下行/避险压力，并与事件风险严重度解耦（persisted 字段名仍为 `s_shock`）。
- Uncertainty：`100 * clip(0.4*p_neu + 0.3*H_norm + 0.3*K_unc, 0, 1)`。

Baseline 使用同一函数，只替换为 `1/0/0`、`1/0/0` 和 `0.6/0.4/0` 权重。`p_positive/p_neutral/p_negative` 与六个组件均持久化到 processed CSV，因此切换权重或做消融时只需纯算术重算，不需要再次运行 FinBERT 或词典匹配。`BASELINE_WEIGHTS`、`ENHANCED_WEIGHTS` 和 `ACTIVE_WEIGHTS` 均集中在 `src/config.py`；一键回退只需让 `ACTIVE_WEIGHTS` 指向 baseline 组。

### 5.3 板块级公式

- Optimism / Fear / Uncertainty：使用文章 `agg_weight` 加权平均。
- Attention 冷启动：近 7 天板块加权新闻量 `N = sum(agg_weight)` 的横截面排名分位，`100 * (rank - 0.5) / 11`，并列取平均排名。
- Attention Enhanced：某板块累计至少 `ATTENTION_MIN_HISTORY_DAYS = 30` 天快照后，自动切换为 `100 * clip(0.7*ECDF_hist(N) + 0.3*ECDF_hist(Growth), 0, 1)`；`Growth` 相对最近 7 天平均加权新闻量计算。历史不足时继续走冷启动并在对比说明中标注。Baseline 历史路径为 `1.0*ECDF_hist(N) + 0.0*ECDF_hist(Growth)`。
- Disagreement：默认去阈值，计算 `100 * Σ(i<j) w_i*w_j*|s_i-s_j| / (DISAGREEMENT_PAIRWISE_NORMALIZATION * Σ(i<j) w_i*w_j)`，当前归一化系数为 2.0；少于 2 条新闻时为 0。`DISAGREEMENT_METHOD="legacy_std_mix"` 可复原旧式加权标准差与 PolarityMix，供消融使用；归一化系数待人工标注校准。
- Risk Intensity：未命中风险时为 0。每个命中类别先计算句级密度 `r_k = min(命中句子数 / 总句子数 * 3, 1)`，再令 `q_k=(v_k/5)*r_k`；默认文章级联合为 `100*(1-Π(1-q_k))`（`RISK_COMBINE="noisy_or"`），`sum` 保留为旧式消融。板块层先按 event_id 取最高 agg_weight 代表，防同事件多篇报道重复计入，再计算 `0.7 * 加权平均 + 0.3 * 加权 P90`；少于 3 个事件时以均值替代 P90。
- Macro risk 词典把衰退、滞胀、硬着陆等作为强触发词；通胀、经济放缓、消费疲弱等弱信号需在同一文章命中至少 2 个不同词才触发。该门槛由词表级 `min_distinct_hits` 配置，避免 `market/economy/growth` 等泛化词造成大面积误报。

以上 Enhanced 权重均为专家先验，`config.py` 已标注 TODO；第二冲刺将基于人工标注做正式消融和敏感性分析。每日板块/市场快照按 `formula_version` 双写 baseline 与 enhanced；趋势图和 LLM 简报只读取 `ACTIVE_FORMULA_VERSION`。

市场级雷达当前采用 11 个板块等权平均，而不是新闻量加权，以避免真实新闻流量过度集中在少数高曝光板块时主导市场总览。

## 6. 本地运行

```bash
cd sector_sentiment_dashboard
python setup_env.py
streamlit run app.py
```

`setup_env.py` 会自动探测 NVIDIA GPU：有 GPU 时安装 CUDA 版 torch，无 GPU 或探测失败时安装 CPU 版 torch；如果已检测到本地 GPU 版 torch，会跳过 torch 安装，避免覆盖。脚本会读取云端基础清单 `requirements.txt` 和本地完整功能附加清单 `requirements-full.txt`，主动排除其中的 CPU torch 和 transformers，再单独安装适合本地环境的版本。附加清单当前固定 `sentence-transformers==5.6.0`，用于事件 embedding 聚类。

本地环境禁止执行 `pip install -r requirements.txt`，因为该文件固定包含云端 CPU 版 torch，可能覆盖已经可用的本地 GPU 版本。

默认采用两段式加载：先以严格本地模式读取 `ProsusAI/finbert` 缓存，命中时直接启动；缓存未命中时才允许联网下载。下载或模型加载失败时自动回退词典模型。

FinBERT 相关配置集中在 `src/config.py`：

- `SENTIMENT_DEVICE = "auto"`：可选 `auto/cuda/cpu`；`auto` 会在 `torch.cuda.is_available()` 为 True 时使用 CUDA。
- `FINBERT_LOCAL_FILES_ONLY`：默认 `auto`，先读缓存、未命中再下载；仅在显式设为 `1` 时启用严格离线并跳过下载重试。
- `FINBERT_BATCH_SIZE`：运行时从环境变量读取，默认 `32`；云端建议设为 `8` 以降低 CPU 内存峰值。
- `HF_TOKEN`：可选 Hugging Face token，配置后会传给 tokenizer 和模型下载请求，用于降低共享出口 IP 遭遇限流的概率。
- `FINBERT_REVISION`：固定为 `4556d13015211d73dccd3fdd39d39232506f3e43`，确保本地与云端使用一致权重，不跟随上游 `main` 静默变化。
- 标签映射使用 `model.config.id2label` 动态解析，并在启动时做映射测试，避免把 `negative` 和 `neutral` 的概率静默互换。

命令行抓取真实 RSS 新闻：

```bash
python -m src.news_collector
```

也可以在 Streamlit 侧边栏点击“抓取最新新闻”。真实数据文件非空时，页面默认使用真实新闻；真实数据为空或不可读时，系统会提示并回落到 Demo 数据。

## 7. 云端部署

Streamlit Community Cloud 直接使用项目根目录的 `requirements.txt`。该文件保留 CPU FinBERT 所需依赖，但不安装 `sentence-transformers`；云端事件聚类会自动使用 lexical Jaccard 路径。`requirements-full.txt` 是本地 embedding 功能附加清单，本地安装仍一律使用 `python setup_env.py`，避免覆盖 GPU torch。

在 Streamlit Community Cloud 的 Secrets 中配置：

```toml
OPENAI_API_KEY = "your_replacement_api_key"
FINBERT_BATCH_SIZE = "8"
DEMO_PIN = "your_private_demo_pin"
# 可选；遇到 Hugging Face 共享出口限流时配置
HF_TOKEN = "hf_your_optional_token"
```

`DEMO_PIN` 用于保护侧边栏“立即重新生成简报”操作，避免公开演示页面被反复调用而产生 API 费用。不要将真实 key 或口令提交到仓库。

云端无需配置 `FINBERT_LOCAL_FILES_ONLY`：默认 `auto` 会先检查缓存，未命中时下载约 440MB 的 `ProsusAI/finbert` 模型并显示等待提示；下载时间受网络和实例性能影响，CPU 推理也会比本地 GPU 慢。模型下载或加载失败时系统会继续使用词典模型，不会中断页面。需要完全断网运行时才将该变量设为 `1`。

Community Cloud 容器文件系统具有易失性：运行期间抓取的新 RSS、快照、历史简报和模型缓存可能在休眠、重启或重新部署后消失。公开演示的基准数据以仓库中已提交的 `data/` 文件为准；需要永久积累真实新闻时，应另接持久化存储。

## 8. 当前限制

- FinBERT 是可选引擎；没有本地模型缓存或依赖时会回退词典模型。
- 事件 embedding 阈值 `0.72` 是待校准先验值；同公司、同主题但不同事件的分析文章仍可能被误合并，第二冲刺需要用事件对标注数据评估。
- RSS 摘要可能很短，证据句质量受来源摘要质量限制。
- 历史 RSS entry 没有保存 publisher 时只能回退旧 feed 名；新抓取记录会优先使用 entry 中的真实出版方。
- 正文抓取受站点 robots、页面结构和反爬策略影响；失败会静默降级为摘要并永久缓存失败状态，不自动重试。
- 宏观/市场级 Unmapped 新闻当前主要进入文章浏览和市场驱动展示；不强行摊入 11 个板块聚合。
- 评估模块已提供两套权重的描述统计、排名变化和新闻算例，但正式消融、显著性检验与敏感性分析仍留到第二冲刺。
- 当前不提供投资建议，也不用于实时交易。

## 9. 后续方向

- 扩展 evaluation：消融、敏感性分析、更多标注字段。
- 用事件对标注数据校准 embedding/lexical 阈值，并评估簇内新闻是否需要降权。

## 10. 每日市场简报与调度

系统已加入“抓取多次/天、简报一次/天”的解耦机制：

- `python -m src.news_collector` 每次运行会从 `rss_sources.json` 读取源、累积写入 `data/raw_articles.csv`，并只对新增 `article_id` 运行映射、标签、情绪和评分管线；日志会输出“本次新增 N 条，复用 M 条”。
- 摘要处理后，系统从 UTC 当日新闻中选择 Top Driver 候选、`|sentiment_score| >= 0.5`、`risk_intensity >= 60` 或多篇事件代表；每轮最多 30 篇，正文请求间隔至少 1 秒、超时 10 秒、失败不重试。成功文章批量重跑句级管线并再次覆盖当天快照，简报门闸最后执行。
- 每次处理完成后会刷新 `data/sector_daily_scores.csv` 和 `data/market_daily_scores.csv`。同一 UTC 日期按 `formula_version` 分别 upsert baseline/enhanced 两行，历史日期不动；旧历史行自动补标 `baseline`。Sector Detail 的 7/30 天趋势和 LLM 简报只读取当前 ACTIVE 版本。
- 简报门闸由 `BRIEF_GENERATION_HOUR_LOCAL` 控制。当前时间已过本地生成时刻且今天尚未生成过简报时，才会写入 `data/latest_brief.md`，并按日期归档到 `data/briefs/`。
- LLM 简报使用 OpenAI 官方 Python SDK，API key 从环境变量 `OPENAI_API_KEY` 读取。运行时按 `gpt-5.6-terra → gpt-5.5` 顺序直接发起生成请求，`models.list()` 只提供日志参考，不再是可用性硬门槛。首选模型遇到 HTTP 429 会等待 5 秒重试一次；仍被限流，或遇到模型不存在、无权限、容量/服务暂不可用时，再切换到下一候选。候选均失败、没有 key、SDK 不可用或其他调用失败时会回退规则模板，管线不会崩溃。每次生成会把候选尝试、各次结果、最终模型及原因同时打印为中文日志，并写入最新简报和日期归档元数据。AI 简报按“核心观点—市场全景—板块与事件深读—风险与明日关注点—数据范围与免责声明”组织为 900-1200 字分析晨读，并在页面署名中显示实际模型；Streamlit 页面渲染路径只读取 `latest_brief.md`，不会自动调用 LLM API。
- RSS 只覆盖最近几天的新闻，30 天趋势需要连续多日运行抓取来积累；短期内真实新闻模式下趋势图稀疏是预期行为。

本地启用 LLM 前可在 PowerShell 设置：

```powershell
$env:OPENAI_API_KEY="your_api_key"
```

注册 Windows 任务计划程序，每 4 小时抓取一次：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_schedule.ps1
```

查看任务：

```powershell
Get-ScheduledTask -TaskName SectorSentimentRSSCollector
```

删除任务：

```powershell
Unregister-ScheduledTask -TaskName SectorSentimentRSSCollector -Confirm:$false
```

## 11. 存储分层与工作集窗口

- `data/raw_articles.csv` 永久保留，不做自动清理，方便第二阶段人工标注抽样。文件超过 50MB 时，系统会在日志中提示建议迁移 SQLite；当前版本暂不执行迁移。
- 仪表盘默认只加载 `WORKING_SET_DAYS = 30` 天内的已处理新闻，降低页面计算成本；Article Explorer 提供“加载全部历史”选项。
- 每日快照表不受工作集窗口影响，会永久累积。

## 12. 同事件折叠

- 默认 `EVENT_SIMILARITY_ENGINE = "embedding"`，使用 `sentence-transformers/all-MiniLM-L6-v2`。两篇文章需同时满足发布时间相差不超过 48 小时、ticker 有交集、标题+摘要余弦相似度不低于 `0.72` 才会合并。无 ticker 的 Unmapped 新闻使用更严格的 `0.82` 阈值。
- embedding 依赖、模型或推理不可用时自动回退 lexical：内容词 Jaccard 阈值为 `0.40`，无 ticker Unmapped 阈值为 `0.55`。日志会输出请求引擎、实际引擎、设备与回退原因。
- 聚类采用并查集，但任一事件簇总时间跨度不得超过 72 小时；两篇报道若一篇情绪分数高于 `+0.3`、另一篇低于 `-0.3`，则禁止连边。全量处理会重算所给历史；增量抓取只比较新增文章与其 48 小时时间邻域以及本批新增文章，不重算历史向量。向量只在内存中存在，不持久化。
- Top Drivers 每个事件只展示最高 `agg_weight` 的代表文章，簇级 `driver_score` 取文章级最大值；`source_count >= 3` 时乘 `EVENT_COVERAGE_BOOST = 1.15`。该加成只用于展示排序。
- 市场总览的 Top Market Drivers 提供“近 48 小时”（默认）和“近 30 天”切换。48 小时模式少于 `DRIVER_MIN_EVENTS = 5` 个事件时，依次扩至 72、168 小时，并在标题显示实际窗口；30 天模式与 `WORKING_SET_DAYS` 一致且不扩窗。每日市场简报继续只使用其既有的 24 小时数据包，因此两者窗口不同是预期设计。
- 宏观/市场级 Unmapped 事件保证进入 Top Drivers，但最终仍按 `driver_score` 降序落位；仅因保障性入选的条目会标记“宏观保底”，不再固定置顶。
- 事件折叠不会修改 `dedup_factor`、`agg_weight` 或六维聚合。多家独立报道仍各自贡献 Attention 和情绪；簇内降权是否合理留待第二冲刺用标注数据评估。

手动重算 processed CSV：

```bash
python -m src.event_clustering --input data/real_processed_articles.csv --engine embedding
python -m src.event_clustering --input data/real_processed_articles.csv --engine lexical --dry-run
```

## 13. 模型评估工具链

从完整 raw 累积新闻生成 300 条盲标样本：

```bash
python scripts/sample_for_annotation.py
```

脚本与 Evaluation 页面的“步骤 1”均按预测板块 × FinBERT 三分类做确定性轮询均衡抽样。页面可配置抽样条数和随机种子，默认值分别为 `300` 与 `5720`；同一新闻池、条数和种子会精确复现同一批 article_id，变更种子会生成新批次。容量不足的小层取尽后，剩余名额分配给仍有候选的层。输出：

- `data/annotation/annotation_blind.csv`：只含文章原文、URL、时间和空白人工标签，严禁包含预测字段。
- `data/annotation/annotation_key.csv`：私有对账文件，保存 FinBERT 情绪概率、置信度、预测板块、风险类别和证据句，不提供给第一遍主标注者。
- `data/annotation/annotation_meta.json`：当前盲标批次的实际条数、随机种子、生成时间与 article_id 指纹。评估报告必须引用该文件记录的最终批次种子，而非页面输入框的当前默认值。
- `data/annotation/sentiment_errors.csv`：评估后导出的全部 FinBERT 情绪误判。
- `docs/annotation_guide.md`：情绪边界、风险类别、证据句标准和两遍标注流程。

两遍流程用于同时满足盲标与 `sector_ok/evidence_ok`：主标注者先在看不到预测的情况下完成情绪和风险；标签锁定后，评估负责人保管私有 key，只补充板块与证据句对账结果。

Evaluation 页面在填写标签后计算：情绪 Accuracy、逐类 Precision/Recall/F1、Macro F1 和 3×3 混淆矩阵；同一标注集上的全中性基线、现有词典 fallback 与 FinBERT 三方对比；板块映射 Accuracy；风险多标签逐类 P/R/F1 与 Macro F1；证据句 Precision；FinBERT 可靠性分桶和多分类 Brier score。风险 Macro F1 当前对配置中的 10 个规范风险类别等权计算，无支持类别按 0 计入，页面同时展示 support 便于解释。

本批只评估文章分类层。六维指标层的敏感性分析、正式消融和稳健性验证属于后续批次。
