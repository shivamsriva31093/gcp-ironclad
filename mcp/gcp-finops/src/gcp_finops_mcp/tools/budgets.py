from __future__ import annotations

from gcp_finops_mcp.config import Config


def _fetch_budgets(config: Config) -> list[dict]:
    from google.cloud.billing import budgets_v1
    from google.cloud import billing_v1

    billing_client = billing_v1.CloudBillingClient()
    billing_info = billing_client.get_project_billing_info(
        name=f"projects/{config.gcp_project_id}"
    )
    billing_account = billing_info.billing_account_name

    client = budgets_v1.BudgetServiceClient()
    results = []
    for budget in client.list_budgets(parent=billing_account):
        amount_usd = None
        if budget.amount and budget.amount.specified_amount:
            units = budget.amount.specified_amount.units
            nanos = budget.amount.specified_amount.nanos
            amount_usd = float(units) + float(nanos) / 1e9

        thresholds = []
        for rule in budget.threshold_rules:
            pct = rule.threshold_percent * 100
            thresholds.append(f"{pct:.0f}%")

        results.append({
            "name": budget.display_name or budget.name.split("/")[-1],
            "amount_usd": amount_usd,
            "thresholds": thresholds,
        })

    return results


def format_budgets(budgets: list[dict]) -> str:
    if not budgets:
        return "No budgets configured. Consider setting up budget alerts in GCP Console > Billing > Budgets."

    lines = ["## Budget Status\n"]
    for b in budgets:
        amount_str = f"${b['amount_usd']:.2f}" if b.get("amount_usd") else "not set"
        lines.append(f"### {b['name']}")
        lines.append(f"- Budget: {amount_str}")

        if b.get("current_spend_usd") is not None:
            lines.append(f"- Current spend: ${b['current_spend_usd']:.2f}")
            lines.append(f"- Used: {b['pct_used']:.1f}%")

        if b.get("thresholds"):
            lines.append(f"- Alert thresholds: {', '.join(b['thresholds'])}")
        lines.append("")

    return "\n".join(lines)


def get_budget_status(config: Config) -> str:
    try:
        budgets = _fetch_budgets(config)
    except Exception as e:
        err = str(e).lower()
        if "403" in err or "permission" in err:
            return "## Budget API Error\n\nPermission denied. Ensure your account has the `Billing Account Viewer` role."
        if "disabled" in err or "not been used" in err or "enable" in err:
            return (
                "## Budget API Not Enabled\n\n"
                "The Cloud Billing Budgets API is not enabled. Run:\n"
                "```bash\ngcloud services enable billingbudgets.googleapis.com\n```"
            )
        return f"## Budget API Error\n\nFailed to fetch budget status: {e}"
    return format_budgets(budgets)
