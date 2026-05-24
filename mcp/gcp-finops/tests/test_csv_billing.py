import pytest
from gcp_finops_mcp.config import Config
from gcp_finops_mcp.tools.csv_billing import (
    _parse_float,
    _parse_csv,
    format_csv_cost_summary,
    format_csv_sku_breakdown,
    load_billing_csv,
    get_csv_sku_breakdown,
)


@pytest.fixture
def config():
    return Config(
        gcp_project_id="test-project",
        bq_billing_dataset="billing_export",
        bq_billing_table=None,
        llm_usage_db_url=None,
    )


def _write_csv(tmp_path, content: str, filename: str = "billing.csv") -> str:
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return str(p)


VALID_CSV = (
    "Service description,SKU description,Cost ($)\n"
    "Cloud Run,CPU Allocation Time,5.50\n"
    "Cloud Run,Memory Allocation Time,2.30\n"
    "Vertex AI,Gemini 2.5 Flash Input,8.00\n"
    "Vertex AI,Gemini 2.5 Flash Output,3.20\n"
    "Cloud Storage,Standard Storage,1.00\n"
)


# --- _parse_float tests ---


def test_parse_float_normal():
    assert _parse_float("12.50") == 12.50


def test_parse_float_with_commas():
    assert _parse_float("1,234.56") == 1234.56


def test_parse_float_empty():
    assert _parse_float("") == 0.0
    assert _parse_float("  ") == 0.0


def test_parse_float_invalid():
    assert _parse_float("N/A") == 0.0


# --- _parse_csv tests ---


def test_parse_csv_success(tmp_path):
    path = _write_csv(tmp_path, VALID_CSV)
    rows, columns = _parse_csv(path)
    assert len(rows) == 5
    assert "Service description" in columns
    assert "SKU description" in columns
    assert "Cost ($)" in columns


def test_parse_csv_file_not_found():
    with pytest.raises(FileNotFoundError):
        _parse_csv("/nonexistent/path/billing.csv")


def test_parse_csv_missing_columns(tmp_path):
    bad_csv = "Name,Amount\nFoo,10\n"
    path = _write_csv(tmp_path, bad_csv)
    with pytest.raises(ValueError, match="missing required columns"):
        _parse_csv(path)


def test_parse_csv_with_bom(tmp_path):
    bom_csv = "\ufeff" + VALID_CSV
    path = _write_csv(tmp_path, bom_csv)
    rows, columns = _parse_csv(path)
    assert len(rows) == 5
    assert "Service description" in columns


# --- format_csv_cost_summary tests ---


def test_format_csv_cost_summary(tmp_path):
    path = _write_csv(tmp_path, VALID_CSV)
    rows, _ = _parse_csv(path)
    result = format_csv_cost_summary(rows)
    assert "Vertex AI" in result
    assert "Cloud Run" in result
    assert "Cloud Storage" in result
    assert "20.00" in result  # total


def test_format_csv_cost_summary_empty():
    result = format_csv_cost_summary([])
    assert "No data" in result


# --- format_csv_sku_breakdown tests ---


def test_format_csv_sku_breakdown_filtered(tmp_path):
    path = _write_csv(tmp_path, VALID_CSV)
    rows, _ = _parse_csv(path)
    result = format_csv_sku_breakdown(rows, "Vertex AI")
    assert "Gemini 2.5 Flash Input" in result
    assert "Gemini 2.5 Flash Output" in result
    assert "Cloud Run" not in result
    assert "11.20" in result  # total for Vertex AI


def test_format_csv_sku_breakdown_case_insensitive(tmp_path):
    path = _write_csv(tmp_path, VALID_CSV)
    rows, _ = _parse_csv(path)
    result = format_csv_sku_breakdown(rows, "vertex ai")
    assert "Gemini 2.5 Flash Input" in result


def test_format_csv_sku_breakdown_service_not_found(tmp_path):
    path = _write_csv(tmp_path, VALID_CSV)
    rows, _ = _parse_csv(path)
    result = format_csv_sku_breakdown(rows, "BigQuery")
    assert "No data found" in result
    assert "Available services" in result
    assert "Cloud Run" in result


def test_format_csv_sku_breakdown_empty():
    result = format_csv_sku_breakdown([], "Vertex AI")
    assert "No data" in result


# --- End-to-end tool tests ---


def test_load_billing_csv_success(tmp_path, config):
    path = _write_csv(tmp_path, VALID_CSV)
    result = load_billing_csv(config, path)
    assert "Cost Summary" in result
    assert "Vertex AI" in result


def test_load_billing_csv_file_not_found(config):
    result = load_billing_csv(config, "/nonexistent/billing.csv")
    assert "File Not Found" in result
    assert "GCP Console" in result


def test_load_billing_csv_invalid_format(tmp_path, config):
    path = _write_csv(tmp_path, "Name,Amount\nFoo,10\n")
    result = load_billing_csv(config, path)
    assert "Invalid CSV Format" in result


def test_get_csv_sku_breakdown_success(tmp_path, config):
    path = _write_csv(tmp_path, VALID_CSV)
    result = get_csv_sku_breakdown(config, path, "Cloud Run")
    assert "CPU Allocation Time" in result
    assert "Memory Allocation Time" in result
