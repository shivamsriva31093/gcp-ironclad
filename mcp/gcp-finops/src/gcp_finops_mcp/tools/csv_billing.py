from __future__ import annotations

import csv
import os
from collections import defaultdict

from gcp_finops_mcp.config import Config

_REQUIRED_COLUMNS = {"Service description", "SKU description", "Cost ($)"}


def _parse_float(value: str) -> float:
    if not value or not value.strip():
        return 0.0
    try:
        return float(value.strip().replace(",", ""))
    except ValueError:
        return 0.0


def _parse_csv(file_path: str) -> tuple[list[dict], list[str]]:
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    with open(file_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []

        missing = _REQUIRED_COLUMNS - set(columns)
        if missing:
            raise ValueError(
                f"CSV is missing required columns: {', '.join(sorted(missing))}. "
                f"Found columns: {', '.join(columns)}. "
                "Expected a CSV exported from GCP Console > Billing > Cost Table."
            )

        rows = []
        for row in reader:
            rows.append(row)

    return rows, columns


def format_csv_cost_summary(rows: list[dict], currency: str = "₹") -> str:
    if not rows:
        return "No data in the CSV file."

    by_service: dict[str, float] = defaultdict(float)
    for row in rows:
        service = row.get("Service description", "Unknown")
        cost = _parse_float(row.get("Cost ($)", "0"))
        by_service[service] += cost

    sorted_services = sorted(by_service.items(), key=lambda x: x[1], reverse=True)
    total = sum(cost for _, cost in sorted_services)

    lines = ["## Cost Summary (from CSV)\n"]
    lines.append("| Service | Cost |")
    lines.append("|---------|------|")
    for service, cost in sorted_services:
        pct = (cost / total * 100) if total > 0 else 0
        lines.append(f"| {service} | {currency}{cost:.2f} ({pct:.1f}%) |")
    lines.append(f"\n**Total: {currency}{total:.2f}**")
    return "\n".join(lines)


def format_csv_sku_breakdown(rows: list[dict], service_name: str, currency: str = "₹") -> str:
    if not rows:
        return "No data in the CSV file."

    service_filter = service_name.strip().lower()

    # Collect all services for suggestions
    all_services: set[str] = set()
    filtered_rows: list[dict] = []
    for row in rows:
        svc = row.get("Service description", "")
        all_services.add(svc)
        if service_filter and svc.lower() == service_filter:
            filtered_rows.append(row)

    if service_filter and not filtered_rows:
        available = sorted(all_services)
        lines = [
            f"No data found for service **{service_name}**.\n",
            "**Available services:**",
        ]
        for svc in available:
            lines.append(f"- {svc}")
        return "\n".join(lines)

    target_rows = filtered_rows if service_filter else rows

    by_sku: dict[str, float] = defaultdict(float)
    for row in target_rows:
        sku = row.get("SKU description", "Unknown")
        cost = _parse_float(row.get("Cost ($)", "0"))
        by_sku[sku] += cost

    sorted_skus = sorted(by_sku.items(), key=lambda x: x[1], reverse=True)
    total = sum(cost for _, cost in sorted_skus)

    title = f"SKU Breakdown: {service_name}" if service_filter else "SKU Breakdown (all services)"
    lines = [f"## {title}\n"]
    lines.append("| SKU | Cost |")
    lines.append("|-----|------|")
    for sku, cost in sorted_skus:
        pct = (cost / total * 100) if total > 0 else 0
        lines.append(f"| {sku} | {currency}{cost:.2f} ({pct:.1f}%) |")
    lines.append(f"\n**Total: {currency}{total:.2f}**")
    return "\n".join(lines)


def load_billing_csv(config: Config, file_path: str) -> str:
    """Load a GCP billing CSV and return a cost-by-service summary.

    Args:
        config: Server config.
        file_path: Path to the CSV file exported from GCP Console > Billing > Cost Table.
    """
    try:
        rows, _columns = _parse_csv(file_path)
        return format_csv_cost_summary(rows, config.currency_symbol)
    except FileNotFoundError as e:
        return (
            f"## File Not Found\n\n{e}\n\n"
            "**How to get this CSV:**\n"
            "1. Go to GCP Console > Billing > Cost Table\n"
            "2. Set your desired date range\n"
            "3. Click **Download CSV**\n"
            "4. Pass the downloaded file path to this tool"
        )
    except ValueError as e:
        return f"## Invalid CSV Format\n\n{e}"
    except Exception as e:
        return f"## CSV Parse Error\n\nFailed to parse CSV: {e}"


def get_csv_sku_breakdown(config: Config, file_path: str, service_name: str = "") -> str:
    """Load a GCP billing CSV and return SKU-level breakdown, optionally filtered by service.

    Args:
        config: Server config.
        file_path: Path to the CSV file exported from GCP Console > Billing > Cost Table.
        service_name: Service to filter by (case-insensitive). Empty string for all services.
    """
    try:
        rows, _columns = _parse_csv(file_path)
        return format_csv_sku_breakdown(rows, service_name, config.currency_symbol)
    except FileNotFoundError as e:
        return (
            f"## File Not Found\n\n{e}\n\n"
            "**How to get this CSV:**\n"
            "1. Go to GCP Console > Billing > Cost Table\n"
            "2. Set your desired date range\n"
            "3. Click **Download CSV**\n"
            "4. Pass the downloaded file path to this tool"
        )
    except ValueError as e:
        return f"## Invalid CSV Format\n\n{e}"
    except Exception as e:
        return f"## CSV Parse Error\n\nFailed to parse CSV: {e}"
