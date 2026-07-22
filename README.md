# AI-powered Sector Sentiment Intelligence Dashboard

An automated sector-level financial news sentiment radar.

## 1. Project Overview

This project is a public financial-news sentiment monitoring tool designed for daily tracking. It extracts titles, summaries, URLs, publication timestamps, feed sources, and actual publishers from financial RSS feeds. Full text is selectively retrieved only for high-value articles and is used solely for model analysis. After company, ticker, and sector mapping; topic and risk tagging; optional FinBERT or lexicon-based sentiment analysis; event-level clustering; and six-dimensional metric aggregation, the results are presented in a Streamlit dashboard at both market and sector levels.

Disclaimer: This system automatically analyzes market sentiment from public financial news. Its output is for research purposes only and does not constitute investment advice. Investing involves risk, and all decisions should be made independently.

Real news is the primary data source. Demo data is retained only as an offline fallback, testing scaffold, and UI demonstration sample. The current version includes an optional FinBERT wrapper. If its dependencies or model are unavailable, the system falls back to the offline lexicon sentiment engine and displays an explanatory message in the sidebar or command line.

## 2. Features

- Market Overview: displays market-level six-dimensional metrics, a sector heatmap, the daily brief, and event-collapsed Top Market Drivers. Each event can be expanded to show all related coverage. Unmapped macro news is included in the Market Brief and Top Drivers but is not allocated to sector aggregates.
- Sector Comparison: compares Optimism, Fear, Uncertainty, Attention, Disagreement, and Risk Intensity across 11 GICS-style sectors.
- Sector Detail: shows a sector radar chart, trend framework, key companies, topics, evidence sentences, and high-risk news.
- Article Explorer: displays processed articles with filters for publication time, publisher, sector, and risk category, plus optional grouping by `event_id`. URLs are clickable.
- Evaluation: provides a 300-item stratified blind-labeling workflow, an all-neutral/lexicon/FinBERT three-way classification comparison, confusion matrices, risk and evidence metrics, FinBERT calibration, and error analysis. Descriptive comparisons of the six-dimensional formulas remain in a separate section.
- RSS collection: 20 active source definitions are managed externally in `data/rss_sources.json`, including Yahoo ticker templates, CNBC categories, MarketWatch categories, Google News, Nasdaq, Benzinga, The Motley Fool, Investing.com, Fortune, Business Insider, and NYT Business. The discontinued Reuters RSS service is not used.

Heatmaps on Market Overview and Sector Comparison use continuous color scales by mode. In relative mode, Optimism uses `Greens`, Attention uses `Blues`, and the remaining caution-oriented metrics use `RdYlGn_r`, where higher values trend red. In absolute mode, Optimism remains `Greens`, Attention remains `Blues`, Fear uses `Reds` for a clear green/red contrast, and Uncertainty, Disagreement, and Risk Intensity continue to use `RdYlGn_r`.

## 3. Data Sources and Storage

The RSS layer reads only the title, summary, URL, publication timestamp, feed name, and the entry's `source/publisher`. If `publisher` is missing, the feed name is used as a fallback. `content` always retains the RSS summary. Full text is selectively retrieved for high-value articles from the current day and stored in `body_text`; it is used only for model analysis and is never displayed in the UI. Full-text requests are disabled in configuration for paywalled or aggregator redirect sources such as MarketWatch, Google News, Fortune, Business Insider, and NYT, which remain headline-feed sources only.

The 20 currently enabled sources are: Yahoo Finance ticker template; CNBC Top News, Markets, Technology, Economy, Earnings, and Business; MarketWatch Top Stories, Real-time Headlines, and Market Pulse; Google News Business and Markets; Nasdaq Markets and Earnings; Benzinga Markets; The Motley Fool; Investing.com Stock Market News; Fortune; Business Insider; and NYT Business.

Primary data files:

- `data/raw_articles.csv`: cumulative raw real-news data collected from RSS. Repeated runs append data, while duplicate URL/title pairs merge ticker, company, publisher, and source context.
- `data/rss_sources.json`: RSS source definitions, source types, enabled state, per-source limits, source-quality weights, and full-text permission policies.
- `data/real_processed_articles.csv`: real news after preprocessing, deduplication, mapping, tagging, sentiment analysis, and scoring.
- `data/fulltext_cache.json`: permanent cache of full-text requests. Both successful retrievals and failed attempts are recorded. The same article ID, URL, or normalized title is not requested again.
- `data/demo_articles.csv`: locally generated raw demo samples.
- `data/processed_articles.csv`: processed demo samples.
- `data/error_records.csv`: degraded records for individual article-processing failures, preventing a single bad item from stopping the batch pipeline.
- `data/sector_daily_scores.csv`: daily sector snapshots. `baseline` and `enhanced` formula versions are stored separately for each day, with `pipeline_revision` recording semantic revisions. Revision r4 adds raw event-count and publisher-count fields.
- `data/market_daily_scores.csv`: daily market snapshots, with the same dual formula-version writes and pipeline revision as sector snapshots.
- `data/backups/`: automatic backups created before CSV writes. The system writes to a temporary file, backs up the previous file, and performs an atomic replacement to reduce overwrite and corruption risk. By default, the 10 most recent backups are retained for each source file.

RSS feeds usually expose only the most recent few days. A 30-day trend requires the collector to run continuously over time, so sparse trend charts are expected shortly after real-news mode is first enabled.

## 4. Data Dictionary Additions

- `agg_weight`: aggregation weight calculated as `time_weight * relevance_weight * dedup_factor * source_weight`, used for weighted means and weighted standard deviations.
- `source_weight`: source-quality prior from `rss_sources.json`. Major direct sources usually use `1.0`, while aggregators and smaller sources use `0.8-0.95`. When duplicate articles are merged across feeds, the maximum value is retained. These weights remain subject to calibration against human annotations.
- `publisher`: actual publisher from the RSS entry, falling back to the feed name when absent. This allows aggregator feeds such as Google News to preserve the original publisher where available.
- `event_id`: event-cluster ID, equal to the `article_id` of the representative article with the highest `agg_weight`. An article that is not clustered with another article uses its own `article_id`.
- `source_count`: number of distinct `publisher` values in an event cluster. All articles with the same `event_id` share the same value.
- `body_text`: full text extracted by Trafilatura, used only for model analysis and offline evaluation and never displayed in the UI.
- `content_level`: either `summary` or `fulltext`, used during the second sprint to compare summary-based and full-text signals.
- `rescored`: whether sentiment, evidence sentence, risk, and topic processing has been rerun after full-text retrieval.
- `pipeline_revision`: semantic revision of the daily snapshot pipeline. `r1` is the early pipeline, `r2` adds the risk-formula and clustering guards, `r3` adds multi-source publishers and source weights, and `r4` adds the Tier-A Fear/Risk/Disagreement formulas and snapshot-count columns. Multiple revisions for the same day coexist under a composite key so trend discontinuities remain auditable.
- `event_count` / `publisher_count`: deduplicated event count and independent publisher count in a daily sector snapshot. Historical rows before r4 retain null values. These fields accumulate from r4 onward for a future three-component Attention ECDF and within-sector historical percentile display.
- `b_bull` / `b_bear`: normalized sentence-level matches for bullish and bearish stance terms.
- `g_growth` / `s_shock`: normalized sentence-level matches for growth themes and market panic or risk-off reactions. `s_shock` is retained for CSV compatibility, while its actual vocabulary now comes from `panic_keywords.json`.
- `k_unc`: normalized sentence-level score from the expanded uncertainty dictionary.
- `entropy_norm`: FinBERT three-class probability entropy divided by `log(3)`, producing a 0-1 score.
- `attention_weight`: retained field fixed at 0. Attention is calculated at sector level from article volume and has no article-level meaning.
- `disagreement_input`: row-level copy of `sentiment_score` retained as the input to sector disagreement. The default aggregation computes weighted pairwise absolute distance directly from it.
- `time_parse_error`: fallback reason recorded when the publication or collection timestamp cannot be parsed.
- `processing_error`: exception summary recorded when an article fails processing; the row is emitted in a low-weight degraded form.

## 5. Six-dimensional Metrics

### 5.1 Components and Dictionaries

Growth, panic, bullish/bearish stance, and uncertainty components share a sentence-level matching function: `K = min(matched sentence count / total sentence count * 3, 1)`. The coefficient `3` is configured through `KEYWORD_SENTENCE_SCORE_MULTIPLIER`. Fear's `S_shock` now reads from `panic_keywords.json` and covers only reactions such as panic selling, risk-off behavior, and flight to safety. Risk events such as defaults, investigations, and recessions no longer enter Fear a second time. `positive_direction_blockers.json` blocks growth or bullish matches when the same sentence contains opposing modifiers such as `slows`, `misses`, `cut`, `weak`, or `decline`. `shock_keywords.json` is retained as an audit grouping for risk events but is no longer used by Fear.

The uncertainty vocabulary merges the original list with currently active Uncertainty terms from the University of Notre Dame [Loughran-McDonald Master Dictionary](https://sraf.nd.edu/loughranmcdonald-master-dictionary/). Citation: Loughran, T. and McDonald, B. (2011), [When Is a Liability Not a Liability? Textual Analysis, Dictionaries, and 10-Ks](https://ssrn.com/abstract=1331573), *Journal of Finance*, 66(1), 35-65. The merged `k_unc` vocabulary contains 302 unique terms.

### 5.2 Article-level Formulas

Let `p_pos/p_neu/p_neg` be the FinBERT probabilities and `H_norm = -sum(p * log(p)) / log(3)`. `ACTIVE_WEIGHTS` currently points to Enhanced:

- Optimism: `100 * clip(0.7*p_pos + 0.2*B_bull + 0.1*G_growth, 0, 1)`.
- Fear: `100 * clip(0.7*p_neg + 0.2*B_bear + 0.1*S_panic, 0, 1)`. Its technical meaning is narrowed to downside and risk-off pressure and is separated from event-risk severity. The persisted field name remains `s_shock`.
- Uncertainty: `100 * clip(0.4*p_neu + 0.3*H_norm + 0.3*K_unc, 0, 1)`.

Baseline uses the same functions with weights `1/0/0`, `1/0/0`, and `0.6/0.4/0`. The three probabilities and all six components are persisted to the processed CSV, so weight changes and ablations require arithmetic recomputation only, without rerunning FinBERT or dictionary matching. `BASELINE_WEIGHTS`, `ENHANCED_WEIGHTS`, and `ACTIVE_WEIGHTS` are centralized in `src/config.py`; a one-step rollback only requires pointing `ACTIVE_WEIGHTS` to the baseline group.

### 5.3 Sector-level Formulas

- Optimism / Fear / Uncertainty: `agg_weight`-weighted article means.
- Attention cold start: cross-sectional rank percentile of seven-day weighted sector article volume `N = sum(agg_weight)`, calculated as `100 * (rank - 0.5) / 11`, with average ranks for ties.
- Attention Enhanced: after a sector accumulates at least `ATTENTION_MIN_HISTORY_DAYS = 30` snapshot days, it automatically switches to `100 * clip(0.7*ECDF_hist(N) + 0.3*ECDF_hist(Growth), 0, 1)`. `Growth` is measured relative to the recent seven-day average weighted article volume. Sectors with insufficient history remain on the cold-start path and are identified in comparison notes. The Baseline historical path uses `1.0*ECDF_hist(N) + 0.0*ECDF_hist(Growth)`.
- Disagreement: the default threshold-free method calculates `100 * sum(i<j) w_i*w_j*|s_i-s_j| / (DISAGREEMENT_PAIRWISE_NORMALIZATION * sum(i<j) w_i*w_j)`, with a current normalization coefficient of 2.0. Fewer than two articles produce 0. `DISAGREEMENT_METHOD="legacy_std_mix"` restores the previous weighted-standard-deviation and PolarityMix method for ablation. The normalization coefficient remains subject to human-label calibration.
- Risk Intensity: 0 when no risk is matched. Each matched category first receives sentence density `r_k = min(matched sentence count / total sentence count * 3, 1)`, then `q_k=(v_k/5)*r_k`. The default article-level combination is `100*(1-product(1-q_k))` with `RISK_COMBINE="noisy_or"`; `sum` is retained as the legacy ablation option. At sector level, the highest-`agg_weight` representative for each `event_id` is selected to prevent duplicate event coverage from being counted repeatedly. The aggregate is then `0.7 * weighted mean + 0.3 * weighted P90`; with fewer than three events, the mean replaces P90.
- The macro-risk dictionary treats recession, stagflation, and hard landing as strong triggers. Weak signals such as inflation, economic slowdown, and consumer weakness require at least two distinct matches in the same article. This threshold is controlled by the dictionary-level `min_distinct_hits` setting and prevents broad terms such as `market`, `economy`, or `growth` from generating widespread false positives.

All Enhanced weights above are expert priors and are marked with TODOs in `config.py`. Formal ablation and sensitivity analysis use the human-annotation workflow. Daily sector and market snapshots store Baseline and Enhanced results separately by `formula_version`; trend charts and LLM briefs read only `ACTIVE_FORMULA_VERSION`.

The market radar currently averages the 11 sectors equally rather than weighting by article volume, preventing a few high-coverage sectors from dominating the market overview.

## 6. Local Setup

```bash
cd sector_sentiment_dashboard
python setup_env.py
streamlit run app.py
```

`setup_env.py` automatically detects an NVIDIA GPU. It installs the CUDA build of torch when a GPU is available and the CPU build otherwise. If an existing local GPU-enabled torch installation is detected, torch installation is skipped to avoid overwriting it. The script reads the cloud base list in `requirements.txt` and the local feature add-ons in `requirements-full.txt`, excludes the cloud CPU torch and transformers entries, and then installs versions suitable for the local environment. The add-on list currently pins `sentence-transformers==5.6.0` for event embedding clustering.

Do not run `pip install -r requirements.txt` for local setup because that file pins the cloud CPU build of torch and may overwrite a working local GPU build.

FinBERT uses two-stage loading by default: it first reads the `ProsusAI/finbert` cache in strict local mode and starts immediately on a cache hit. Only a cache miss permits an online download. Download or model-loading failures automatically fall back to the lexicon engine.

FinBERT settings are centralized in `src/config.py`:

- `SENTIMENT_DEVICE = "auto"`: accepts `auto/cuda/cpu`; `auto` uses CUDA when `torch.cuda.is_available()` is true.
- `FINBERT_LOCAL_FILES_ONLY`: defaults to `auto`, reading the cache first and downloading only after a miss. Set it explicitly to `1` for strict offline mode with no download retry.
- `FINBERT_BATCH_SIZE`: read from the environment at runtime and defaults to `32`. A value of `8` is recommended in the cloud to reduce peak CPU memory.
- `HF_TOKEN`: optional Hugging Face token passed to tokenizer and model download requests to reduce rate-limit risk on shared outbound IP addresses.
- `FINBERT_REVISION`: pinned to `4556d13015211d73dccd3fdd39d39232506f3e43` so local and cloud environments use identical weights instead of silently following upstream `main`.
- Label mapping is resolved dynamically from `model.config.id2label` and tested at startup to prevent silent swaps between `negative` and `neutral` probabilities.

Collect real RSS news from the command line:

```bash
python -m src.news_collector
```

You can also select **Fetch Latest News** in the Streamlit sidebar. Real news is used by default when the real-data file is non-empty. If the file is empty or unreadable, the system displays a warning and falls back to Demo data.

## 7. Cloud Deployment

Streamlit Community Cloud uses the project-root `requirements.txt`. It contains the CPU FinBERT dependencies but does not install `sentence-transformers`; cloud event clustering therefore uses the lexical Jaccard path automatically. `requirements-full.txt` contains the local embedding add-on, and local installation should always use `python setup_env.py` to protect a GPU-enabled torch installation.

Configure these values in Streamlit Community Cloud Secrets:

```toml
OPENAI_API_KEY = "your_replacement_api_key"
FINBERT_BATCH_SIZE = "8"
DEMO_PIN = "your_private_demo_pin"
# Optional: configure this if the shared Hugging Face outbound IP is rate-limited.
HF_TOKEN = "hf_your_optional_token"
```

`DEMO_PIN` protects the sidebar's **Regenerate Brief Now** operation from repeated use on a public demo, which could incur API costs. Never commit real keys or passwords to the repository.

`FINBERT_LOCAL_FILES_ONLY` does not need to be configured in the cloud. The default `auto` mode checks the cache first and, on a miss, downloads the approximately 440 MB `ProsusAI/finbert` model while displaying a waiting message. Download time depends on network and instance performance, and CPU inference is slower than a local GPU. If download or model loading fails, the system continues with the lexicon engine. Set the variable to `1` only for fully offline operation.

The Community Cloud container filesystem is ephemeral. RSS data, snapshots, historical briefs, and model caches created at runtime may disappear after sleep, restart, or redeployment. The public demo baseline is the committed content under `data/`. Use separate persistent storage if long-term real-news accumulation is required.

## 8. Current Limitations

- FinBERT is optional and falls back to the lexicon engine when its model cache or dependencies are unavailable.
- The event embedding threshold of `0.72` is a prior that still requires calibration. Articles about the same company and topic but different events may be merged incorrectly; this should be evaluated against labeled article pairs.
- RSS summaries may be short, so evidence quality depends on source-summary quality.
- Historical RSS entries without a stored publisher can only fall back to the previous feed name. Newly collected records prefer the actual publisher in the entry.
- Full-text retrieval depends on site robots rules, page structure, and anti-bot controls. Failures silently fall back to the summary and are cached permanently rather than retried automatically.
- Unmapped macro and market news currently appears mainly in Article Explorer and market-driver displays and is not forced into the 11 sector aggregates.
- The Evaluation module includes descriptive comparisons, annotation-based model evaluation, and weight sensitivity analysis. Additional ablation and significance testing remain future work.
- The project does not provide investment advice and is not intended for real-time trading.

## 9. Future Work

- Extend evaluation with formal ablation, significance testing, and additional annotation fields.
- Calibrate embedding and lexical thresholds against labeled event pairs and evaluate whether articles inside a cluster should be down-weighted.

## 10. Daily Market Brief and Scheduling

The system separates frequent collection from once-daily brief generation:

- Each `python -m src.news_collector` run reads source definitions from `rss_sources.json`, appends to `data/raw_articles.csv`, and runs mapping, tagging, sentiment, and scoring only for new `article_id` values. Logs report how many items were new and how many were reused.
- After summary processing, the system selects full-text candidates from the current UTC day: Top Driver candidates, articles with `|sentiment_score| >= 0.5`, articles with `risk_intensity >= 60`, or representatives of multi-article events. Each run handles at most 30 articles, waits at least one second between requests, uses a 10-second timeout, and does not retry failures. Successfully retrieved articles are rescored in a batch, today's snapshots are rewritten, and the brief gate runs last.
- Every completed processing run refreshes `data/sector_daily_scores.csv` and `data/market_daily_scores.csv`. Baseline and Enhanced rows are upserted separately by `formula_version` for the current UTC date; historical dates are left untouched, and legacy history is labeled `baseline`. Sector Detail trends and LLM briefs read only the active formula version.
- The brief gate is controlled by `BRIEF_GENERATION_HOUR_LOCAL`. It writes `data/latest_brief.md` and a dated file under `data/briefs/` only when the local generation time has passed and today's brief has not already been generated.
- The LLM brief uses the official OpenAI Python SDK and reads `OPENAI_API_KEY` from the environment. At runtime it attempts `gpt-5.6-terra` followed by `gpt-5.5`; `models.list()` is informational rather than a hard availability gate. A first HTTP 429 from the preferred model waits five seconds and retries once. If rate limiting persists, or the model is missing, unauthorized, at capacity, or temporarily unavailable, the next candidate is attempted. If every candidate fails, the key is absent, the SDK is unavailable, or another API error occurs, a rule-based template is used and the pipeline continues. Each generation logs candidate attempts, outcomes, the final model, and the reason, and writes that metadata into both the latest and dated brief. The AI brief is organized as Core View, Market Overview, Sector and Event Deep Dive, Risks and Tomorrow's Watch List, and Data Scope and Disclaimer, targeting 900-1,200 words. The page attribution displays the model that actually succeeded. Streamlit only reads `latest_brief.md` and never invokes the LLM API during page rendering.
- RSS covers only the most recent few days. Thirty-day trends require continuous collection, so sparse real-news trend charts are expected during the initial accumulation period.

Set the API key in PowerShell before enabling the LLM locally:

```powershell
$env:OPENAI_API_KEY="your_api_key"
```

Register a Windows Scheduled Task that collects every four hours:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup_schedule.ps1
```

Inspect the task:

```powershell
Get-ScheduledTask -TaskName SectorSentimentRSSCollector
```

Remove the task:

```powershell
Unregister-ScheduledTask -TaskName SectorSentimentRSSCollector -Confirm:$false
```

## 11. Storage Tiers and Working-set Window

- `data/raw_articles.csv` is retained permanently for second-stage human-annotation sampling. When it exceeds 50 MB, the system logs a recommendation to migrate to SQLite; the current version does not perform that migration.
- The dashboard loads only the most recent `WORKING_SET_DAYS = 30` days of processed news by default to reduce page-computation cost. Article Explorer provides a **Load Full History** option.
- Daily snapshot tables are not constrained by the working-set window and accumulate permanently.

## 12. Event-level Collapsing

- `EVENT_SIMILARITY_ENGINE = "embedding"` by default and uses `sentence-transformers/all-MiniLM-L6-v2`. Two articles are merged only when they are published within 48 hours, share at least one ticker, and have title-plus-summary cosine similarity of at least `0.72`. Unmapped articles without tickers use the stricter `0.82` threshold.
- If the embedding dependency, model, or inference path is unavailable, the system falls back to lexical matching. Content-word Jaccard thresholds are `0.40` for ticker-linked articles and `0.55` for Unmapped articles without tickers. Logs report the requested engine, actual engine, device, and fallback reason.
- Clustering uses union-find, but the total timespan of any event cluster cannot exceed 72 hours. An edge is also blocked if one article has sentiment above `+0.3` and the other below `-0.3`. Full processing recalculates the supplied history; incremental collection compares new articles only with their 48-hour neighborhood and other newly collected articles. Embeddings exist only in memory and are not persisted.
- Top Drivers displays only the highest-`agg_weight` representative for each event, while cluster-level `driver_score` takes the maximum article-level value. A cluster with `source_count >= 3` receives `EVENT_COVERAGE_BOOST = 1.15` for display ranking only.
- Market Overview supports **Last 48 Hours** (default) and **Last 30 Days**. If the 48-hour mode contains fewer than `DRIVER_MIN_EVENTS = 5` events, it expands to 72 and then 168 hours, and the heading shows the actual window. The 30-day mode matches `WORKING_SET_DAYS` and does not expand. The daily market brief continues to use its existing 24-hour payload, so the two windows intentionally differ.
- Unmapped macro and market events are guaranteed inclusion in Top Drivers but retain descending `driver_score` order. Entries included only through this guarantee are marked as a macro fallback and are not pinned to the top.
- Event collapsing does not modify `dedup_factor`, `agg_weight`, or six-dimensional aggregation. Independent reports still contribute separately to Attention and sentiment. Whether cluster members should be down-weighted remains an evaluation question.

Manually recalculate event IDs in a processed CSV:

```bash
python -m src.event_clustering --input data/real_processed_articles.csv --engine embedding
python -m src.event_clustering --input data/real_processed_articles.csv --engine lexical --dry-run
```

## 13. Model Evaluation Toolchain

Generate a 300-item blind-labeling sample from the complete accumulated raw-news set:

```bash
python scripts/sample_for_annotation.py
```

The script and **Step 1** on the Evaluation page use deterministic round-robin balancing across predicted sector x FinBERT class. Sample size and random seed are configurable on the page and default to `300` and `5720`. The same article pool, size, and seed reproduce the exact same `article_id` set; changing the seed generates a new batch. Small strata are exhausted first, and remaining capacity is allocated across strata that still have candidates.

Outputs:

- `data/annotation/annotation_blind.csv`: contains only source article text, URL, timestamp, and blank human-label fields. Prediction fields are strictly prohibited.
- `data/annotation/annotation_manual_raw.csv`: audit copy of the annotator's original input, preserving pre-normalization sector names and evidence-sentence text.
- `data/annotation/annotation_key.csv`: private reconciliation file containing FinBERT probabilities, confidence, predicted sector, risk categories, and evidence sentence. It must not be shown to the primary annotator during the first pass.
- `data/annotation/annotation_meta.json`: final batch size, random seed, generation time, and article-ID fingerprint. Evaluation reports must cite the persisted final-batch seed rather than the page input's current default.
- `data/annotation/sentiment_errors.csv`: all FinBERT sentiment errors exported after evaluation.
- `docs/annotation_guide.md`: sentiment boundaries, risk categories, evidence-sentence rules, and the two-pass annotation process.

The two-pass process supports both blind labeling and `sector_ok/evidence_ok`. The primary annotator first labels sentiment and risk and independently selects an evidence sentence without seeing predictions. After those labels are locked, the evaluation owner uses the private key only to reconcile sector and evidence results. `label_evidence_ok` is generated by automatically comparing the annotator and model evidence sentences: a match is recorded when normalized text contains the other sentence or similarity reaches `0.85`.

After labels are completed, the Evaluation page calculates sentiment Accuracy, per-class Precision/Recall/F1, Macro F1, and a 3x3 confusion matrix; a three-way comparison among the all-neutral baseline, the existing lexicon fallback, and FinBERT on the same labels; sector-mapping Accuracy; per-class multi-label risk Precision/Recall/F1 and Macro F1; evidence Top-1 agreement; FinBERT reliability bins; and multiclass Brier score. Evidence Top-1 agreement measures whether both sides selected the same sentence and is a stricter conservative lower bound than the annotation guide's broader acceptability criterion. Risk Macro F1 equally weights the 10 configured canonical risk categories, assigning 0 to unsupported categories while displaying support for interpretation. Blank risk fields are treated as missing rather than `none`; the current batch contains 187 valid risk samples.

Article-classification evaluation and six-dimensional weight sensitivity analysis are independent. Formal ablation and significance testing remain future work.

### 13.1 Weight Sensitivity Analysis

`src/sensitivity_analysis.py` reads the full real-news history exclusively from `data/real_processed_articles.csv`. It rejects Demo sources such as `data/processed_articles.csv` and never falls back to them. The module reuses persisted sentiment probabilities, formula components, and the existing `sector_metrics(weights=...)` path to replay sector-day metrics by UTC publication date without rerunning FinBERT.

Starting from `ENHANCED_WEIGHTS`, each component in each dimension is multiplied independently by `{0, 0.5, 0.8, 1.2, 1.5}` and then renormalized within that dimension so its weights sum to 1. Factor `0` is a single-component ablation; the other factors represent local reductions of 20%/50% and increases of 20%/50%.

Each perturbation reports three stability metrics relative to the default Enhanced result: mean daily Spearman correlation across the 11 sector rankings; mean absolute score change across all sector-days on the 0-100 scale; and mean daily Jaccard overlap of the Top-3 sector sets. The default `pairwise_distance` Disagreement formula does not consume the legacy component weights retained for `legacy_std_mix`, so perturbing those legacy weights may correctly produce zero change rather than forcing an artificial result.

Results are persisted to `data/evaluation/sensitivity_analysis.csv`, including generation time, formula version, fixed real-data source, target dimension and component, perturbation factor, default and renormalized weights, and all three stability metrics. Recalculation occurs only when **Run Weight Sensitivity Analysis** is selected on the Evaluation page. Normal page loads display existing results, generation time, and the most sensitive component in each dimension.
