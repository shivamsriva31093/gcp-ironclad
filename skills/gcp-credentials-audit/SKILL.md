---
name: gcp-credentials-audit
description: Use to inventory and risk-classify every API key and user-managed service-account key across all accessible GCP projects. READ-ONLY — does not mutate cloud state. Use standalone, or as Phase 1a of the `gcp-ironclad` driver.
---

# GCP Credentials Audit (READ-ONLY)

## Overview

Walks every GCP project the caller can access, lists every API key and every user-managed service-account key, and classifies each by risk. Writes the result as JSON to the session directory. **Does not mutate cloud state.**

## When to Use

- Triggered by the `gcp-ironclad` driver as Phase 1a.
- Or invoked standalone when you want only the audit, without applying any controls.

## Inputs

- `SESSION_DIR` env var: path to the session directory created by the driver (e.g. `/tmp/gcp-ironclad/2026-05-25T10-30-00Z/`). If invoked standalone, default to `/tmp/gcp-ironclad/standalone-$(date -u +%Y-%m-%dT%H-%M-%SZ)/`.
- `LOOKBACK_DAYS` env var (optional): how many days back to look for last-used signal. Default `30`.

## Outputs

Writes `${SESSION_DIR}/audit.json` matching `output.schema.json` in this skill's directory.

## Risk classification

| Class | Trigger |
|---|---|
| `CRITICAL` | API key with `restrictions = NONE` (fully unrestricted) |
| `HIGH` | API key restricted to a service the project has never used; SA with ≥3 user-managed keys; SA key older than 365 days |
| `MEDIUM` | API key created >180 days ago AND last-used >90 days ago; SA key older than 90 days |
| `LOW` | API key restricted to ≤1 service and used within the last 30 days |
| `INFO` | Google-managed keys (Firebase browser keys, default compute SAs, `firebase-adminsdk-fbsvc@*`) |

## Execution

### Step A: Establish session directory

```bash
SESSION_DIR="${SESSION_DIR:-/tmp/gcp-ironclad/standalone-$(date -u +%Y-%m-%dT%H-%M-%SZ)}"
mkdir -p "${SESSION_DIR}/raw"
echo "SESSION_DIR=${SESSION_DIR}"
```

### Step B: Discover projects (or read from driver-provided scope)

```bash
if [ -f "${SESSION_DIR}/scope.json" ]; then
  jq -r '.projects[].projectId' "${SESSION_DIR}/scope.json" > "${SESSION_DIR}/projects.txt"
else
  gcloud projects list --format='value(projectId)' > "${SESSION_DIR}/projects.txt"
fi
wc -l "${SESSION_DIR}/projects.txt"
```

### Step C: Inventory each project

For each `$P` in `projects.txt`:

```bash
while read P; do
  echo "## $P"
  # API keys
  gcloud services api-keys list --project="$P" --format=json \
    > "${SESSION_DIR}/raw/${P}.apikeys.json" 2>"${SESSION_DIR}/raw/${P}.apikeys.err"
  # Per-key details (restrictions, createTime)
  if jq -e 'length>0' "${SESSION_DIR}/raw/${P}.apikeys.json" >/dev/null 2>&1; then
    jq -r '.[].uid' "${SESSION_DIR}/raw/${P}.apikeys.json" | while read uid; do
      gcloud services api-keys describe "$uid" --project="$P" --format=json \
        > "${SESSION_DIR}/raw/${P}.key.${uid}.json" 2>/dev/null
    done
  fi
  # Service accounts
  gcloud iam service-accounts list --project="$P" --format=json \
    > "${SESSION_DIR}/raw/${P}.sas.json" 2>"${SESSION_DIR}/raw/${P}.sas.err"
  # Per-SA user-managed keys
  if jq -e 'length>0' "${SESSION_DIR}/raw/${P}.sas.json" >/dev/null 2>&1; then
    jq -r '.[].email' "${SESSION_DIR}/raw/${P}.sas.json" | while read sa; do
      gcloud iam service-accounts keys list --iam-account="$sa" --managed-by=user --format=json \
        > "${SESSION_DIR}/raw/${P}.sakeys.${sa}.json" 2>/dev/null
    done
  fi
done < "${SESSION_DIR}/projects.txt"
```

If a project errors with `PERMISSION_DENIED` or `API has not been used`, record it in `projectsSkipped` with the reason and move on.

### Step D: Best-effort last-used signal per API key

For each API key UID, query Cloud Monitoring metric `serviceruntime.googleapis.com/api/request_count` filtered by `credential_id = apikey:<UID>` over the last `LOOKBACK_DAYS` days. If the response contains any non-zero points, set `lastUsedAt` to the latest point's timestamp; otherwise `null`.

```bash
TOKEN=$(gcloud auth application-default print-access-token)
LOOKBACK_DAYS="${LOOKBACK_DAYS:-30}"
START=$(date -u -v-${LOOKBACK_DAYS}d +%Y-%m-%dT00:00:00Z 2>/dev/null \
        || date -u -d "${LOOKBACK_DAYS} days ago" +%Y-%m-%dT00:00:00Z)
END=$(date -u +%Y-%m-%dT00:00:00Z)

# For each api-key UID in each project:
#   curl ... monitoring.googleapis.com/v3/projects/$P/timeSeries
#     filter: metric.type="serviceruntime.googleapis.com/api/request_count"
#             AND metric.label.credential_id="apikey:$uid"
#     interval.startTime=$START interval.endTime=$END
#     aggregation.alignmentPeriod=86400s
#     aggregation.perSeriesAligner=ALIGN_SUM
#   → parse the latest point with value > 0 from response.timeSeries[].points
```

Treat missing responses (Monitoring API disabled, no data, etc.) as `lastUsedAt: null`. Record any non-trivial error in `errors[]`.

### Step E: Classify and write `audit.json`

For each credential, apply the risk taxonomy and assemble the final JSON in the schema documented in `output.schema.json`. Write atomically:

```bash
jq -n --argjson creds "$CREDS_JSON" --argjson scope "$SCOPE_JSON" --argjson errs "$ERRS_JSON" '
{
  schemaVersion: 1,
  generatedAt: (now | strftime("%Y-%m-%dT%H:%M:%SZ")),
  scope: $scope,
  credentials: $creds,
  errors: $errs
}' > "${SESSION_DIR}/audit.json.tmp" \
  && mv "${SESSION_DIR}/audit.json.tmp" "${SESSION_DIR}/audit.json"
```

### Step F: Inline summary

Print a one-paragraph summary:

> Audit complete. Scanned N projects (OK accessible / S skipped). Found A API keys ({{c}} CRITICAL, {{h}} HIGH, {{m}} MEDIUM, {{l}} LOW, {{i}} INFO) and B user-managed SA keys ({{by-risk}}). Output: `${SESSION_DIR}/audit.json`.

## Error handling

- Project inaccessible (`PERMISSION_DENIED`): record in `scope.projectsSkipped[]` with reason `"no_access"`; continue.
- API Keys API not enabled on a project: record `"apikeys_api_disabled"`; continue.
- Monitoring API call fails for a key: `lastUsedAt = null`; append to `errors[]`.
- Any other unexpected error: append to `errors[]`; do not abort the audit.
