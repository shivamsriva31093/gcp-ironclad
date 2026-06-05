# CAI Inventory Fast-Path for `gcp-credentials-audit` — Design

- **Date:** 2026-06-05
- **Status:** Approved — ready for implementation planning
- **Affected skill:** `skills/gcp-credentials-audit/SKILL.md` (Phase 1a of the `gcp-ironclad` driver)
- **Approach:** Hybrid — org/folder-scoped Cloud Asset Inventory (CAI) fast-path with a per-project-loop fallback (Approach A of three considered)

## Why

`gcp-credentials-audit` inventories every API key and user-managed service-account key across every accessible project, then risk-classifies each. Today it does this with a **nested per-project loop** (`SKILL.md` Steps B–C): `gcloud projects list`, then per project a `services api-keys list` + a `describe` per key + `iam service-accounts list` + a `keys list` per SA. That is roughly `N_projects × (2 + #keys + #SAs)` sequential `gcloud` invocations, each paying CLI + auth startup. On a multi-organization account it is the wall-clock bottleneck and it emits a per-project error whenever an API is not enabled.

Cloud Asset Inventory exposes `apikeys.googleapis.com/Key`, `iam.googleapis.com/ServiceAccountKey`, and `iam.googleapis.com/ServiceAccount` as asset types and can return every resource of a type **across an entire org/folder in one paginated query**. Google documents CAI as the way to "list the API keys that don't have restrictions" — exactly this skill's `CRITICAL` bucket. Collapsing the inventory loop into a handful of org/folder-scoped queries is the primary win; batching the last-used enrichment is the secondary win that keeps the enrichment step from becoming the new bottleneck.

Target environment for this change: an operator with access to **multiple organizations plus some standalone projects**.

## Goals

- Replace the per-project inventory loop with org/folder-scoped CAI queries **where CAI is available**.
- Fall back to today's loop, transparently, where CAI is not available.
- Batch the last-used (Step D) Monitoring enrichment from per-key to per-project.
- Produce a **byte-for-byte identical** `audit.json` shape (no `output.schema.json` change).
- Preserve the skill's strict **READ-ONLY** guarantee.
- Keep the skill working both standalone and under the driver, with **no driver change**.

## Non-goals

- Auto-enabling `cloudasset.googleapis.com` (would break READ-ONLY — see Constraints).
- Project-scope CAI for standalone/orphan projects (Approach B). Deferred; the loop handles them. Revisit if a standalone fleet proves large and slow.
- Changing the risk taxonomy, the `output.schema.json`, the driver, or the `scope.json` contract.
- Any change to the other sub-skills (`gcp-cost-anomaly-scan`, `gcp-spend-guardrails`, `gcp-key-restrictions`).

This change **promotes a previously documented v1 non-goal** — `docs/design.md` lists "Cross-org / multi-tenant operation" under *Not in v1*. That line moves into scope as part of this work (see Documentation changes).

## Constraints & key decisions

1. **Strict READ-ONLY, never auto-enable.** CAI needs `cloudasset.googleapis.com` enabled on a quota project and `roles/cloudasset.viewer` at the org/folder. The audit must not enable or grant anything. When CAI is unavailable for a scope, the audit **falls back to the loop and still completes**, and emits a recommendation with the exact unlock commands so the operator can opt into the fast path next run. (Mirrors the suite's existing "flag with the exact `gcloud` command attached" pattern.)
2. **Schema-stable.** `audit.json` keeps its exact shape; `output.schema.json` is untouched. Coverage statistics surface only in the inline summary.
3. **No driver / `scope.json` change.** CAI scopes are derived from project `parent` data already present in `scope.json` (or from the skill's own `gcloud projects list` when run standalone).

## Architecture / data flow

```
scope.json (or `gcloud projects list`)         ← unchanged source
   │  projects[] each w/ projectId, projectNumber, parent{type,id}
   ▼
[Discovery]  distinct accessible parents = CAI scopes (orgs + folders)
   ▼
[Fast path]  per scope: 2 CAI queries → keys + SA-keys ──┐
   │  mark every project under a SUCCEEDED scope "covered"│
   ▼                                                      ▼
[Fallback]   uncovered (no parent, or scope failed)    merge + dedupe
   │         → existing per-project loop  ───────────►   credential set
   ▼
[Enrich]     last-used: ONE Monitoring query per project (group_by credential_id)
   ▼
[Classify]   existing risk taxonomy → audit.json (unchanged schema)
```

The change rewrites Steps B–D of `gcp-credentials-audit/SKILL.md`. Steps A (session dir), E (classify + write), and F (inline summary) are unchanged except that E/F also report the CAI-vs-loop coverage split in the summary text.

## Discovery & coverage map

- **CAI scopes** = the **distinct immediate parents** of the in-scope projects — `organizations/<id>` and `folders/<id>` — read from `scope.json.projects[].parent`. Because we scope to immediate parents directly, there is no hierarchy walking and no org⊃folder double-coverage.
- A project is **covered** iff its parent-scope CAI query **succeeded** — i.e. we obtained the complete picture for that scope — regardless of whether the project actually had any keys. (A covered project with zero keys must not be re-scanned by the loop.)
- **Uncovered** = projects with **no `parent`** (true standalone, no organization) **or** whose parent-scope query **failed** (API not enabled / `PERMISSION_DENIED`). Uncovered projects go to the loop.
- `gcloud organizations list` is intentionally **not** used: deriving scopes from project parents is sufficient, avoids a driver change, and avoids redundant org-wide queries. (Considered and rejected as YAGNI.)

## CAI fast path

Per scope `S` (e.g. `organizations/123456789` or `folders/987654321`), exactly **two** queries. The `iam.googleapis.com/ServiceAccount` *list* query is intentionally dropped: grouping the returned SA **keys** by their SA email already yields the key-count-per-SA needed for the `HIGH` ("≥3 user-managed keys") tier and the email patterns the `INFO` tier matches (`firebase-adminsdk-fbsvc@*`, default compute SAs). A service account with no user-managed keys produces no credential rows today, so it does not need to be enumerated.

```bash
gcloud asset search-all-resources --scope="$S" \
  --asset-types=apikeys.googleapis.com/Key --read-mask='*'
gcloud asset search-all-resources --scope="$S" \
  --asset-types=iam.googleapis.com/ServiceAccountKey --read-mask='*'
```

Field mapping (CAI `versionedResources[].resource` → `audit.json` credential entry):

| audit.json field | API key (`apikeys.googleapis.com/Key`) | SA key (`iam.googleapis.com/ServiceAccountKey`) |
|---|---|---|
| `project` | resolve `project` (a project **number**) → `projectId` via `scope.json` | parse from key `name` |
| `uid` / `keyId` | `uid` | parse `…/keys/<KEY_ID>` from `name` |
| `displayName` / `serviceAccount` | `displayName` | parse SA email from `name` |
| `createTime` | `createTime` | `validAfterTime` |
| `restrictions` | `restrictions` (absent ⇒ unrestricted ⇒ `CRITICAL`) | — (n/a) |
| `lastUsedAt` | filled by Step D (null from CAI) | filled by Step D (null from CAI) |
| filter | — | keep only `keyType == "USER_MANAGED"` |

- **Project number → projectId:** CAI returns `projects/<PROJECT_NUMBER>` in the resource `project` field. `scope.json.projects[]` carries both `projectNumber` and `projectId`, so resolution is a local join.
- **Dedupe** by `uid` (API keys) / key `name` (SA keys) in case scopes overlap.
- **Resilience to field availability:** if `search-all-resources --read-mask='*'` does not populate `restrictions` (API keys) or `keyType`/`validAfterTime` (SA keys) inside `versionedResources` for a given asset type, substitute that single query with:
  ```bash
  gcloud asset list --<organization|folder|project>=<id> \
    --content-type=resource --asset-types=<type>
  ```
  which returns the full resource config directly. The implementation plan verifies which form carries the fields on real data before committing the jq.

## Fallback, degradation & the read-only recommendation

- **Uncovered projects → the existing Step B–C loop, verbatim**, run over only that subset of projects. It is already proven, already READ-ONLY, and requires no new code — only that the loop iterate the uncovered subset rather than all projects.
- **Per-scope CAI failure handling:**
  - `cloudasset.googleapis.com` not enabled, **or** `PERMISSION_DENIED` (caller lacks `cloudasset.viewer` on the scope) → that scope's projects drop to the loop; emit **one** entry into `errors[]` (context `cai_fallback`) recording the scope and reason, and surface a recommendation with the exact unlock commands:
    ```bash
    gcloud services enable cloudasset.googleapis.com --project=<quota-project>
    gcloud organizations add-iam-policy-binding <org-id> \
      --member="user:<you>" --role="roles/cloudasset.viewer"
    ```
  - Partial CAI page/transport error mid-scope → treat the whole scope as failed (fall back for its projects) rather than risk a partial inventory.
- The audit **never** enables an API or modifies IAM. Strict READ-ONLY is preserved.

## Batched last-used (Step D)

Replace the per-key Monitoring loop with **one `timeSeries.list` per project**:

- Filter: `metric.type="serviceruntime.googleapis.com/api/request_count"`.
- `aggregation.groupByFields=["metric.label.credential_id"]`, `perSeriesAligner=ALIGN_SUM`, `alignmentPeriod=86400s`, interval = last `LOOKBACK_DAYS`.
- Result: one series per `credential_id` used in the project. For each credential, `lastUsedAt` = timestamp of the latest point with value > 0; otherwise `null`.

Same semantics as today (`SKILL.md` Step D), applied uniformly to credentials discovered via **either** path. Missing/disabled Monitoring is still treated as `lastUsedAt: null` with a non-fatal `errors[]` entry.

## Contract & documentation changes

- `skills/gcp-credentials-audit/output.schema.json`: **unchanged.**
- `skills/gcp-credentials-audit/SKILL.md`: rewrite Steps B–D per this design; extend Step F's summary with the coverage split (e.g. "inventoried via CAI: K projects across M scopes; via per-project fallback: L projects").
- `docs/design.md`: remove "Cross-org / multi-tenant operation" from the *Not in v1* list; add a one-paragraph "Inventory fast-path (Cloud Asset Inventory)" note to the architecture section; add a row to the Errors & edge-cases table (`CAI not enabled/permitted → per-project fallback + recommendation`).
- `docs/threat-model.md`: note the added **read** scope (`roles/cloudasset.viewer` at org/folder) and that CAI access is read-only (no new mutation surface).
- No change to the driver, `scope.json`, or the other sub-skills.

## Error handling

| Condition | Behavior |
|---|---|
| `cloudasset.googleapis.com` not enabled for a scope | That scope's projects → loop; `errors[]` (`cai_fallback`) + unlock recommendation. |
| `PERMISSION_DENIED` on a CAI scope query | Same as above. |
| Partial/transport error mid-scope | Treat scope as failed → loop for its projects (no partial inventory). |
| Project has no `parent` (standalone) | Routed to loop by design (not an error). |
| Project unreadable by **both** CAI and loop (`PERMISSION_DENIED` in loop too) | Recorded in `scope.projectsSkipped[]` with reason `no_access`. |
| Monitoring API disabled / no data (Step D) | `lastUsedAt: null`; non-fatal `errors[]` entry. |
| `versionedResources` missing `restrictions`/`keyType` | Use the `gcloud asset list --content-type=resource` form (see Resilience). |

## Testing & verification

The repo's design philosophy is "the playbook *is* the program; there is no engine." This change adds no extracted scripts and no fixtures-engine. Verification:

- **CI stays green trivially.** No `output.schema.json` change and no SKILL.md frontmatter change, so `.github/scripts/validate_schemas.py` continues to pass. The pytest / bandit / pip-audit jobs touch only the MCP server and are unaffected.
- **Differential parity check (the real correctness test).** An opt-in env toggle (`AUDIT_VERIFY_PARITY=1`) that runs **both** the CAI path and the loop over the **same** scope and asserts the resulting **raw inventory** sets match — `uid`/`keyId`, `project`, `createTime`, `restrictions`, `keyType` — *before* the shared Step-D enrichment and classification (which are identical for both paths, so comparing the inventory is what actually exercises the new code). This proves field-mapping equivalence on real data and implicitly confirms CAI returns `restrictions`/`keyType`. Off by default (it defeats the speedup); used once during rollout and after changes.
- **Runtime self-check.** Before declaring success, validate the produced `audit.json` against `output.schema.json` (jsonschema if available, else a structural jq check).
- **Manual.** Run the audit standalone on the multi-org account; confirm the coverage split in the summary and the recommendation emit on any org lacking CAI.

## Open verification items (resolve during planning/implementation)

1. Confirm `search-all-resources --read-mask='*'` returns `restrictions` (keys) and `keyType` + `validAfterTime` (SA keys) inside `versionedResources`; otherwise adopt the `gcloud asset list --content-type=resource` form for that type.
2. Confirm the exact shape of `project` in CAI results (`projects/<number>`) and that `scope.json` always carries `projectNumber` for the number→id join (it comes from `gcloud projects list`, which includes it).
3. Confirm SA-key `name` format from CAI (`projects/<p>/serviceAccounts/<email>/keys/<id>`) for the parse.

## Rollout / sequencing

1. Implement the Step B–D rewrite behind the coverage-map logic, keeping the loop intact as the fallback function.
2. Run the differential parity check on a real org; resolve the open verification items.
3. Update `docs/design.md` and `docs/threat-model.md`.
4. Land; the inline summary's coverage split is the at-a-glance signal that the fast path engaged.
