# Warranty Claims Analytics Pipeline — Plan

## Overview

An end-to-end warranty claims analytics pipeline that ingests claim records from CSV/JSON,
detects failure patterns across components and suppliers, calculates reliability metrics
(MTTF, failure rates), performs root-cause clustering, scores supplier quality, and produces
monthly trend reports with early-warning alerts. Maintains historical baselines for YoY comparison.

---

## Agents

| Agent | Model | Role |
|---|---|---|
| **claim-parser** | claude-haiku-4-5 | Ingests raw claim files, normalizes fields, validates data quality, writes structured claim records |
| **failure-analyst** | claude-sonnet-4-6 | Aggregates claims by part/model-year/supplier, calculates failure rates and MTTF, flags anomalies |
| **pattern-detector** | claude-opus-4-6 | Applies statistical thresholds to detect emerging failure patterns, classifies severity, issues alerts |
| **root-cause-clusterer** | claude-sonnet-4-6 | Groups related failures by symptom similarity, identifies common root causes, links to supplier/batch |
| **report-generator** | claude-haiku-4-5 | Compiles trend reports, supplier scorecards, recovery cost estimates, early-warning summaries |

---

## MCP Servers

| Server | Package | Purpose |
|---|---|---|
| **filesystem** | `@modelcontextprotocol/server-filesystem` | Read claim files, write reports and intermediate data |
| **sequential-thinking** | `@modelcontextprotocol/server-sequential-thinking` | Structured reasoning for pattern detection and root-cause analysis |

---

## Data Model

| File | Writer | Reader(s) | Description |
|---|---|---|---|
| `data/claims/raw/*.csv` | (external input) | claim-parser | Raw warranty claim CSV files |
| `data/claims/raw/*.json` | (external input) | claim-parser | Raw warranty claim JSON files |
| `data/claims/normalized.json` | claim-parser | failure-analyst, root-cause-clusterer | Cleaned, normalized claim records |
| `data/claims/quality-report.json` | claim-parser | failure-analyst | Data quality stats (missing fields, duplicates, parse errors) |
| `data/metrics/failure-rates.json` | failure-analyst | pattern-detector, report-generator | Failure rates by part number, model year, supplier |
| `data/metrics/mttf.json` | failure-analyst | pattern-detector, report-generator | Mean-time-to-failure calculations per component |
| `data/metrics/aggregations.json` | failure-analyst | pattern-detector, root-cause-clusterer | Claims aggregated by part, model-year, supplier |
| `data/patterns/detected-patterns.json` | pattern-detector | root-cause-clusterer, report-generator | Emerging failure patterns with severity classification |
| `data/patterns/alerts.json` | pattern-detector | report-generator | Critical/field-action alerts requiring attention |
| `data/clusters/root-causes.json` | root-cause-clusterer | report-generator | Root cause clusters with linked suppliers/batches |
| `data/clusters/supplier-issues.json` | root-cause-clusterer | report-generator | Supplier-specific quality issues |
| `reports/supplier-scorecards.md` | report-generator | (human consumer) | Per-supplier quality scorecards |
| `reports/monthly-trends.md` | report-generator | (human consumer) | Monthly trend report with YoY comparison |
| `reports/early-warnings.md` | report-generator | (human consumer) | Early warning alert summary |
| `reports/recovery-estimates.md` | report-generator | (human consumer) | Supplier recovery cost estimates |
| `data/baselines/historical.json` | report-generator | failure-analyst, pattern-detector | Historical baselines for YoY comparison |

---

## Phase Pipeline

### Daily Claim Ingestion Workflow

| # | Phase | Mode | Agent | Description |
|---|---|---|---|---|
| 1 | `ingest-claims` | agent | claim-parser | Read raw CSV/JSON claim files, normalize schema, deduplicate, validate fields, write normalized.json |
| 2 | `validate-data-quality` | command | — | Run python3 script to check data quality thresholds (completeness, consistency) |
| 3 | `review-data-quality` | agent | claim-parser | Review quality-report.json; decide if data is usable or needs re-ingestion |
| 4 | `calculate-metrics` | agent | failure-analyst | Aggregate claims, calculate failure rates and MTTF by part/model-year/supplier |
| 5 | `update-baselines` | command | — | Run python3 script to merge new metrics into historical baselines |

### Weekly Pattern Analysis Workflow

| # | Phase | Mode | Agent | Description |
|---|---|---|---|---|
| 1 | `detect-patterns` | agent | pattern-detector | Analyze failure-rates.json and mttf.json against baselines, detect emerging patterns using statistical thresholds |
| 2 | `assess-severity` | agent | pattern-detector | Classify each pattern's severity; decide if action needed |
| 3 | `cluster-root-causes` | agent | root-cause-clusterer | Group related failures by symptom, identify common root causes, link to supplier/batch |
| 4 | `score-suppliers` | agent | root-cause-clusterer | Calculate supplier quality scores, identify repeat offenders, flag for audit |
| 5 | `generate-weekly-alerts` | agent | report-generator | Produce early-warning alerts and supplier issue summaries |

### Monthly Trend Report Workflow

| # | Phase | Mode | Agent | Description |
|---|---|---|---|---|
| 1 | `calculate-monthly-stats` | command | — | Run python3 script to compute monthly aggregates and YoY deltas |
| 2 | `generate-supplier-scorecards` | agent | report-generator | Produce per-supplier quality scorecards with recovery cost estimates |
| 3 | `compile-trend-report` | agent | report-generator | Write monthly trend report with charts data, early warnings, and YoY comparison |

---

## Workflow Routing

### daily-ingestion
```
ingest-claims → validate-data-quality → review-data-quality
  ├─ [pass] → calculate-metrics → update-baselines → DONE
  └─ [rework] → ingest-claims (max 2 retries)
```

### weekly-analysis
```
detect-patterns → assess-severity
  ├─ [normal] → generate-weekly-alerts → DONE
  ├─ [monitor/field-action/critical-recall] → cluster-root-causes → score-suppliers → generate-weekly-alerts → DONE
  └─ [rework] → detect-patterns (max 2 retries)
```

### monthly-report
```
calculate-monthly-stats → generate-supplier-scorecards → compile-trend-report → DONE
```

---

## Scripts

### validate-data-quality.py
Reads `data/claims/normalized.json`, checks:
- Field completeness (>95% required)
- Date format consistency
- Duplicate claim IDs
- Valid part number format
Writes results to `data/claims/quality-report.json`.

### update-baselines.py
Reads `data/metrics/failure-rates.json` and `data/baselines/historical.json`.
Merges current period metrics into historical baselines with timestamp.
Maintains rolling 24-month window.

### calculate-monthly-stats.py
Reads `data/metrics/failure-rates.json`, `data/metrics/mttf.json`, and `data/baselines/historical.json`.
Computes monthly aggregates, YoY deltas, trend direction indicators.
Writes to `data/metrics/monthly-summary.json`.

---

## Key Design Decisions

1. **Model allocation**: Haiku for high-volume parsing and report compilation (cost-efficient for repetitive work). Sonnet for analytical work (failure analysis, root-cause clustering). Opus for pattern detection (needs strongest reasoning for statistical anomaly detection).

2. **Two-tier pattern detection**: First detect patterns statistically, then assess severity separately. This prevents the detector from self-censoring marginal signals — severity classification is a distinct judgment.

3. **Data quality gate**: The review-data-quality phase has a rework loop back to ingest-claims. Bad data in → bad analytics out. Worth the retry cost.

4. **Severity-based routing in weekly analysis**: Normal findings skip root-cause clustering entirely (no point clustering when there's nothing anomalous). Only elevated severities trigger the full analysis chain.

5. **Historical baselines as shared state**: The baselines file is both read and written by different workflows. Daily ingestion updates it; weekly analysis reads it for comparison. This creates a natural feedback loop.

6. **Supplier scorecards separate from trend report**: Different audiences — procurement reads scorecards, engineering reads trends. Separate documents serve both.

7. **Command phases for pure computation**: Statistical calculations (validation, baseline merging, monthly stats) use python3 command phases. No LLM reasoning needed for arithmetic — cheaper and more reliable.
