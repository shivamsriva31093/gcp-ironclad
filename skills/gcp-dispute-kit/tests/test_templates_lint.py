import json

import pytest

from conftest import TEMPLATES, run_script

DISCLAIMER = "> **Note:** This is a template prepared from your own billing data. It is not legal advice."
US_BANNER = "> **Status: NOT FIELD-VALIDATED**"

VOCAB = json.loads((TEMPLATES / "placeholders.json").read_text())["placeholders"]
ALL_TEMPLATES = sorted(TEMPLATES.glob("**/*.template.md"))


def test_templates_exist():
    assert len(ALL_TEMPLATES) == 8  # evidence-summary, packet-README, 2 google, 3 india, 1 us


@pytest.mark.parametrize("tpl", ALL_TEMPLATES, ids=lambda p: str(p.relative_to(TEMPLATES)))
def test_every_placeholder_is_in_vocabulary(tpl):
    r = run_script("render.py", "--template", str(tpl), "--list")
    assert r.returncode == 0
    unknown = [p for p in r.stdout.split() if p not in VOCAB]
    assert not unknown, f"{tpl.name}: placeholders missing from placeholders.json: {unknown}"


@pytest.mark.parametrize("tpl", ALL_TEMPLATES, ids=lambda p: str(p.relative_to(TEMPLATES)))
def test_disclaimer_present(tpl):
    assert DISCLAIMER in tpl.read_text(), f"{tpl.name} missing disclaimer line"


def test_us_templates_carry_not_field_validated_banner():
    for tpl in sorted((TEMPLATES / "us").glob("*.template.md")):
        assert US_BANNER in tpl.read_text(), f"{tpl.name} missing NOT-FIELD-VALIDATED banner"


def test_no_dead_vocabulary_entries():
    used = set()
    for tpl in ALL_TEMPLATES:
        r = run_script("render.py", "--template", str(tpl), "--list")
        used.update(r.stdout.split())
    dead = sorted(set(VOCAB) - used)
    assert not dead, f"placeholders.json entries used by no template: {dead}"


LETTER_DIRS = ("google", "india", "us")
FORM_LIMIT_CHARS = 6000  # conservative bound for support/complaint form text fields


@pytest.mark.parametrize(
    "tpl",
    [t for t in ALL_TEMPLATES if t.parent.name in LETTER_DIRS],
    ids=lambda p: str(p.relative_to(TEMPLATES)),
)
def test_letters_fit_support_form_limits(tpl):
    # Rendered length ≈ template length + value expansion; keep raw templates
    # comfortably under the bound so filled letters stay paste-ready.
    assert len(tpl.read_text()) < FORM_LIMIT_CHARS, (
        f"{tpl.name} exceeds {FORM_LIMIT_CHARS} chars — no longer paste-ready for form fields"
    )
