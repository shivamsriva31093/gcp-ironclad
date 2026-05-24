# Architecture & Design

## Why this exists

Cloud security is officially a *shared-responsibility model*. Google's own documentation, in the same article, says:

- *"DO NOT create unrestricted keys."*
- *"By default a new API key is created without restriction."*

That is: the dangerous configuration is the default. Combine that with:

- API keys are **"open secrets"** (Google's own phrasing) — not paired with identity; anyone with the string can use a key.
- A stolen API key grants access to *"any available service at your expense."*
- Cloud Billing budgets **do not cap spending** — per Google's docs, a budget *"does not automatically cap usage/spending."*
- Spend tiers can be auto-upgraded; a `$250` cap has, in published cases, silently become `$100,000`.
- No platform-side fraud-detection block fires at >100× baseline spend in a single hour.

… and a leaked API key — a foreseeable failure mode — can produce a five- or six-figure bill before you wake up. The platform has prevention controls; it does not have a credible last line of defense.

This project provides that line: an automated audit-and-harden pass you can run from Claude Code that establishes safe defaults across every project you can access, surfaces what it can't safely auto-fix, and tells you when something has already gone wrong.

## Top-level architecture

A driver skill (`gcp-ironclad`) plus four focused sub-skills:

```
gcp-ironclad/                 Driver — orchestrates the run, assembles the final report
├── gcp-credentials-audit/    READ-ONLY  inventory + risk classification
├── gcp-cost-anomaly-scan/    READ-ONLY  did abuse already happen?
├── gcp-spend-guardrails/     APPLY      quotas + budgets + idle-API disable
└── gcp-key-restrictions/     APPLY      lock down unrestricted keys
```

Each sub-skill is invocable standalone. The driver composes them.

Skills are Markdown playbooks the Claude Code `Skill` tool loads. The model executes the playbook with `Bash` (calling `gcloud`, `bq`, `jq`) and the `gcp-finops` MCP server. There is no Python "engine" — the playbook *is* the program and the model is the interpreter. This is what lets users read, audit, and modify the behavior without writing code.

## Execution: four phases

```
Phase 0 — Discover scope (driver)
            gcloud projects list, gcloud billing accounts list, gcloud config get-value account
            → /tmp/gcp-ironclad/<iso-ts>/scope.json

Phase 1 — READ-ONLY audits (parallel)
            ├─ gcp-credentials-audit   → audit.json
            └─ gcp-cost-anomaly-scan   → anomalies.json

Phase 2 — Gate (driver)
            Inline summary printed.
            HALT if any project shows >Nx baseline spend in the last 24h (default N=10).
            No mutations run while bleeding.

Phase 3 — APPLY (sequential, mutating)
            ├─ gcp-spend-guardrails    → guardrails-applied.json
            └─ gcp-key-restrictions    → key-restrictions.json

Phase 4 — Consolidate (driver)
            Merge phase JSONs → markdown + JSON final report.
            → ~/.claude/reports/gcp-ironclad-<iso-ts>.{md,json}
```

The JSON files in `/tmp/gcp-ironclad/<ts>/` are the contract between sub-skills — which is what lets sub-skills run independently *or* via the driver. Each sub-skill has an `output.schema.json` documenting its contract.

## Auto-apply safety matrix

Every applied action has a *precondition* that makes it genuinely side-effect-free. If the precondition isn't met, it's demoted to "flag for review."

| Action | Auto-apply ONLY when | Demoted to "flag" when |
|---|---|---|
| Set Gemini-API quota | API enabled + ≥7 days usage + proposed quota > observed peak | No usage data; new project (<7d); billing export missing |
| Quota sizing | `max(peak_30d × 5, 5000/day floor)` | Peak shows abuse signature → use floor only (don't size from abuse) |
| Create budget alerts | caller is `billing.admin` on the account + no existing budget at proposed threshold | viewer-only; budget already configured |
| Disable idle paid API | Zero 30-day usage + API enabled >7 days + project not `sys-*` | Any 30d usage; enabled <7d; system-managed project |
| Restrict unrestricted key | Used in last 30d + 1–5 distinct APIs touched + key created >7d ago | No usage signal; >5 APIs touched (likely a default-everywhere key — needs human); key created <7d ago |

## Never auto-applied

Always flagged for human review with the exact `gcloud` command attached:

- Deleting any API key — even an obvious leaked one.
- Lowering a quota below current observed usage.
- Disabling any API with traffic in the last 30 days.
- Modifying IAM (org, project, billing-account).
- Closing billing accounts.
- Rotating service-account keys.

## Cross-cutting safeguards

- **Active-spike halt** (Phase 2). Default threshold: >10× baseline in last 24h.
- **Reversibility:** every applied change has its undo command in the final report.
- **`--dry-run`:** all phases run; nothing mutates; the report shows what *would* change.
- **`--confirm-each`:** y/n prompt per action even in auto mode.
- **Idempotency:** every action gates on `current state ≠ desired state`. Re-running on a hardened environment is a no-op.

## Output: the final report

A markdown + JSON file at `~/.claude/reports/gcp-ironclad-<ts>.{md,json}`. Sections:

1. **Executive summary** — top risks before/after, money at risk, actions taken, whether an active spike was detected.
2. **Audit findings** — every API key + SA key by project, with risk class.
3. **Cost anomaly check** — any spike >N× baseline in the lookback window.
4. **Actions applied** — what changed, with the exact rollback command per change.
5. **⚠ Flagged for review** — destructive items the suite refused to auto-apply, with the exact `gcloud` command for the user.
6. **Re-run hygiene checklist** — verify in console, when to re-run, recommended manual follow-ups.

## Errors & edge cases

| Condition | Behavior |
|---|---|
| ADC auth expired | Phase 0 fails clean with the `gcloud auth application-default login` instruction. |
| `gcp-finops` MCP unavailable | Anomaly scan falls back to direct `bq query`. If billing export is missing for an account, an `info` finding is emitted and the run continues. |
| Caller has no access to a project | Skipped; recorded in `scope.json.projectsSkipped[]`. |
| Project has no usage data | Skip auto-quota and auto-restriction for it; emit `flag for review`. |
| Caller is not `billing.admin` on an account | Budget creation skipped; flagged. |
| Peak in usage data has an abuse signature | Use floor for quota sizing; don't size *from* a peak that is itself abuse. |
| Sub-skill failure | Sub-skill writes partial JSON with `errors[]`, exits non-fatally; driver continues and surfaces errors in the report. |
| Two concurrent driver runs | Each gets its own timestamped session directory; no shared state. |

## Status / non-goals

**v1 scope:** API-key + SA-key audit, spend guardrails, key restrictions, cost anomaly detection, final consolidated report.

**Not in v1 (PRs welcome):**

- Local codebase / git-history secret scanning (`AIza…` pattern, SA-key JSON discovery).
- IAM auditing (project / org / billing-account).
- Secret-Manager migration helper.
- Org-policy enforcement (`apikeys.googleapis.com/allowedRestrictions`) to prevent unrestricted keys at creation time.
- Continuous monitoring via scheduled Cloud Run.
- Cross-org / multi-tenant operation.
- Auto-deletion of any credential.
