import json

import jsonschema
import pytest

from conftest import FIXTURES, SKILL_DIR

SCHEMA = json.loads((SKILL_DIR / "output.schema.json").read_text())
SAMPLE = json.loads((FIXTURES / "manifest_sample.json").read_text())


def test_schema_is_valid_draft07():
    jsonschema.Draft7Validator.check_schema(SCHEMA)


def test_sample_manifest_validates():
    jsonschema.validate(SAMPLE, SCHEMA)


def test_bleeding_is_not_a_valid_manifest_state():
    bad = dict(SAMPLE, state="BLEEDING")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, SCHEMA)


def test_missing_gaps_is_invalid():
    bad = {k: v for k, v in SAMPLE.items() if k != "gaps"}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(bad, SCHEMA)
