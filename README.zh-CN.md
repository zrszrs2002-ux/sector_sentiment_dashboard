# AI 驱动的行业情绪智能看板 [English](./README.md) | [简体中文](./README.zh-CN.md)

一款自动化的行业级财经新闻情绪雷达。

## 1. 项目概述

本项目是一款面向日常跟踪的公开财经新闻情绪监测工具。它从财经 RSS 源中提取标题、摘要、URL、发布时间、订阅源名称和实际发布方；只对高价值文章选择性抓取全文，且全文仅用于模型分析。数据依次经过公司、股票代码与行业映射，主题与风险打标，可选的 FinBERT 或词典情绪分析，事件级聚类，以及六维指标聚合，最终在 Streamlit 看板中以市场和行业两个层级呈现。

免责声明：本系统基于公开财经新闻自动分析市场情绪，输出结果仅供研究参考，不构成任何投资建议。投资有风险，决策请独立判断。

真实新闻是主要数据来源。Demo 数据只作为离线兜底、测试脚手架和界面演示样例保留。当前版本内置一个可选的 FinBERT 封装；如果其依赖或模型不可用，系统会回退到离线词典情绪引擎，并在侧边栏或命令行中给出说明。

## 2. 功能

- 市场总览（Market Overview）：展示市场层面的六维指标、行业热力图、每日简报，以及按事件折叠的市场主要驱动因素（Top Market Drivers）。每个事件都可以展开查看全部相关报道。未映射到具体行业的宏观新闻会进入市场简报和 Top Drivers，但不分配到行业聚合中。
- 行业对比（Sector Comparison）：在 11 个 GICS 风格行业之间比较乐观度（Optimism）、恐惧度（Fear）、不确定性（Uncertainty）、关注度（Attention）、分歧度（Disagreement）和风险强度（Risk Intensity）。
- 行业详情（Sector Detail）：展示行业雷达图、趋势框架、重点公司、主题、证据句和高风险新闻。
- 文章浏览器（Article Explorer）：展示处理后的文章，可按发布时间、发布方、行业和风险类别筛选，也可选择按 `event_id` 分组。URL 可直接点击。
- 评估（Evaluation）：提供 300 条分层盲标流程、全中性基线 / 词典 / FinBERT 三方分类对比、混淆矩阵、风险与证据指标、FinBERT 校准和错误分析。六维公式的描述性对比单独成节。
- RSS 采集：20 个启用中的源定义统一在外部文件 `data/rss_sources.json` 中管理，涵盖 Yahoo 股票代码模板、CNBC 各栏目、MarketWatch 各栏目、Google News、Nasdaq、Benzinga、The Motley Fool、Investing.com、Fortune、Business Insider 和 NYT Business。已停止服务的 Reuters RSS 不再使用。

市场总览和行业对比页面的热力图按模式使用连续色阶。相对模式下，乐观度用 `Greens`，关注度用 `Blues`，其余偏警示性的指标用 `RdYlGn_r`，数值越高越偏红。绝对模式下，乐观度仍用 `Greens`，关注度仍用 `Blues`，恐惧度改用 `Reds`，形成清晰的红绿对比；不确定性、分歧度和风险强度继续使用 `RdYlGn_r`。

## 3. 数据来源与存储

RSS 层只读取标题、摘要、URL、发布时间、订阅源名称，以及条目自带的 `source/publisher`。缺少 `publisher` 时，以订阅源名称兜底。`content` 字段始终保留 RSS 摘要。对于当天的高价值文章，系统会选择性抓取全文并存入 `body_text`；全文只用于模型分析，从不在界面上展示。对于付费墙或聚合跳转类来源（如 MarketWatch、Google News、Fortune、Business Insider 和 NYT），配置中已禁用全文请求，这些来源只作为标题源使用。

当前启用的 20 个来源为：Yahoo Finance 股票代码模板；CNBC Top News、Markets、Technology、Economy、Earnings 和 Business；MarketWatch Top Stories、Real-time Headlines 和 Market Pulse；Google News Business 和 Markets；Nasdaq Markets 和 Earnings；Benzinga Markets；The Motley Fool；Investing.com Stock Market News；Fortune；Business Insider；以及 NYT Business。

主要数据文件：

- `data/raw_articles.csv`：从 RSS 采集的累计原始真实新闻。重复运行时追加写入；URL/标题重复的条目会合并各自的股票代码、公司、发布方和来源上下文。
- `data/rss_sources.json`：RSS 源定义，包括源类型、启用状态、单源抓取上限、来源质量权重和全文抓取权限策略。
- `data/real_processed_articles.csv`：经过预处理、去重、映射、打标、情绪分析和评分后的真实新闻。
- `data/fulltext_cache.json`：全文请求的永久缓存，成功和失败的尝试都会记录。同一文章 ID、URL 或规范化标题不会被重复请求。
- `data/demo_articles.csv`：本地生成的原始 Demo 样本。
- `data/processed_articles.csv`：处理后的 Demo 样本。
- `data/error_records.csv`：单篇文章处理失败时生成的降级记录，避免个别坏数据中断整个批处理流程。
- `data/sector_daily_scores.csv`：行业每日快照。每天的 `baseline` 和 `enhanced` 两个公式版本分开存储，`pipeline_revision` 记录语义修订版本。r4 修订新增了原始事件数和发布方数字段。
- `data/market_daily_scores.csv`：市场每日快照，同样按两个公式版本分别写入，并记录流水线修订版本。
- `data/backups/`：每次写入 CSV 前自动生成的备份。系统先写入临时文件，再备份旧文件，最后执行原子替换，以降低覆盖和损坏风险。默认每个源文件保留最近 10 份备份。

RSS 源通常只提供最近几天的内容。要形成 30 天趋势，采集器需要长期持续运行，所以刚启用真实新闻模式时趋势图比较稀疏，属于正常现象。

## 4. 数据字典补充

- `agg_weight`：聚合权重，计算方式为 `time_weight * relevance_weight * dedup_factor * source_weight`，用于加权均值和加权标准差。
- `source_weight`：来自 `rss_sources.json` 的来源质量先验。主要的直接来源通常取 `1.0`，聚合平台和较小来源取 `0.8-0.95`。跨订阅源合并重复文章时保留最大值。这些权重仍有待用人工标注进行校准。
- `publisher`：RSS 条目中的实际发布方，缺失时回退为订阅源名称。这样，Google News 这类聚合源在条件允许时也能保留原始发布方。
- `event_id`：事件簇 ID，等于簇内 `agg_weight` 最高的代表文章的 `article_id`。没有与其他文章聚成一簇的文章使用自身的 `article_id`。
- `source_count`：事件簇中不同 `publisher` 的数量。同一 `event_id` 下的所有文章共享这个值。
- `body_text`：由 Trafilatura 提取的全文，仅用于模型分析和离线评估，从不在界面上展示。
- `content_level`：取值为 `summary` 或 `fulltext`，用于第二轮迭代中比较基于摘要和基于全文的信号。
- `rescored`：抓取全文后，是否已重新运行情绪、证据句、风险和主题处理。
- `pipeline_revision`：每日快照流水线的语义修订版本。`r1` 是早期流水线；`r2` 加入风险公式和聚类防护；`r3` 加入多来源发布方和来源权重；`r4` 加入 Tier-A 恐惧度/风险强度/分歧度公式以及快照计数列。同一天的多个修订版本以复合主键并存，确保趋势断点可审计。
- `event_count` / `publisher_count`：行业每日快照中去重后的事件数和独立发布方数。r4 之前的历史行保留空值。这两个字段从 r4 开始累积，为今后的三成分关注度 ECDF 和行业内历史百分位展示做准备。
- `b_bull` / `b_bear`：看涨与看跌立场词的句子级归一化匹配得分。
- `g_growth` / `s_shock`：增长主题词和市场恐慌/避险反应词的句子级归一化匹配得分。保留 `s_shock` 这个名字是为了兼容 CSV，其实际词表现在来自 `panic_keywords.json`。
- `k_unc`：基于扩展不确定性词典的句子级归一化得分。
- `entropy_norm`：FinBERT 三分类概率熵除以 `log(3)`，得到 0-1 之间的分数。
- `attention_weight`：保留字段，固定为 0。关注度在行业层面根据文章量计算，放在文章层面没有意义。
- `disagreement_input`：`sentiment_score` 的行级副本，保留作为行业分歧度的输入。默认聚合直接基于它计算加权两两绝对距离。
- `time_parse_error`：发布时间或采集时间无法解析时记录的回退原因。
- `processing_error`：文章处理失败时记录的异常摘要；该行会以低权重的降级形式输出。

## 5. 六维指标

### 5.1 成分与词典

增长、恐慌、看涨/看跌立场和不确定性几个成分共用同一个句子级匹配函数：`K = min(命中句子数 / 总句子数 * 3, 1)`。系数 `3` 通过 `KEYWORD_SENTENCE_SCORE_MULTIPLIER` 配置。恐惧度中的 `S_shock` 现在读取 `panic_keywords.json`，只涵盖恐慌性抛售、避险情绪（risk-off）和资金避险流动（flight to safety）这类市场反应；违约、调查、衰退等风险事件不再重复计入恐惧度。`positive_direction_blockers.json` 的作用是：当同一句话里出现 `slows`、`misses`、`cut`、`weak`、`decline` 等反向修饰词时，阻止增长或看涨词的命中。`shock_keywords.json` 作为风险事件的审计分组保留，但不再参与恐惧度计算。

不确定性词表在原有列表的基础上，合并了圣母大学（University of Notre Dame）[Loughran-McDonald 主词典](https://sraf.nd.edu/loughranmcdonald-master-dictionary/)中当前有效的 Uncertainty 类词条。引用：Loughran, T. and McDonald, B. (2011), [When Is a Liability Not a Liability? Textual Analysis, Dictionaries, and 10-Ks](https://ssrn.com/abstract=1331573), *Journal of Finance*, 66(1), 35-65。合并后的 `k_unc` 词表共有 302 个唯一词条。

### 5.2 文章级公式

设 `p_pos/p_neu/p_neg` 为 FinBERT 输出的三类概率，`H_norm = -sum(p * log(p)) / log(3)`。`ACTIVE_WEIGHTS` 当前指向 Enhanced：

- 乐观度：`100 * clip(0.7*p_pos + 0.2*B_bull + 0.1*G_growth, 0, 1)`。
- 恐惧度：`100 * clip(0.7*p_neg + 0.2*B_bear + 0.1*S_panic, 0, 1)`。它的技术含义被收窄为下行压力和避险压力，与事件风险的严重程度区分开。持久化字段名仍为 `s_shock`。
- 不确定性：`100 * clip(0.4*p_neu + 0.3*H_norm + 0.3*K_unc, 0, 1)`。

Baseline 使用相同的函数，权重分别为 `1/0/0`、`1/0/0` 和 `0.6/0.4/0`。三类概率和全部六个成分都持久化在处理后的 CSV 中，所以调整权重或做消融时只需做算术重算，不用重新运行 FinBERT 或词典匹配。`BASELINE_WEIGHTS`、`ENHANCED_WEIGHTS` 和 `ACTIVE_WEIGHTS` 统一定义在 `src/config.py` 中；要一键回滚，只需把 `ACTIVE_WEIGHTS` 指向 baseline 组。

### 5.3 行业级公式

- 乐观度 / 恐惧度 / 不确定性：按 `agg_weight` 加权的文章均值。
- 关注度冷启动：对各行业近七天的加权文章量 `N = sum(agg_weight)` 做横截面排名百分位，计算方式为 `100 * (rank - 0.5) / 11`，并列时取平均排名。
- 关注度 Enhanced：某个行业累计的快照天数达到 `ATTENTION_MIN_HISTORY_DAYS = 30` 后，自动切换为 `100 * clip(0.7*ECDF_hist(N) + 0.3*ECDF_hist(Growth), 0, 1)`，其中 `Growth` 衡量的是相对于近七天平均加权文章量的变化。历史不足的行业继续走冷启动路径，并在对比说明中标注。Baseline 的历史路径为 `1.0*ECDF_hist(N) + 0.0*ECDF_hist(Growth)`。
- 分歧度：默认采用无阈值方法，计算 `100 * sum(i<j) w_i*w_j*|s_i-s_j| / (DISAGREEMENT_PAIRWISE_NORMALIZATION * sum(i<j) w_i*w_j)`，当前归一化系数为 2.0。文章少于两篇时结果为 0。设置 `DISAGREEMENT_METHOD="legacy_std_mix"` 可恢复旧的加权标准差加 PolarityMix 方法，用于消融。归一化系数仍有待基于人工标注校准。
- 风险强度：没有命中任何风险时为 0。对每个命中的类别，先计算句子密度 `r_k = min(命中句子数 / 总句子数 * 3, 1)`，再计算 `q_k=(v_k/5)*r_k`。文章级默认用 `100*(1-product(1-q_k))` 组合，对应 `RISK_COMBINE="noisy_or"`；`sum` 作为旧版消融选项保留。到了行业层面，每个 `event_id` 只取 `agg_weight` 最高的代表文章，避免同一事件的重复报道被多次计入。聚合值为 `0.7 * 加权均值 + 0.3 * 加权 P90`；事件少于三个时，用均值代替 P90。
- 宏观风险词典把 recession（衰退）、stagflation（滞胀）和 hard landing（硬着陆）视为强触发词。inflation（通胀）、economic slowdown（经济放缓）、consumer weakness（消费疲软）等弱信号，需要在同一篇文章里至少命中两个不同词条才会触发。这个阈值由词典级的 `min_distinct_hits` 设置控制，可以防止 `market`、`economy`、`growth` 这类宽泛词造成大面积误报。

以上所有 Enhanced 权重都是专家先验，并在 `config.py` 中标了 TODO。正式的消融和敏感性分析依托人工标注流程完成。行业和市场的每日快照按 `formula_version` 分别存储 Baseline 和 Enhanced 结果；趋势图和 LLM 简报只读取 `ACTIVE_FORMULA_VERSION` 对应的版本。

市场雷达图目前对 11 个行业做等权平均，而不是按文章量加权，以免少数高覆盖行业主导市场总览。

## 6. 本地运行

```bash
cd sector_sentiment_dashboard
python setup_env.py
streamlit run app.py
```

`setup_env.py` 会自动检测 NVIDIA GPU：有 GPU 时安装 CUDA 版 torch，没有则安装 CPU 版。如果检测到本地已经装有支持 GPU 的 torch，就跳过 torch 安装，避免把它覆盖掉。脚本会读取 `requirements.txt` 中的云端基础依赖和 `requirements-full.txt` 中的本地功能扩展依赖，剔除云端 CPU 版 torch 和 transformers 条目，再安装适合本地环境的版本。扩展依赖列表目前固定了 `sentence-transformers==5.6.0`，用于事件向量聚类。

本地安装时不要运行 `pip install -r requirements.txt`，因为这个文件固定的是云端 CPU 版 torch，可能会覆盖本地已经能用的 GPU 版本。

FinBERT 默认采用两阶段加载：先以严格本地模式读取 `ProsusAI/finbert` 缓存，命中就立即启动；只有缓存未命中时才允许联网下载。下载或模型加载失败时，自动回退到词典引擎。

FinBERT 相关设置集中在 `src/config.py` 中：

- `SENTIMENT_DEVICE = "auto"`：可选 `auto/cuda/cpu`；`auto` 在 `torch.cuda.is_available()` 为真时使用 CUDA。
- `FINBERT_LOCAL_FILES_ONLY`：默认为 `auto`，先读缓存，未命中再下载。显式设为 `1` 则进入严格离线模式，不再尝试下载。
- `FINBERT_BATCH_SIZE`：运行时从环境变量读取，默认 `32`。云端建议设为 `8`，以降低 CPU 内存峰值。
- `HF_TOKEN`：可选的 Hugging Face token，会随 tokenizer 和模型下载请求一起发送，降低共享出口 IP 被限流的风险。
- `FINBERT_REVISION`：固定为 `4556d13015211d73dccd3fdd39d39232506f3e43`，确保本地和云端使用完全相同的权重，而不是悄悄跟随上游 `main` 分支变化。
- 标签映射通过 `model.config.id2label` 动态解析，并在启动时做测试，防止 `negative` 和 `neutral` 的概率在不知不觉中被调换。

从命令行采集真实 RSS 新闻：

```bash
python -m src.news_collector
```

也可以在 Streamlit 侧边栏中点击 **Fetch Latest News**（获取最新新闻）。真实数据文件非空时默认使用真实新闻；如果文件为空或无法读取，系统会显示警告并回退到 Demo 数据。

## 7. 云端部署

Streamlit Community Cloud 使用项目根目录下的 `requirements.txt`。该文件包含 CPU 版 FinBERT 依赖，但不安装 `sentence-transformers`，所以云端的事件聚类会自动走词汇 Jaccard 路径。`requirements-full.txt` 包含本地的向量化扩展依赖；本地安装应始终使用 `python setup_env.py`，以保护支持 GPU 的 torch。

在 Streamlit Community Cloud 的 Secrets 中配置以下值：

```toml
OPENAI_API_KEY = "your_replacement_api_key"
FINBERT_BATCH_SIZE = "8"
DEMO_PIN = "your_private_demo_pin"
# 可选：如果 Hugging Face 的共享出口 IP 被限流，可以配置此项。
HF_TOKEN = "hf_your_optional_token"
```

`DEMO_PIN` 用来保护侧边栏中的 **Regenerate Brief Now**（立即重新生成简报）操作，防止公开演示被反复调用而产生 API 费用。切勿把真实密钥或密码提交到代码仓库。

云端不需要配置 `FINBERT_LOCAL_FILES_ONLY`。默认的 `auto` 模式会先检查缓存，未命中时下载约 440 MB 的 `ProsusAI/finbert` 模型，并显示等待提示。下载耗时取决于网络和实例性能，而且 CPU 推理比本地 GPU 慢。如果下载或模型加载失败，系统会继续使用词典引擎。只有需要完全离线运行时，才把这个变量设为 `1`。

Community Cloud 的容器文件系统是临时性的。运行时生成的 RSS 数据、快照、历史简报和模型缓存，可能在休眠、重启或重新部署后丢失。公开演示的基线数据是 `data/` 目录下已提交的内容。如果需要长期积累真实新闻，请另外使用持久化存储。

## 8. 当前局限

- FinBERT 是可选组件，模型缓存或依赖不可用时回退到词典引擎。
- 事件向量相似度阈值 `0.72` 是一个仍需校准的先验值。同一公司、同一主题但属于不同事件的文章可能被错误合并，这一点应基于已标注的文章对进行评估。
- RSS 摘要可能很短，因此证据质量取决于来源摘要本身的质量。
- 没有存储发布方的历史 RSS 条目，只能回退为当时的订阅源名称；新采集的记录会优先使用条目中的实际发布方。
- 全文抓取受站点 robots 规则、页面结构和反爬机制影响。失败时会静默回退到摘要，并被永久缓存，不会自动重试。
- 未映射的宏观与市场新闻目前主要出现在文章浏览器和市场驱动因素展示中，不会被强行纳入 11 个行业的聚合。
- 评估模块包含描述性对比、基于标注的模型评估和权重敏感性分析。更多的消融实验和显著性检验留待后续工作。
- 本项目不提供投资建议，也不适用于实时交易。

## 9. 后续工作

- 扩展评估体系，加入正式的消融实验、显著性检验和更多标注字段。
- 用已标注的事件对校准向量与词汇阈值，并评估事件簇内的文章是否应当降权。

## 10. 每日市场简报与定时调度

系统把高频采集和每日一次的简报生成分开处理：

- 每次运行 `python -m src.news_collector` 时，系统从 `rss_sources.json` 读取源定义，追加写入 `data/raw_articles.csv`，并且只对新的 `article_id` 执行映射、打标、情绪分析和评分。日志会报告新增了多少条、复用了多少条。
- 摘要处理完成后，系统从当前 UTC 日内挑选全文抓取候选：Top Driver 候选、`|sentiment_score| >= 0.5` 的文章、`risk_intensity >= 60` 的文章，以及多文章事件的代表文章。每次运行最多处理 30 篇，请求间隔至少一秒，超时 10 秒，失败不重试。成功抓到全文的文章会批量重新评分，随后重写当日快照，最后执行简报门控。
- 每次完整处理都会刷新 `data/sector_daily_scores.csv` 和 `data/market_daily_scores.csv`。当前 UTC 日期的 Baseline 和 Enhanced 行按 `formula_version` 分别 upsert；历史日期保持不变，旧的历史数据标记为 `baseline`。行业详情的趋势图和 LLM 简报只读取当前启用的公式版本。
- 简报门控由 `BRIEF_GENERATION_HOUR_LOCAL` 控制。只有当本地时间已过生成时点、且当天的简报还没有生成时，才会写入 `data/latest_brief.md` 以及 `data/briefs/` 下带日期的文件。
- LLM 简报使用官方 OpenAI Python SDK，从环境变量读取 `OPENAI_API_KEY`。运行时依次尝试 `gpt-5.6-terra` 和 `gpt-5.5`；`models.list()` 只作参考，不作为硬性的可用性判断。首选模型第一次返回 HTTP 429 时，等待五秒后重试一次。如果仍然持续限流，或者模型不存在、未授权、容量已满、暂时不可用，就尝试下一个候选模型。如果所有候选都失败、未配置密钥、SDK 不可用或出现其他 API 错误，则改用基于规则的模板，流水线继续运行。每次生成都会记录各候选模型的尝试情况、结果、最终使用的模型和原因，并把这些元数据同时写入最新简报和带日期的简报。AI 简报分为五个部分：核心观点（Core View）、市场概览（Market Overview）、行业与事件深度分析（Sector and Event Deep Dive）、风险与明日关注清单（Risks and Tomorrow's Watch List）、数据范围与免责声明（Data Scope and Disclaimer），目标篇幅为 900-1,200 词。页面署名显示实际生成成功的模型。Streamlit 只读取 `latest_brief.md`，渲染页面时从不调用 LLM API。
- RSS 只覆盖最近几天。30 天趋势需要持续采集，因此在初始积累期内，真实新闻的趋势图比较稀疏是预期中的情况。

在本地启用 LLM 之前，先在 PowerShell 中设置 API 密钥：

```powershell
$env:OPENAI_API_KEY="your_api_key"
```

注册一个每四小时采集一次的 Windows 计划任务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_schedule.ps1
```

查看该任务：

```powershell
Get-ScheduledTask -TaskName SectorSentimentRSSCollector
```

删除该任务：

```powershell
Unregister-ScheduledTask -TaskName SectorSentimentRSSCollector -Confirm:$false
```

## 11. 存储分层与工作集窗口

- `data/raw_articles.csv` 永久保留，供第二阶段的人工标注抽样使用。文件超过 50 MB 时，系统会在日志中建议迁移到 SQLite；当前版本不会自动执行迁移。
- 看板默认只加载最近 `WORKING_SET_DAYS = 30` 天的处理后新闻，以降低页面计算开销。文章浏览器提供 **Load Full History**（加载全部历史）选项。
- 每日快照表不受工作集窗口限制，会永久累积。

## 12. 事件级折叠

- `EVENT_SIMILARITY_ENGINE` 默认为 `"embedding"`，使用 `sentence-transformers/all-MiniLM-L6-v2`。两篇文章必须同时满足以下条件才会合并：发布时间相差不超过 48 小时、至少共享一个股票代码、标题加摘要的余弦相似度不低于 `0.72`。没有股票代码的未映射文章使用更严格的 `0.82` 阈值。
- 如果向量化依赖、模型或推理路径不可用，系统回退到词汇匹配。实词 Jaccard 阈值为：有关联股票代码的文章 `0.40`，无股票代码的未映射文章 `0.55`。日志会报告请求的引擎、实际使用的引擎、设备和回退原因。
- 聚类使用并查集（union-find），但任一事件簇的总时间跨度不得超过 72 小时。如果一篇文章的情绪高于 `+0.3`、另一篇低于 `-0.3`，两者之间的连边也会被阻断。完整处理时会重算传入的全部历史；增量采集时，新文章只与其 48 小时邻域内的文章以及其他新采集的文章比较。向量只存在于内存中，不做持久化。
- Top Drivers 只展示每个事件中 `agg_weight` 最高的代表文章，事件簇级的 `driver_score` 取文章级得分的最大值。`source_count >= 3` 的事件簇获得 `EVENT_COVERAGE_BOOST = 1.15` 的加成，但仅用于展示排序。
- 市场总览支持 **Last 48 Hours**（最近 48 小时，默认）和 **Last 30 Days**（最近 30 天）两种模式。如果 48 小时模式下的事件少于 `DRIVER_MIN_EVENTS = 5` 个，窗口会依次扩展到 72 小时和 168 小时，标题显示实际使用的窗口。30 天模式与 `WORKING_SET_DAYS` 保持一致，不做扩展。每日市场简报仍沿用原有的 24 小时数据，所以这两个窗口是有意设计成不同的。
- 未映射的宏观与市场事件保证会进入 Top Drivers，但仍按 `driver_score` 降序排列。仅凭这一保证机制入选的条目会标记为宏观兜底（macro fallback），不会被置顶。
- 事件折叠不会修改 `dedup_factor`、`agg_weight` 或六维聚合。独立报道仍然各自计入关注度和情绪。事件簇成员是否应该降权，仍是一个有待评估的问题。

手动重算处理后 CSV 中的事件 ID：

```bash
python -m src.event_clustering --input data/real_processed_articles.csv --engine embedding
python -m src.event_clustering --input data/real_processed_articles.csv --engine lexical --dry-run
```

## 13. 模型评估工具链

从完整的累计原始新闻集中生成 300 条盲标样本：

```bash
python scripts/sample_for_annotation.py
```

该脚本和评估页面上的 **Step 1** 采用确定性的轮询（round-robin）均衡，在"预测行业 × FinBERT 类别"各分层之间分配样本。样本量和随机种子可以在页面上配置，默认分别为 `300` 和 `5720`。相同的文章池、样本量和种子会复现完全相同的 `article_id` 集合；更换种子则生成新的批次。小分层优先抽完，剩余名额再分配给仍有候选的分层。

输出文件：

- `data/annotation/annotation_blind.csv`：只包含原始文章文本、URL、时间戳和空白的人工标签字段，严禁包含任何预测字段。
- `data/annotation/annotation_manual_raw.csv`：标注员原始输入的审计副本，保留规范化之前的行业名称和证据句文本。
- `data/annotation/annotation_key.csv`：私有对账文件，包含 FinBERT 概率、置信度、预测行业、风险类别和证据句。第一轮标注期间不得向主标注员展示。
- `data/annotation/annotation_meta.json`：最终批次的样本量、随机种子、生成时间和文章 ID 指纹。评估报告必须引用这里持久化的最终批次种子，而不是页面输入框当前的默认值。
- `data/annotation/sentiment_errors.csv`：评估后导出的全部 FinBERT 情绪错误。
- `docs/annotation_guide.md`：情绪边界、风险类别、证据句规则以及两轮标注流程的说明。

两轮流程同时支持盲标和 `sector_ok/evidence_ok` 核对。主标注员先在看不到预测结果的情况下标注情绪和风险，并独立选出证据句。这些标签锁定之后，评估负责人才使用私有 key 文件对账行业和证据结果。`label_evidence_ok` 通过自动比较标注员和模型各自选出的证据句生成：规范化后的文本互相包含，或相似度达到 `0.85`，即记为一致。

标注完成后，评估页面会计算以下内容：情绪准确率（Accuracy）、各类别的精确率/召回率/F1（Precision/Recall/F1）、Macro F1 和 3×3 混淆矩阵；在同一批标签上对全中性基线、现有词典兜底引擎和 FinBERT 做三方对比；行业映射准确率；多标签风险分类的各类别 Precision/Recall/F1 及 Macro F1；证据 Top-1 一致率；FinBERT 可靠性分箱（reliability bins）；以及多分类 Brier 分数。证据 Top-1 一致率衡量的是双方是否选中了同一句话，比标注指南中较宽松的"可接受"标准更严格，属于保守的下界。风险 Macro F1 对 10 个已配置的标准风险类别等权计算，没有样本支撑的类别记为 0，同时展示各类别的支撑数（support）以便解读。空白的风险字段视为缺失，而不是 `none`；当前批次共有 187 个有效风险样本。

文章分类评估与六维权重敏感性分析相互独立。正式的消融实验和显著性检验留待后续工作。

### 13.1 权重敏感性分析

`src/sensitivity_analysis.py` 只从 `data/real_processed_articles.csv` 读取完整的真实新闻历史。它会拒绝 `data/processed_articles.csv` 等 Demo 数据源，也绝不会回退到这些数据。该模块复用已持久化的情绪概率、公式成分以及现有的 `sector_metrics(weights=...)` 路径，按 UTC 发布日期回放行业-日指标，无需重新运行 FinBERT。

以 `ENHANCED_WEIGHTS` 为起点，对每个维度中的每个成分分别乘以 `{0, 0.5, 0.8, 1.2, 1.5}`，再在该维度内重新归一化，使权重之和为 1。系数 `0` 相当于单成分消融；其余系数分别对应局部下调 50%、20% 和上调 20%、50%。

每次扰动都会相对于默认的 Enhanced 结果报告三项稳定性指标：11 个行业排名的日均 Spearman 相关系数；所有行业-日在 0-100 量表上的平均绝对得分变化；以及前三名行业集合的日均 Jaccard 重合度。默认的 `pairwise_distance` 分歧度公式并不使用为 `legacy_std_mix` 保留的旧版成分权重，因此扰动这些旧版权重时得到零变化是正确结果，不需要人为制造差异。

结果持久化到 `data/evaluation/sensitivity_analysis.csv`，包括生成时间、公式版本、固定的真实数据来源、目标维度与成分、扰动系数、默认权重与重新归一化后的权重，以及三项稳定性指标。只有在评估页面点击 **Run Weight Sensitivity Analysis**（运行权重敏感性分析）时才会重新计算；正常加载页面时，只展示已有结果、生成时间以及每个维度中最敏感的成分。
