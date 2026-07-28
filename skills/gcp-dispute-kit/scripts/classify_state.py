#!/usr/bin/env python3
"""Classify a dispute-kit intake into BLEEDING / FRESH / STUCK and select
the letter templates to emit. BLEEDING never proceeds to evidence work —
the only output is the emergency-stop handoff.

Stdlib-only; Python >= 3.11.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

GOOGLE_FRESH = "templates/google/console-dispute.template.md"
GOOGLE_STUCK = "templates/google/escalation-reply.template.md"
INDIA = [
    "templates/india/bank-chargeback.template.md",
    "templates/india/nch-complaint.template.md",
    "templates/india/cert-in-report.template.md",
]
US = ["templates/us/ftc-complaint.template.md"]
KNOWN_JURISDICTIONS = {"IN", "US"}


def classify(intake: dict) -> dict:
    for field in ("activeSpike", "disputeFiled", "jurisdictions"):
        if field not in intake:
            raise ValueError(f"intake missing required field: {field}")
    unknown = set(intake["jurisdictions"]) - KNOWN_JURISDICTIONS
    if unknown:
        raise ValueError(f"unknown jurisdictions: {sorted(unknown)}")

    if intake["activeSpike"]:
        return {"state": "BLEEDING", "letters": [], "handoff": "checklists/emergency-stop.md"}

    if not intake["disputeFiled"]:
        letters = [GOOGLE_FRESH]
        # The India card-chargeback window runs from the statement date, not
        # from Google's reply — FRESH must not sit on that clock.
        if "IN" in intake["jurisdictions"]:
            letters.append(INDIA[0])
        return {"state": "FRESH", "letters": letters, "handoff": None}

    letters = [GOOGLE_STUCK]
    if "IN" in intake["jurisdictions"]:
        letters += INDIA
    if "US" in intake["jurisdictions"]:
        letters += US
    return {"state": "STUCK", "letters": letters, "handoff": None}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--intake", required=True)
    args = ap.parse_args()
    try:
        intake = json.loads(Path(args.intake).read_text())
        result = classify(intake)
    except (ValueError, json.JSONDecodeError, OSError) as e:
        print(str(e), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
