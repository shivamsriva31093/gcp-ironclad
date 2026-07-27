#!/usr/bin/env python3
"""Fill a {{placeholder}} template. Any placeholder left unresolved after
substitution is a HARD ERROR (exit 1, names on stderr) — a dispute letter
with {{...}} in it must never reach a victim's filing.

Stdlib-only; Python >= 3.11.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PLACEHOLDER = re.compile(r"\{\{([a-z0-9_]+)\}\}")
UNRESOLVED = re.compile(r"\{\{[^}]*\}\}")


def find_placeholders(text: str) -> list[str]:
    seen: dict[str, None] = {}
    for m in PLACEHOLDER.finditer(text):
        seen.setdefault(m.group(1))
    return list(seen)


def find_unresolved_spans(text: str) -> list[str]:
    seen: dict[str, None] = {}
    for m in UNRESOLVED.finditer(text):
        seen.setdefault(m.group(0))
    return list(seen)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True)
    ap.add_argument("--values")
    ap.add_argument("--out")
    ap.add_argument("--list", action="store_true", dest="list_only")
    args = ap.parse_args()

    text = Path(args.template).read_text()

    if args.list_only:
        for name in find_placeholders(text):
            print(name)
        return 0

    if not args.values or not args.out:
        print("--values and --out are required unless --list", file=sys.stderr)
        return 2

    values = json.loads(Path(args.values).read_text())
    rendered = PLACEHOLDER.sub(
        lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0),
        text,
    )

    unresolved = find_unresolved_spans(rendered)
    if unresolved:
        print("unresolved placeholders: " + ", ".join(unresolved), file=sys.stderr)
        return 1

    Path(args.out).write_text(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())
