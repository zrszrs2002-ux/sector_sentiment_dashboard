# Blind News-Classification Annotation Guide

This task evaluates article-level model classifications, not investment merit. In the first pass, the primary annotator must open only `annotation_blind.csv` and must not inspect `annotation_key.csv`. Complete and lock the sentiment and risk labels first. In the second pass, the evaluation lead keeps the private key and reconciles only sector assignment and evidence sentences without changing first-pass labels. Read each article's title, summary, and content before labeling; when all three repeat the same text, treat them as one passage.

Generate the blind-labeling sample from **Step 1** on the Evaluation page. The sample size and random seed can be changed on the page. Using the same news pool, sample size, and seed reproduces the exact same set of `article_id` values. After generation, `data/annotation/annotation_meta.json` records the actual row count, seed, and generation time for the current batch. Reports and reproducibility runs must cite the final batch seed from that file, not the page input's default value.

## 1. Fields

- `url`: Read-only. In Excel it appears as an **Open Article** link that opens the corresponding news article in a browser.
- `label_sentiment`: Enter only `positive`, `neutral`, or `negative`.
- `label_sector_ok`: Second-pass reconciliation field. Enter `1` when the model's sector assignment is correct and `0` when it is incorrect. Leave it blank when uncertain and explain the uncertainty in `notes`.
- `label_risk_categories`: Multiple selections are allowed. Use the English labels in the table below, separated by ASCII semicolons (`;`). Enter `none` when the text contains no explicit risk.
- `label_evidence_ok`: Second-pass reconciliation field. Enter `1` when the model's evidence sentence independently supports the main sentiment or risk judgment; otherwise enter `0`. Leave it blank when uncertain.
- `notes`: Record borderline cases, suggested sector corrections, or reasons for misclassification. Do not record model predictions.

## 2. Three-Way Sentiment Labels

- `positive`: The article's main narrative clearly indicates improving operations, growing demand, results above expectations, an upgrade, risk relief, or another favorable outcome.
- `negative`: The main narrative clearly indicates worsening operations, falling demand, results below expectations, a downgrade, litigation or regulatory pressure, a crisis, or another unfavorable outcome.
- `neutral`: The article is purely factual, lacks enough information or a clear direction, or contains roughly balanced positive and negative evidence.

Boundary rules:

1. When positive and negative evidence are mixed, determine the main conclusion the article is trying to convey; do not count keywords mechanically. If favorable and unfavorable information are equally important and there is no clear conclusion, label it `neutral`.
2. Purely factual reports of earnings figures, completed transactions, personnel changes, meeting schedules, and similar events default to `neutral`. Use a positive or negative label only when the text explicitly explains a favorable or unfavorable implication.
3. When share-price movement is the article's main subject, a clear increase is `positive` and a clear decrease is `negative`. If the text only describes greater volatility, repeated intraday reversals, or a mixture of gainers and losers without a dominant direction, label it `neutral`.
4. Analyst buy recommendations or target-price increases are usually `positive`; sell recommendations or target-price cuts are usually `negative`. When a headline contains a contrast, follow its final conclusion.
5. Do not add inferences from outside knowledge. Judge only the text in the current row.

## 3. Risk Categories

| Label | Definition and typical cases |
|---|---|
| `macro risk` | Recession, inflation, slowing growth, or systemic macroeconomic shocks |
| `interest rate risk` | Changes in interest rates, yields, financing costs, or monetary policy |
| `regulatory risk` | Regulatory review, policy restrictions, pricing rules, or compliance changes |
| `earnings risk` | Earnings, revenue, margins, guidance, or execution falling below expectations |
| `valuation risk` | Excessive valuation, multiple compression, asset-price pressure, or pullback risk |
| `liquidity risk` | Financing, refinancing, access to funding, or insufficient liquidity |
| `credit risk` | Default, credit quality, loan losses, or reserve pressure |
| `geopolitical risk` | Sanctions, trade restrictions, war, or cross-border supply shocks |
| `commodity risk` | Volatility in oil, metals, other commodity prices, or input costs |
| `demand risk` | Weak customer demand, orders, traffic, or sales, or declining visibility |
| `none` | The text contains no explicit risk and is only general information or a positive event |

One article may contain multiple explicit risks. For example, an oil-price shock that also affects inflation may be labeled `commodity risk;macro risk`. Do not add a risk merely because it could exist; the text must provide direct evidence.

## 4. Evidence-Sentence Standard

A valid evidence sentence must meet all of these conditions: it comes from the current article; it is semantically complete; it is understandable without outside context; and it directly supports the main sentiment, risk, or event judgment. A company name alone, an incomplete phrase, a truncated RSS fragment, a number unrelated to the main conclusion, or text that requires cross-sentence guessing is invalid. A headline may serve as evidence only when it is itself a complete statement that sufficiently supports the judgment.

## 5. Quality Control

The independent first-pass annotator must not inspect the reconciliation key. When uncertain, leave a field blank and explain the issue in `notes` rather than guessing. After first-pass labels are locked, the evaluation lead completes second-pass reconciliation. Finally, verify that every non-empty label uses exactly the English values and delimiters defined in this guide.
