"""Shared paths + helpers for gcp-dispute-kit tests. Scripts are exercised
via subprocess so the CLI contract (exit codes, stdout JSON) is what's tested."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_DIR / "scripts"
TEMPLATES = SKILL_DIR / "templates"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def run_script(name: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *args],
        capture_output=True,
        text=True,
    )
