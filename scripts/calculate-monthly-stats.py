#!/usr/bin/env python3
"""
calculate-monthly-stats.py
Computes monthly aggregates and YoY deltas from failure-rates.json, mttf.json,
and historical baselines. Writes monthly-summary.json for the report-generator.
Called as a command phase in the monthly-report workflow.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict

FAILURE_RATES_PATH = "data/metrics/failure-rates.json"
MTTF_PATH = "data/metrics/mttf.json"
AGGREGATIONS_PATH = "data/metrics/aggregations.json"
BASELINES_PATH = "data/baselines/historical.json"
MONTHLY_SUMMARY_PATH = "data/metrics/monthly-summary.json"


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r") as f:
        return json.load(f)


def get_period(months_offset=0):
    """Return YYYY-MM for current month offset by N months."""
    now = datetime.utcnow()
    target = now - timedelta(days=months_offset * 30)
    return target.strftime("%Y-%m")


def yoy_delta(current, prior_year):
    """Compute YoY percentage change. Returns None if prior is missing/zero."""
    if prior_year is None or prior_year == 0:
        return None
    return round((current - prior_year) / prior_year * 100, 1)


def calculate():
    failure_rates = load_json(FAILURE_RATES_PATH, default=[])
    mttf_data = load_json(MTTF_PATH, default=[])
    aggregations = load_json(AGGREGATIONS_PATH, default={})
    historical = load_json(BASELINES_PATH, default=[])

    current_period = get_period(0)
    prior_month_period = get_period(1)
    yoy_period = get_period(12)

    # --- Index historical baselines by period for quick lookup ---
    baseline_by_period = defaultdict(list)
    for entry in historical:
        baseline_by_period[entry.get("period", "")].append(entry)

    # --- Total claims this month vs prior month vs YoY ---
    current_total = sum(e.get("total_claims", 0) for e in failure_rates)
    prior_month_total = sum(e.get("total_claims", 0) for e in baseline_by_period[prior_month_period])
    yoy_total = sum(e.get("total_claims", 0) for e in baseline_by_period[yoy_period])

    mom_delta = yoy_delta(current_total, prior_month_total)
    yoy_delta_claims = yoy_delta(current_total, yoy_total)

    # --- Total warranty cost ---
    current_cost = sum(
        (e.get("total_repair_cost") or (e.get("avg_repair_cost", 0) * e.get("total_claims", 0)))
        for e in failure_rates
    )
    prior_cost = sum(
        (e.get("avg_repair_cost", 0) * e.get("total_claims", 0))
        for e in baseline_by_period[prior_month_period]
    )
    yoy_cost = sum(
        (e.get("avg_repair_cost", 0) * e.get("total_claims", 0))
        for e in baseline_by_period[yoy_period]
    )

    # --- Top 10 parts by claim volume ---
    part_counts = defaultdict(lambda: {"claims": 0, "cost": 0.0})
    for entry in failure_rates:
        pn = entry.get("part_number", "UNKNOWN")
        part_counts[pn]["claims"] += entry.get("total_claims", 0)
        part_counts[pn]["cost"] += entry.get("avg_repair_cost", 0) * entry.get("total_claims", 0)

    top_parts_by_volume = sorted(
        [{"part_number": k, **v} for k, v in part_counts.items()],
        key=lambda x: x["claims"],
        reverse=True
    )[:10]

    # Attach YoY delta for each top part
    for part_entry in top_parts_by_volume:
        pn = part_entry["part_number"]
        prior_year_claims = sum(
            e.get("total_claims", 0)
            for e in baseline_by_period[yoy_period]
            if e.get("part_number") == pn
        )
        part_entry["yoy_delta_pct"] = yoy_delta(part_entry["claims"], prior_year_claims)

    # --- Top 10 suppliers by total cost ---
    supplier_costs = defaultdict(lambda: {"cost": 0.0, "claims": 0})
    for entry in failure_rates:
        sid = entry.get("supplier_id", "UNKNOWN")
        supplier_costs[sid]["cost"] += entry.get("avg_repair_cost", 0) * entry.get("total_claims", 0)
        supplier_costs[sid]["claims"] += entry.get("total_claims", 0)

    top_suppliers_by_cost = sorted(
        [{"supplier_id": k, **v} for k, v in supplier_costs.items()],
        key=lambda x: x["cost"],
        reverse=True
    )[:10]

    # --- MTTF summary ---
    high_concern_parts = [
        {
            "part_number": e.get("part_number"),
            "supplier_id": e.get("supplier_id"),
            "mttf_miles": e.get("mttf_miles"),
        }
        for e in mttf_data
        if e.get("mttf_miles") and e.get("mttf_miles") < 30000
    ]

    # --- 3-month cost projection (linear trend) ---
    cost_trend_slope = 0.0
    if prior_cost > 0:
        cost_trend_slope = current_cost - prior_cost
    projected_3mo = round(current_cost * 3 + cost_trend_slope * 3, 2)

    # --- Monthly claim trend (last 12 months from baselines) ---
    monthly_trend = []
    for offset in range(11, -1, -1):
        p = get_period(offset)
        period_entries = baseline_by_period[p]
        monthly_trend.append({
            "period": p,
            "total_claims": sum(e.get("total_claims", 0) for e in period_entries),
            "total_cost": round(sum(
                e.get("avg_repair_cost", 0) * e.get("total_claims", 0)
                for e in period_entries
            ), 2)
        })

    # Override current month with fresh data
    if monthly_trend:
        monthly_trend[-1]["total_claims"] = current_total
        monthly_trend[-1]["total_cost"] = round(current_cost, 2)

    summary = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "reporting_period": current_period,
        "claims_summary": {
            "current_month": current_total,
            "prior_month": prior_month_total,
            "same_month_last_year": yoy_total,
            "mom_delta_pct": mom_delta,
            "yoy_delta_pct": yoy_delta_claims,
        },
        "cost_summary": {
            "current_month_usd": round(current_cost, 2),
            "prior_month_usd": round(prior_cost, 2),
            "same_month_last_year_usd": round(yoy_cost, 2),
            "mom_cost_delta_pct": yoy_delta(current_cost, prior_cost),
            "yoy_cost_delta_pct": yoy_delta(current_cost, yoy_cost),
            "projected_next_3mo_usd": projected_3mo,
        },
        "top_parts_by_volume": top_parts_by_volume,
        "top_suppliers_by_cost": top_suppliers_by_cost,
        "high_concern_parts_mttf": high_concern_parts,
        "monthly_claim_trend_12mo": monthly_trend,
    }

    os.makedirs(os.path.dirname(MONTHLY_SUMMARY_PATH), exist_ok=True)
    with open(MONTHLY_SUMMARY_PATH, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Monthly stats computed: period={current_period}")
    print(f"  Total claims this month: {current_total} (MoM: {mom_delta}%, YoY: {yoy_delta_claims}%)")
    print(f"  Total warranty cost: ${current_cost:,.2f}")
    print(f"  High-concern parts (MTTF < 30k miles): {len(high_concern_parts)}")
    print(f"  Projected 3-month cost: ${projected_3mo:,.2f}")
    print(f"Wrote {MONTHLY_SUMMARY_PATH}")


if __name__ == "__main__":
    calculate()
