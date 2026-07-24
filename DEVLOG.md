# DEVLOG

## 2026-07-06 21:58

- Stage / objective: Build the Phase 1 project skeleton.
- Work completed: Inspected the workspace and confirmed that `sector_sentiment_dashboard` did not yet exist. Confirmed local Python 3.12.7 and that Streamlit was not installed. Created the project structure, `requirements.txt`, `requirements-full.txt`, `README.md`, `app.py`, `data/demo_articles.csv`, `data/processed_articles.csv`, placeholder modules under `src/`, and four Streamlit page files. Selected `streamlit==1.58.0` and organized the multipage app with `st.Page` and `st.navigation`.
- Issues and resolution: The default `python` command pointed to Windows Python Manager and was denied in the sandbox. Switched to the full path of the local Python 3.12 installation and confirmed the version with a read-only check. Streamlit was not installed, so the app was not launched in this phase; installation and run commands were provided instead.
- Current status: The project skeleton is complete. After dependency installation, the demo framework can be opened with `pip install -r requirements.txt` followed by `streamlit run app.py`.
- Next step: After user confirmation, expand Demo data to 100-150 records and implement loading, UTC timestamp handling, duplicate marking, and baseline preprocessing.

## 2026-07-07 00:17

- Stage / objective: Phase 2 data-layer enhancement.
- Work completed: Added `src/demo_data_generator.py` to generate 132 deterministic financial-news samples across 11 sectors, 12 per sector, with UTC timestamps from 2026-06-07 through 2026-07-07. Expanded `src/preprocessing.py` with UTC normalization, URL deduplication, exact-title deduplication, and highly similar repost detection. Centralized article fields in `src/config.py`. Added `load_articles()` to `src/data_loader.py`, preferring `data/processed_articles.csv`. Updated all four pages to use processed data and regenerated `data/demo_articles.csv` and `data/processed_articles.csv`.
- Issues and resolution: The initial similar-title threshold was too broad and template-based titles were frequently misclassified as duplicates. Title templates were revised and preprocessing now requires a matching prefix token plus a conservative similarity threshold. The final distribution is 102 unique articles, 19 highly similar reposts, and 11 clear duplicates.
- Current status: The Phase 2 data layer is complete. `processed_articles.csv` contains 132 records covering all 11 sectors, and timestamps use UTC ISO 8601. Python 3.12 compilation passed.
- Next step: Implement company/ticker/sector mapping, topic and risk dictionaries, and an offline lexicon sentiment fallback.

## 2026-07-07 00:17

- Stage / objective: Synchronize README with Phase 2.
- Work completed: Updated `README.md` from the Phase 1 small-demo description to the Phase 2 data-layer state, documenting 132 Demo articles, `processed_articles.csv`, the UTC date range, and baseline deduplication.
- Issues and resolution: None.
- Current status: README matches the current code and data. The dashboard still starts with `streamlit run app.py`.
- Next step: Proceed to Phase 3 mapping, dictionaries, and sentiment fallback after confirmation.

## 2026-07-07 01:05

- Stage / objective: Phase 3 rule recognition and lexicon sentiment fallback.
- Work completed: Added four standalone dictionaries: `data/dictionaries/company_sector_mapping.json`, `topic_keywords.json`, `risk_keywords.json`, and `sentiment_lexicon.json`. Implemented company aliases, tickers, and sector keyword mapping in `src/mapping.py`; topic, risk-category, and risk-evidence detection in `src/topic_risk_tagger.py`; an offline sentence-level lexicon sentiment fallback with article-level probability aggregation in `src/sentiment_model.py`; and initial article-level six-dimensional scores from fallback sentiment and risk severity in `src/scoring.py`. Added `src/article_pipeline.py` to connect preprocessing, mapping, tagging, sentiment, and scoring. Updated the Demo generator to invoke the Phase 3 pipeline, refreshed `data/processed_articles.csv`, and updated README.
- Issues and resolution: An initial review found 16 articles still falling into `general market sentiment`, indicating insufficient topic coverage. Added rules for actual Demo phrases such as streaming margins, pricing power, drug pipeline, capital spending, cash flow, tenant demand, and copper prices. Only two fallback topics remain. Hugging Face was not used because the course demo needed to run offline; the lexicon fallback was implemented first.
- Current status: `processed_articles.csv` contains 132 records, 12 for each of the 11 sectors. There are no unmapped sectors, every article has companies and tickers, 10 risk categories are represented, and duplicate weights cover 102 unique articles, 19 similar reposts, and 11 clear duplicates.
- Next step: Build the formal aggregation layer using `time_weight * relevance_weight * dedup_factor`, sector and market radars, Top Drivers, positive/negative/risk news, and evidence aggregation.

## 2026-07-07 01:31

- Stage / objective: Phase 4 formal aggregation of the six dimensions.
- Work completed: Corrected the radar fields in `src/config.py` to `optimism`, `fear`, `uncertainty`, `attention`, `disagreement`, and `risk_intensity`. Added `p_positive`, `p_neutral`, `p_negative`, `relevance_weight`, `time_weight`, and `agg_weight` to `src/scoring.py`, defining `agg_weight = time_weight * relevance_weight * dedup_factor`. Rewrote `src/aggregation.py` with weighted means for Optimism/Fear/Uncertainty, weighted `sentiment_score` standard deviation for Disagreement, cross-sector min-max normalization of seven-day article volume for Attention, and `0.7 * weighted mean + 0.3 * P90` for Risk Intensity. The market radar averages the 11 sectors equally. Updated all dashboard references, regenerated processed data, and documented the formulas in README.
- Issues and resolution: The user identified that the previous `aggregation.py` averaged `disagreement_input`, which measured mean sentiment rather than disagreement, and used `time_weight * relevance_weight` as Attention, which gave Attention the wrong meaning. Aggregation weight was renamed `agg_weight` and fully separated from Attention. Article Risk Intensity followed the requested risk-tag severity direction, but the initial baseline also included negative-sentiment and uncertainty pressure because the lexicon fallback lacked FinBERT's stable risk confidence. Those weights were marked for later calibration.
- Current status: The 132 processed records now include `agg_weight`. Sector Disagreement ranges from 9.4 to 29.5 with no negatives. Attention spans 0 to 100 with visible sector differences. The market radar is sector-equal-weighted.
- Next step: Strengthen Top Driver explanations, positive/negative/risk displays, evaluation tooling, and an optional real-news import path.

## 2026-07-07 05:08

- Stage / objective: Improve Attention normalization and correct field documentation.
- Work completed: Replaced raw article counts with sector-level sums of `agg_weight` in the seven-day Attention window. Replaced min-max normalization with rank percentile `100 * (rank - 0.5) / sector_count`, using average ranks for ties. Added a TODO beside `ATTENTION_WINDOW_DAYS` noting that this is a cross-sectional approximation and should switch to each sector's own historical ECDF after at least 30 days of real-news history. Corrected README definitions for `attention_weight`, `disagreement_input`, and `agg_weight`.
- Issues and resolution: The previous raw-count min-max method created only 0/33.3/66.7/100 tiers in Demo data and placed several sectors at 100. Weighted volume and rank percentiles fixed this. Also corrected an earlier report: `attention_weight` is a retained field fixed at 0, while `disagreement_input` is a row-level copy of `sentiment_score`, not 0.
- Current status: Aggregation and documentation are updated; final compilation and numeric validation remain.
- Next step: Verify that all 11 Attention values avoid 0.0 and widespread ties at 100, then pause for confirmation.

## 2026-07-07 05:09

- Stage / objective: Validate the Attention improvement.
- Work completed: Ran Python 3.12 compilation and called `sector_metrics()` directly to inspect Attention, Disagreement, and weighted window volume for all 11 sectors.
- Issues and resolution: No code errors. `rg` was denied by the sandbox, so the check used direct file reads and Python aggregation instead.
- Current status: Compilation passed. Attention ranges from 4.545 to 95.455, all 11 sectors have distinct values, and neither 0 nor 100 occurs. Disagreement remains within 0-100 and has no negative values.
- Next step: Pause for user confirmation.

## 2026-07-07 05:25

- Stage / objective: Add real-news RSS collection.
- Work completed: Replaced the `src/news_collector.py` placeholder with an RSS collector using `feedparser` for Yahoo Finance ticker feeds, CNBC Top News, and MarketWatch Top Stories. Each feed has independent error handling, a User-Agent, and a timeout. Only titles, summaries, URLs, publication timestamps, and sources are read; article pages are not fetched. Added cumulative `data/raw_articles.csv` and processed `data/real_processed_articles.csv`. Updated `src/data_loader.py` for Demo and real-news modes; added a data-source selector and **Fetch Latest News** button in `app.py`; added `src/ui_helpers.py` for empty-state handling and clickable URLs; updated all four pages; and documented RSS storage and expected sparse trends.
- Issues and resolution: RSS usually covers only a few recent days, so 30-day trends require continuous collection. Reuters RSS was excluded because it had been discontinued. To avoid scraping and copyright issues, the first version did not request article pages and filled `content` from RSS summaries. If every RSS source fails, the UI displays a warning and keeps Demo data available.
- Current status: The real-news entry point is implemented. `raw_articles.csv` and `real_processed_articles.csv` contain headers and await the first collection run. Network access was restricted in the execution environment, so implementation was recorded before live validation.
- Next step: Compile the code and run `python -m src.news_collector` if dependencies and network access are available.

## 2026-07-07 05:28

- Stage / objective: Live-test RSS collection and correct mapping.
- Work completed: Successfully parsed 20 items from the Yahoo Finance NVDA feed, then ran the full collector. All 45 feeds succeeded, 890 entries were parsed, 702 were new, and both raw and processed files reached 702 records. Review found that case-insensitive single-letter tickers such as `T`, `C`, and `O` could match ordinary text. Company aliases remain case-insensitive, but ticker matching is now case-sensitive. Rebuilt processed real news from the existing raw file.
- Issues and resolution: A small number of market-level RSS articles could not be mapped to one of the 11 sectors. They remain `Unmapped` in Article Explorer, while sector radars continue to aggregate only the 11 target sectors.
- Current status: Compilation passed and real-news mode works. All 702 URLs are non-empty HTTP URLs. The 11 sectors are covered, with 15 additional Unmapped market articles. Technology has 166 items, Communication Services 64, Consumer Discretionary 66, Financials 62, and Attention has no zero values.
- Next step: Pause for confirmation; future work may define how macro news affects the market overview or add Evaluation.

## 2026-07-07 05:45

- Stage / objective: Fix widespread duplication between `title` and `evidence_sentence` on Sector Detail.
- Work completed: The user reported that the Key Evidence Sentences table displayed nearly identical title and evidence columns. Inspection of the page, pipeline, sentiment, risk-tagger, and real CSV confirmed that the page was correctly displaying the fields and the issue came from pipeline-generated evidence. Added `normalize_evidence_text()`, `article_parts()`, `article_body_text()`, `strip_title_from_evidence()`, `first_body_sentence()`, and `choose_evidence_sentence()` in `src/article_pipeline.py`. Evidence now prefers `summary/content`, strips a repeated title prefix, and falls back to the title only when no usable body or summary remains. Rebuilt Demo and real processed data.
- Issues and resolution: `rg` was denied, so PowerShell `Select-String` and targeted reads were used. Python execution also required authorization. Two real RSS records have identical title, summary, and content, so they reasonably retain the title as evidence.
- Current status: Compilation passed. In 705 real records, exact title/evidence equality dropped from 526 to 2; the Demo set has none. Run `streamlit run app.py`, select a source in the sidebar, and the two columns should now be visibly distinct.
- Next step: Consider fuller text extraction or source-summary cleanup to reduce short, duplicated, or truncated RSS evidence.

## 2026-07-08 22:24

- Stage / objective: Phase 4.5 production-readiness consistency fixes.
- Work completed: Completed the five approved P0 items, real-news-first default behavior, and two new checks. Centralized the disclaimer, RSS User-Agent, URLs, timeout, per-feed limit, title-similarity threshold, and Risk Intensity sentiment-pressure switch in `src/config.py`. `preprocessing.py` now records `time_parse_error` instead of silently replacing bad timestamps with the current time, and CSV writes now use a temporary file, backup, and atomic replacement. `article_pipeline.py` handles each article independently; failed rows are written to `data/error_records.csv` and emitted with low weight rather than stopping the batch. Dictionary loaders have minimum fallbacks. Article Risk Intensity returned to a risk-severity-only default; negative sentiment and uncertainty pressure remain behind `RISK_USE_SENTIMENT_PRESSURE`, disabled by default to avoid coupling with Fear and Uncertainty.
- RSS and data-source fixes: Collector settings are no longer hard-coded. Duplicate URL/title records merge tickers, companies, and source context rather than discarding later feeds. If merged tickers span sectors, the single-sector fallback is cleared so the first feed does not dominate. The pipeline remaps entities from text and merged raw context. Real news is selected by default when available; otherwise the app falls back to Demo with a warning. Sidebar wording now presents the app as an operational tool.
- Documentation: Rewrote README positioning, disclaimer, data sources, write safety, error records, RSS coverage limitations, data dictionary, and metric formulas. Demo is explicitly an offline fallback and testing scaffold. Corrected Risk Intensity documentation and noted equal sector weighting in the market radar.
- Issues and resolution: Chinese terminal output was garbled, so critical files were read with `Get-Content -Encoding UTF8` and narrow ASCII anchors were used for patches. Streamlit cannot mutate a widget's same-named session state after widget creation, so a successful fetch does not force the radio state; real-news preference is resolved during initial page load. Existing raw data was reprocessed without another network collection.
- Current status: Regenerated Demo and processed files and added `data/error_records.csv` plus backups. Demo has 132 rows and real processed data has 705, with no missing columns or error records. Timestamp and processing error fields are empty. `has_real_articles()` is true. A neutral macro-risk article scores 80.0 under the restored severity-only formula. Real Attention ranges from 4.545 to 95.455 with 11 distinct values and no endpoints; Disagreement ranges from 8.444 to 25.089. A duplicate-merge test combined AAPL/MSFT/JPM context and cleared `sector` when sectors conflicted.
- Next step: Pause Phase 4.5. P1 should begin with an optional FinBERT wrapper, a minimal evaluation interface, and a macro overlay limited to Unmapped news in Market Brief and Top Drivers.

## 2026-07-08 22:39

- Stage / objective: Phase 4.5.1 patch and first P1 production enhancement.
- Work completed: Fixed RSS publication-time fallback so `parsed_time_to_utc()` uses the record's `collected_at` when missing or unparseable and records `published_at: missing/unparseable in RSS; fallback=collected_at`. Added `BACKUP_RETENTION_COUNT = 10`; each source now keeps only its 10 latest backups.
- P1 FinBERT wrapper: Added an optional single-sentence FinBERT wrapper in `src/sentiment_model.py`, defaulting to `ProsusAI/finbert`, CPU, and local cache only. Missing dependencies or model files automatically fall back to the lexicon engine with a message. `score_sentence()` remains the single replacement point, preserving article aggregation and evidence semantics. `requirements-full.txt` switched to CPU PyTorch dependencies.
- P1 pages and evaluation: Added a publication-date filter to Article Explorer. Added `pages/5_Evaluation.py` with coverage statistics, output distributions, a downloadable annotation template, and accuracy calculation. Ablation and sensitivity analysis were intentionally excluded from this minimal version.
- P1 Top Drivers and macro overlay: Added `src/driver_analysis.py` for display-only `driver_score` and `driver_reason`. Market Overview now uses the new drivers and guarantees at least one Unmapped macro or market article. The Market Brief reports the Unmapped count and a representative headline.
- Issues and resolution: Local Python lacked `torch`, so the wrapper correctly logged that FinBERT dependencies were unavailable and continued with the lexicon engine. Initial driver review found that macro articles could be pushed out by ranking; selection now reserves the highest-scoring Unmapped article before filling remaining driver slots. No new RSS network request was made.
- Current status: Regenerated 132 Demo and 705 real processed records with zero errors. Compilation passed. Missing RSS timestamps correctly use `collected_at` and carry an error marker. Backup counts remain below 10. Evaluation output includes complete coverage fields, 10 distribution rows, and three annotation metrics. Among 15 Unmapped real articles, one appears in the five Top Drivers.
- Next step: Continue refining model cache/download documentation, annotation guidance, and driver explanations as needed.

## 2026-07-09 00:41

- Stage / objective: Enable FinBERT and correct batch inference.
- Work completed: Added `SENTIMENT_DEVICE = "auto"` and `FINBERT_BATCH_SIZE = 32`. `auto` uses CUDA when available and the sidebar reports the active engine and device. Replaced article-by-article sentence inference with cross-article sentence collection, batched inference, and result reconstruction. `score_sentence()` remains as a compatibility entry point, and article aggregation and evidence semantics remain unchanged.
- Label mapping: FinBERT probability mapping is derived entirely from `model.config.id2label`, with a startup validation. The observed mapping is `{'positive': 0, 'negative': 1, 'neutral': 2}`, preventing silent swaps of negative and neutral probabilities.
- Dependencies and documentation: Pinned `transformers==5.13.0` and `torch==2.12.1+cpu` in `requirements-full.txt`, with a warning not to run it over an existing GPU torch installation. README documents device selection, batch size, and dynamic label mapping.
- Data rebuild and validation: Rebuilt Demo and real data with local Python 3.12, `torch 2.12.1+cu130`, `transformers 5.13.0`, CUDA, and a cached FinBERT model. Real data remains 705 rows, Demo 132, and errors 0. Compilation passed.
- Distribution change: For real news, lexicon `sentiment_score` had mean 0.0234, median 0.0000, P10 -0.1000, and P90 0.2280. FinBERT produced mean 0.1469, median 0.1360, P10 -0.5526, and P90 0.8410, showing stronger separation. Demo mean moved from -0.1126 to 0.0905 and median from -0.1435 to 0.1775.
- Evidence review: Five real examples showed more differentiated FinBERT probabilities while retaining summary-based evidence. A Duke Energy investment article moved from neutral to strongly positive (`0.844`); a SpaceX Nasdaq-100 options article moved from neutral to strongly negative (`-0.955`). A Jim Cramer/Blackstone example gained a fuller summary sentence but still contained an RSS truncation marker, confirming that evidence quality remains constrained by source summaries.

## 2026-07-09 00:49

- Stage / objective: Add an adaptive environment setup script.
- Work completed: Added root-level `setup_env.py`. It detects NVIDIA hardware with `nvidia-smi`, installs the cu130 build of `torch==2.12.1` when successful, and otherwise installs `torch==2.12.1+cpu`. An existing GPU-enabled torch installation is preserved. The script then installs `requirements.txt` and `transformers==5.13.0` and reports torch version, CUDA availability, device, and a conclusion.
- Documentation: Updated comments in `requirements-full.txt` and made `python setup_env.py` the recommended local installation path. Cloud deployment documentation points to the cloud dependency list.
- Issues and resolution: The user requested roughly 50 lines; the implementation was reduced to 62 lines. To protect the verified GPU environment, only `python -m py_compile setup_env.py` was run rather than executing installation.
- Current status: Syntax validation passed and the existing FinBERT/GPU environment was not overwritten.

## 2026-07-10 01:12

- Stage / objective: Fix mojibake when CSV files are opened directly in Chinese Windows Excel.
- Work completed: The user reported that BOM-less UTF-8 files were interpreted as GBK, turning curly quotes into garbled byte-decoding text. Standardized all project CSV exports to `utf-8-sig`, including `write_article_csv`, `error_records.csv`, Evaluation annotation downloads, and Demo generation. Added `CSV_EXPORT_ENCODING = "utf-8-sig"` to `src/config.py`, routed the shared temporary-file writer through it, and reused it in Evaluation downloads. Verified that all main data outputs use the shared writer. Historical backup CSVs received only a BOM prefix without parsing or rewriting fields.
- Issues and resolution: `rg` remained unavailable, so PowerShell `Select-String` located write paths. Python required authorization. The first real-data rebuild hit a Windows `PermissionError` because the file was open elsewhere; it succeeded after the lock was released. Curly quotes were verified by Unicode code point after PowerShell parsing problems.
- Current status: The encoding is unified in config, preprocessing, and Evaluation. Main CSVs were rewritten and begin with `EF BB BF`. All 34 CSV files under `data` include a UTF-8 BOM. A real headline containing `Doesn't` retains the correct `U+2019` curly apostrophe rather than mojibake. Syntax checks passed and CSVs can be opened directly in Excel.
- Next step: Reuse `CSV_EXPORT_ENCODING` or `write_article_csv()` for every future CSV export.

## 2026-07-10 02:05

- Stage / objective: Add an LLM daily market brief, daily snapshots, and incremental processing for multiple collections per day.
- Work completed: Added daily writes to `data/sector_daily_scores.csv` and `data/market_daily_scores.csv`, upserting the current UTC date while preserving history. Added `src/daily_snapshots.py`, `src/brief_builder.py`, and `src/brief_generator.py` to build a 24-hour payload containing market metrics, prior-day deltas, sector rankings, movers, Top 5 Drivers, Top 5 risk categories, Unmapped macro headlines, and coverage statistics. `src/llm_summary.py` initially used the Anthropic SDK with `claude-opus-4-8`, reading `ANTHROPIC_API_KEY` and falling back to a rule template. `src/news_collector.py` now uses `process_articles_incremental()`, processing only new IDs and reusing historical results before invoking the daily brief gate.
- Pages and scheduling: Market Overview only reads `data/latest_brief.md` and shows separate data-update and brief-generation timestamps. The sidebar gained a confirmed **Regenerate Brief Now** operation warning about API cost. Sector Detail prefers daily snapshots for 7/30-day trends. Article Explorer gained **Load Full History** while other pages default to `WORKING_SET_DAYS = 30`. Added `scripts/setup_schedule.ps1` to register collection every four hours.
- Storage tiers: Raw articles are kept permanently. Files above `RAW_SQLITE_WARNING_MB = 50` log a migration recommendation without automatically migrating. Daily snapshots accumulate independently of the working-set window. Briefs are written to `data/latest_brief.md` and dated files under `data/briefs/`.
- Issues and resolution: Older Chinese files still rendered incorrectly in PowerShell, so most were patched with narrow anchors; smaller page files were rewritten in UTF-8. The Anthropic SDK was optional and failure-safe so missing keys or network access could not block collection.
- Current status: Snapshots, incremental processing, brief gating, LLM/rule fallback, read-only brief rendering, and scheduling are implemented. Compilation, snapshot refresh, and no-key rule-template writing remained to be validated.

## 2026-07-10 02:58

- Stage / objective: Validate the daily brief and incremental pipeline.
- Work completed: Ran Python 3.12 `compileall` across `src`, `pages`, `app.py`, and `setup_env.py`. Wrote Demo snapshots from existing processed data. Incrementally processed raw and real processed data with 0 new and 1,201 reused records. Cleared `ANTHROPIC_API_KEY` and forced brief generation, confirming rule fallback writes both `data/latest_brief.md` and `data/briefs/2026-07-10.md`. Sector snapshots contain 22 rows, 11 per source mode, and market snapshots contain two rows. Confirmed that the gate skips generation before local 08:00 and that the scheduling script parses successfully.
- Current status: Validation passed. Because testing occurred before 08:00, the latest brief is a manually forced rule-based brief. It can be regenerated after an API key is configured.

## 2026-07-10 03:17

- Stage / objective: Final UI and cold-start fixes for the brief phase.
- Work completed: Reorganized Market Overview with four top `st.metric` cards for window article count, publisher coverage, data window, and update time. The left column contains the market radar and score table; the right uses `st.container(height=600, border=True)` so long briefs scroll without stretching the page. Sector Heatmap and Top Drivers remain full width below. Sector Detail now draws trend lines only after at least two snapshot days and uses a categorical date axis. With less history, it reports the accumulated day count and shows the current values in a table.
- Brief template fix: `generate_rule_brief_from_payload()` no longer emits a missing prior-day phrase. When no prior snapshot exists, the delta clause is omitted and the coverage note explains that mover comparison becomes available the next day.
- Validation: `compileall` passed. Streamlit 1.58.0 supports the fixed-height bordered container. Forced no-key rule generation succeeded, the old missing-prior-day phrase is absent, and the coverage note is present. Current real data has one sector snapshot day and therefore follows the cold-start table path.
- Time-zone audit: `brief_generator._local_now()` uses `datetime.now().astimezone()`. The machine reported Australian Eastern Standard Time at UTC+10. `BRIEF_GENERATION_HOUR_LOCAL = 8` is applied to the same timezone-aware datetime, so the gate triggers at system-local 08:00 without UTC mixing. At `2026-07-10T03:16:55+10:00`, it correctly remained closed.

## 2026-07-10 03:35

- Stage / objective: Switch the daily brief LLM provider to the OpenAI API.
- Work completed: Replaced the Anthropic SDK in `src/llm_summary.py` with the official OpenAI Python SDK, reading `OPENAI_API_KEY` and using the Responses API with the existing grounded system instructions and JSON payload. Added task-specific `LLM_MODEL_BRIEF`, `LLM_MODEL_SECTOR_SUMMARY`, and `LLM_MODEL_CHAT` settings; the expected brief model was initially `gpt-5.6-terra`, with `LLM_MODEL` retained as a compatibility alias. Before generation, the first implementation called `client.models.list()` and generated only when the exact ID appeared in the account response. Otherwise it logged the reason and used the rule template. Existing gating, grounding, disclaimer completion, archiving, and read-only page rendering were preserved.
- Dependencies and documentation: Replaced the Anthropic dependency with `openai>=1.66.0,<2.0.0`, updated README environment variables and model-validation notes, and changed the sidebar confirmation to reference `OPENAI_API_KEY`.
- Validation: The current environment had neither the OpenAI SDK nor `OPENAI_API_KEY`, so `/v1/models` could not be tested against a real account. `compileall` passed. An offline fake client verified no-key fallback, strict `models.list()` before `responses.create()` when available, and no generation call when the requested model was absent.

## 2026-07-10 07:07

- Stage / objective: Correct the OpenAI brief model ID.
- Work completed: Based on the account's real `models.list()` result, changed `LLM_MODEL_BRIEF` and compatibility setting `LLM_MODEL` to the available `gpt-5.5`. Existing model-list validation, Responses API use, gating, and rule fallback remained unchanged. The unavailable-model message now derives the model family from configuration. The setting can return to `gpt-5.6-terra` when access becomes available.

## 2026-07-11 02:21

- Stage / objective: Complete CPU FinBERT deployment support for Streamlit Community Cloud.
- Dependencies and local protection: Turned root `requirements.txt` into the complete cloud list with the PyTorch CPU index, `torch==2.12.1+cpu`, and `transformers==5.13.0`, while retaining app dependencies. The then-obsolete `requirements-full.txt` was removed. Because the cloud list could overwrite local GPU torch, `setup_env.py` now filters out the CPU torch, transformers, and cloud index, installs the remaining dependencies, and installs ML packages separately for the detected local hardware.
- Configuration and startup: Made `FINBERT_LOCAL_FILES_ONLY` and `FINBERT_BATCH_SIZE` environment settings, initially defaulting locally to `1` and `32`, with cloud values `0` and `8`. Kept `SENTIMENT_DEVICE=auto` and added `DEMO_PIN`. Before importing `src.config`, `app.py` bridges Streamlit Secrets into environment variables and silently skips missing local Secrets. `st.set_page_config()` remains the first Streamlit call.
- Page protection and model experience: When cloud downloads are allowed and FinBERT has not loaded, the first load is wrapped in a spinner explaining the approximately 440 MB download. Existing exception handling still falls back to the lexicon engine. When `DEMO_PIN` is set, forced brief regeneration requires the correct PIN; an incorrect PIN never reaches `generate_daily_brief()`.
- Documentation and cloud limits: README now identifies root `requirements.txt` as the Community Cloud dependency file and lists `OPENAI_API_KEY`, `FINBERT_LOCAL_FILES_ONLY="0"`, `FINBERT_BATCH_SIZE="8"`, and `DEMO_PIN` Secrets. It documents initial download time, slower CPU inference, fallback behavior, and ephemeral container storage.
- Validation: `compileall`, dependency structure, setup filtering, cloud/local defaults, and AST ordering checks passed. The incorrect-PIN branch cannot call brief generation. Runtime scans across `src/`, `pages/`, and `app.py` found no Windows drive paths, `python.exe`, PowerShell, `cmd.exe`, `nvidia-smi`, or `.ps1` dependencies. Cloud CPU requirements were not installed locally to protect the verified GPU environment.

## 2026-07-11 03:11

- Stage / objective: Implement two-stage FinBERT loading and fix cloud cache misses.
- Model loading: `load_finbert_resources()` now always attempts `local_files_only=True` first and retries with `local_files_only=False` only after a confirmed cache miss. In Streamlit, the online stage is wrapped in the first-start download spinner; command-line use prints the same message. Other download or loading errors still fall through to the outer lexicon fallback. `FINBERT_LOCAL_FILES_ONLY` now defaults to `auto`; only explicit true values enable strict offline mode and suppress the second attempt.
- Revision and authentication: Pinned `FINBERT_REVISION` to `4556d13015211d73dccd3fdd39d39232506f3e43` from the official `ProsusAI/finbert` history. Cache reads and downloads for both tokenizer and model use the same revision. Added lazy `HF_TOKEN` reading; the argument is omitted entirely when no token is configured.
- Secrets and lazy settings: `app.py` completes the `st.secrets -> os.environ.setdefault` bridge before `st.set_page_config()` and any `src.*` import. FinBERT mode, batch size, `DEMO_PIN`, and `HF_TOKEN` are now read at call time. The OpenAI key was already lazy. This prevents early module imports from freezing values before Secrets are bridged.
- Documentation: README now explains two-stage loading, strict offline mode, optional `HF_TOKEN`, and the pinned revision. The no-longer-needed `FINBERT_LOCAL_FILES_ONLY="0"` cloud secret was removed.
- Validation: `compileall` passed. Fake loaders verified cache hit without download, local-then-online order on a miss, spinner placement, strict-offline behavior, optional token handling, consistent revision, and lexicon fallback after simulated download failure. AST checks confirmed Secrets ordering and no module-level `os.getenv` evaluation. No live model download was performed; Streamlit Cloud reboot remained the real-world test.

## 2026-07-11 05:04

- Stage / objective: Upgrade the daily market brief from numeric reporting to analytical interpretation.
- Payload enhancements: Rounded market scores, prior-day deltas, sector rankings, and mover metrics to one decimal. Added Top-5 topic distribution, positive/negative article counts for all 11 sectors, and Top-3 most positive and negative articles with title, sector, and evidence. Added a seven-day market-position label only when seven distinct snapshot days exist; it is intentionally omitted with the current two-day history. Risk counts are explicitly converted to integers for clean JSON.
- Prompt upgrade: Reframed the system instruction as a senior market-sentiment analyst writing a next-day morning brief. It remains strictly grounded, makes no price forecasts, and gives no advice, while allowing qualitative metric interpretation, event-sector connections, and cross-article theme synthesis. The structure became Core View, Market Overview, Sector and Event Deep Dive, Risks and Tomorrow's Watch List, and Data Scope and Disclaimer, targeting 600-900 Chinese characters at that stage. Internal field names and uncontextualized number lists were prohibited. The output budget increased to 3,200 tokens.
- Numeric-density guard: Required at least two market-overview paragraphs with no more than four Arabic numbers each. AI output alone receives deterministic paragraph splitting at Chinese sentence punctuation before a paragraph exceeds the limit; no words are changed. Rule fallback behavior remains unchanged.
- Real generation and validation: Generated a brief from a 24-hour window covering 420 articles and three sources. The first draft revealed numeric-density issues. A tighter second request returned empty text and correctly fell back to the rule template. After increasing the output budget, a final request succeeded and wrote both latest and dated briefs. The result had 692 Chinese characters, no paragraph exceeded four numbers, and no forbidden internal fields appeared. Payload, cold-start, fallback compatibility, and compilation checks passed.

## 2026-07-11 05:35

- Stage / objective: Expand analytical depth, add a model candidate chain, and record the actual model.
- Length and focus: Increased the target from 600-900 to 900-1,200 Chinese characters and required Sector and Event Deep Dive to occupy about half the brief. Only three to five sectors with notable attention, risk, or sentiment are expanded, each in two to four sentences linking metric levels with specific news. The token budget increased from 3,200 to 4,600.
- Candidate chain: Added ordered `LLM_MODEL_BRIEF_CANDIDATES = ["gpt-5.6-terra", "gpt-5.5"]`. The initial `_resolve_brief_model()` implementation read the account model list and selected the first available candidate, logging why earlier candidates were unavailable. Fake clients covered Terra preference, fallback to 5.5, and total unavailability.
- Model attribution: AI results now include `model_id`. `brief_generator.py` writes it to front matter and returns it; rule briefs leave it empty. Market Overview shows AI source, model ID, and brief time, while rule briefs show source and time only. README was updated.
- Real validation: The account list contained `gpt-5.6-terra`, so Terra was used. The latest and dated briefs record that ID. The final brief covered 404 articles from three sources, contained 1,126 Chinese characters, devoted 46.8% to sector analysis, stayed below four numbers per paragraph, and contained no forbidden internal fields. Rule-template simulation omitted model metadata. `compileall` and `git diff --check` passed.

## 2026-07-11 05:55

- Stage / objective: Harden the model candidate chain against list inconsistency and rate limits.
- Selection correction: Replaced the previous `_resolve_brief_model()` availability gate. `models.list()` is now informational only. Even if listing fails or omits Terra, generation directly tries `gpt-5.6-terra` and then `gpt-5.5`, using actual Responses API outcomes as the availability test.
- Fallback and retry: A first 429 from the preferred model waits `LLM_CANDIDATE_RATE_LIMIT_RETRY_SECONDS = 5` and retries once. A second failure moves to the next candidate. Missing-model, permission, rate-limit, capacity, and temporary-service errors move to the next candidate; other errors immediately enter rule fallback to avoid repeating global parameter failures. External API exceptions never escape the pipeline.
- Traceability: Each generation records model-list information, candidate, attempt count, classified result, final model, and selection reason. A single-line `model_selection_log` is written to latest and dated front matter. No-key, disabled-LLM, and missing-SDK paths also record that no request was made and why rule fallback was used.
- Offline validation: Fake clients covered a Terra success despite list omission; two Terra 429 responses followed by 5.5; missing, unauthorized, and 503 failures; model-list failure; and total candidate failure. The 429 order is `Terra -> wait 5 seconds -> Terra -> 5.5`, with one wait and single-line metadata. No real API request was made.

## 2026-07-11 07:30

- Stage / objective: Collapse articles by event with event-level clustering.
- Clustering core: Added `src/event_clustering.py`. Candidate pairs require publication within 48 hours and overlapping tickers; Unmapped articles without tickers are compared under stricter thresholds. A pluggable `SimilarityIndex` defaults to normalized embeddings from `sentence-transformers/all-MiniLM-L6-v2`, cosine threshold `0.72`, and Unmapped threshold `0.82`. Missing model or dependency falls back to content-word Jaccard at `0.40` and `0.55`. Candidate embeddings are computed in memory only.
- Data and incrementality: Added `event_id` and `source_count` to the processed schema. Union-find clusters use the highest-`agg_weight` article ID as the event ID and count distinct RSS sources; singleton events use their own ID. Full processing clusters after scoring. Incremental processing reuses existing event members and compares new articles with nearby existing items and one another. Legacy data without event IDs receives a one-time full migration. A no-new-data test on real history produced zero pairs and vectors in about 0.007 seconds.
- Dependency tiers: Restored `requirements-full.txt` with `sentence-transformers==5.6.0`, installed locally through `setup_env.py` while preserving GPU torch. Cloud requirements omit it and use FinBERT plus lexical clustering. Local execution reused `torch 2.12.1+cu130` and RTX 4080 SUPER; embeddings ran on CUDA and simulated failures fell back to lexical.
- Display layer: Top Drivers now shows one row per event, represented by the highest-`agg_weight` article, with cluster `driver_score` equal to the article-level maximum. Events with `source_count >= 3` receive `EVENT_COVERAGE_BOOST = 1.15` only for display ranking. Multi-article events show the number of other sources and expand to clickable coverage. Article Explorer gained `event_id` and a grouping toggle with article and source counts. Daily brief drivers use the same collapse.
- Metric boundary: `dedup_factor`, `agg_weight`, and aggregation formulas were unchanged. Before/after comparison of 2,037 real articles showed exact equality for weights, all 11 sector metric tables, and market metrics. Independent reporting still contributes to Attention and sentiment.
- Real results: Embedding produced 1,716 event clusters. There were 172 multi-article clusters (10.02% of clusters) containing 493 articles (24.20% coverage), with a maximum size of 25. Twenty Apple/Broadcom partnership headlines formed the main event `rss-9d53d9cf9bbfd98a`, ultimately 25 articles across Yahoo Finance RSS and CNBC.
- Engine comparison: Lexical dry-run on the same 2,037 rows produced 1,996 clusters, only 29 multi-article clusters, and 70 clustered articles (3.44%), showing a much more conservative method. Clear embedding-only merges included the Apple/Broadcom chip partnership, Microsoft's 4,800 layoffs and Xbox restructuring, and Tesla Robotaxi expansion to Miami.
- Manual review: Five multi-article clusters sampled with seed 5720 showed coherent SK Hynix listing/Micron comparison, Citigroup Q2 preview, and 7-Eleven/Nike lawsuit clusters. McDonald's price movement/long-term opportunity/Russell adjustment and Wix recommendations/valuation return appeared to merge different events. The approved `0.72` threshold was retained and marked as a TODO rather than tuned to improve the sample.
- Validation: Event, incremental, and coverage-boost contracts passed, as did `compileall`. Streamlit AppTest found no errors in Market Overview or grouped Article Explorer. The stage awaited approval before commit.

## 2026-07-11 08:39

- Stage / objective: Implement the enhanced six-dimensional formulas from parts of PDF Sections 6 and 9.2.
- Single implementation and weight groups: `src/scoring.py` and `src/aggregation.py` now keep one formula implementation supplied with `BASELINE_WEIGHTS` or `ENHANCED_WEIGHTS`; `ACTIVE_WEIGHTS` points to Enhanced. Baseline Optimism/Fear weights are `1/0/0`, Uncertainty `0.6/0.4/0`, and Disagreement `1/0`. Enhanced uses `0.7/0.2/0.1`, `0.4/0.3/0.3`, and `0.5/0.5`. Both versions retain `0.7*mean + 0.3*P90` for Risk Intensity in this batch.
- Dictionaries and components: Added 33 growth terms, 33 shock terms, 20 bullish stance terms, 20 bearish stance terms, and the shared normalization `min(matched sentences/total sentences*3, 1)`. Extracted 297 currently active uncertainty terms from the March 2026 Loughran-McDonald Master Dictionary and merged them with five existing terms for 302 unique entries. README includes the official source and paper citation.
- Article-level preservation: Added `b_bull`, `b_bear`, `g_growth`, `s_shock`, `k_unc`, and `entropy_norm` to the processed schema. Active article scores use the Enhanced formulas while probabilities and all components are persisted, allowing arithmetic recomputation under any weight group without rerunning models or dictionaries. Incremental processing fills missing components in legacy records from persisted FinBERT probabilities.
- Sector enhancements: Disagreement became `100*(0.5*weighted standard deviation + 0.5*PolarityMix)`, with `PolarityMix=2*min(PosShare,NegShare)`, threshold `0.15`, and 0 for fewer than two articles. Attention retains seven-day cross-sectional cold start and switches to each sector's historical `0.7*volume ECDF + 0.3*growth ECDF` after 30 days. Current one-day real history keeps both formulas on cold start.
- Snapshot dual write: Added `formula_version` to sector and market snapshots. Each day upserts both versions and labels legacy history as Baseline. Sector snapshots persist `attention_volume`, using `article_count` during migration where necessary. Trends and brief loaders read only `ACTIVE_FORMULA_VERSION`.
- Evaluation page: Added Baseline vs Enhanced mean/standard-deviation/range tables, the three largest sector rank changes per metric with component explanations, and concrete article examples under both formulas. Output distributions include the six components. Formal ablation, significance testing, and sensitivity analysis remained future work at that stage.
- Real rebuild: Reprocessed 132 Demo and 2,088 real articles using local GPU FinBERT and CUDA embeddings with zero errors. Nonzero real-component coverage was `b_bull=78`, `b_bear=29`, `g_growth=361`, `s_shock=60`, and `k_unc=656`.
- Baseline to Enhanced: Sector means changed as follows: Optimism `36.49->27.86`, Fear `19.90->14.46`, Uncertainty `48.95->42.57`, Attention `50.00->50.00`, Disagreement `49.64->46.67`, and Risk Intensity `75.98->75.98`. Ranges were Optimism `31.91-40.64->25.03-30.35`, Fear `11.37-27.96->9.17-20.28`, Uncertainty `41.11-54.34->36.67-48.82`, unchanged Attention `4.55-95.45`, Disagreement `39.13-61.51->32.74-60.38`, and unchanged Risk `72.98-77.34`. Lower first-three means mainly reflect reduced FinBERT primary-probability weight; enhanced components alter relative ranking and event sensitivity rather than guaranteeing higher absolute scores.
- Rank changes: Optimism moved Real Estate `9->7`, Healthcare `4->3`, and Industrials `3->4`; Fear moved Financials `6->5`, Consumer Staples `5->6`, while Energy stayed first; Uncertainty moved Communication Services `7->3`, Materials `4->8`, and Healthcare `5->9`; Disagreement moved Consumer Staples `9->6`, Consumer Discretionary `5->3`, and Industrials `3->5`. Attention and Risk rankings remained unchanged for the documented reasons.
- Directional samples: A Shopify upgrade/growth article matched `growth/expansion/buy rating` and moved Optimism `55.10->68.57`; a 3M growth/upside/buy-rating article moved `35.50->49.85`. A bearish Cramer article matched `crash/bearish` and moved Fear `43.70->60.59`; an AI-chip sell-off article moved `2.10->11.47`. All four directions matched the design.
- Validation: Added five standard-library regression tests covering formulas, normalization, LM merge, Disagreement, unchanged Risk, legacy Attention history, and snapshot dual writes. Tests, compilation, diff checks, and dictionary parsing passed. Real-data contracts kept components in 0-1 and both metric tables in 0-100. The current real snapshot has 22 sector rows and two market rows. Arithmetic recomputation of 200 sampled rows differed by at most 0.08 due only to persisted rounding. AppTest found no errors on Market Overview, Sector Comparison, Sector Detail, or Evaluation and confirmed active Enhanced snapshots.
- Current status: Implementation and validation were complete and awaiting approval before staging.

## 2026-07-11 18:05

- Stage / objective: Perform a second completeness audit and commit the enhanced metric stage.
- Audit reason: A previous commit attempt had been blocked by Codex approval-budget limits, so the user requested confirmation that no work had been interrupted before starting the second sprint.
- Review: Audited the staged snapshot and confirmed the growth/shock/stance dictionaries, 302 uncertainty terms, both weight groups, six persisted components, enhanced formulas, PolarityMix Disagreement, 30-day Attention ECDF switch, dual snapshots, active-version filtering, Evaluation comparison, and README formulas were present.
- Rerun: All five enhanced-metric tests passed. Real processed data contained 2,088 rows and zero errors, all components were within 0-1, arithmetic recomputation differed by at most 0.08, both formula versions stayed within 0-100, and latest snapshots contained both versions with no missing `attention_volume`.
- Commit: After confirming completeness, committed as `5e63439` with the stage description. No missing or half-complete implementation was found.

## 2026-07-11 18:20

- Stage / objective: Model evaluation toolchain, first batch of Sprint 2.
- Stratified blind sample: Added `scripts/sample_for_annotation.py`, aligning raw and processed news one-to-one by `article_id` and performing deterministic round-robin balancing across predicted sector x FinBERT class. Small strata are exhausted before remaining capacity is reallocated. Defaults are 300 samples and seed 5720, with configuration and CLI overrides.
- Production sample: Generated 300-row `annotation_blind.csv` and `annotation_key.csv` from 2,088 candidates with no unmatched raw rows. All 36 cross-strata are represented by 3-9 rows. The blind file has exactly 11 approved fields, blank labels, unique IDs, and no predictions; key and blind ID sets match exactly.
- Annotation guide: Added `docs/annotation_guide.md` for sentiment boundaries, mixed/neutral cases, 10 risk categories, evidence standards, and a two-pass process. The primary annotator labels sentiment and risk without predictions; after labels are locked, the evaluation owner uses the private key only for sector and evidence reconciliation.
- Metric engine: Expanded `src/evaluation.py` with sentiment Accuracy, per-class P/R/F1, Macro F1, 3x3 confusion matrices, all-neutral/lexicon/FinBERT comparison, sector Accuracy, risk multi-label metrics and 10-class Macro F1, evidence Precision, 10-bin reliability data, and multiclass Brier score. Invalid labels, duplicate or blank IDs, and unmatched key IDs raise explicit errors.
- Lexicon comparison: Added a forced lexicon entry point that reuses the existing fallback sentence scoring and the same aggregation and evidence logic as FinBERT rather than implementing an approximation.
- Error analysis: Writes every FinBERT sentiment error to `data/annotation/sentiment_errors.csv` with ID, title, true label, prediction, and confidence. Identical content does not generate duplicate writes or backups. Evaluation supports filtering and downloading errors.
- Page: Evaluation now clearly separates classification evaluation from future six-dimensional robustness work. It includes the three-way comparison, selectable confusion matrices, class metrics, Brier, reliability, sector/risk/evidence metrics, and error browsing. Formula comparisons remain in a collapsed descriptive section. The private key is read in the backend but never rendered or downloadable.
- Synthetic 30-row validation: Built 10 rows per class with two deliberate FinBERT mistakes in each. Program and hand calculations matched: 0.8 Accuracy and Macro F1, all-neutral Accuracy `1/3` and Macro F1 `1/6`, lexicon 1.0, and Brier `(24*0.06+6*1.46)/30=0.34`. Sector Accuracy was 0.9, evidence Precision 0.8, risk Macro F1 0.24, and six error rows were written.
- Issues and fix: Pandas parsed `0/1` as integers and the initial Boolean normalizer treated integer 0 as empty. It was corrected to test NaN first and then normalize string values. All eight standard-library tests passed.
- Page and static validation: Empty and fully labeled AppTest states passed. Evaluation displayed FinBERT Accuracy 0.800, Macro F1 0.800, and Brier 0.340. Compilation and diff checks passed, with no new Windows paths or credentials.
- Current status: Implementation, production sampling, and validation were complete and awaiting approval.

## 2026-07-11 20:55

- Stage / objective: P0 signal-quality fixes for broken Risk Intensity and over-merged event clusters. UI styling was intentionally unchanged.
- Risk Intensity: Removed unknown-risk default severity and macro fallback. Articles with no matched risk now have an empty category and score 0. Risk tags are semicolon-delimited multi-labels. Each category uses shared sentence density `r_k=min(matched sentences/total sentences*3,1)`, and the article formula is `100*clip(sum((v_k/5)*r_k),0,1)`. Sentiment and uncertainty pressure remain disabled. Severity cap and density coefficient are centralized and marked for calibration.
- Dictionary fixes: Removed broad terms such as `macro` from macro risk. Strong signals include recession, stagflation, hard landing, and inflation shock. Weak signals such as inflation, economic slowdown, and consumer weakness require at least two distinct matches. Added more specific topic categories for AI infrastructure spending, chip supply deals, streaming, EV demand, bank earnings, drug approvals, dividends, buybacks, analyst ratings, space economy, and restructuring.
- Shared implementation: Added `src/keyword_matching.py` for boundary-aware matching, unique-term handling, and sentence normalization, shared by risk tags and enhanced components. Added `tests/test_signal_quality.py` for zero-risk, macro weak-term thresholds, multi-label math, 72-hour chain blocking, polarity guarding, and semicolon source counts.
- Clustering guards: Added `EVENT_MAX_SPAN_HOURS=72` and `EVENT_POLARITY_GUARD_THRESHOLD=0.30`. Union-find rejects merges whose combined cluster span exceeds 72 hours. Strongly positive and negative articles cannot connect. `source_count` splits semicolon and pipe delimiters and Top Drivers no longer overwrite current counts with stale persisted values.
- Snapshot continuity: Added `PIPELINE_REVISION="r2"` to sector and market snapshots; legacy rows become r1. Reprocessing added 22 r2 sector rows and two r2 market rows. README explains revision breaks.
- Full rebuild: Reprocessed 2,154 real articles with CUDA FinBERT and sentence-transformers, with zero errors. Risk Intensity mean was 9.7203, standard deviation 22.6524, median 0, P90 40, and range 0-100. There were 1,760 no-risk articles and 20 distinct persisted scores rather than only four tiers.
- Distribution change: Macro risk dropped from 1,718 to 5 articles. Other categories included valuation 167, commodity 67, interest rate 64, and earnings 51. `general market sentiment` dropped from 1,504 to 1,028 and from 285 to 181 in Technology, while specific topics increased.
- Clustering result: Clusters increased from 1,794 to 1,818, with 178 multi-article clusters. Maximum size fell from 26 to 16 and clusters over 72 hours fell from 10 to 0. The Apple/Broadcom core remained a coherent 16-article cluster spanning 51.324 hours; later coverage split into nine- and one-article clusters. A mixed Meta cluster split into 13 non-strong-negative articles and one strong-negative singleton. Its three sources were genuinely Yahoo Finance, CNBC, and MarketWatch.
- Manual review: Exxon/Chevron comparison, Chevron licensing, and Chevron/Alinta supply-agreement clusters were coherent. Chevron recommendation/data-center narratives and Microsoft cost-cutting/Copilot/investment/valuation narratives still appeared over-merged. Complete-link or representative-consistency evaluation was deferred; the embedding threshold was not silently tuned.
- Validation: Added `scripts/validate_p0_signal_quality.py` to compare committed r1 data with current r2. Fourteen tests, compilation, dictionary parsing, and diff checks passed. The stage awaited approval.

## 2026-07-11 21:11

- Acceptance and commit: The user approved the P0 signal-quality fixes and authorized staging and committing under the stage name.
- Deferred item 1: Chevron and Microsoft mixed-narrative clusters were recorded for future complete-link or representative-consistency work.
- Deferred item 2: Macro-risk terms will remain unchanged until annotation-based precision and recall, especially recall, can guide thresholds.

## 2026-07-11 21:51

- Stage / objective: Expand data sources and add selective full-text retrieval, including external RSS configuration, publisher identity, source-quality weights, Trafilatura caching, and r3 snapshot continuity.
- External RSS configuration and live test: Added `data/rss_sources.json` and strict loading so URLs are no longer hard-coded. Enabled 20 sources: Yahoo ticker template; six CNBC categories; three MarketWatch categories; Google News Business/Markets; Nasdaq Markets/Earnings; Benzinga Markets; The Motley Fool; Investing.com; Fortune; Business Insider; and NYT Business. The 62 concrete feeds, including 43 Yahoo tickers, all succeeded and parsed 1,285 items.
- Candidate exclusions: A legacy Motley Fool endpoint recovered after initially returning no items and was included; `/a/feeds/foolwatch` remained unauthorized. Fortune Finance returned 404. WSJ Markets returned 20 stale entries dated 2025-01-27 and was excluded. Other parsable endpoints were omitted because they duplicated selected sources.
- Publisher: Extracts `source`, `publisher`, then `dc_publisher`, falling back to feed name. Duplicate URL/title records merge publishers. Event source counts, coverage boosts, overview coverage, brief coverage, and Evaluation coverage now use publisher, with row-level source fallback for Demo and legacy records. Legacy items without publisher retain feed names.
- Source weight: `agg_weight` became `time_weight * relevance_weight * dedup_factor * source_weight`. External weights span `0.8/0.85/0.9/0.95/1.0`; cross-feed merges retain the maximum. Recalculation across 2,535 final rows differed by at most `6e-7`. The values remain priors awaiting label-based calibration.
- Selective full text: Added `src/fulltext_fetcher.py` and `trafilatura==2.1.0`. Candidates are current-UTC-day Top Drivers, high-absolute-sentiment articles, high-risk articles, or multi-article representatives. At most 30 are requested per run with a one-second interval, 10-second timeout, and no retry. Paywalls and redirects are disabled in configuration. Successful and failed requests are cached, and matching article ID, URL, or normalized title prevents another request.
- Full-text contract: Added `body_text`, `content_level`, and `rescored`; `content` remains the RSS summary. Successful full text reruns FinBERT, evidence, risk, topic, and scoring, and brief drivers prefer full-text evidence within an event. Pages do not reference `body_text`; Article Explorer shows only publisher, source weight, and content level.
- Live runs: The first 19-source run parsed 1,265 items and added 338; 26 of 30 full-text requests succeeded. RSS took 27.0 seconds, full text 41.4, and total 85.5. After adding The Motley Fool, 20 sources parsed 1,285 items and added 24; 10 of 11 remaining candidates succeeded. Combined full-text success was 36/41 (87.8%), average length 4,030 characters, and raw/processed data reached 2,535 rows.
- Summary/full-text examples: A Palo Alto Networks article moved from -0.782 to 0.385 with guidance evidence; an AI-stock article moved from -0.963 to 0.090 with TSMC execution evidence; and an oil-price article moved from -0.917 to 0.030 with broader market context. The examples show how full text can materially correct headline or short-summary polarity.
- r3 continuity: Raised `PIPELINE_REVISION` to r3 because source structure and weights affect volume, Attention, and all weighted metrics. Snapshot keys now include revision, and committed r2 data was restored for the same date. Sector counts became `r1/r2/r3=66/22/22` and market counts `6/2/2` without revision overwrite.
- Validation status: Existing 14 tests and six new source/full-text tests passed. Live collection, JSON, schema, non-display of full text, `content==summary`, non-empty publishers, Linux paths, and diff checks were verified. The final full-suite rerun was delayed by Codex execution limits rather than a test failure, and the stage remained uncommitted.

## 2026-07-11 23:41

- Final validation rerun: After execution access returned, `compileall` and complete unittest discovery passed all 21 tests, covering existing metrics, evaluation, P0, external RSS configuration, publisher fallback, source-weight arithmetic, full-text selection/cache/deduplication, paywall blocking, brief evidence preference, and same-day r2/r3 snapshots.
- Current status: Code, real data, README, DEVLOG, and validation were complete and held uncommitted for acceptance.

## 2026-07-11 23:43

- Final page and data acceptance: Reran `scripts/validate_data_source_extension.py`, confirming 20 sources, 2,535 processed rows, 36 full-text/rescored rows, `6e-7` weight error, and unchanged r1/r2/r3 counts. Market Overview and Article Explorer AppTests had zero exceptions. Only the pre-existing `use_container_width` deprecation warning remained.

## 2026-07-12 01:43

- Stage / objective: Fix full-text rescore signal dilution. Restore production aggregation and ranking to title plus summary, retaining full text for parallel evaluation, supplemental tags, and higher-quality evidence.
- Production scoring: `sentiment_score`, all three `p_*` values, Optimism, Fear, and Uncertainty are consistently calculated from the summary batch. Averaging every sentence in long documents dilutes signal toward neutral, so full text no longer overwrites aggregation or ranking fields.
- Parallel full-text view: Added `sentiment_score_fulltext`, `p_positive_fulltext`, `p_neutral_fulltext`, and `p_negative_fulltext` to the processed schema for second-stage summary-vs-full-text annotation evaluation only. They do not affect ranking or aggregation.
- Retained full-text value: Evidence prefers risk-relevant and high-signal full-text sentences. Risk categories use the union of summary and full-text tags with the greater intensity. Full text supplements topics only when summary processing falls back to `general market sentiment`; a specific summary topic is never overwritten.
- Data migration: Disabled network requests and used local GPU FinBERT to recalculate summary and full-text batches for 36 cached full-text articles. All succeeded and all 2,535 historical processed rows were preserved.
- Validation: Mean summary `|sentiment_score|` returned from the incorrectly diluted 0.211250 to 0.470806, exactly matching the pre-full-text distribution. The parallel full-text mean remains 0.211250, all four parallel fields are populated for 36/36 articles, and 34/36 evidence sentences can be located directly in full text.

## 2026-07-12 02:54

- Stage / objective: P1 UI and display fixes, nine items. This stage was performed directly by the primary Claude assistant rather than Codex.
- Work completed: 1) Added shared `src/ui_helpers.py::render_sector_heatmap()` for Market Overview and Sector Comparison. Each dimension uses its own directional colors: high Optimism green, high Fear/Uncertainty/Disagreement/Risk red, and Attention blue. Scales were fixed to 0-100 with an explanatory caption, replacing single-scale `px.imshow` charts. 2) Shortened the overview update card to `MM-DD HH:MM` and moved the full UTC value into help text. 3) Standardized the sector table to one decimal, integer article counts, translated headings, and fixed column order; six ranking summaries are arranged in a 2x3 grid. 4) Added an `st.info` note above the brief with its article count, source window, and generation time, explaining that it may differ from the live page window. 5) Translated Sector Detail trend legends and axes through `METRIC_LABELS` and formatted sentiment to three decimals. 6) Removed implementation details from driver reasons, replacing the explicit 1.15 multiplier with plain-language multi-publisher importance wording. 7) Moved Article Explorer toggles below the title and formatted 0-100 metrics to one decimal, sentiment to three, and weights to four. 8) Confirmed stored data contained no replacement characters or cp1252 pseudo-encoding; a previously observed `It??s` was only a GBK console rendering artifact. Added defensive `repair_mojibake()` processing for future bad sources.
- Additional fix from visual review: After P0, 82% of articles had an empty risk category, but the Article Explorer filter used exact `isin` matching and silently excluded them, showing only 448 of 2,478 rows. Replaced it with set matching over semicolon labels, added a **No Risk** option for empty sets, and retained rows matching any selected label. Default all-selection now shows all 2,478 rows.
- Issues and resolution: The local terminal used GBK and could raise `UnicodeEncodeError` for curly quotes. Checks switched to `python -X utf8` and `ascii()` escapes, confirming the data itself was clean.
- Current status: Compilation and all 21 unit tests passed. All five Streamlit pages were visually reviewed, including heatmap colors, cards, rankings, brief scope, trend legends, browser layout, and filter counts. The stage was not yet committed.
- Next step: Await acceptance, then commit and proceed to full-page review and human annotation.

## 2026-07-12 05:52

- Stage / objective: Add one-click blind-label CSV download to Evaluation, replacing the need to run `scripts/sample_for_annotation.py` manually.
- Page capability: Added sample-size and random-seed controls. **Generate/Refresh Blind Sample** reuses the existing stratified logic and synchronously refreshes `annotation_blind.csv` plus private `annotation_key.csv`. If a blind file already exists, the page immediately shows a download button.
- Blind boundary: The annotator download still contains only article ID, title, summary, content, URL, publication timestamp, and empty label fields. The reconciliation key appears only in a collapsed warning section and must not be given to the annotator.
- Validation: The page and sampling script compiled. A temporary smoke test generated five rows with no prediction fields in the blind columns. The page-specific diff check passed.

## 2026-07-12 19:55

- Stage / objective: Move the complete annotation workflow into the Evaluation page and remove command-line dependency.
- Sampling core: Added `src/annotation_sampling.py`, consolidating stratified selection, safe writes for blind/private files, and completed-label counts into reusable functions. The CLI script remains as a thin wrapper over the same core. Added fixed `ANNOTATION_SAMPLE_SEED = 5720` with a legacy alias.
- Page flow: Reorganized Evaluation as **Obtain Blind Sample -> Complete Offline -> Upload and Results**. Files are created only after **Generate 300 Blind Samples** is clicked and downloads use UTF-8-SIG. The annotation guide is downloadable, while the private key is used only in the backend and has no download entry point.
- Resampling guard: If any of the four label columns contain values, the page reports the filled-cell count and backup warning. Regeneration remains disabled until the user explicitly confirms discarding them. `notes` does not count as a completed label.
- Validation: Compilation passed. Real AppTest had zero exceptions and did not change the blind-file modification time during page load. In an isolated test with three completed labels, regeneration was initially disabled and unlocked only after confirmation. A temporary three-row annotation produced three sentiment evaluations, the three-way comparison, and confusion-matrix input. All 21 unit tests passed.

## 2026-07-12 20:10

- Small patch: Made the blind CSV `url` column clickable in Excel. `src/annotation_sampling.py` converts HTTP/HTTPS URLs into `HYPERLINK()` formulas displaying **Open Original Article**. Empty, invalid, and already formatted values remain unchanged. The Evaluation download path applies the same formatting, so legacy samples need not be regenerated.
- Documentation and validation: Updated the annotation guide to mark URL read-only and explain clicking it. Added hyperlink assertions to sampling tests. Verified readable Unicode display text, idempotent formatting, zero AppTest exceptions, and both blind CSV and guide downloads.

## 2026-07-13 06:10

- Stage / objective: Add sampling controls and persist blind-batch metadata.
- Work completed: Restored sample-size and random-seed controls to Evaluation Step 1, defaulting to `ANNOTATION_SAMPLE_SIZE=300` and `ANNOTATION_SAMPLE_SEED=5720`. Added `data/annotation/annotation_meta.json` with actual batch size, seed, UTC generation time, and article-ID fingerprint, written atomically after blind/key files. The page displays the persisted seed and time only after fingerprint and row count match the current blind CSV, preventing restart-time confusion with input defaults. README and the guide now require reports to cite the metadata seed.
- Historical migration and acceptance: Reconstructed the current 300-item sample in a temporary directory with seed 5720 and wrote metadata only after exact article-ID order matched the historical blind file. Used the original blind mtime `2026-07-12T11:18:58.346933+00:00`. Real-pool checks showed `5720 -> 1234 -> 5720` produced a different set at 1234 and exact ordered reproduction when restored. AppTest had zero exceptions and showed controls plus persisted seed 5720.
- Validation: `compileall` passed. Explicit `unittest discover -s tests` ran all 21 tests successfully. Plain `unittest discover` found zero because it did not enter the tests directory and was not used as evidence.
- Current status: Implementation, historical metadata, documentation, and validation were complete and awaiting acceptance.

## 2026-07-13 06:40

- Stage / objective: Fix the recency window for Top Market Drivers.
- Work completed: Added `DRIVER_WINDOW_HOURS = 48` and `DRIVER_MIN_EVENTS = 5`. `top_driver_articles()` can now filter by publication window before event collapse and ranking. Market Overview starts at 48 hours, expands to 72 then 168 when fewer than five events are available, and carries the actual window through DataFrame attributes. The heading displays the actual time range. README documents this behavior. The daily brief remains on its existing 24-hour payload by design.
- Boundaries and tests: Did not change `driver_score`, six-dimensional aggregation, `brief_builder`, or full-text candidate logic. Added regressions proving that a five-day-old high-risk item is excluded from a strict 48-hour window and that a two-event 48-hour window expands to 72 hours and returns five events. Compilation and all 23 tests passed. The real overview used 48 hours and every selected driver met the cutoff. AppTest had zero exceptions and showed the correct title.
- Current status: Implementation and validation were complete and awaiting acceptance.

## 2026-07-13 07:00

- Stage / objective: Add Top Market Drivers window switching and fix macro-guarantee ordering.
- Work completed: Added a horizontal **Last 48 Hours** (default) / **Last 30 Days** radio beneath the driver heading. Both modes reuse the same filter, event-collapse, and ranking path. Short mode keeps 48/72/168-hour expansion. Long mode uses `WORKING_SET_DAYS * 24 = 720`, never expands, and displays 30 days. A placeholder heading is created before the radio and filled after state resolution to support AppTest reruns.
- Macro guarantee: Unmapped macro events remain guaranteed but are no longer pinned first. If absent from the natural Top 5, the highest macro event replaces the lowest regular event and the final set is sorted by `driver_score`. Only guarantee-only rows carry `macro_guaranteed=True` and display a macro fallback note. README, but not metrics or brief/full-text logic, was updated.
- Validation: Added regressions for fixed 30-day behavior and descending macro-guarantee placement, retaining earlier recency tests. Compilation and all 25 tests passed. AppTest switched modes without error and updated the title. Real short and long windows each returned five correctly ordered events within the cutoff, currently with one guaranteed macro event each.
- Current status: Both the recency fix and this window/ordering increment were complete and awaiting acceptance.

## 2026-07-13 07:45

- Stage / objective: Tier A, first batch of six-dimensional formula improvements plus relative heatmaps.
- Fear and direction gating: Added `panic_keywords.json`; persisted `s_shock` now reads only market panic and risk-off reaction terms. `shock_keywords.json` remains for risk-event auditing but no longer enters Fear. Added `positive_direction_blockers.json`, preventing growth/bullish matches when the same sentence contains opposing modifiers such as slow, misses, cut, weak, or decline. Costco, McDonald's, and GE/Lockheed samples retained their text but correctly produced `g_growth/b_bull=0`.
- Risk and Disagreement: Article Risk now defaults to bounded `RISK_COMBINE="noisy_or"`, retaining `sum` as an ablation option. Sector Risk selects the highest-`agg_weight` representative per event and uses weighted P90. Disagreement now defaults to threshold-free weighted pairwise absolute sentiment distance, retaining `legacy_std_mix`/PolarityMix behind a configuration switch. README and Evaluation were synchronized.
- Snapshots and heatmaps: Raised `PIPELINE_REVISION` to r4. Sector snapshots gained `event_count` and `publisher_count`; r1-r3 history retains nulls and all 44 current r4 rows across two sources and formulas are complete. Heatmaps default to per-dimension cross-sector min-max color position while displaying raw scores in cells and hover, with an absolute 0-100 toggle.
- Full rebuild and results: Processed 132 Demo and 2,976 real articles, with CUDA embedding clustering. Cross-sector standard deviations from r3 to r4 were Optimism `2.1196->2.1574`, Fear `3.3836->3.3343`, Uncertainty unchanged at `2.8536`, Attention unchanged at `28.7480`, Disagreement `9.2288->3.6529`, and Risk `7.1401->6.9608`. Risk distribution was `0:2462, 0-5:8, 5-20:28, 20-40:212, 40-60:173, 60-80:52, 80-100:41`. Fear-Risk rank correlation changed from `-0.3545` to `-0.3727`; the unexpected small absolute increase was reported without extra tuning.
- Validation and acceptance: Compilation and all 27 tests passed. Relative/absolute heatmap switching on overview and comparison pages had no AppTest errors. Playwright prerequisites found no local npx, so no workaround was used; the user completed visual review with another tool and accepted both modes.
- Current status: Tier A was complete and awaiting commit.

## 2026-07-13 07:56

- Tier-A acceptance note: External browser review confirmed relative and absolute 0-100 heatmaps on both relevant pages. Relative mode separates each column correctly, absolute mode matches prior behavior, and captions switch with the mode. The local Playwright screenshot step was skipped based on this acceptance.
- Fear-Risk decoupling correction: Article-level Pearson correlation is `0.034` for `n=2,976`, near independence and therefore valid evidence of decoupling. Rank correlation across only 11 sectors is too small a sample and is no longer an acceptance metric; the previous expectation that it must decrease was withdrawn.
- Disagreement interpretation: The cross-sector standard-deviation reduction from `9.2288` to `3.6529` is an expected consequence of removing PolarityMix. The legacy formula remains available for later ablation.
- Current status: Tier A passed acceptance and was ready for commit.

## 2026-07-19 04:50

- Stage / objective: Complete human annotation by merging and normalizing 300 blind labels.
- Work completed: The annotator completed all 300 rows in Excel, and an external repair process merged them into `data/annotation/annotation_blind.csv`. `annotation_manual_raw.csv` and its backup preserve the original annotator input. The human-label files were not cleaned, formatted, regenerated, or resampled during this stage.
- Validation: The merged article-ID fingerprint matched `annotation_meta.json`.
- Current status: Annotation output was ready for acceptance and commit. Derived `sentiment_errors.csv` remained excluded and untracked for this stage.

## 2026-07-19 06:58

- Stage / objective: Narrow Phase 1.5 to mode-specific color scales only, based on user acceptance.
- Work completed: Restored the earlier uncommitted Phase 1.5 text-color, gamma, scale-compression, caption, test, and documentation changes to `9cb340c`. Then split `_HEATMAP_COLOR_SCALES` into named relative and absolute scales and made `render_sector_heatmap` select by `color_mode`. Relative uses `Greens / Blues / RdYlGn_r`; absolute uses `Greens / Reds / Blues / RdYlGn_r`, keeping high Fear red. Existing `texttemplate`, `textfont={"size": 11}`, hover, captions, and linear scaling were retained without a contrast-mapping algorithm.
- Validation: Compilation passed, all 28 tests passed, and AppTest opened Market Overview and Sector Comparison under both relative and absolute modes with zero exceptions. Only the existing `use_container_width` deprecation warning appeared.
- Current status: Narrow Phase 1.5 code, lightweight structural tests, README, and validation were complete. External collection data, caches, snapshots, backups, `.claude/`, and `sentiment_errors.csv` remained unchanged and excluded.

## 2026-07-19 07:40

- Stage / objective: Compress monochrome gradient bands in relative mode. This was an external direct edit, not a Codex session change.
- Work completed: Added `_SEQUENTIAL_SCALES` for Greens/Blues/Reds and `_SEQUENTIAL_BAND=(20.0, 85.0)` to `src/ui_helpers.py`. `heatmap_color_values` gained a `sequential` parameter. Relative monochrome columns are linearly compressed into 20-85 so minima are not nearly white and maxima are not nearly black. Diverging `RdYlGn_r` and absolute mode remain unchanged. `render_sector_heatmap` sets the flag based on the selected column scale; text and hover behavior were untouched.
- Validation: Compilation and all 29 tests passed, including a new test for endpoints, equal values, and unchanged absolute mode. Browser review showed the lightest Optimism cell move from `rgb(247,252,245)` to visible `rgb(194,231,187)` and the darkest to `rgb(7,115,49)`. Attention narrowed similarly, while `RdYlGn_r` metrics retained full saturation. Real data clusters at 22-24 and 28.6-30.3 remained distinguishable.
- Current status: Awaiting acceptance together with the narrowed Phase 1.5 work.

## 2026-07-19 07:43

- Stage / objective: Fix multi-version historical snapshot selection in daily briefs.
- Work completed: Real brief generation around the UTC date boundary could read both r3 and r4 rows for the same sector on `2026-07-12`, causing `.loc[sector]` to return a DataFrame and a later Series `or 0` expression to raise an ambiguity error. Added unified selection that prefers current `PIPELINE_REVISION` and otherwise chooses the latest `snapshot_timestamp`. Applied the same rule to prior market snapshots and added defensive uniqueness in `_sector_movers()`. Historical r3/r4 data remains intact.
- Validation: Added two regressions covering r3/r4 preference, latest-time fallback, same-day market versions, and scalar mover deltas. Prior real data collapsed from 22 rows to 11 unique r4 sectors. `build_brief_payload()` returned five unique movers. The full forced-generation path returned generated under mocked LLM and writes without API or data changes. Compilation and all 31 tests passed.
- Current status: The Series truth-value error was fixed and code, tests, and real-data flow were validated. External data, caches, snapshots, backups, `.claude/`, and `sentiment_errors.csv` remained excluded.

## 2026-07-19 07:54

- Stage / objective: Phase 1 blind-label CSV dtype fix.
- Work completed: Evaluation uploads, default blind-file reads, and `evaluate_annotation_files()` now use `dtype=str`, preventing binary columns with blanks from being inferred as floats. `annotation_key.csv` retains its existing read behavior. `normalize_binary_label()` also accepts `"1.0"` and `"0.0"`. Added a temporary CSV round-trip regression covering `"1"`, `"0"`, and blanks and asserting correct valid-sample counts.
- Validation: Compilation and all 32 tests passed. The real 300-row evaluation aligned all 300 records, found 299 valid sentiment labels, produced three model comparisons, three confusion matrices, seven calibration bins, 187 valid risk labels, and 140 derived sentiment-error rows. Evaluation AppTest had zero exceptions and errors and rendered all comparison, matrix, and calibration sections.
- Current status: Phase 1 code, regressions, real evaluation, and page validation were complete. Original annotation files were untouched. External data, caches, snapshots, backups, and `.claude/` remained excluded, while derived `sentiment_errors.csv` was included with this stage.

## 2026-07-19 08:15

- Stage / objective: Phase 2 evidence-sentence and risk-metric terminology corrections.
- Work completed: Changed display text and README only, without calculation changes. Renamed **Evidence Precision** to **Evidence Top-1 Agreement**. Help text explains that `label_evidence_ok` is automatically derived from independent annotator and model evidence when normalized text contains the other or similarity is at least 0.85. It measures selection of the same sentence and is a stricter conservative lower bound than general acceptability. The risk section states that blanks are missing rather than `none`, with 187 valid samples. README also records `annotation_manual_raw.csv` as the original audit file.
- Validation: Real Evaluation AppTest had zero exceptions and errors and rendered the renamed metric, full matching explanation, and 187-sample caption. Compilation and all 32 tests passed.
- Current status: Page wording, README, and validation were complete. Evaluation calculations, annotation files, and external runtime products were unchanged.

## 2026-07-19 08:51

- Stage / objective: Phase 3 weight sensitivity analysis.
- Work completed: Added `src/sensitivity_analysis.py`, reading real news only from the production `real_processed_articles.csv` path. Each of the 15 components across six dimensions receives one-at-a-time factors `{0, 0.5, 0.8, 1.2, 1.5}` and within-dimension renormalization. Existing `sector_metrics()` recomputes every sector-day without Demo fallback or FinBERT reruns. Each run reports mean daily Spearman rank correlation, mean absolute 0-100 score change, and mean daily Top-3 Jaccard. All 75 rows are persisted to `data/evaluation/sensitivity_analysis.csv`. Evaluation recalculates only on button click and otherwise displays existing results plus a six-row most-sensitive summary. README and config TODOs were synchronized.
- Real-data results: The production path loaded 3,866 records, 3,529 of them in the 11 target sectors, covering 51 valid dates and 561 sector-days. Including factor-0 ablation, minimum mean daily Spearman by dimension was Optimism `0.358475`, Fear `0.163845`, Uncertainty `0.896136`, Attention `0.941126`, Disagreement `1.000000`, and Risk Intensity `0.982224`. Restricting to factors 0.5/0.8/1.2/1.5 produced `0.990357`, `0.998394`, `0.964027`, `0.993168`, `1.000000`, and `0.997139`. Results were reported without tuning. Pairwise Disagreement does not consume legacy weights, so that perturbation correctly remains unchanged.
- Validation: Compilation and all 37 tests passed, covering factor 1.0 identity, within-dimension normalization, isolated changes, Demo rejection, and constant-rank handling. AppTest clicked the analysis button, completed the full real replay with zero exceptions/errors, wrote results, and rendered the `(75, 10)` table, `(6, 6)` summary, timestamp, formula version, real source, and explanation.
- Current status: Implementation, persisted real results, documentation, and validation were complete. News, annotations, collection/brief products, backups, and `.claude/` were excluded; AppTest-generated sensitivity backups remained untracked.

## 2026-07-19 08:20

- Stage / objective: Fix heatmap hover values. This was an external direct edit, not a Codex session change.
- Work completed: Since Tier A, hover displayed `-` instead of the raw score because each cell's `customdata` was a scalar but the template used `%{customdata[0]:.1f}`, indexing the scalar to undefined. Changed the template in `src/ui_helpers.py` to `%{customdata:.1f}` and left all other rendering behavior unchanged.
- Validation: Browser comparison showed `%{customdata:.1f}` and `%{text}` both display 23.8 while the old expression displays `-`. Compilation and the full test suite passed at the time, and the user accepted the local dashboard result.
- Current status: The code fix was already committed in `9d0a80a`; this entry was added afterward for the record.

## 2026-07-24 21:52

- Stage / objective: Complete repository-wide English localization.
- Work completed: Audited all tracked and ignored text assets in the project and translated every Chinese-language occurrence into English. This included Python comments, docstrings, command-line messages, dependency notes, the full annotation guide, four historical market briefs, full-text cache error text, snapshot source labels, tests, and all tracked and ignored snapshot backups. Legacy Chinese annotation-value aliases remain backward compatible through Unicode escape sequences, leaving the source itself English-only. Historical `data_source` values now match the application's current `Real news` and `Demo data` labels.
- Annotation protection: `annotation_key.csv`, `annotation_manual_raw.csv`, `annotation_meta.json`, and `sentiment_errors.csv` retained their original SHA-256 hashes. In `annotation_blind.csv`, only the Excel hyperlink display text (`Open article`) and one existing Chinese note were translated; article rows, labels, and scores were not regenerated, resampled, reordered, or recalculated. Its three tracked backups received only the same hyperlink-display translation.
- Validation: A recursive scan across visible and ignored `.py`, `.md`, `.json`, `.toml`, `.txt`, `.csv`, `.yaml`, `.yml`, `.html`, `.js`, `.css`, `.ps1`, and `.gitignore` files found zero CJK ideographs. Python 3.12 compilation passed, all 37 unit tests passed, and the root Streamlit AppTest completed with zero exceptions and zero errors. `git diff --check` passed for code and documentation; `annotation_blind.csv` was excluded because its intentionally empty final `notes` fields are represented by trailing CSV delimiters.
- Current status: English localization and validation are complete. No calculation logic, model weights, real-news records, manual annotation decisions, or sensitivity-analysis results were changed. Changes remain uncommitted pending user review.
