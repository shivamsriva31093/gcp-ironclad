import pytest
from gcp_finops_mcp.config import Config
from gcp_finops_mcp.tools.llm_costs import (
    format_user_costs,
    format_provider_costs,
    get_per_user_llm_costs,
    get_provider_costs,
)


def test_format_user_costs_empty():
    result = format_user_costs([])
    assert "No LLM cost data" in result


def test_format_user_costs_with_data():
    rows = [
        {"user_id": "user-abc-12345", "total_cost": 2.50, "total_requests": 150, "total_input_tokens": 500000, "total_output_tokens": 100000},
        {"user_id": "user-def-67890", "total_cost": 1.20, "total_requests": 80, "total_input_tokens": 200000, "total_output_tokens": 50000},
    ]
    result = format_user_costs(rows)
    assert "user-abc-123" in result
    assert "2.50" in result
    assert "150" in result
    assert "500,000" in result


def test_format_provider_costs_empty():
    result = format_provider_costs([])
    assert "No provider cost data" in result


def test_format_provider_costs_with_data():
    rows = [
        {"provider": "google", "model": "gemini-2.5-flash", "total_cost": 5.00, "total_requests": 200, "total_input_tokens": 500000, "total_output_tokens": 100000},
        {"provider": "openai", "model": "gpt-4o", "total_cost": 1.50, "total_requests": 300, "total_input_tokens": 800000, "total_output_tokens": 200000},
    ]
    result = format_provider_costs(rows)
    assert "google" in result
    assert "gemini-2.5-flash" in result
    assert "5.00" in result
    assert "500,000" in result


@pytest.mark.asyncio
async def test_get_per_user_llm_costs_no_db_url():
    config = Config(
        gcp_project_id="test",
        bq_billing_dataset="test",
        bq_billing_table="test",
        llm_usage_db_url=None,
    )
    result = await get_per_user_llm_costs(config, "2026-03-01", "2026-03-03")
    assert "Database Not Configured" in result


@pytest.mark.asyncio
async def test_get_provider_costs_no_db_url():
    config = Config(
        gcp_project_id="test",
        bq_billing_dataset="test",
        bq_billing_table="test",
        llm_usage_db_url=None,
    )
    result = await get_provider_costs(config, "2026-03-01", "2026-03-03")
    assert "Database Not Configured" in result
