import pytest
from gcp_finops_mcp.config import Config
from gcp_finops_mcp.tools.bigquery import (
    BillingDataNotReady,
    _BQ_NOT_CONFIGURED_MSG,
    build_cost_summary_query,
    format_cost_summary,
    get_cost_summary,
    build_sku_breakdown_query,
    format_sku_breakdown,
    build_cost_trend_query,
    format_cost_trend,
    build_anomaly_query,
    format_anomalies,
    build_compare_periods_query,
    format_period_comparison,
    build_vertex_ai_query,
    format_vertex_ai_costs,
)


@pytest.fixture
def config():
    return Config(
        gcp_project_id="test-project",
        bq_billing_dataset="test_billing",
        bq_billing_table="gcp_billing_export_v1_TEST",
        llm_usage_db_url=None,
    )


def test_build_cost_summary_query(config):
    query = build_cost_summary_query(config, "2026-03-01", "2026-03-03")
    assert "test-project.test_billing.gcp_billing_export_v1_TEST" in query
    assert "2026-03-01" in query
    assert "2026-03-03" in query
    assert "service.description" in query


def test_format_cost_summary_empty():
    result = format_cost_summary([])
    assert "No billing data" in result


def test_format_cost_summary_with_data():
    rows = [
        {"service_name": "Cloud Run", "net_cost": 12.50, "gross_cost": 15.00},
        {"service_name": "Vertex AI", "net_cost": 8.30, "gross_cost": 8.30},
    ]
    result = format_cost_summary(rows)
    assert "Cloud Run" in result
    assert "12.50" in result
    assert "Vertex AI" in result
    assert "20.80" in result  # total


def test_build_sku_breakdown_query(config):
    query = build_sku_breakdown_query(config, "Vertex AI", "2026-03-01", "2026-03-03")
    assert "Vertex AI" in query
    assert "sku.description" in query


def test_format_sku_breakdown_empty():
    result = format_sku_breakdown([], "Vertex AI")
    assert "No SKU data" in result
    assert "Vertex AI" in result


def test_format_sku_breakdown_with_data():
    rows = [
        {"sku_name": "Gemini 2.5 Flash Input", "cost": 5.20, "usage_amount": 10000000.0, "usage_unit": "count"},
        {"sku_name": "Gemini 2.5 Flash Output", "cost": 3.10, "usage_amount": 5000000.0, "usage_unit": "count"},
    ]
    result = format_sku_breakdown(rows, "Vertex AI")
    assert "Gemini 2.5 Flash Input" in result
    assert "5.20" in result


def test_build_cost_trend_query(config):
    query = build_cost_trend_query(config, lookback_days=14)
    assert "14" in query
    assert "service.description" in query


def test_format_cost_trend_empty():
    result = format_cost_trend([])
    assert "No trend data" in result


def test_format_cost_trend_with_data():
    rows = [
        {"day": "2026-03-01", "service_name": "Cloud Run", "net_cost": 4.50},
        {"day": "2026-03-01", "service_name": "Vertex AI", "net_cost": 3.20},
        {"day": "2026-03-02", "service_name": "Cloud Run", "net_cost": 5.10},
        {"day": "2026-03-02", "service_name": "Vertex AI", "net_cost": 2.80},
    ]
    result = format_cost_trend(rows)
    assert "2026-03-01" in result
    assert "Cloud Run" in result


def test_build_anomaly_query(config):
    query = build_anomaly_query(config, threshold_pct=30, lookback_days=30)
    assert "30" in query
    assert "avg_7d" in query


def test_format_anomalies_none_found():
    result = format_anomalies([])
    assert "No anomalies" in result


def test_format_anomalies_with_spikes():
    rows = [
        {"day": "2026-03-02", "daily_cost": 25.0, "avg_7d": 15.0, "pct_above_avg": 66.7},
    ]
    result = format_anomalies(rows)
    assert "2026-03-02" in result
    assert "66.7" in result


def test_build_compare_periods_query(config):
    query = build_compare_periods_query(
        config, "2026-02-01", "2026-02-28", "2026-03-01", "2026-03-03"
    )
    assert "2026-02-01" in query
    assert "period_a_cost" in query


def test_format_period_comparison_with_data():
    rows = [
        {"service_name": "Cloud Run", "period_a_cost": 100.0, "period_b_cost": 120.0},
        {"service_name": "Vertex AI", "period_a_cost": 50.0, "period_b_cost": 35.0},
    ]
    result = format_period_comparison(rows, "Feb", "Mar")
    assert "Cloud Run" in result
    assert "+20.0%" in result


def test_format_period_comparison_empty():
    result = format_period_comparison([], "A", "B")
    assert "No data" in result


def test_build_vertex_ai_query(config):
    query = build_vertex_ai_query(config, "2026-03-01", "2026-03-03")
    assert "Vertex AI" in query
    assert "sku.description" in query


def test_format_vertex_ai_costs_empty():
    result = format_vertex_ai_costs([])
    assert "No Vertex AI" in result


def test_format_vertex_ai_costs_with_data():
    rows = [
        {"sku_name": "Gemini 2.5 Flash Batch Input", "cost": 3.50, "usage_amount": 8000000.0, "usage_unit": "count"},
    ]
    result = format_vertex_ai_costs(rows)
    assert "Gemini" in result
    assert "3.50" in result


# --- Error handling tests ---


def test_billing_data_not_ready_message():
    err = BillingDataNotReady("example-project.billing_export.gcp_billing_export_v1")
    msg = str(err)
    assert "Billing Export Not Ready" in msg
    assert "gcp_billing_export_v1" in msg
    assert "48 hours" in msg


def test_billing_data_not_ready_with_detail():
    err = BillingDataNotReady("table_name", "404 Not Found")
    msg = str(err)
    assert "404 Not Found" in msg
    assert "table_name" in msg


# --- None table guard tests ---


def test_get_cost_summary_with_none_table():
    cfg = Config(
        gcp_project_id="test-project",
        bq_billing_dataset="test_billing",
        bq_billing_table=None,
        llm_usage_db_url=None,
    )
    result = get_cost_summary(cfg, "2026-03-01", "2026-03-03")
    assert result == _BQ_NOT_CONFIGURED_MSG
    assert "discover_billing_tables" in result
    assert "load_billing_csv" in result


def test_fully_qualified_table_returns_none_when_table_not_set():
    cfg = Config(
        gcp_project_id="test-project",
        bq_billing_dataset="test_billing",
        bq_billing_table=None,
        llm_usage_db_url=None,
    )
    assert cfg.fully_qualified_table is None
