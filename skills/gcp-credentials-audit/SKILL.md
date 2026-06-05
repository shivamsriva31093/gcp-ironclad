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

### Step B: Discover projects (from driver scope or standalone), then derive the CAI query scopes and the number→id map.

```bash
# Project list (from driver scope, or discover standalone)
if [ -f "${SESSION_DIR}/scope.json" ]; then
  cp "${SESSION_DIR}/scope.json" "${SESSION_DIR}/scope.local.json"
else
  gcloud projects list --format=json > "${SESSION_DIR}/raw-projects.json"
  jq -n --slurpfile p "${SESSION_DIR}/raw-projects.json" '{projects:$p[0]}' \
    > "${SESSION_DIR}/scope.local.json"
fi
jq -r '.projects[].projectId' "${SESSION_DIR}/scope.local.json" > "${SESSION_DIR}/projects.txt"

# Derivations for the CAI fast path:
#  - projnum-to-id.json : project NUMBER -> projectId (CAI returns numbers)
#  - cai-scopes.txt     : distinct org/folder scopes to query
#  - uncovered.txt      : starts with parent-less (standalone) projects; the
#                         fast path appends projects whose scope query failed
jq '[.projects[] | select(.projectNumber) | {(.projectNumber): .projectId}] | add // {}' \
  "${SESSION_DIR}/scope.local.json" > "${SESSION_DIR}/projnum-to-id.json"
jq -r '.projects[] | select(.parent) | "\(.parent.type)s/\(.parent.id)"' \
  "${SESSION_DIR}/scope.local.json" | sort -u > "${SESSION_DIR}/cai-scopes.txt"
jq -r '.projects[] | select(.parent|not) | .projectId' \
  "${SESSION_DIR}/scope.local.json" > "${SESSION_DIR}/uncovered.txt"

echo "projects=$(wc -l < "${SESSION_DIR}/projects.txt") scopes=$(wc -l < "${SESSION_DIR}/cai-scopes.txt") standalone=$(wc -l < "${SESSION_DIR}/uncovered.txt")"
```

### Step C1: CAI fast path (per scope)

For each scope in `cai-scopes.txt`, query the two asset types. A scope that returns cleanly means **every project under it is covered**; a scope that errors sends its projects to the fallback (Step C2) and emits a recommendation.

```bash
: > "${SESSION_DIR}/creds.cai.json.parts"
: > "${SESSION_DIR}/covered.txt"
: > "${SESSION_DIR}/cai-errors.json.parts"
while read SCOPE; do
  SAFE=$(echo "$SCOPE" | tr '/' '_')
  ok=1
  for TYPE in apikeys.googleapis.com/Key iam.googleapis.com/ServiceAccountKey; do
    OUT="${SESSION_DIR}/raw/cai.${SAFE}.$(echo "$TYPE" | tr '/.' '__').json"
    if ! gcloud asset search-all-resources --scope="$SCOPE" \
          --asset-types="$TYPE" --read-mask='*' --format=json \
          > "$OUT" 2>"${OUT}.err"; then
      ok=0; break
    fi
  done

  if [ "$ok" = 0 ]; then
    # Scope failed — fall back for its projects, recommend the unlock (READ-ONLY: we never enable).
    REASON=$(tr -d '\n' < "${OUT}.err" | sed 's/"/'"'"'/g' | cut -c1-300)
    jq -r --arg s "$SCOPE" '.projects[] | select(.parent) | select(("\(.parent.type)s/\(.parent.id)")==$s) | .projectId' \
      "${SESSION_DIR}/scope.local.json" >> "${SESSION_DIR}/uncovered.txt"
    jq -nc --arg s "$SCOPE" --arg r "$REASON" \
      '{context:"cai_fallback", message:("CAI query failed for \($s): \($r). Falling back to the per-project loop for its projects. To enable the fast path next run: (1) gcloud services enable cloudasset.googleapis.com --project=<quota-project> ; (2) grant your account roles/cloudasset.viewer on \($s).")}' \
      >> "${SESSION_DIR}/cai-errors.json.parts"
    continue
  fi

  # Scope OK — mark its projects covered (complete picture, even if zero keys).
  jq -r --arg s "$SCOPE" '.projects[] | select(.parent) | select(("\(.parent.type)s/\(.parent.id)")==$s) | .projectId' \
    "${SESSION_DIR}/scope.local.json" >> "${SESSION_DIR}/covered.txt"

  AK="${SESSION_DIR}/raw/cai.${SAFE}.apikeys_googleapis_com_Key.json"
  SK="${SESSION_DIR}/raw/cai.${SAFE}.iam_googleapis_com_ServiceAccountKey.json"
  jq --slurpfile map "${SESSION_DIR}/projnum-to-id.json" '
    [ .[] | (.versionedResources[0].resource) as $r
      | select((($r.deleteTime) // "") == "")          # drop soft-deleted keys (Task 1 finding)
      | {
        type:"api_key",
        project:(.project | sub("projects/";"") as $n | ($map[0][$n] // $n)),
        uid:($r.uid // (.name | sub(".*/keys/";""))),
        displayName:($r.displayName // .displayName // ""),
        createTime:($r.createTime // $r.create_time),
        restrictions:($r.restrictions // null),
        lastUsedAt:null } ]' "$AK" >> "${SESSION_DIR}/creds.cai.json.parts"
  jq --slurpfile map "${SESSION_DIR}/projnum-to-id.json" '
    [ .[] | . as $row | ($row.versionedResources[0].resource) as $r
      | ($r.keyType // $r.key_type) as $kt | select($kt=="USER_MANAGED")
      | (($row.displayName // $row.name) | capture("serviceAccounts/(?<sa>[^/]+)/keys/")) as $m
      | { type:"sa_key",
          project:($row.project | sub("projects/";"") as $n | ($map[0][$n] // $n)),
          serviceAccount:$m.sa,                          # email — result-level displayName (Task 1 finding)
          keyId:($row.name | sub(".*/keys/";"")),
          createTime:($r.validAfterTime // $r.valid_after_time),
          lastUsedAt:null } ]' "$SK" >> "${SESSION_DIR}/creds.cai.json.parts"
done < "${SESSION_DIR}/cai-scopes.txt"

# Flatten + dedupe (uid for keys, project+serviceAccount+keyId for SA keys) in case scopes overlap.
# stderr is intentionally NOT suppressed: a parse failure here would otherwise silently
# yield zero CAI credentials — a dangerous false-clean for a security audit.
jq -s 'add // [] | unique_by(.uid // "\(.project)/\(.serviceAccount)/\(.keyId)")' \
  "${SESSION_DIR}/creds.cai.json.parts" > "${SESSION_DIR}/creds.cai.json" \
  || { echo "WARN: could not parse creds.cai.json.parts; writing empty CAI set" >&2; \
       echo '[]' > "${SESSION_DIR}/creds.cai.json"; }
# De-dupe uncovered (a project listed standalone won't also be covered, but guard anyway).
sort -u "${SESSION_DIR}/uncovered.txt" -o "${SESSION_DIR}/uncovered.txt"
echo "cai_credentials=$(jq length "${SESSION_DIR}/creds.cai.json") covered_projects=$(sort -u "${SESSION_DIR}/covered.txt" 2>/dev/null | wc -l)"
```

**Resilience:** the live probe confirmed `restrictions` (keys) and `keyType`/`validAfterTime` (SA keys) are present in `versionedResources`, so the `--read-mask='*'` fast form above is the path used. Kept as a defensive note: if for some asset type/org those fields are ever absent, swap that one query for `gcloud asset list --<organization|folder|project>=<id> --content-type=resource --asset-types="$TYPE" --format=json` and read the resource from `.[].resource.data` instead of `.versionedResources[0].resource`.

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
