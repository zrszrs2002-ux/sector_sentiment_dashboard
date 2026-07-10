# AI-powered Sector Sentiment Intelligence Dashboard

中文名：自动化板块级金融舆情雷达系统

## 1. 项目简介

本项目是一个面向日常跟踪的公开财经新闻舆情监测工具。系统从 RSS 财经新闻中提取标题、摘要、URL、发布时间和来源，经过公司/ticker/板块映射、主题与风险标签、可选 FinBERT/词典情绪模型和六维指标聚合后，在 Streamlit dashboard 中展示市场级和板块级舆情状态。

免责声明：本系统基于公开财经新闻自动分析市场舆情，结果仅供研究参考，不构成投资建议。投资有风险，决策需独立判断。

真实新闻是主要数据源；Demo 数据只作为离线兜底、测试脚手架和页面演示样本。当前版本提供 FinBERT 可选 wrapper；依赖或模型不可用时会回退到离线词典情绪 fallback，并在侧边栏/命令行给出中文提示。

## 2. 功能

- 市场总览：展示市场级六维指标、板块热力图、规则摘要和 Top Market Drivers；Unmapped 宏观新闻进入 Market Brief 和 Top Drivers，但不摊入板块聚合。
- 板块比较：比较 11 个 GICS 风格板块的 Optimism、Fear、Uncertainty、Attention、Disagreement、Risk Intensity。
- 板块详情：查看单板块雷达图、趋势框架、重点公司、主题、证据句和高风险新闻。
- 文章浏览器：查看处理后的新闻列表，支持发布时间、来源、板块、风险类别筛选，URL 可点击跳转。
- 评估：展示覆盖统计、输出分布，并提供人工标注 CSV 模板下载和准确率计算接口。
- RSS 抓取：支持 Yahoo Finance ticker RSS、CNBC Top News RSS、MarketWatch Top Stories RSS；不使用已停止服务的 Reuters RSS。

## 3. 数据来源与存储

真实新闻抓取只读取 RSS 中的标题、摘要、URL、发布时间和来源；`content` 字段使用摘要填充。第一版不抓取新闻原文页面，以减少反爬、登录限制和版权风险。

主要数据文件：

- `data/raw_articles.csv`：RSS 抓取后的真实新闻原始累积数据。多次抓取会累积保存，重复 URL+标题会合并 ticker/company/source 语境。
- `data/real_processed_articles.csv`：真实新闻经过预处理、去重、映射、标签、情绪和评分后的结果。
- `data/demo_articles.csv`：本地生成的 Demo 原始样本。
- `data/processed_articles.csv`：Demo 样本处理后的结果。
- `data/error_records.csv`：单条新闻处理失败时的降级记录，避免一条坏数据中断整批流水线。
- `data/backups/`：CSV 写入前的自动备份目录。系统采用临时文件写入、备份旧文件、原子替换，降低数据被覆盖或写坏的风险；每个源文件默认保留最近 10 份备份。

RSS 通常只覆盖最近几天的新闻。30 天趋势需要连续多日运行抓取来积累，短期内真实新闻模式下趋势图稀疏是预期行为。

## 4. 数据字典补充

- `agg_weight`：聚合权重，计算为 `time_weight * relevance_weight * dedup_factor`，用于加权平均和加权标准差。
- `attention_weight`：保留字段，恒为 0。关注度在板块层由新闻量计算，文章层无实际含义。
- `disagreement_input`：`sentiment_score` 的逐行副本，作为板块分歧度加权标准差的输入留档；聚合代码当前直接读取 `sentiment_score`。
- `time_parse_error`：发布时间或采集时间解析失败时记录 fallback 原因。
- `processing_error`：单条新闻处理失败时记录异常摘要；该行会以低权重降级输出。

## 5. 六维指标

- Optimism：文章正向概率或正向信号强度，板块层使用 `agg_weight` 加权平均。
- Fear：文章负向概率或风险担忧强度，板块层使用 `agg_weight` 加权平均。
- Uncertainty：中性概率与概率熵的组合，板块层使用 `agg_weight` 加权平均。
- Attention：板块层指标。当前使用近 7 天窗口内该板块加权新闻量在 11 个板块中的排名分位数，公式为 `100 * (rank - 0.5) / 板块数`，并列取平均排名。
- Disagreement：板块内 `sentiment_score` 的加权标准差，`D = 100 * clip(weighted_std, 0, 1)`；板块内新闻少于 2 条时为 0。
- Risk Intensity：文章层默认由风险标签严重度映射到 0-100。早期“负向情绪压力/不确定性压力”公式已放到 `src/config.py` 的 `RISK_USE_SENTIMENT_PRESSURE` 开关后，默认关闭，避免与 Fear/Uncertainty 维度耦合。板块层使用 `0.7 * 加权平均 + 0.3 * P90`，样本不足时用均值替代 P90。

市场级雷达当前采用 11 个板块等权平均，而不是新闻量加权，以避免真实新闻流量过度集中在少数高曝光板块时主导市场总览。

## 6. 本地运行

```bash
cd sector_sentiment_dashboard
python setup_env.py
streamlit run app.py
```

`setup_env.py` 会自动探测 NVIDIA GPU：有 GPU 时安装 CUDA 版 torch，无 GPU 或探测失败时安装 CPU 版 torch；如果已检测到本地 GPU 版 torch，会跳过 torch 安装，避免覆盖。脚本会从云端完整清单中读取并安装其余应用依赖，但主动排除其中的 CPU torch 和 transformers，再单独安装适合本地环境的版本，最后打印 torch 版本、CUDA 状态和中文结论。

本地环境禁止执行 `pip install -r requirements.txt`，因为该文件固定包含云端 CPU 版 torch，可能覆盖已经可用的本地 GPU 版本。

默认配置只读取本地缓存中的 `ProsusAI/finbert`，不会在 dashboard 运行时强制联网下载；模型不可用时自动回退词典模型。

FinBERT 相关配置集中在 `src/config.py`：

- `SENTIMENT_DEVICE = "auto"`：可选 `auto/cuda/cpu`；`auto` 会在 `torch.cuda.is_available()` 为 True 时使用 CUDA。
- `FINBERT_LOCAL_FILES_ONLY`：从环境变量读取，默认 `1`，本地只读已有模型缓存；云端设为 `0` 后允许首次启动下载模型。
- `FINBERT_BATCH_SIZE`：从环境变量读取，默认 `32`；云端建议设为 `8` 以降低 CPU 内存峰值。
- 标签映射使用 `model.config.id2label` 动态解析，并在启动时做映射测试，避免把 `negative` 和 `neutral` 的概率静默互换。

命令行抓取真实 RSS 新闻：

```bash
python -m src.news_collector
```

也可以在 Streamlit 侧边栏点击“抓取最新新闻”。真实数据文件非空时，页面默认使用真实新闻；真实数据为空或不可读时，系统会提示并回落到 Demo 数据。

## 7. 云端部署

Streamlit Community Cloud 直接使用项目根目录的 `requirements.txt`。该文件已包含 CPU 版 torch、transformers 和全部应用依赖；旧的 `requirements-full.txt` 已废弃并删除。本地安装仍一律使用 `python setup_env.py`。

在 Streamlit Community Cloud 的 Secrets 中配置：

```toml
OPENAI_API_KEY = "your_replacement_api_key"
FINBERT_LOCAL_FILES_ONLY = "0"
FINBERT_BATCH_SIZE = "8"
DEMO_PIN = "your_private_demo_pin"
```

`DEMO_PIN` 用于保护侧边栏“立即重新生成简报”操作，避免公开演示页面被反复调用而产生 API 费用。不要将真实 key 或口令提交到仓库。

云端首次启动需要下载约 440MB 的 `ProsusAI/finbert` 模型，页面会显示等待提示；下载时间受网络和实例性能影响，CPU 推理也会比本地 GPU 慢。模型下载或加载失败时系统会继续使用词典模型，不会中断页面。

Community Cloud 容器文件系统具有易失性：运行期间抓取的新 RSS、快照、历史简报和模型缓存可能在休眠、重启或重新部署后消失。公开演示的基准数据以仓库中已提交的 `data/` 文件为准；需要永久积累真实新闻时，应另接持久化存储。

## 8. 当前限制

- FinBERT 是可选引擎；没有本地模型缓存或依赖时会回退词典模型。
- RSS 摘要可能很短，证据句质量受来源摘要质量限制。
- 宏观/市场级 Unmapped 新闻当前主要进入文章浏览和市场驱动展示；不强行摊入 11 个板块聚合。
- 评估模块当前只做覆盖统计、输出分布和人工标注 CSV 准确率，不包含消融或敏感性分析。
- 当前不提供投资建议，也不用于实时交易。

## 9. 后续方向

- 扩展 evaluation：消融、敏感性分析、更多标注字段。
- 更完整的 Top Drivers 解释和宏观新闻处理策略。

## 10. 每日市场简报与调度

系统已加入“抓取多次/天、简报一次/天”的解耦机制：

- `python -m src.news_collector` 每次运行会抓取 RSS、累积写入 `data/raw_articles.csv`，并只对新增 `article_id` 运行映射、标签、情绪和评分管线；日志会输出“本次新增 N 条，复用 M 条”。
- 每次处理完成后会刷新 `data/sector_daily_scores.csv` 和 `data/market_daily_scores.csv`。同一 UTC 日期重跑会覆盖当天行，历史行不动；Sector Detail 的 7/30 天趋势优先读取这些快照。
- 简报门闸由 `BRIEF_GENERATION_HOUR_LOCAL` 控制。当前时间已过本地生成时刻且今天尚未生成过简报时，才会写入 `data/latest_brief.md`，并按日期归档到 `data/briefs/`。
- LLM 简报使用 OpenAI 官方 Python SDK，API key 从环境变量 `OPENAI_API_KEY` 读取。调用前会用 `models.list()` 核实 `LLM_MODEL_BRIEF` 是否为当前账户实际可用的模型 ID；没有 key、SDK 不可用、模型不可用或调用失败时都会回退到规则模板，管线不会崩溃。Streamlit 页面渲染路径只读取 `latest_brief.md`，不会自动调用 LLM API。
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
