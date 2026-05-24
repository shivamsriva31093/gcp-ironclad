from __future__ import annotations

from gcp_finops_mcp.config import Config


def _list_tables(config: Config) -> list[dict]:
    from google.cloud import bigquery

    client = bigquery.Client(project=config.gcp_project_id)
    dataset_ref = f"{config.gcp_project_id}.{config.bq_billing_dataset}"

    tables = []
    for table_item in client.list_tables(dataset_ref):
        table = client.get_table(table_item.reference)
        tables.append(
            {
                "table_id": table.table_id,
                "created": table.created.strftime("%Y-%m-%d %H:%M UTC") if table.created else "unknown",
                "num_rows": table.num_rows or 0,
                "size_mb": round((table.num_bytes or 0) / (1024 * 1024), 2),
                "is_billing_export": table.table_id.startswith("gcp_billing_export"),
            }
        )
    return tables


def format_discovered_tables(tables: list[dict], config: Config) -> str:
    if not tables:
        lines = [
            "## No Tables Found\n",
            f"Dataset `{config.gcp_project_id}.{config.bq_billing_dataset}` exists but has no tables.\n",
            "This means BigQuery billing export data hasn't arrived yet.",
            "After enabling billing export, it can take **24-48 hours** for GCP to create the table and populate data.\n",
            "**What to do:**",
            "1. Verify export is enabled: GCP Console > Billing > Billing Export",
            "2. Use `load_billing_csv` with a CSV from GCP Console > Billing > Cost Table in the meantime",
        ]
        return "\n".join(lines)

    billing_tables = [t for t in tables if t["is_billing_export"]]

    lines = [
        f"## Tables in `{config.gcp_project_id}.{config.bq_billing_dataset}`\n",
        "| Table | Rows | Size (MB) | Created | Billing Export? |",
        "|-------|------|-----------|---------|-----------------|",
    ]
    for t in tables:
        flag = "Yes" if t["is_billing_export"] else "No"
        lines.append(
            f"| `{t['table_id']}` | {t['num_rows']:,} | {t['size_mb']} | {t['created']} | {flag} |"
        )

    lines.append("")

    # Suggest the correct table name
    if billing_tables:
        best = max(billing_tables, key=lambda t: t["num_rows"])
        if best["num_rows"] == 0:
            lines.append(
                f"**Warning:** Billing table `{best['table_id']}` exists but has **0 rows**. "
                "Data may still be loading (can take up to 48 hours after export is enabled).\n"
            )
            lines.append("Use `load_billing_csv` with a CSV from GCP Console in the meantime.")
        else:
            lines.append(f"**Suggested `BQ_BILLING_TABLE`:** `{best['table_id']}`")
            if config.bq_billing_table and config.bq_billing_table != best["table_id"]:
                lines.append(
                    f"\n**Mismatch:** Currently configured table is `{config.bq_billing_table}`, "
                    f"but the actual billing table is `{best['table_id']}`. "
                    "Update `BQ_BILLING_TABLE` to fix."
                )
    else:
        lines.append(
            "No billing export tables found. The tables above are not billing exports.\n"
            "Verify billing export is enabled in GCP Console > Billing > Billing Export."
        )

    return "\n".join(lines)


def discover_billing_tables(config: Config) -> str:
    """List all tables in the billing export dataset to find the correct table name."""
    try:
        tables = _list_tables(config)
        return format_discovered_tables(tables, config)
    except Exception as e:
        error_str = str(e)
        if "Not found" in error_str or "404" in error_str:
            return (
                f"## Dataset Not Found\n\n"
                f"Dataset `{config.gcp_project_id}.{config.bq_billing_dataset}` does not exist.\n\n"
                "**To fix:** Go to GCP Console > Billing > Billing Export and enable Standard usage cost export. "
                "Set the destination dataset or create one named `billing_export`."
            )
        if "403" in error_str or "Permission" in error_str.lower() or "Access Denied" in error_str:
            return (
                f"## Permission Denied\n\n"
                f"Cannot access dataset `{config.gcp_project_id}.{config.bq_billing_dataset}`.\n\n"
                "Ensure your account has the **BigQuery Data Viewer** role on the billing dataset."
            )
        return f"## Discovery Error\n\nFailed to list tables: {e}"
