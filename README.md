# Warranty Claims Analytics Pipeline

End-to-end warranty analytics — ingests raw claim files, calculates failure rates and MTTF, detects emerging failure patterns, clusters root causes, scores suppliers, and generates monthly trend reports with early-warning alerts.

---

## Workflow Diagram

```
Daily Claim Ingestion (6:00 AM daily)
────────────────────────────────────
ingest-claims (claim-parser)
    │
    ▼
validate-data-quality [python3 script]
    │
    ▼
review-data-quality (claim-parser)  ──[rework/fail]──► ingest-claims (max 2 retries)
    │ [pass]
    ▼
calculate-metrics (failure-analyst)
    │
    ▼
update-baselines [python3 script]
    │
    ▼
  DONE (PR → main)


Weekly Pattern Analysis (Monday 8:00 AM)
─────────────────────────────────────────
detect-patterns (pattern-detector)
    │
    ▼
assess-severity (pattern-detector)
    ├──[normal]──────────────────────────────────────► generate-weekly-alerts
    ├──[rework]──────────────────────────────────────► detect-patterns (max 2 retries)
    └──[monitor/field-action/critical-recall]
            │
            ▼
    cluster-root-causes (root-cause-clusterer)
            │
            ▼
    score-suppliers (root-cause-clusterer)
            │
            ▼
    generate-weekly-alerts (report-generator)
            │
            ▼
         DONE (PR → main)


Monthly Trend Report (1st of month, 9:00 AM)
──────────────────────────────────────────────
calculate-monthly-stats [python3 script]
    │
    ▼
generate-supplier-scorecards (report-generator)
    │
    ▼
compile-trend-report (report-generator)
    │
    ▼
  DONE (PR → main)
```

---

## Quick Start

```bash
cd examples/warranty-analytics

# Drop raw claim files (CSV or JSON) into:
mkdir -p data/claims/raw
cp /path/to/claims.csv data/claims/raw/

# Start the daemon
ao daemon start

# Run immediately (don't wait for schedule)
ao workflow run daily-ingestion
ao workflow run weekly-analysis
ao workflow run monthly-report

# Watch live
ao daemon stream --pretty
```

---

## Agents

| Agent | Model | Role |
|---|---|---|
| **claim-parser** | claude-haiku-4-5 | Ingests raw CSV/JSON claim files, normalizes schema, deduplicates, validates fields |
| **failure-analyst** | claude-sonnet-4-6 | Aggregates claims by part/model-year/supplier, calculates failure rates and MTTF metrics |
| **pattern-detector** | claude-opus-4-6 | Detects emerging failure patterns using statistical thresholds, classifies severity |
| **root-cause-clusterer** | claude-sonnet-4-6 | Clusters related failures by symptom/batch/supplier, identifies root causes |
| **report-generator** | claude-haiku-4-5 | Compiles supplier scorecards, monthly trend reports, early-warning summaries |

---

## AO Features Demonstrated

| Feature | Where |
|---|---|
| **Scheduled workflows** | Daily ingestion (6 AM), weekly analysis (Mondays), monthly report (1st of month) |
| **Multi-agent pipeline** | 5 specialized agents across 3 independent workflows |
| **Command phases** | `python3` for validation, baseline merging, monthly stats computation |
| **Decision contracts** | `review-data-quality` (pass/rework/fail), `assess-severity` (critical-recall/field-action/monitor/normal) |
| **Rework loops** | Data quality gate retries ingestion up to 2×; pattern detection retries on ambiguous data |
| **Severity-based routing** | `assess-severity` normal verdict skips RCA chain; elevated verdicts proceed to clustering |
| **Output contracts** | Structured JSON data files flowing between agents; final Markdown reports |
| **Multiple models** | Haiku (cost-efficient parsing/reporting), Sonnet (analytical work), Opus (statistical anomaly detection) |
| **Post-success merge** | All workflows auto-PR to main on completion |

---

## Data Flow

```
data/claims/raw/*.{csv,json}
    └── claim-parser ──► data/claims/normalized.json
                    ──► data/claims/quality-report.json
                         │
                    [python3 validate]
                         │
                failure-analyst ──► data/metrics/failure-rates.json
                                ──► data/metrics/mttf.json
                                ──► data/metrics/aggregations.json
                         │
                    [python3 update-baselines]
                         │
                         └──► data/baselines/historical.json
                                    │
                        pattern-detector ──► data/patterns/detected-patterns.json
                                         ──► data/patterns/alerts.json
                                    │
                        root-cause-clusterer ──► data/clusters/root-causes.json
                                             ──► data/clusters/supplier-issues.json
                                    │
                    [python3 monthly-stats] ──► data/metrics/monthly-summary.json
                                    │
                        report-generator ──► reports/supplier-scorecards.md
                                         ──► reports/monthly-trends.md
                                         ──► reports/early-warnings.md
                                         ──► reports/recovery-estimates.md
```

---

## Requirements

**No external API keys required.** All analysis runs locally using Claude models.

### Input Data Format

**CSV** (required columns):
```
claim_id,date_filed,vehicle_vin,model_year,make,model,mileage_at_failure,
part_number,part_description,failure_symptom,failure_code,warranty_cost,
labor_hours,dealer_code,supplier_id
```

**JSON** (array of objects with the same fields).

### Optional Config

`data/config/fleet-sizes.json` — estimated fleet size per part/model-year for accurate failure rate calculations:
```json
[
  { "part_number": "ENG-0421-A", "model_year": 2022, "fleet_size": 45000 }
]
```

`data/config/benchmarks.json` — industry benchmarks for supplier scorecard comparison:
```json
[
  { "component_category": "powertrain", "benchmark_failure_rate_per_1000": 2.1 }
]
```

### Directory Structure

```
warranty-analytics/
├── .ao/workflows/          # AO workflow definitions
│   ├── agents.yaml
│   ├── phases.yaml
│   ├── workflows.yaml
│   ├── mcp-servers.yaml
│   └── schedules.yaml
├── data/
│   ├── claims/
│   │   ├── raw/            # Drop input files here
│   │   ├── normalized.json  # Generated
│   │   └── quality-report.json  # Generated
│   ├── metrics/             # Generated
│   ├── patterns/            # Generated
│   ├── clusters/            # Generated
│   ├── baselines/           # Maintained across runs
│   └── config/              # Optional benchmarks/fleet sizes
├── reports/                 # Generated Markdown reports
├── scripts/                 # Python computation scripts
│   ├── validate-data-quality.py
│   ├── update-baselines.py
│   └── calculate-monthly-stats.py
├── sample-data/             # Example input files for testing
│   ├── sample-claims.csv
│   └── sample-claims.json
├── CLAUDE.md
└── README.md
```
