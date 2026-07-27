#!/usr/bin/env python3
"""Deterministically generate synthetic_billing.csv, modeled on the shape in
docs/incident-story.md: a steady $1,400/day baseline for 30 days, then an
8-hour multi-model image-generation spike totaling $80,000 with a $20,000
peak hour. No randomness — the file is committed; this exists to regenerate."""
from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).parent / "synthetic_billing.csv"

BASELINE_SKU = "Gemini 2.5 Flash — text output tokens"
SERVICE = "generativelanguage.googleapis.com"
SPIKE = [  # (hour, sku, cost) — 8 distinct SKUs, total 80_000, peak 20_000
    ("2026-05-24T00:00:00Z", "Gemini 2.5 Pro — image output", 5000.0),
    ("2026-05-24T01:00:00Z", "Gemini 2.5 Flash — image output", 8000.0),
    ("2026-05-24T02:00:00Z", "Gemini 3 Pro — image output", 20000.0),
    ("2026-05-24T03:00:00Z", "Gemini 3 Flash — image output", 15000.0),
    ("2026-05-24T04:00:00Z", "Gemini 3.1 Pro — image output", 12000.0),
    ("2026-05-24T05:00:00Z", "Gemini 3.1 Flash — image output", 10000.0),
    ("2026-05-24T06:00:00Z", "Gemini 2.5 Flash-Lite — image output", 6000.0),
    ("2026-05-24T07:00:00Z", "Gemini 3 Flash-Lite — image output", 4000.0),
]


def main() -> None:
    rows = []
    day = date(2026, 4, 24)
    for _ in range(30):  # 30 baseline days, 4 rows/day x 350.0 = 1400.0/day
        for hh in ("00", "06", "12", "18"):
            rows.append((f"{day.isoformat()}T{hh}:00:00Z", SERVICE, BASELINE_SKU, 350.0, "USD"))
        day += timedelta(days=1)
    for hour, sku, cost in SPIKE:
        rows.append((hour, SERVICE, sku, cost, "USD"))

    with OUT.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["usage_start_time", "service", "sku", "cost", "currency"])
        w.writerows(rows)


if __name__ == "__main__":
    main()
