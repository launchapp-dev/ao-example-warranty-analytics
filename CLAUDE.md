# Warranty Claims Analytics Pipeline — Agent Context

## What This Repo Does

This is an automated warranty analytics system for automotive/manufacturing quality management.
It processes raw warranty claim records to detect failure patterns, calculate reliability metrics,
and generate actionable reports for procurement and engineering teams.

## Three Independent Workflows

### 1. `daily-ingestion` (runs every morning at 6 AM)
Ingests new claim files, validates quality, computes failure rates and MTTF, updates historical baselines.
Run manually: `ao workflow run daily-ingestion`

### 2. `weekly-analysis` (runs every Monday at 8 AM)
Detects emerging failure patterns against baselines, clusters root causes, scores suppliers, issues alerts.
Run manually: `ao workflow run weekly-analysis`

### 3. `monthly-report` (runs on the 1st of each month at 9 AM)
Computes monthly aggregates, generates supplier scorecards and trend reports.
Run manually: `ao workflow run monthly-report`

## Data Directory Conventions

- `data/claims/raw/` — Drop input files here (CSV or JSON). Both formats are supported.
- `data/claims/normalized.json` — Written by `claim-parser`. Single source of truth for clean claim records.
- `data/claims/quality-report.json` — Written by `claim-parser`, read by `review-data-quality` phase.
- `data/metrics/` — All computed metrics live here. Written by `failure-analyst` and python3 scripts.
- `data/patterns/` — Pattern detection output. Written by `pattern-detector`.
- `data/clusters/` — Root cause clusters and supplier issues. Written by `root-cause-clusterer`.
- `data/baselines/historical.json` — Rolling 24-month baseline window. Updated daily by `update-baselines.py`.
- `data/config/fleet-sizes.json` — Optional. Estimated fleet sizes per part/model-year for failure rate accuracy.
- `data/config/benchmarks.json` — Optional. Industry benchmarks for supplier scorecard comparison.
- `reports/` — Final Markdown reports. Written by `report-generator`.

## Key Data Schemas

### Normalized Claim Record
```json
{
  "claim_id": "CLM-2024-001234",
  "claim_date": "2024-03-15",
  "vehicle_vin": "1HGBH41JXMN109186",
  "model_year": 2022,
  "make": "Ford",
  "model": "F-150",
  "mileage_at_claim": 34521,
  "part_number": "ENG-0421-A",
  "part_description": "Engine oil pump assembly",
  "failure_symptom": "Low oil pressure warning, engine knock at idle",
  "failure_code": "P0520",
  "repair_cost": 1240.00,
  "labor_hours": 4.5,
  "dealer_code": "DLR-TX-0042",
  "supplier_id": "SUP-ACME-003",
  "manufacture_date": "2021-09-14",
  "warranty_type": "powertrain"
}
```

### Historical Baseline Entry
```json
{
  "period": "2024-02",
  "part_number": "ENG-0421-A",
  "supplier_id": "SUP-ACME-003",
  "model_year": 2022,
  "failure_rate_per_1000": 1.4,
  "mttf_miles": 52300,
  "avg_repair_cost": 1180.00,
  "claim_count": 18,
  "recorded_at": "2024-03-01T06:15:00Z"
}
```

## Decision Verdicts

### `review-data-quality` phase
- `pass` — completeness >95%, duplicate rate <2%, parse error rate <5%
- `rework` — fixable issues (parsing problems, format inconsistencies) — retries ingestion
- `fail` — fundamental data problems (no valid records, missing required fields everywhere)

### `assess-severity` phase
- `critical-recall` — safety-related, rate >5/1000, or fleet exposure >10,000 units
- `field-action` — high cost/frequency, rate >2/1000, or >5,000 exposure
- `monitor` — emerging signal, below thresholds but trending up
- `normal` — within statistical norms, skips root-cause analysis

## Severity Routing
When `assess-severity` returns `normal`, the weekly-analysis workflow skips directly to
`generate-weekly-alerts` (no RCA needed). All other verdicts proceed through
`cluster-root-causes` → `score-suppliers` → `generate-weekly-alerts`.

## Python Scripts
Three command-phase scripts in `scripts/`:
- `validate-data-quality.py` — Reads normalized.json, checks thresholds, writes quality-report.json
- `update-baselines.py` — Merges current metrics into historical.json, maintains 24-month window
- `calculate-monthly-stats.py` — Computes monthly aggregates and YoY deltas for report-generator

## Model Selection Rationale
- **Haiku** (`claim-parser`, `report-generator`) — High-volume, repetitive tasks. Parsing thousands of records and formatting reports doesn't need heavy reasoning.
- **Sonnet** (`failure-analyst`, `root-cause-clusterer`) — Analytical work with complex aggregations and multi-factor root cause analysis.
- **Opus** (`pattern-detector`) — Statistical anomaly detection requires the strongest reasoning model. False negatives (missed recall patterns) create safety and legal liability.
