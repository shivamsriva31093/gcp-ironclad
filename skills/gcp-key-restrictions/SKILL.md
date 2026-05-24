---
name: gcp-key-restrictions
description: Use to apply API-target restrictions to fully-unrestricted GCP API keys, inferring the allow-list from recent usage signals. Idempotent. Honors `--dry-run`. Use standalone or as Phase 3b of `gcp-ironclad`.
---

# GCP Key Restrictions (APPLY)

## Overview

For each API key flagged `CRITICAL` (unrestricted) by `gcp-credentials-audit`, queries the last 30 days of Cloud Monitoring `request_count` filtered by that key's `credential_id`, and — if the usage signal is unambiguous — restricts the key to exactly those APIs via `gcloud services api-keys update`. Keys with no usage signal, signals spanning >5 APIs, or that are <7 days old are demoted to "flag for review" rather than auto-restricted.

## When to Use

- Triggered by `gcp-ironclad` as Phase 3b, after `gcp-spend-guardrails`.
- Or standalone when you have a known list of unrestricted keys to lock down.

## Inputs

- `SESSION_DIR` (must contain a fresh `audit.json` with `riskClass = "CRITICAL"` entries).
- `DRY_RUN` env var (default `0`).
- `MAX_INFERRED_APIS` env var (default `5` — keys with usage across more APIs are flagged, not auto-restricted).
- `LOOKBACK_DAYS` env var (default `30`).

## Outputs

Writes `${SESSION_DIR}/key-restrictions.json` matching `output.schema.json`.

## Execution

### Step A: Load candidate keys

```bash
jq -r '.credentials[] | select(.type == "api_key" and .riskClass == "CRITICAL") | "\(.project)\t\(.uid)\t\(.displayName)\t\(.createTime)"' \
  "${SESSION_DIR}/audit.json" > "${SESSION_DIR}/restriction-candidates.tsv"
wc -l "${SESSION_DIR}/restriction-candidates.tsv"
```

### Step B: For each candidate, query usage

For each line `(project, uid, displayName, createTime)`:

1. If `createTime` is within the last 7 days → outcome `"flagged"`, reason `"too_fresh"`.
2. Else query Monitoring `serviceruntime.googleapis.com/api/request_count` grouped by `metric.label.service`, filtered to `credential_id = apikey:${uid}`, over `LOOKBACK_DAYS`.
3. Collect the set of unique services with non-zero counts.
   - If set is empty → outcome `"flagged"`, reason `"no_usage_signal"`.
   - If set size > `MAX_INFERRED_APIS` → outcome `"flagged"`, reason `"signal_too_broad"`.
   - Otherwise the set is the proposed `apiTargets`.

### Step C: Apply the restriction

If `DRY_RUN=0` and outcome is to apply:
```bash
TARGETS=$(printf -- '--api-target=service=%s ' ${INFERRED_APIS[@]})
gcloud services api-keys update "${uid}" --project="${P}" ${TARGETS}
```
Record `before` (was `null` since unrestricted) and `after` (the new `apiTargets` list).
Rollback for the report: `gcloud services api-keys update ${uid} --project=${P} --clear-api-target`.

### Step D: Write `key-restrictions.json`

Atomic write, summary:

> Key restrictions complete (dryRun=${DRY_RUN}). Applied: A. Flagged for review: B (no signal: X / too broad: Y / too fresh: Z). Skipped: C. Output: `${SESSION_DIR}/key-restrictions.json`.

## Error handling

- Monitoring API permission denied → outcome `"flagged"`, reason `"no_signal_access"`.
- `gcloud services api-keys update` fails → emit `error`, mark outcome `"skipped"` with reason `"update_failed"`.
- Key already deleted between audit and now → emit `error`, skip.

## Never auto-applied

This skill **never** deletes a key. If a key looks abandoned and unused, that decision is for the human. The flag-for-review report includes the one-line `gcloud services api-keys delete ${uid} --project=${P}` for the human to run.
