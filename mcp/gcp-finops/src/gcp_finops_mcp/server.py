from mcp.server.fastmcp import FastMCP

from gcp_finops_mcp.config import Config
from gcp_finops_mcp.tools.bigquery import (
    get_cost_summary,
    get_sku_breakdown,
    get_cost_trend,
    detect_anomalies as _detect_anomalies,
    compare_periods as _compare_periods,
    get_vertex_ai_costs,
)
from gcp_finops_mcp.tools.recommender import get_recommendations
from gcp_finops_mcp.tools.budgets import get_budget_status
from gcp_finops_mcp.tools.llm_costs import get_per_user_llm_costs, get_provider_costs
from gcp_finops_mcp.tools.discovery import discover_billing_tables as _discover_billing_tables
from gcp_finops_mcp.tools.csv_billing import (
    load_billing_csv as _load_billing_csv,
    get_csv_sku_breakdown as _get_csv_sku_breakdown,
)

mcp = FastMCP("gcp-finops")
_config = None


def _get_config() -> Config:
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


@mcp.tool()
def cost_summary(start_date: str, end_date: str) -> str:
    """Get total GCP cost broken down by service for a date range.

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format

    Returns:
        Markdown table of costs by service, sorted by net cost descending.
    """
    return get_cost_summary(_get_config(), start_date, end_date)


@mcp.tool()
def sku_breakdown(service_name: str, start_date: str, end_date: str) -> str:
    """Get SKU-level cost breakdown for a specific GCP service.

    Args:
        service_name: Exact service name (e.g., "Vertex AI", "Cloud Run", "Cloud Storage")
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    """
    return get_sku_breakdown(_get_config(), service_name, start_date, end_date)


@mcp.tool()
def cost_trend(lookback_days: int = 14) -> str:
    """Get day-by-day cost trend showing top services per day.

    Args:
        lookback_days: Number of days to look back (default: 14)
    """
    return get_cost_trend(_get_config(), lookback_days)


@mcp.tool()
def anomalies(threshold_pct: int = 30, lookback_days: int = 30) -> str:
    """Detect cost anomalies — days where spending spiked above the 7-day rolling average.

    Args:
        threshold_pct: Percentage above average to flag (default: 30)
        lookback_days: Days to analyze (default: 30)
    """
    return _detect_anomalies(_get_config(), threshold_pct, lookback_days)


@mcp.tool()
def compare_costs(
    period_a_start: str,
    period_a_end: str,
    period_b_start: str,
    period_b_end: str,
    label_a: str = "Period A",
    label_b: str = "Period B",
) -> str:
    """Compare GCP costs between two date ranges, broken down by service.

    Args:
        period_a_start: First period start (YYYY-MM-DD)
        period_a_end: First period end (YYYY-MM-DD)
        period_b_start: Second period start (YYYY-MM-DD)
        period_b_end: Second period end (YYYY-MM-DD)
        label_a: Label for first period (default: "Period A")
        label_b: Label for second period (default: "Period B")
    """
    return _compare_periods(
        _get_config(), period_a_start, period_a_end, period_b_start, period_b_end, label_a, label_b
    )


@mcp.tool()
def vertex_ai_costs(start_date: str, end_date: str) -> str:
    """Get detailed Vertex AI cost breakdown by SKU (Gemini tokens, etc.).

    Args:
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    """
    return get_vertex_ai_costs(_get_config(), start_date, end_date)


# --- GCP Recommender ---


@mcp.tool()
def recommendations() -> str:
    """Get GCP cost optimization recommendations (idle resources, oversized instances, etc.)."""
    return get_recommendations(_get_config())


# --- Budget ---


@mcp.tool()
def budget_status() -> str:
    """Get current budget configuration and alert thresholds from GCP Cloud Billing."""
    return get_budget_status(_get_config())


# --- Deep-Mentor LLM Costs ---


@mcp.tool()
async def user_llm_costs(start_date: str, end_date: str, top_n: int = 20) -> str:
    """Get per-user LLM spending from the LLM usage database.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        top_n: Number of top users to show (default: 20)
    """
    return await get_per_user_llm_costs(_get_config(), start_date, end_date, top_n)


@mcp.tool()
async def provider_llm_costs(start_date: str, end_date: str) -> str:
    """Get LLM cost breakdown by provider (OpenAI, Anthropic, Google, Cohere).

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
    """
    return await get_provider_costs(_get_config(), start_date, end_date)


# --- Discovery ---


@mcp.tool()
def discover_billing_tables() -> str:
    """List all tables in the BigQuery billing export dataset.

    Finds the correct billing table name, shows row counts, and detects
    mismatches with the configured BQ_BILLING_TABLE. No parameters needed.
    """
    return _discover_billing_tables(_get_config())


# --- CSV Billing ---


@mcp.tool()
def load_billing_csv(file_path: str) -> str:
    """Load a GCP billing CSV exported from GCP Console and show cost-by-service summary.

    Use this when BigQuery billing export isn't available yet.

    Args:
        file_path: Absolute path to the CSV file downloaded from GCP Console > Billing > Cost Table
    """
    return _load_billing_csv(_get_config(), file_path)


@mcp.tool()
def csv_sku_breakdown(file_path: str, service_name: str = "") -> str:
    """Get SKU-level cost breakdown from a GCP billing CSV file.

    Use this when BigQuery billing export isn't available yet.

    Args:
        file_path: Absolute path to the CSV file downloaded from GCP Console > Billing > Cost Table
        service_name: Service to filter by (e.g., "Vertex AI"). Leave empty for all services.
    """
    return _get_csv_sku_breakdown(_get_config(), file_path, service_name)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
