import json

from conftest import run_script


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content)
    return p


def test_renders_all_placeholders(tmp_path):
    tpl = _write(tmp_path, "t.md", "Dear {{name}}, you are owed {{amount}}.\n")
    vals = _write(tmp_path, "v.json", json.dumps({"name": "Asha", "amount": "₹1,00,000"}))
    out = tmp_path / "out.md"
    r = run_script("render.py", "--template", str(tpl), "--values", str(vals), "--out", str(out))
    assert r.returncode == 0, r.stderr
    assert out.read_text() == "Dear Asha, you are owed ₹1,00,000.\n"


def test_unresolved_placeholder_is_hard_error(tmp_path):
    tpl = _write(tmp_path, "t.md", "Hello {{name}}, case {{case_number}}.\n")
    vals = _write(tmp_path, "v.json", json.dumps({"name": "Asha"}))
    out = tmp_path / "out.md"
    r = run_script("render.py", "--template", str(tpl), "--values", str(vals), "--out", str(out))
    assert r.returncode == 1
    assert "case_number" in r.stderr
    assert not out.exists()


def test_multiline_value_and_numeric_value(tmp_path):
    tpl = _write(tmp_path, "t.md", "Summary:\n{{summary}}\nCount: {{count}}\n")
    vals = _write(tmp_path, "v.json", json.dumps({"summary": "line1\nline2", "count": 8}))
    out = tmp_path / "out.md"
    r = run_script("render.py", "--template", str(tpl), "--values", str(vals), "--out", str(out))
    assert r.returncode == 0, r.stderr
    assert "line1\nline2" in out.read_text()
    assert "Count: 8" in out.read_text()


def test_list_mode_prints_placeholders(tmp_path):
    tpl = _write(tmp_path, "t.md", "{{alpha}} then {{beta}} then {{alpha}}\n")
    r = run_script("render.py", "--template", str(tpl), "--list")
    assert r.returncode == 0
    assert r.stdout.split() == ["alpha", "beta"]


def test_malformed_placeholder_is_hard_error(tmp_path):
    tpl = _write(tmp_path, "t.md", "Hello {{name}}, ref {{CaseNumber}}.\n")
    vals = _write(tmp_path, "v.json", json.dumps({"name": "Asha"}))
    out = tmp_path / "out.md"
    r = run_script("render.py", "--template", str(tpl), "--values", str(vals), "--out", str(out))
    assert r.returncode == 1
    assert "CaseNumber" in r.stderr
    assert not out.exists()
