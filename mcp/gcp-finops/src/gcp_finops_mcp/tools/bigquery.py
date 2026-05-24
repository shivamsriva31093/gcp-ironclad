from __future__ import annotations

from gcp_finops_mcp.config import Config


def _get_client(config: Config):
    from google.cloud import bigquery
    return bigquery.Client(project=config.gcp_project_id)


class BillingDataNotReady(Exception):
    """Raised when BigQuery billing export table doesn't exist yet."""

    def __init__(self, table: str, detail: str = ""):
        self.table = table
        self.detail = detail
        super().__init__(self._message())

    def _message(self) -> str:
        lines = [
            f"## Billing Export Not Ready\n",
            f"The billing export table `{self.table}` was not found.",
            "",
            "This usually means:",
            "- BigQuery billing export was recently enabled and GCP hasn't created the table yet (can take up to 48 hours)",
            "- The table name in `BQ_BILLING_TABLE` env var doesn't match the auto-generated table name",
            "",
            "**To check:** Go to GCP Console > Billing > Billing Export and verify the export is enabled. "
            "Then check BigQuery for the actual table name (it looks like `gcp_billing_export_v1_XXXXXX_YYYYYY_ZZZZZZ`).",
        ]
        if self.detail:
            lines.append(f"\nError detail: {self.detail}")
        return "\n".join(lines)


def _run_query(config: Config, query: str) -> list[dict]:
    from google.api_core import exceptions as gcp_exceptions

    client = _get_client(config)
    try:
        result = client.query(query).result()
        return [dict(row) for row in result]
    except gcp_exceptions.NotFound as e:
        raise BillingDataNotReady(config.fully_qualified_table, str(e))
    except gcp_exceptions.Forbidden as e:
        raise BillingDataNotReady(
            config.fully_qualified_table,
            f"Permission denied. Ensure your account has BigQuery Data Viewer role on the billing dataset. {e}",
        )


def build_cost_summary_query(config: Config, start_date: str, end_date: str) -> str:
    table = config.fully_qualified_table
    return f"""
SELECT
  service.description AS service_name,
  ROUND(SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)), 2) AS net_cost,
  ROUND(SUM(cost), 2) AS gross_cost
FROM `{table}`
WHERE DATE(usage_start_time) BETWEEN '{start_date}' AND '{end_date}'
GROUP BY service.description
ORDER BY net_cost DESC
"""


def format_cost_summary(rows: list[dict], currency: str = "₹") -> str:
    if not rows:
        return "No billing data found for the specified date range."

    total = sum(r["net_cost"] for r in rows)
    lines = [f"## Cost Summary (net after credits)\n"]
    lines.append(f"| Service | Net Cost | Gross Cost |")
    lines.append(f"|---------|----------|------------|")
    for r in rows:
        pct = (r["net_cost"] / total * 100) if total > 0 else 0
        lines.append(
            f"| {r['service_name']} | {currency}{r['net_cost']:.2f} ({pct:.1f}%) | {currency}{r['gross_cost']:.2f} |"
        )
    lines.append(f"\n**Total: {currency}{total:.2f}**")
    return "\n".join(lines)


_BQ_NOT_CONFIGURED_MSG = (
    "## BigQuery Billing Table Not Configured\n\n"
    "`BQ_BILLING_TABLE` environment variable is not set.\n\n"
    "**Options:**\n"
    "1. Use the `discover_billing_tables` tool to find the correct table name in your dataset\n"
    "2. Use `load_billing_csv` to analyze a CSV exported from GCP Console > Billing > Cost Table\n"
    "3. Set `BQ_BILLING_TABLE` to the table name (e.g., `gcp_billing_export_v1_XXXXXX_YYYYYY_ZZZZZZ`)"
)


def _safe_query(config: Config, query: str) -> list[dict] | str:
    """Run a BigQuery query, returning rows or a user-friendly error string."""
    if config.bq_billing_table is None:
        return _BQ_NOT_CONFIGURED_MSG
    try:
        return _run_query(config, query)
    except BillingDataNotReady as e:
        return str(e)
    except Exception as e:
        return f"## BigQuery Error\n\nFailed to query billing data: {e}"


def get_cost_summary(config: Config, start_date: str, end_date: str) -> str:
    query = build_cost_summary_query(config, start_date, end_date)
    result = _safe_query(config, query)
    if isinstance(result, str):
        return result
    return format_cost_summary(result, config.currency_symbol)


def build_sku_breakdown_query(
    config: Config, service_name: str, start_date: str, end_date: str
) -> str:
    table = config.fully_qualified_table
    return f"""
SELECT
  sku.description AS sku_name,
  ROUND(SUM(cost), 2) AS cost,
  SUM(usage.amount) AS usage_amount,
  usage.unit AS usage_unit
FROM `{table}`
WHERE DATE(usage_start_time) BETWEEN '{start_date}' AND '{end_date}'
  AND service.description = '{service_name}'
GROUP BY sku.description, usage.unit
ORDER BY cost DESC
"""


def format_sku_breakdown(rows: list[dict], service_name: str, currency: str = "₹") -> str:
    if not rows:
        return f"No SKU data found for {service_name} in the specified date range."

    total = sum(r["cost"] for r in rows)
    lines = [f"## SKU Breakdown: {service_name}\n"]
    lines.append("| SKU | Cost | Usage | Unit |")
    lines.append("|-----|------|-------|------|")
    for r in rows:
        pct = (r["cost"] / total * 100) if total > 0 else 0
        lines.append(
            f"| {r['sku_name']} | {currency}{r['cost']:.2f} ({pct:.1f}%) | {r['usage_amount']:,.0f} | {r['usage_unit']} |"
        )
    lines.append(f"\n**Total: {currency}{total:.2f}**")
    return "\n".join(lines)


def get_sku_breakdown(
    config: Config, service_name: str, start_date: str, end_date: str
) -> str:
    query = build_sku_breakdown_query(config, service_name, start_date, end_date)
    result = _safe_query(config, query)
    if isinstance(result, str):
        return result
    return format_sku_breakdown(result, service_name, config.currency_symbol)


def build_cost_trend_query(config: Config, lookback_days: int = 14) -> str:
    table = config.fully_qualified_table
    return f"""
SELECT
  FORMAT_DATE('%Y-%m-%d', DATE(usage_start_time)) AS day,
  service.description AS service_name,
  ROUND(SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)), 2) AS net_cost
FROM `{table}`
WHERE DATE(usage_start_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL {lookback_days} DAY)
GROUP BY 1, 2
HAVING net_cost > 0.01
ORDER BY 1, 3 DESC
"""


def format_cost_trend(rows: list[dict], currency: str = "₹") -> str:
    if not rows:
        return "No trend data found for the specified period."

    from collections import defaultdict

    by_day: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_day[r["day"]].append(r)

    lines = ["## Daily Cost Trend\n"]
    for day in sorted(by_day.keys()):
        day_total = sum(r["net_cost"] for r in by_day[day])
        lines.append(f"### {day} — {currency}{day_total:.2f}")
        for r in by_day[day][:5]:  # top 5 services per day
            lines.append(f"  - {r['service_name']}: {currency}{r['net_cost']:.2f}")
        lines.append("")
    return "\n".join(lines)


def get_cost_trend(config: Config, lookback_days: int = 14) -> str:
    query = build_cost_trend_query(config, lookback_days)
    result = _safe_query(config, query)
    if isinstance(result, str):
        return result
    return format_cost_trend(result, config.currency_symbol)


def build_anomaly_query(config: Config, threshold_pct: int = 30, lookback_days: int = 30) -> str:
    table = config.fully_qualified_table
    return f"""
WITH daily AS (
  SELECT
    FORMAT_DATE('%Y-%m-%d', DATE(usage_start_time)) AS day,
    ROUND(SUM(cost), 2) AS daily_cost
  FROM `{table}`
  WHERE DATE(usage_start_time) >= DATE_SUB(CURRENT_DATE(), INTERVAL {lookback_days} DAY)
  GROUP BY 1
),
rolling AS (
  SELECT
    day,
    daily_cost,
    ROUND(AVG(daily_cost) OVER (ORDER BY day ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING), 2) AS avg_7d
  FROM daily
)
SELECT day, daily_cost, avg_7d,
  ROUND((daily_cost - avg_7d) / NULLIF(avg_7d, 0) * 100, 1) AS pct_above_avg
FROM rolling
WHERE avg_7d IS NOT NULL
  AND daily_cost > avg_7d * (1 + {threshold_pct} / 100.0)
ORDER BY day DESC
"""


def format_anomalies(rows: list[dict], currency: str = "₹") -> str:
    if not rows:
        return "No anomalies detected. Spending is within normal ranges."

    lines = ["## Cost Anomalies Detected\n"]
    for r in rows:
        lines.append(
            f"- **{r['day']}**: {currency}{r['daily_cost']:.2f} "
            f"(+{r['pct_above_avg']:.1f}% above 7-day avg of {currency}{r['avg_7d']:.2f})"
        )
    return "\n".join(lines)


def detect_anomalies(config: Config, threshold_pct: int = 30, lookback_days: int = 30) -> str:
    query = build_anomaly_query(config, threshold_pct, lookback_days)
    result = _safe_query(config, query)
    if isinstance(result, str):
        return result
    return format_anomalies(result, config.currency_symbol)


def build_compare_periods_query(
    config: Config,
    period_a_start: str,
    period_a_end: str,
    period_b_start: str,
    period_b_end: str,
) -> str:
    table = config.fully_qualified_table
    return f"""
SELECT
  service.description AS service_name,
  ROUND(SUM(CASE
    WHEN DATE(usage_start_time) BETWEEN '{period_a_start}' AND '{period_a_end}'
    THEN cost + IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)
    ELSE 0
  END), 2) AS period_a_cost,
  ROUND(SUM(CASE
    WHEN DATE(usage_start_time) BETWEEN '{period_b_start}' AND '{period_b_end}'
    THEN cost + IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)
    ELSE 0
  END), 2) AS period_b_cost
FROM `{table}`
WHERE DATE(usage_start_time) BETWEEN '{period_a_start}' AND '{period_b_end}'
GROUP BY service.description
HAVING period_a_cost > 0.01 OR period_b_cost > 0.01
ORDER BY period_b_cost DESC
"""


def format_period_comparison(rows: list[dict], label_a: str, label_b: str, currency: str = "₹") -> str:
    if not rows:
        return "No data found for the specified periods."

    lines = [f"## Cost Comparison: {label_a} vs {label_b}\n"]
    lines.append(f"| Service | {label_a} | {label_b} | Change |")
    lines.append("|---------|----------|----------|--------|")
    for r in rows:
        a, b = r["period_a_cost"], r["period_b_cost"]
        if a > 0:
            change = (b - a) / a * 100
            sign = "+" if change >= 0 else ""
            change_str = f"{sign}{change:.1f}%"
        elif b > 0:
            change_str = "NEW"
        else:
            change_str = "—"
        lines.append(f"| {r['service_name']} | {currency}{a:.2f} | {currency}{b:.2f} | {change_str} |")

    total_a = sum(r["period_a_cost"] for r in rows)
    total_b = sum(r["period_b_cost"] for r in rows)
    overall_change = ((total_b - total_a) / total_a * 100) if total_a > 0 else 0
    sign = "+" if overall_change >= 0 else ""
    lines.append(f"\n**Total: {currency}{total_a:.2f} → {currency}{total_b:.2f} ({sign}{overall_change:.1f}%)**")
    return "\n".join(lines)


def compare_periods(
    config: Config,
    period_a_start: str,
    period_a_end: str,
    period_b_start: str,
    period_b_end: str,
    label_a: str = "Period A",
    label_b: str = "Period B",
) -> str:
    query = build_compare_periods_query(
        config, period_a_start, period_a_end, period_b_start, period_b_end
    )
    result = _safe_query(config, query)
    if isinstance(result, str):
        return result
    return format_period_comparison(result, label_a, label_b, config.currency_symbol)


def build_vertex_ai_query(config: Config, start_date: str, end_date: str) -> str:
    table = config.fully_qualified_table
    return f"""
SELECT
  sku.description AS sku_name,
  ROUND(SUM(cost), 4) AS cost,
  SUM(usage.amount) AS usage_amount,
  usage.unit AS usage_unit
FROM `{table}`
WHERE DATE(usage_start_time) BETWEEN '{start_date}' AND '{end_date}'
  AND service.description = 'Vertex AI'
GROUP BY sku.description, usage.unit
ORDER BY cost DESC
"""


def format_vertex_ai_costs(rows: list[dict], currency: str = "₹") -> str:
    if not rows:
        return "No Vertex AI costs found for the specified date range."

    total = sum(r["cost"] for r in rows)
    lines = ["## Vertex AI Cost Breakdown\n"]
    lines.append("| SKU | Cost | Usage | Unit |")
    lines.append("|-----|------|-------|------|")
    for r in rows:
        lines.append(
            f"| {r['sku_name']} | {currency}{r['cost']:.4f} | {r['usage_amount']:,.0f} | {r['usage_unit']} |"
        )
    lines.append(f"\n**Total Vertex AI: {currency}{total:.4f}**")
    return "\n".join(lines)


def get_vertex_ai_costs(config: Config, start_date: str, end_date: str) -> str:
    query = build_vertex_ai_query(config, start_date, end_date)
    result = _safe_query(config, query)
    if isinstance(result, str):
        return result
    return format_vertex_ai_costs(result, config.currency_symbol)
