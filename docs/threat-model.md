# Threat Model

## Goal

State explicitly what `gcp-ironclad` does and does *not* protect against, what it assumes about the environment it runs in, and which trust boundaries it crosses. A security tool without an explicit threat model is asking its users to guess.

## Assets being protected

| Asset | Concern |
|---|---|
| Active GCP API keys, service-account keys, OAuth credentials | leakage → unauthorized usage |
| GCP project budgets and quotas | runaway spend from fraud |
| Billing-export data (BigQuery) | confidentiality (cost detail is competitive intel) |
| The generated audit report | contains identifiers; leakage shrinks attacker recon time |

## Adversaries considered

1. **External attacker holding a leaked credential.** The primary motivating threat. Pattern: API key committed to a repo, embedded in a built mobile/web app, leaked via a former employee or contractor, harvested from CI logs.
2. **External attacker probing the MCP server.** If the server were accidentally network-exposed, its tool surface (BigQuery query construction, CSV-file paths) becomes attack surface.
3. **A malicious PR contributor.** Could land code that mis-classifies a risk class, sizes a quota dangerously, or leaks data through the report. Mitigation: review.

## Out of scope

- A compromised local developer machine (an attacker with shell access to your laptop wins regardless).
- A compromised GitHub account belonging to a maintainer (separate problem; mitigated by branch protection + signed commits).
- GCP platform vulnerabilities (Google's problem).
- Compromise of upstream Python packages (`mcp`, `google-cloud-*`, `asyncpg`). Mitigation: major-version upper bounds in `pyproject.toml`; users who care should also `pip freeze > requirements.lock`.

## Trust boundaries

```
┌─────────────────────────────────┐
│  Your developer machine         │  ← trusted (you control it)
│                                 │
│    Claude Code                  │
│      ↓ Skill tool               │
│    gcp-ironclad skills          │  ← trusted (you control these files)
│      ↓ Bash → gcloud/bq/jq      │
│      ↓ Skill tool               │
│    gcp-finops MCP server        │  ← trusted, but exposes a tool surface
└─────────────────────────────────┘
                ↓ gcloud / google-cloud-* SDK (HTTPS, ADC token)
┌─────────────────────────────────┐
│  GCP                            │
│    IAM, billing APIs            │
│    BigQuery (billing export)    │
│    Cloud Monitoring             │
│    Cloud Asset Inventory (RO)   │
└─────────────────────────────────┘
```

The MCP server is the most consequential trust boundary in this picture because:

- It executes whatever queries an LLM constructs (so it must be safe against malformed or maliciously-crafted LLM-generated input).
- It runs with the full ADC permissions of the invoking user.
- Its responses are markdown that flow back into the LLM context.

## Concrete mitigations in place

| Threat | Mitigation |
|---|---|
| SQL injection via MCP tool args (dates, service names, integers) | All user-supplied values flow through BigQuery parameterised queries (`@param`). Identifiers (project / dataset / table) are validated against a strict regex at the `Config` layer (`_IDENT_RE`). |
| Malformed inputs reaching BigQuery | Date format, integer range, and string-length validators run before any SQL is constructed (see `tools/bigquery.py::_valid_date`, `_valid_int`, `_valid_service_name`). |
| Phase 3 mutating action while a project is bleeding | Active-spike gate halts Phase 3 if any project shows `>N×` baseline spend in the last 24h (`N=10` by default). |
| Auto-applied mutation breaking production | Every auto-apply action has a precondition documented in the safety matrix; failing the precondition demotes the action to "flag for review." |
| Accidental key deletion | `gcp-key-restrictions` and the driver *never* delete keys — they emit the `gcloud services api-keys delete …` command for the user to run. |
| Quota cap below current usage | Quota sizing is `max(peak_30d × 5, floor)` — strictly above the observed peak unless the peak itself is an abuse signature, in which case the floor is used. |
| Disabling an API in active use | API-disable gates on zero usage in the last 30 days **and** API enabled `>7` days ago **and** project not `sys-*`. |
| Privilege creep | All actions inherit the calling identity's permissions; no `--impersonate` or sudo escalation inside the skills. |
| Over-broad access for the CAI fast path | CAI access is **read-only** and needs only `roles/cloudasset.viewer` at the org/folder; the audit never enables the API or modifies IAM — missing access degrades to the per-project loop, it does not escalate. |
| Event-loop blocking from long BQ queries | BigQuery tool functions are `async def` and run their blocking GCP-SDK calls via `asyncio.to_thread`. |

## Known limitations

| Gap | Why it's open |
|---|---|
| No supply-chain lockfile shipped | Adds maintenance burden; users who care can `pip freeze` post-install. |
| No `bandit` / `semgrep` in CI yet | Coming in a follow-up release. |
| Cross-org *apply* unsupported | The audit inventory now reads across orgs/folders via Cloud Asset Inventory; the APPLY phases (guardrails, key-restrictions) remain per-project. |
| Local-codebase / git-history secret scanning | Out of v1 scope; PR welcome. |
| Audit report may contain identifiers | Documented in the report footer; users must redact before sharing. |
| No platform-side fraud-detection integration | GCP does not expose one that can be subscribed to. |

## What we want help on

Specifically for security-minded contributors:

- **Fuzzing the MCP tool surface.** A `hypothesis`-based property test for the query builders would be valuable.
- **A `bandit` baseline + CI integration.** Adopt it.
- **A signed-release workflow.** Sigstore + tagged releases.
- **Translation of the safety matrix into an executable policy** (e.g., OPA Rego) for users who want to audit our claims mechanically.

See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for general PR guidelines.
