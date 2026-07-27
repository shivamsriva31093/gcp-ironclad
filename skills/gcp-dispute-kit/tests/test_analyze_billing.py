import json

import pytest

from conftest import FIXTURES, run_script

CSV = str(FIXTURES / "synthetic_billing.csv")
ARGS = [
    "--csv", CSV,
    "--baseline-start", "2026-04-24",
    "--baseline-end", "2026-05-24",
    "--incident-start", "2026-05-24T00:00:00Z",
    "--incident-end", "2026-05-24T08:00:00Z",
]


def _analysis():
    r = run_script("analyze_billing.py", *ARGS)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_baseline_median_and_days():
    a = _analysis()
    assert a["baselineDailyMedian"] == 1400.0
    assert a["baselineDays"] == 30


def test_incident_totals_and_peak():
    a = _analysis()
    assert a["incidentTotal"] == 80000.0
    assert a["incidentHours"] == 8.0
    assert a["peakHourlyCost"] == 20000.0
    assert a["peakHour"] == "2026-05-24T02:00:00Z"


def test_multiplier_is_daily_rate_over_baseline():
    a = _analysis()
    # (80000 / 8h * 24h) / 1400 = 171.428...
    assert a["multiplierDailyRate"] == pytest.approx(171.4286, abs=0.001)


def test_model_spray_fingerprint():
    a = _analysis()
    assert a["distinctSkusIncident"] == 8
    assert a["distinctServicesIncident"] == 1
    assert a["topSkus"][0] == {"sku": "Gemini 3 Pro — image output", "cost": 20000.0}
    assert a["currency"] == "USD"


def test_empty_incident_window_is_error():
    r = run_script(
        "analyze_billing.py", "--csv", CSV,
        "--baseline-start", "2026-04-24", "--baseline-end", "2026-05-24",
        "--incident-start", "2027-01-01T00:00:00Z", "--incident-end", "2027-01-02T00:00:00Z",
    )
    assert r.returncode == 2
    assert "incident" in r.stderr.lower()
