#!/usr/bin/env python3
"""
validate-data-quality.py
Reads data/claims/normalized.json and writes a quality-report.json with completeness,
duplicate, and parse error statistics. Called as a command phase after claim ingestion.
"""

import json
import os
import sys
from datetime import datetime

NORMALIZED_PATH = "data/claims/normalized.json"
QUALITY_REPORT_PATH = "data/claims/quality-report.json"

REQUIRED_FIELDS = ["claim_id", "claim_date", "part_number", "supplier_id"]
OPTIONAL_FIELDS = [
    "vehicle_vin", "model_year", "make", "model", "mileage_at_claim",
    "part_description", "failure_symptom", "failure_code", "repair_cost",
    "labor_hours", "dealer_code", "manufacture_date", "warranty_type"
]
ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

COMPLETENESS_THRESHOLD = 95.0
DUPLICATE_RATE_THRESHOLD = 2.0
PARSE_ERROR_THRESHOLD = 5.0


def validate():
    if not os.path.exists(NORMALIZED_PATH):
        print(f"ERROR: {NORMALIZED_PATH} not found. Run ingest-claims first.", file=sys.stderr)
        sys.exit(1)

    with open(NORMALIZED_PATH, "r") as f:
        try:
            claims = json.load(f)
        except json.JSONDecodeError as e:
            print(f"ERROR: Could not parse {NORMALIZED_PATH}: {e}", file=sys.stderr)
            sys.exit(1)

    if not isinstance(claims, list):
        print(f"ERROR: {NORMALIZED_PATH} must be a JSON array.", file=sys.stderr)
        sys.exit(1)

    total = len(claims)
    if total == 0:
        report = {
            "checked_at": datetime.utcnow().isoformat() + "Z",
            "total_claims": 0,
            "completeness_pct": 0.0,
            "duplicate_rate_pct": 0.0,
            "duplicate_count": 0,
            "fields_null_count": {},
            "required_fields_missing": {},
            "invalid_values": [],
            "status": "fail",
            "status_reason": "No claims found in normalized.json"
        }
        _write_report(report)
        print("FAIL: No claims found.")
        sys.exit(1)

    # --- Duplicate check ---
    claim_ids = [c.get("claim_id") for c in claims if c.get("claim_id")]
    duplicate_count = len(claim_ids) - len(set(claim_ids))
    duplicate_rate_pct = (duplicate_count / total) * 100

    # --- Field completeness ---
    fields_null_count = {f: 0 for f in ALL_FIELDS}
    required_fields_missing = {f: 0 for f in REQUIRED_FIELDS}
    invalid_values = []

    for i, claim in enumerate(claims):
        for field in ALL_FIELDS:
            val = claim.get(field)
            if val is None or val == "":
                fields_null_count[field] += 1
                if field in REQUIRED_FIELDS:
                    required_fields_missing[field] += 1

        # Validate specific field formats
        if claim.get("claim_date"):
            try:
                datetime.fromisoformat(str(claim["claim_date"]).replace("Z", ""))
            except ValueError:
                invalid_values.append({
                    "claim_id": claim.get("claim_id", f"index_{i}"),
                    "field": "claim_date",
                    "value": claim["claim_date"],
                    "reason": "invalid ISO 8601 date"
                })

        if claim.get("mileage_at_claim") is not None:
            try:
                mileage = float(claim["mileage_at_claim"])
                if mileage < 0:
                    invalid_values.append({
                        "claim_id": claim.get("claim_id", f"index_{i}"),
                        "field": "mileage_at_claim",
                        "value": mileage,
                        "reason": "negative mileage"
                    })
                elif mileage > 500000:
                    invalid_values.append({
                        "claim_id": claim.get("claim_id", f"index_{i}"),
                        "field": "mileage_at_claim",
                        "value": mileage,
                        "reason": "implausibly high mileage (>500k)"
                    })
            except (TypeError, ValueError):
                invalid_values.append({
                    "claim_id": claim.get("claim_id", f"index_{i}"),
                    "field": "mileage_at_claim",
                    "value": claim["mileage_at_claim"],
                    "reason": "not a number"
                })

        if claim.get("repair_cost") is not None:
            try:
                cost = float(claim["repair_cost"])
                if cost < 0:
                    invalid_values.append({
                        "claim_id": claim.get("claim_id", f"index_{i}"),
                        "field": "repair_cost",
                        "value": cost,
                        "reason": "negative cost"
                    })
            except (TypeError, ValueError):
                pass  # claim-parser should have already cleaned this

    # --- Completeness percentage ---
    total_possible_fields = total * len(ALL_FIELDS)
    total_null = sum(fields_null_count.values())
    completeness_pct = ((total_possible_fields - total_null) / total_possible_fields) * 100

    # --- Determine status ---
    issues = []
    if completeness_pct < COMPLETENESS_THRESHOLD:
        issues.append(f"completeness {completeness_pct:.1f}% < {COMPLETENESS_THRESHOLD}% threshold")
    if duplicate_rate_pct > DUPLICATE_RATE_THRESHOLD:
        issues.append(f"duplicate rate {duplicate_rate_pct:.1f}% > {DUPLICATE_RATE_THRESHOLD}% threshold")
    any_required_missing = any(v > 0 for v in required_fields_missing.values())
    if any_required_missing:
        missing_summary = ", ".join(f"{k}={v}" for k, v in required_fields_missing.items() if v > 0)
        issues.append(f"required fields missing in some records: {missing_summary}")

    status = "pass" if not issues else "warn"

    report = {
        "checked_at": datetime.utcnow().isoformat() + "Z",
        "total_claims": total,
        "completeness_pct": round(completeness_pct, 2),
        "duplicate_count": duplicate_count,
        "duplicate_rate_pct": round(duplicate_rate_pct, 2),
        "fields_null_count": {k: v for k, v in fields_null_count.items() if v > 0},
        "required_fields_missing": {k: v for k, v in required_fields_missing.items() if v > 0},
        "invalid_values_count": len(invalid_values),
        "invalid_values_sample": invalid_values[:20],
        "thresholds": {
            "completeness_required": COMPLETENESS_THRESHOLD,
            "duplicate_rate_max": DUPLICATE_RATE_THRESHOLD,
        },
        "status": status,
        "issues": issues
    }

    _write_report(report)

    print(f"Quality check complete: {status.upper()}")
    print(f"  Total claims:    {total}")
    print(f"  Completeness:    {completeness_pct:.1f}%")
    print(f"  Duplicates:      {duplicate_count} ({duplicate_rate_pct:.1f}%)")
    print(f"  Invalid values:  {len(invalid_values)}")
    if issues:
        for issue in issues:
            print(f"  WARN: {issue}")

    if status == "pass":
        sys.exit(0)
    else:
        # Non-zero exit signals the workflow to check the report
        sys.exit(0)  # Let review-data-quality agent make the pass/rework/fail decision


def _write_report(report):
    os.makedirs(os.path.dirname(QUALITY_REPORT_PATH), exist_ok=True)
    with open(QUALITY_REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Wrote {QUALITY_REPORT_PATH}")


if __name__ == "__main__":
    validate()
