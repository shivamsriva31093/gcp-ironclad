# GCP FinOps MCP Server

An [MCP](https://modelcontextprotocol.io) server that lets you ask natural-language questions about your GCP costs through Claude Code, Claude Desktop, or any MCP-compatible client.

Distributed as part of [**gcp-ironclad**](../..) — the GCP API-key audit and spend-hardening suite — but works fine standalone.

## What it gives you

| Tool | What it does |
|------|--------------|
| `cost_summary` | GCP costs by service for a date range |
| `sku_breakdown` | SKU-level costs for a specific service |
| `cost_trend` | Daily cost trend over N days |
| `anomalies` | Detect cost spikes above the rolling 7-day average |
| `compare_costs` | Compare costs between two periods |
| `vertex_ai_costs` | Vertex AI / Gemini token cost details |
| `recommendations` | GCP Recommender optimization suggestions |
| `budget_status` | Budget config and alert thresholds |
| `discover_billing_tables` | List tables in your billing dataset to find the correct table name |
| `load_billing_csv` | Cost summary from a GCP Console CSV export |
| `csv_sku_breakdown` | SKU breakdown from a GCP Console CSV export |
| `user_llm_costs` *(optional)* | Per-user LLM spending from a custom PostgreSQL schema |
| `provider_llm_costs` *(optional)* | LLM costs by provider from the same custom schema |

The two `*_llm_costs` tools require a PostgreSQL schema that this server doesn't define; leave `LLM_USAGE_DB_URL` unset to disable them. The other 11 tools work regardless.

## Prerequisites

1. **Enable BigQuery billing export** (Console → Billing → Billing Export → Standard usage cost). Note the auto-generated table name like `gcp_billing_export_v1_<billing_id>`.
2. **Enable APIs:**
   ```bash
   gcloud services enable bigquery.googleapis.com recommender.googleapis.com cloudbilling.googleapis.com
   ```
3. **Authenticate ADC:**
   ```bash
   gcloud auth application-default login
   ```

## Install

```bash
cd mcp/gcp-finops
pip install -e ".[dev]"
```

## Register with Claude Code

Copy `.mcp.json.example` from the repo root to `.mcp.json` (or merge into `~/.claude/settings.json` for a global registration) and fill in your values:

```json
{
  "mcpServers": {
    "gcp-finops": {
      "command": "python",
      "args": ["-m", "gcp_finops_mcp.server"],
      "cwd": "/absolute/path/to/gcp-ironclad/mcp/gcp-finops",
      "env": {
        "GCP_PROJECT_ID": "<your-project-id>",
        "BQ_BILLING_DATASET": "billing_export",
        "BQ_BILLING_TABLE": "<your-billing-export-table>",
        "CURRENCY_SYMBOL": "$"
      }
    }
  }
}
```

## Environment variables

| Variable | Required? | Purpose |
|---|---|---|
| `GCP_PROJECT_ID` *(or `GOOGLE_CLOUD_PROJECT`)* | **required** | Your GCP project ID — the one that owns the billing-export dataset |
| `BQ_BILLING_DATASET` | optional, default `billing_export` | The dataset where billing-export tables live |
| `BQ_BILLING_TABLE` | optional | Specific billing-export table name. If unset, use `discover_billing_tables` to find it |
| `CURRENCY_SYMBOL` | optional, default `$` | Display symbol for cost output (e.g. set to `₹` for INR) |
| `LLM_USAGE_DB_URL` | optional | PostgreSQL URL for the optional per-user LLM cost tools (see above) |

## Example questions

After registering with Claude Code, ask things like:

- *"What are my top GCP cost drivers this month?"*
- *"Break down Vertex AI costs by SKU."*
- *"Any cost anomalies in the last 30 days?"*
- *"Compare February vs March spending."*
- *"What does GCP Recommender suggest for savings?"*
- *"Discover what billing tables exist in my dataset."*
- *"Load this CSV (from GCP Console → Billing → Cost Table) and show me costs by service."*

## Run tests

```bash
pytest -v
```

## License

[MIT](../../LICENSE).
