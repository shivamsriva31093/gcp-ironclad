import pytest
from gcp_finops_mcp.config import Config
from gcp_finops_mcp.tools.discovery import format_discovered_tables


@pytest.fixture
def config():
    return Config(
        gcp_project_id="test-project",
        bq_billing_dataset="billing_export",
        bq_billing_table=None,
        llm_usage_db_url=None,
    )


def test_empty_dataset(config):
    result = format_discovered_tables([], config)
    assert "No Tables Found" in result
    assert "24-48 hours" in result
    assert "load_billing_csv" in result


def test_billing_table_found(config):
    tables = [
        {
            "table_id": "gcp_billing_export_v1_01A2B3_C4D5E6",
            "created": "2026-03-01 10:00 UTC",
            "num_rows": 15000,
            "size_mb": 12.5,
            "is_billing_export": True,
        },
    ]
    result = format_discovered_tables(tables, config)
    assert "gcp_billing_export_v1_01A2B3_C4D5E6" in result
    assert "15,000" in result
    assert "Suggested `BQ_BILLING_TABLE`" in result


def test_wrong_table_configured():
    cfg = Config(
        gcp_project_id="test-project",
        bq_billing_dataset="billing_export",
        bq_billing_table="gcp_billing_export_v1",
        llm_usage_db_url=None,
    )
    tables = [
        {
            "table_id": "gcp_billing_export_v1_01A2B3_C4D5E6",
            "created": "2026-03-01 10:00 UTC",
            "num_rows": 5000,
            "size_mb": 4.0,
            "is_billing_export": True,
        },
    ]
    result = format_discovered_tables(tables, cfg)
    assert "Mismatch" in result
    assert "gcp_billing_export_v1_01A2B3_C4D5E6" in result
    assert "gcp_billing_export_v1" in result


def test_zero_rows_warning(config):
    tables = [
        {
            "table_id": "gcp_billing_export_v1_01A2B3_C4D5E6",
            "created": "2026-03-01 10:00 UTC",
            "num_rows": 0,
            "size_mb": 0.0,
            "is_billing_export": True,
        },
    ]
    result = format_discovered_tables(tables, config)
    assert "0 rows" in result
    assert "load_billing_csv" in result


def test_mixed_tables(config):
    tables = [
        {
            "table_id": "gcp_billing_export_v1_01A2B3_C4D5E6",
            "created": "2026-03-01 10:00 UTC",
            "num_rows": 8000,
            "size_mb": 6.0,
            "is_billing_export": True,
        },
        {
            "table_id": "custom_analysis",
            "created": "2026-02-15 08:00 UTC",
            "num_rows": 200,
            "size_mb": 0.1,
            "is_billing_export": False,
        },
    ]
    result = format_discovered_tables(tables, config)
    assert "gcp_billing_export_v1_01A2B3_C4D5E6" in result
    assert "custom_analysis" in result
    assert "Suggested `BQ_BILLING_TABLE`" in result
