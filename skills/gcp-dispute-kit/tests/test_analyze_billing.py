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


def test_multi_currency_in_scope_is_error(tmp_path):
    # Baseline row is USD, incident rows are INR: two distinct currencies
    # across baseline + incident windows must be rejected rather than summed
    # together and reported under an arbitrarily-chosen currency label.
    csv_path = tmp_path / "mixed_currency.csv"
    csv_path.write_text(
        "usage_start_time,service,sku,cost,currency\n"
        "2026-04-24T00:00:00Z,generativelanguage.googleapis.com,Gemini Flash,100.0,USD\n"
        "2026-05-24T01:00:00Z,generativelanguage.googleapis.com,Gemini Flash,500.0,INR\n"
        "2026-05-24T02:00:00Z,generativelanguage.googleapis.com,Gemini Flash,600.0,INR\n"
    )
    r = run_script(
        "analyze_billing.py", "--csv", str(csv_path),
        "--baseline-start", "2026-04-24", "--baseline-end", "2026-05-24",
        "--incident-start", "2026-05-24T00:00:00Z", "--incident-end", "2026-05-24T08:00:00Z",
    )
    assert r.returncode == 2
    assert "currenc" in r.stderr.lower()
