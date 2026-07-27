"""The spec's e2e requirement: the synthetic fixture drives a FRESH-state
packet run — classify → analyze → render every selected letter + README +
evidence summary → manifest validates. All via the same CLIs SKILL.md uses."""
import json

import jsonschema

from conftest import FIXTURES, SKILL_DIR, run_script

ANALYZE_ARGS = [
    "--csv", str(FIXTURES / "synthetic_billing.csv"),
    "--baseline-start", "2026-04-24", "--baseline-end", "2026-05-24",
    "--incident-start", "2026-05-24T00:00:00Z", "--incident-end", "2026-05-24T08:00:00Z",
]


def test_fresh_packet_run(tmp_path):
    # 1. classify
    r = run_script("classify_state.py", "--intake", str(FIXTURES / "intake_fresh.json"))
    assert r.returncode == 0, r.stderr
    classification = json.loads(r.stdout)
    assert classification["state"] == "FRESH"

    # 2. analyze
    r = run_script("analyze_billing.py", *ANALYZE_ARGS)
    assert r.returncode == 0, r.stderr
    analysis = json.loads(r.stdout)

    # 3. render every selected letter + README + evidence summary
    letters_dir = tmp_path / "letters"
    letters_dir.mkdir()
    to_render = classification["letters"] + [
        "templates/packet-README.template.md",
        "templates/evidence-summary.template.md",
    ]
    for rel in to_render:
        out = letters_dir / rel.split("/")[-1].replace(".template", "")
        r = run_script(
            "render.py", "--template", str(SKILL_DIR / rel),
            "--values", str(FIXTURES / "values_fresh.json"), "--out", str(out),
        )
        assert r.returncode == 0, f"{rel}: {r.stderr}"
        assert "{{" not in out.read_text(), f"{rel}: unresolved placeholder leaked"

    # 4. assemble a manifest from real computed values and validate it
    manifest = {
        "schemaVersion": 1,
        "generatedAt": "2026-07-26T12:00:00Z",
        "state": classification["state"],
        "jurisdictions": ["IN"],
        "amounts": {"disputed": analysis["incidentTotal"], "currencyCode": analysis["currency"]},
        "incidentWindow": {"start": "2026-05-24T00:00:00Z", "end": "2026-05-24T08:00:00Z"},
        "analysis": {
            "baselineDailyMedian": analysis["baselineDailyMedian"],
            "multiplierDailyRate": analysis["multiplierDailyRate"],
            "peakHourlyCost": analysis["peakHourlyCost"],
            "distinctSkusIncident": analysis["distinctSkusIncident"],
        },
        "sources": [{"type": "billing_csv", "available": True, "exhibits": ["EX-01"]}],
        "letters": [
            {"track": "google", "template": classification["letters"][0], "path": "letters/console-dispute.md"}
        ],
        "exhibits": [
            {"id": "EX-01", "file": "exhibits/EX-01-billing-normalized.csv", "producedBy": "test fixture"}
        ],
        "gaps": [],
    }
    schema = json.loads((SKILL_DIR / "output.schema.json").read_text())
    jsonschema.validate(manifest, schema)


def test_stuck_selects_escalation_letters_and_they_render(tmp_path):
    r = run_script("classify_state.py", "--intake", str(FIXTURES / "intake_stuck.json"))
    classification = json.loads(r.stdout)
    assert classification["state"] == "STUCK"
    assert len(classification["letters"]) == 5  # google escalation + 3 IN + 1 US
    for rel in classification["letters"]:
        out = tmp_path / rel.split("/")[-1].replace(".template", "")
        rr = run_script(
            "render.py", "--template", str(SKILL_DIR / rel),
            "--values", str(FIXTURES / "values_fresh.json"), "--out", str(out),
        )
        assert rr.returncode == 0, f"{rel}: {rr.stderr}"
