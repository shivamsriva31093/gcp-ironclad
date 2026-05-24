from __future__ import annotations

from gcp_finops_mcp.config import Config

RECOMMENDER_TYPES = {
    "google.cloudsql.instance.IdleRecommender": "Idle Cloud SQL instances",
    "google.cloudsql.instance.OverprovisionedRecommender": "Oversized Cloud SQL instances",
    "google.compute.instance.MachineTypeRecommender": "Right-size VMs",
    "google.compute.disk.IdleResourceRecommender": "Idle persistent disks",
    "google.run.service.CostRecommender": "Cloud Run Cost optimizations",
}

LOCATIONS = ["us-central1", "asia-south1"]


def _fetch_recommendations(config: Config) -> list[dict]:
    from google.cloud import recommender_v1

    client = recommender_v1.RecommenderClient()
    all_recs = []

    for location in LOCATIONS:
        for rec_type in RECOMMENDER_TYPES:
            parent = f"projects/{config.gcp_project_id}/locations/{location}/recommenders/{rec_type}"
            try:
                for rec in client.list_recommendations(parent=parent):
                    cost_amount = None
                    if rec.primary_impact and rec.primary_impact.cost_projection:
                        nanos = rec.primary_impact.cost_projection.cost.nanos
                        units = rec.primary_impact.cost_projection.cost.units
                        cost_amount = float(units) + float(nanos) / 1e9

                    all_recs.append({
                        "name": rec.name,
                        "description": rec.description,
                        "recommender_subtype": rec.recommender_subtype,
                        "priority": rec.priority.name if rec.priority else "UNSET",
                        "primary_impact_cost_usd": cost_amount,
                    })
            except Exception:
                continue

    return all_recs


def format_recommendations(recs: list[dict]) -> str:
    if not recs:
        return "No recommendations found. Your resources appear to be well-optimized."

    lines = ["## GCP Cost Optimization Recommendations\n"]
    total_savings = 0
    for r in recs:
        cost_str = ""
        if r["primary_impact_cost_usd"] is not None:
            savings = abs(r["primary_impact_cost_usd"])
            total_savings += savings
            cost_str = f" — potential savings: **${savings:.2f}/month**"

        lines.append(f"- [{r['priority']}] **{r['recommender_subtype']}**: {r['description']}{cost_str}")

    if total_savings > 0:
        lines.append(f"\n**Total potential savings: ${total_savings:.2f}/month**")
    return "\n".join(lines)


def get_recommendations(config: Config) -> str:
    try:
        recs = _fetch_recommendations(config)
    except Exception as e:
        err = str(e).lower()
        if "403" in err or "permission" in err:
            return "## Recommender API Error\n\nPermission denied. Ensure your account has the `Recommender Viewer` role."
        if "disabled" in err or "not been used" in err or "enable" in err:
            return (
                "## Recommender API Not Enabled\n\n"
                "The Recommender API is not enabled for this project. Run:\n"
                "```bash\ngcloud services enable recommender.googleapis.com\n```"
            )
        return f"## Recommender API Error\n\nFailed to fetch recommendations: {e}"
    return format_recommendations(recs)
