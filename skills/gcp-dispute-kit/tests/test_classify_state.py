import json

import pytest

from conftest import run_script

G = "templates/google/console-dispute.template.md"
GE = "templates/google/escalation-reply.template.md"
IN_ALL = [
    "templates/india/bank-chargeback.template.md",
    "templates/india/nch-complaint.template.md",
    "templates/india/cert-in-report.template.md",
]
US_FTC = "templates/us/ftc-complaint.template.md"

CASES = [
    # (activeSpike, disputeFiled, jurisdictions, state, letters, handoff)
    (True, False, ["IN"], "BLEEDING", [], "checklists/emergency-stop.md"),
    (True, True, ["IN", "US"], "BLEEDING", [], "checklists/emergency-stop.md"),
    (False, False, [], "FRESH", [G], None),
    (False, False, ["IN"], "FRESH", [G], None),
    (False, True, [], "STUCK", [GE], None),
    (False, True, ["IN"], "STUCK", [GE, *IN_ALL], None),
    (False, True, ["US"], "STUCK", [GE, US_FTC], None),
    (False, True, ["IN", "US"], "STUCK", [GE, *IN_ALL, US_FTC], None),
]


@pytest.mark.parametrize("spike,filed,jur,state,letters,handoff", CASES)
def test_classification_table(tmp_path, spike, filed, jur, state, letters, handoff):
    intake = tmp_path / "intake.json"
    intake.write_text(json.dumps(
        {"activeSpike": spike, "disputeFiled": filed, "jurisdictions": jur}
    ))
    r = run_script("classify_state.py", "--intake", str(intake))
    assert r.returncode == 0, r.stderr
    got = json.loads(r.stdout)
    assert got["state"] == state
    assert got["letters"] == letters
    assert got["handoff"] == handoff


def test_missing_field_is_error(tmp_path):
    intake = tmp_path / "intake.json"
    intake.write_text(json.dumps({"activeSpike": False}))
    r = run_script("classify_state.py", "--intake", str(intake))
    assert r.returncode == 2
    assert "disputeFiled" in r.stderr


def test_unknown_jurisdiction_is_error(tmp_path):
    intake = tmp_path / "intake.json"
    intake.write_text(json.dumps(
        {"activeSpike": False, "disputeFiled": True, "jurisdictions": ["EU"]}
    ))
    r = run_script("classify_state.py", "--intake", str(intake))
    assert r.returncode == 2
    assert "EU" in r.stderr
