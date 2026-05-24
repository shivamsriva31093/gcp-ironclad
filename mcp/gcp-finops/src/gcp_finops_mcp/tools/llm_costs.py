from __future__ import annotations

from datetime import datetime

from gcp_finops_mcp.config import Config

SCHEMA = "llm_usage_schema"


def _parse_datetime(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


async def _query_db(db_url: str, query: str, *args) -> list[dict]:
    import asyncpg

    conn = await asyncpg.connect(db_url)
    try:
        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]
    finally:
        await conn.close()


async def _run_db_query(config: Config, query: str, *args) -> list[dict] | str:
    """Run a PostgreSQL query, returning rows or a user-friendly error string."""
    if not config.llm_usage_db_url:
        return "## Database Not Configured\n\nSet `LLM_USAGE_DB_URL` env var to query per-user LLM costs."
    try:
        return await _query_db(config.llm_usage_db_url, query, *args)
    except Exception as e:
        err = str(e).lower()
        if "connection refused" in err or "could not connect" in err:
            return f"## Database Connection Failed\n\nCould not connect to LLM usage database. Check that the DB is running and `LLM_USAGE_DB_URL` is correct.\n\nError: {e}"
        if "password authentication" in err:
            return "## Database Auth Failed\n\nPassword authentication failed. Check the credentials in `LLM_USAGE_DB_URL`."
        if "does not exist" in err:
            return f"## Database Error\n\nTable or schema not found. Ensure `llm_usage_schema` exists in the target database.\n\nError: {e}"
        return f"## Database Error\n\nFailed to query LLM usage database: {e}"


def format_user_costs(rows: list[dict]) -> str:
    if not rows:
        return "No LLM cost data found for the specified period."

    total = sum(float(r["total_cost"]) for r in rows)
    lines = ["## Per-User LLM Costs\n"]
    lines.append("| User ID | Total Cost | Requests | Input Tokens | Output Tokens |")
    lines.append("|---------|-----------|----------|--------------|---------------|")
    for r in rows:
        user_display = str(r["user_id"])[:12] + "..." if len(str(r["user_id"])) > 12 else str(r["user_id"])
        lines.append(
            f"| {user_display} | ${float(r['total_cost']):.4f} | {r['total_requests']} "
            f"| {int(r['total_input_tokens']):,} | {int(r['total_output_tokens']):,} |"
        )
    lines.append(f"\n**Total LLM spend: ${total:.4f}**")
    return "\n".join(lines)


async def get_per_user_llm_costs(config: Config, start_date: str, end_date: str, top_n: int = 20) -> str:
    query = f"""
    SELECT
        user_id::text AS user_id,
        COALESCE(SUM(total_cost), 0) AS total_cost,
        COUNT(*) AS total_requests,
        COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
        COALESCE(SUM(output_tokens), 0) AS total_output_tokens
    FROM {SCHEMA}.llm_requests
    WHERE created_at >= $1 AND created_at < $2
      AND status = 'completed'
    GROUP BY user_id
    ORDER BY total_cost DESC
    LIMIT $3
    """
    result = await _run_db_query(config, query, _parse_datetime(start_date), _parse_datetime(end_date), top_n)
    if isinstance(result, str):
        return result
    return format_user_costs(result)


def format_provider_costs(rows: list[dict]) -> str:
    if not rows:
        return "No provider cost data found for the specified period."

    total = sum(float(r["total_cost"]) for r in rows)
    lines = ["## LLM Costs by Provider\n"]
    lines.append("| Provider | Model | Cost | Requests | Input Tokens | Output Tokens |")
    lines.append("|----------|-------|------|----------|--------------|---------------|")
    for r in rows:
        pct = (float(r["total_cost"]) / total * 100) if total > 0 else 0
        lines.append(
            f"| {r['provider']} | {r['model']} | ${float(r['total_cost']):.4f} ({pct:.1f}%) "
            f"| {r['total_requests']} "
            f"| {int(r['total_input_tokens']):,} "
            f"| {int(r['total_output_tokens']):,} |"
        )
    lines.append(f"\n**Total: ${total:.4f}**")
    return "\n".join(lines)


async def get_provider_costs(config: Config, start_date: str, end_date: str) -> str:
    query = f"""
    SELECT
        provider::text AS provider,
        model AS model,
        COALESCE(SUM(total_cost), 0) AS total_cost,
        COUNT(*) AS total_requests,
        COALESCE(SUM(input_tokens), 0) AS total_input_tokens,
        COALESCE(SUM(output_tokens), 0) AS total_output_tokens
    FROM {SCHEMA}.llm_requests
    WHERE created_at >= $1 AND created_at < $2
      AND status = 'completed'
    GROUP BY provider, model
    ORDER BY total_cost DESC
    """
    result = await _run_db_query(config, query, _parse_datetime(start_date), _parse_datetime(end_date))
    if isinstance(result, str):
        return result
    return format_provider_costs(result)
