# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Cloud Asset Inventory (CAI) fast-path for `gcp-credentials-audit`.** When `cloudasset.googleapis.com` is enabled and the caller has `roles/cloudasset.viewer`, the credentials audit inventories API keys and user-managed SA keys through a few org/folder-scoped CAI queries instead of a per-project `gcloud` loop — collapsing thousands of sequential calls into a handful on multi-organization accounts. Projects not covered by a successful CAI query (standalone projects, or scopes the caller can't read) transparently fall back to the existing per-project loop, and the audit emits the exact `gcloud services enable …` / grant-`roles/cloudasset.viewer` commands to unlock the fast path next run. Strict READ-ONLY is preserved — the audit never enables an API or changes IAM — and `audit.json` output is unchanged.
- Opt-in `AUDIT_VERIFY_PARITY=1` mode that cross-checks the CAI fast path against the per-project loop on identical scope (a defect in field mapping shows up as a parity mismatch).
- Runtime self-validation of the produced `audit.json` against `output.schema.json` at the end of the audit, with a structural `jq` fallback when the `jsonschema` CLI is absent.

### Changed

- The last-used signal in `gcp-credentials-audit` now issues one Cloud Monitoring query per project (grouped by `credential_id`) instead of one per key, so the enrichment step doesn't become the new bottleneck once CAI removes the inventory loop.
- `docs/design.md`: cross-org inventory is now in scope (previously a v1 non-goal) and a CAI fast-path section was added. `docs/threat-model.md`: documents the new read-only `roles/cloudasset.viewer` scope and that missing CAI access degrades to the loop rather than escalating.

## [1.0.0] — 2026-05-25

Initial public release.

### Security

- **All BigQuery queries are parameterised.** User-supplied MCP tool arguments (dates, service names, integers) flow through `bigquery.ScalarQueryParameter`. Identifiers (project / dataset / table) are validated against a strict regex at the `Config` layer (`__post_init__`). Closes the SQL-injection class through the `gcp-finops` MCP tool surface.
- Date / integer / service-name validators run before any SQL is constructed; invalid inputs return a clean error rather than a confusing BQ exception.
- Added `SECURITY.md` (private vulnerability disclosure policy) and `docs/threat-model.md`.
- CI now runs `bandit` (static analysis) and `pip-audit` (CVE scan), both fail-on-finding.
- All runtime dependencies in `pyproject.toml` now declare major-version upper bounds, to bound supply-chain blast radius.
- Issue templates strengthened: the `incident-report` template makes redaction an enforced requirement.
- Final-report template explicitly warns that the report contains identifiers and must be redacted before sharing.

### Added

- 5 Claude Code skills under `skills/`: `gcp-ironclad` (driver), `gcp-credentials-audit`, `gcp-cost-anomaly-scan`, `gcp-spend-guardrails`, `gcp-key-restrictions`.
- `gcp-finops` MCP server under `mcp/gcp-finops/` — 13 tools for GCP billing analysis.
- GitHub Actions CI: pytest matrix (Python 3.11/3.12/3.13), schema validation, bandit, pip-audit.
- Issue templates: bug-report, feature-request, incident-report, config.

### Changed

- Every blocking BigQuery tool function is now `async def` and runs its GCP-SDK call via `asyncio.to_thread`, so a long query doesn't block the MCP event loop.
- Final-report template no longer hardcodes `INR` / `₹` — currency is consumer-controlled via `CURRENCY_SYMBOL`.
- README install instructions use `pip install ./mcp/gcp-finops` (non-editable) for end users; `-e` is for dev mode in `CONTRIBUTING.md`.
- `.mcp.json.example` LLM_USAGE_DB_URL example uses obvious `<your-password>` placeholder.

### Test count

- 96 pytest tests in `mcp/gcp-finops/tests/` (up from 58 in pre-release), including new tests for input validation and SQL-injection-prevention proofs.
