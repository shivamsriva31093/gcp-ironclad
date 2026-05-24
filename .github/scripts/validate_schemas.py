#!/usr/bin/env python3
"""Validate every skill's `output.schema.json` and `SKILL.md` frontmatter.

Runs in CI. Three checks:

  1. Every `skills/*/output.schema.json` parses as a valid Draft-07 JSON Schema.
  2. Every `skills/*/SKILL.md` has frontmatter declaring both `name:` and
     `description:`.
  3. The `name:` in each SKILL.md matches its directory name (so skill
     discovery in Claude Code does not silently break on a typo).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

REPO = Path(__file__).resolve().parents[2]
SKILLS_DIR = REPO / "skills"


def _frontmatter_lines(text: str) -> list[str]:
    """Return the YAML frontmatter lines (between leading `---` markers)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return []
    out = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        out.append(line)
    return out


def main() -> int:
    fail = False

    # 1. Validate JSON schemas.
    for schema_path in sorted(SKILLS_DIR.glob("*/output.schema.json")):
        rel = schema_path.relative_to(REPO)
        try:
            schema = json.loads(schema_path.read_text())
            jsonschema.Draft7Validator.check_schema(schema)
            print(f"OK   schema     {rel}")
        except Exception as e:
            print(f"FAIL schema     {rel}: {e}", file=sys.stderr)
            fail = True

    # 2. + 3. Frontmatter checks on every SKILL.md.
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        rel = skill_md.relative_to(REPO)
        skill_dir = skill_md.parent.name
        fm = _frontmatter_lines(skill_md.read_text())
        if not fm:
            print(f"FAIL frontmatter {rel}: missing leading '---' fence", file=sys.stderr)
            fail = True
            continue

        name = None
        description = None
        for line in fm:
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("description:"):
                description = line.split(":", 1)[1].strip()

        if name is None:
            print(f"FAIL frontmatter {rel}: missing 'name:'", file=sys.stderr)
            fail = True
            continue
        if not description:
            print(f"FAIL frontmatter {rel}: missing or empty 'description:'", file=sys.stderr)
            fail = True
            continue
        if name != skill_dir:
            print(
                f"FAIL frontmatter {rel}: name: {name!r} does not match "
                f"directory name {skill_dir!r}",
                file=sys.stderr,
            )
            fail = True
            continue

        print(f"OK   frontmatter {rel} (name={name})")

    if fail:
        print("\nValidation FAILED.", file=sys.stderr)
        return 1
    print("\nAll schemas + frontmatter OK.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
