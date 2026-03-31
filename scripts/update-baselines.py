#!/usr/bin/env python3
"""
update-baselines.py
Merges current period failure metrics into historical baselines.
Maintains a rolling 24-month window. Called as a command phase after calculate-metrics.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict

FAILURE_RATES_PATH = "data/metrics/failure-rates.json"
MTTF_PATH = "data/metrics/mttf.json"
BASELINES_PATH = "data/baselines/historical.json"

WINDOW_MONTHS = 24


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        return json.load(f)


def get_current_period():
    now = datetime.utcnow()
    return now.strftime("%Y-%m")


def cutoff_period(months_back):
    """Return the YYYY-MM string N months ago."""
    now = datetime.utcnow()
    # Subtract months by going back day by day won't work — use timedelta approximation
    target = now - timedelta(days=months_back * 30)
    return target.strftime("%Y-%m")


def update_baselines():
    failure_rates = load_json(FAILURE_RATES_PATH)
    mttf_data = load_json(MTTF_PATH)
    historical = load_json(BASELINES_PATH, default=[])

    if not isinstance(historical, list):
        print("WARN: historical.json was not a list, resetting.", file=sys.stderr)
        historical = []

    period = get_current_period()
    recorded_at = datetime.utcnow().isoformat() + "Z"
    cutoff = cutoff_period(WINDOW_MONTHS)

    # Remove existing entries for the current period (idempotent re-runs)
    historical = [e for e in historical if e.get("period") != period]

    new_entries = []

    # --- Process failure rates ---
    if failure_rates and isinstance(failure_rates, list):
        for entry in failure_rates:
            part_number = entry.get("part_number")
            supplier_id = entry.get("supplier_id")
            model_year = entry.get("model_year")
            if not (part_number and supplier_id):
                continue

            baseline_entry = {
                "period": period,
                "recorded_at": recorded_at,
                "part_number": part_number,
                "supplier_id": supplier_id,
                "model_year": model_year,
                "failure_rate_per_1000": entry.get("failure_rate_per_1000"),
                "total_claims": entry.get("total_claims"),
                "avg_repair_cost": entry.get("avg_repair_cost"),
                "cost_per_1000_vehicles": entry.get("cost_per_1000_vehicles"),
            }

            # Attach MTTF if available
            if mttf_data and isinstance(mttf_data, list):
                mttf_match = next(
                    (m for m in mttf_data
                     if m.get("part_number") == part_number and m.get("supplier_id") == supplier_id),
                    None
                )
                if mttf_match:
                    baseline_entry["mttf_miles"] = mttf_match.get("mttf_miles")
                    baseline_entry["mttf_months"] = mttf_match.get("mttf_months")

            new_entries.append(baseline_entry)

    elif failure_rates and isinstance(failure_rates, dict):
        # Handle dict-style failure rates (keyed by part_number or composite key)
        for key, entry in failure_rates.items():
            baseline_entry = {
                "period": period,
                "recorded_at": recorded_at,
                "key": key,
                **{k: v for k, v in entry.items() if k not in ("period", "recorded_at")}
            }
            new_entries.append(baseline_entry)

    historical.extend(new_entries)

    # --- Prune entries older than WINDOW_MONTHS ---
    historical = [e for e in historical if e.get("period", "9999-99") >= cutoff]

    # Sort by period descending
    historical.sort(key=lambda e: e.get("period", ""), reverse=True)

    os.makedirs(os.path.dirname(BASELINES_PATH), exist_ok=True)
    with open(BASELINES_PATH, "w") as f:
        json.dump(historical, f, indent=2)

    print(f"Updated baselines: period={period}, new_entries={len(new_entries)}, "
          f"total_entries={len(historical)}, window={WINDOW_MONTHS} months")
    print(f"Pruned entries older than {cutoff}")
    print(f"Wrote {BASELINES_PATH}")


if __name__ == "__main__":
    update_baselines()
