#!/usr/bin/env python3
"""Compute the fraud signature from a normalized billing CSV
(usage_start_time,service,sku,cost,currency). READ-ONLY math, no cloud calls.

Stdlib-only; Python >= 3.11.
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def _parse_ts(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_date_or_ts(s: str) -> datetime:
    if "T" in s:
        return _parse_ts(s)
    return datetime.fromisoformat(s + "T00:00:00+00:00")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--baseline-start", required=True)
    ap.add_argument("--baseline-end", required=True)
    ap.add_argument("--incident-start", required=True)
    ap.add_argument("--incident-end", required=True)
    args = ap.parse_args()

    b_start = _parse_date_or_ts(args.baseline_start)
    b_end = _parse_date_or_ts(args.baseline_end)
    i_start = _parse_date_or_ts(args.incident_start)
    i_end = _parse_date_or_ts(args.incident_end)

    daily = defaultdict(float)          # baseline: date -> cost
    hourly = defaultdict(float)         # incident: hour-ts -> cost
    sku_cost = defaultdict(float)       # incident: sku -> cost
    services, currencies = set(), set()
    baseline_currencies = set()
    incident_total = 0.0

    with Path(args.csv).open() as f:
        for row in csv.DictReader(f):
            ts = _parse_ts(row["usage_start_time"])
            cost = float(row["cost"])
            if b_start <= ts < b_end:
                daily[ts.date().isoformat()] += cost
                baseline_currencies.add(row["currency"])
            if i_start <= ts < i_end:
                incident_total += cost
                hour = ts.replace(minute=0, second=0, microsecond=0)
                hourly[hour.strftime("%Y-%m-%dT%H:%M:%SZ")] += cost
                sku_cost[row["sku"]] += cost
                services.add(row["service"])
                currencies.add(row["currency"])

    if not daily:
        print("no rows in baseline window", file=sys.stderr)
        return 2
    if not hourly:
        print("no rows in incident window", file=sys.stderr)
        return 2

    all_currencies = currencies | baseline_currencies
    if len(all_currencies) > 1:
        print(
            "multiple currencies present in scope "
            f"({', '.join(sorted(all_currencies))}); normalize the billing "
            "CSV to a single currency before analysis",
            file=sys.stderr,
        )
        return 2

    baseline_median = statistics.median(daily.values())
    incident_hours = (i_end - i_start).total_seconds() / 3600
    peak_hour, peak_cost = max(hourly.items(), key=lambda kv: kv[1])
    top = sorted(sku_cost.items(), key=lambda kv: -kv[1])[:10]

    print(json.dumps({
        "baselineDailyMedian": round(baseline_median, 2),
        "baselineDays": len(daily),
        "incidentTotal": round(incident_total, 2),
        "incidentHours": incident_hours,
        "peakHourlyCost": round(peak_cost, 2),
        "peakHour": peak_hour,
        "multiplierDailyRate": round((incident_total / incident_hours * 24) / baseline_median, 4),
        "distinctSkusIncident": len(sku_cost),
        "distinctServicesIncident": len(services),
        "topSkus": [{"sku": s, "cost": round(c, 2)} for s, c in top],
        "currency": sorted(currencies)[0] if currencies else "UNKNOWN",
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
