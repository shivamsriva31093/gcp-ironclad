# CAI Inventory Fast-Path Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `gcp-credentials-audit` inventory API keys and SA keys via org/folder-scoped Cloud Asset Inventory (CAI) where available, falling back to the existing per-project loop, and batch the last-used enrichment — cutting a multi-org audit from thousands of sequential `gcloud` calls to a handful of queries, with `audit.json` unchanged.

**Architecture:** Rewrite Steps B–D of the `skills/gcp-credentials-audit/SKILL.md` playbook into a discovery → CAI-fast-path → loop-fallback → batched-enrichment → classify pipeline. Credentials from both paths are normalized to one record shape (`creds.cai.json`, `creds.loop.json`), merged, enriched, and classified by the unchanged taxonomy. Strict READ-ONLY is preserved: CAI is never auto-enabled; when a scope's CAI query fails, its projects drop to the loop and the audit emits the exact unlock command.

**Tech Stack:** Bash, `gcloud` (incl. `gcloud asset`), `jq`, Cloud Monitoring REST (`timeSeries.list`), `python3 -m jsonschema` (runtime self-check). The skill is a Markdown playbook — "the playbook *is* the program," so there is no compiled artifact; the deliverables are edited playbook + doc prose and runnable `jq` verification against sample JSON.

**Spec:** `docs/superpowers/specs/2026-06-05-cai-inventory-fast-path-design.md`

**Branch:** `feat/cai-inventory-fast-path` (already created; the spec is committed there).

---

## Record shape (used by every task)

Both inventory paths emit an array of credential records in this exact shape (pre-classification; `lastUsedAt` filled in Step D):

```jsonc
// api_key record
{ "type": "api_key", "project": "<projectId>", "uid": "<uid>",
  "displayName": "<name>", "createTime": "<rfc3339>",
  "restrictions": { /* obj */ } /* or null */, "lastUsedAt": null }

// sa_key record
{ "type": "sa_key", "project": "<projectId>", "serviceAccount": "<email>",
  "keyId": "<id>", "createTime": "<rfc3339>", "lastUsedAt": null }
```

These map 1:1 to the `oneOf` entries in `skills/gcp-credentials-audit/output.schema.json` after Step E adds `riskClass` + `riskReason`. The schema is **not** modified by this plan.

## File map

- **Modify:** `skills/gcp-credentials-audit/SKILL.md` — Steps B, C (becomes C1 fast-path + C2 fallback), D, E (merge input), F (summary + self-check); new "Parity mode" + "CAI fallback" notes. Tasks 2–8.
- **Modify:** `docs/design.md` — remove the cross-org non-goal; add a fast-path note + edge-case row. Task 9.
- **Modify:** `docs/threat-model.md` — update the cross-org limitation; add the `cloudasset.viewer` read scope. Task 10.
- **No** new committed source files. **No** change to the driver, `scope.json`, `output.schema.json`, or other sub-skills.

---

## Task 1: Confirm CAI resource shapes (read-only probe)

This resolves the spec's three "Open verification items" against real data before any jq is written against assumed field names. It is a read-only probe; **no commit**.

**Files:** none (records findings for Tasks 2–5).

- [ ] **Step 1: Pick a scope and ensure CAI is reachable**

Run (substitute one real org id you can access):

```bash
ORG=organizations/$(gcloud organizations list --format='value(ID)' | head -n1)
QUOTA=$(gcloud config get-value project)
gcloud services list --enabled --project="$QUOTA" --filter='config.name=cloudasset.googleapis.com' --format='value(config.name)'
```

Expected: prints `cloudasset.googleapis.com`. If blank, CAI is not enabled on your quota project — enable it (read-only setup you opt into) before continuing:
`gcloud services enable cloudasset.googleapis.com --project="$QUOTA"`. If you cannot/won't enable it, the fast path will simply never engage and the audit runs the loop; you can still implement and review Tasks 2–10, but skip the live checks.

- [ ] **Step 2: Capture a real API-key asset and inspect field paths**

```bash
gcloud asset search-all-resources --scope="$ORG" \
  --asset-types=apikeys.googleapis.com/Key --read-mask='*' \
  --format=json > /tmp/cai-apikeys.json
jq '.[0] | {project, name, displayName, createTime,
            res_keys: (.versionedResources[0].resource | keys)}' /tmp/cai-apikeys.json
```

Confirm and **write down**: (a) `project` looks like `projects/<NUMBER>`; (b) `versionedResources[0].resource` contains `uid`, `displayName`, `restrictions` (or `create_time`/snake variants), `createTime`. If `restrictions` is **absent** from `versionedResources`, note it — Task 3's resilience branch (use `gcloud asset list --content-type=resource`) applies.

- [ ] **Step 3: Capture a real SA-key asset and inspect field paths**

```bash
gcloud asset search-all-resources --scope="$ORG" \
  --asset-types=iam.googleapis.com/ServiceAccountKey --read-mask='*' \
  --format=json > /tmp/cai-sakeys.json
jq '.[0] | {project, name,
            res: (.versionedResources[0].resource | {keyType, key_type, validAfterTime, valid_after_time})}' /tmp/cai-sakeys.json
```

Confirm: `name` ends `…/serviceAccounts/<email>/keys/<id>`; the resource carries `keyType` (or `key_type`) and `validAfterTime` (or `valid_after_time`). Note which case (camel/snake) — Tasks 3 uses tolerant `a // b` fallbacks so either works, but confirm at least one is present.

- [ ] **Step 4: Record the outcome**

In the PR description (or a scratch note), record: project-number format ✓/path, key resource field names, SA-key resource field names, and whether `restrictions`/`keyType` ride in `versionedResources` (fast form) or require the `gcloud asset list --content-type=resource` form.

**Findings (confirmed 2026-06-05 against the real account):**
- `project` = `projects/<NUMBER>` ✓ — number→id join required.
- API-key `versionedResources[0].resource` is **camelCase**: `uid`, `displayName`, `createTime`, `restrictions`, `name`, `updateTime`, `deleteTime`, `annotations`. `restrictions` present ⇒ **fast form works; resilience branch NOT needed** (kept only as defensive code).
- ⚠️ **Soft-deleted API keys still appear in CAI** within their ~30-day purge window (carry a non-empty `deleteTime`). The loop's `gcloud services api-keys list` does **not** list deleted keys → the CAI mapping (Task 3) **must filter out any record with a non-empty `deleteTime`**, or it reports phantom keys and fails parity.
- ⚠️ **SA-key email is in the result-level `displayName`** (`…/serviceAccounts/<email>/keys/<id>`), NOT `name` — the resource `name` uses the SA's **numeric** unique id (`…/serviceAccounts/110432393508830098446/keys/<id>`). The SA-key resource has **no** `displayName` of its own; parse the email from the top-level result `displayName`. SA-key resource (camelCase): `keyType`, `validAfterTime`, `validBeforeTime`, `keyAlgorithm`, `keyOrigin`.
- camelCase is confirmed; the `// snake_case` fallbacks in Tasks 3–5 are harmless and retained defensively.

---

## Task 2: Step B — discovery + coverage-scope derivation

Rewrite Step B so it produces, besides today's `projects.txt`: a project-number→id map, the set of distinct CAI scopes, and the initial uncovered set (parent-less projects).

**Files:** Modify `skills/gcp-credentials-audit/SKILL.md` (Step B, currently lines 46–55).

- [ ] **Step 1: Write the verification first (runnable jq against a sample scope.json)**

Create a throwaway sample and assert the derivations. Run:

```bash
cat > /tmp/scope.sample.json <<'JSON'
{ "projects": [
  {"projectId":"alpha","projectNumber":"111","parent":{"type":"organization","id":"700"}},
  {"projectId":"beta","projectNumber":"222","parent":{"type":"folder","id":"800"}},
  {"projectId":"gamma","projectNumber":"333"}
]}
JSON
# number->id map
jq '[.projects[] | {(.projectNumber): .projectId}] | add' /tmp/scope.sample.json
# distinct CAI scopes (orgs + folders), parent-less excluded
jq -r '.projects[] | select(.parent) | "\(.parent.type)s/\(.parent.id)"' /tmp/scope.sample.json | sort -u
# parent-less projects (initial uncovered)
jq -r '.projects[] | select(.parent|not) | .projectId' /tmp/scope.sample.json
```

Expected output, in order:
```
{"111":"alpha","222":"beta","333":"gamma"}
folders/800
organizations/700
gamma
```

(`organization` → `organizations/`, `folder` → `folders/` — the `\(...)s` pluralization is what produces the valid `--scope` values.)

- [ ] **Step 2: Verify the sample commands produce exactly that**

Run the three jq commands above. Expected: the four output lines match. If pluralization or selection is off, fix the jq before editing the skill.

- [ ] **Step 3: Replace Step B in the skill**

In `skills/gcp-credentials-audit/SKILL.md`, replace the Step B fenced block (the `if [ -f .../scope.json ] … wc -l` block) with:

````markdown
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
````

Also update the Step B prose line above the block to: *"Discover projects (from driver scope or standalone), then derive the CAI query scopes and the number→id map."*

- [ ] **Step 4: Validate the skill still passes schema/frontmatter CI**

Run: `python .github/scripts/validate_schemas.py`
Expected: `OK frontmatter skills/gcp-credentials-audit/SKILL.md (name=gcp-credentials-audit)` and overall `All schemas + frontmatter OK.` (Frontmatter/schema untouched, so this stays green.)

- [ ] **Step 5: Commit**

```bash
git add skills/gcp-credentials-audit/SKILL.md
git commit -m "feat(credentials-audit): derive CAI scopes + number→id map in Step B" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Step C1 — CAI fast path

Add a new Step C1 that queries each scope and emits `creds.cai.json`, marking covered projects and appending failed-scope projects to `uncovered.txt`.

**Files:** Modify `skills/gcp-credentials-audit/SKILL.md` (insert Step C1 before the existing Step C; the existing Step C becomes C2 in Task 4).

- [ ] **Step 1: Write the verification first — API-key mapping jq**

```bash
cat > /tmp/map.json <<'JSON'
{"111":"alpha"}
JSON
cat > /tmp/cai-apikeys.sample.json <<'JSON'
[
 {"project":"projects/111","name":"projects/111/locations/global/keys/k-unrestricted",
  "versionedResources":[{"resource":{"uid":"k-unrestricted","displayName":"web key","createTime":"2025-01-01T00:00:00Z"}}]},
 {"project":"projects/111","name":"projects/111/locations/global/keys/k-restricted",
  "versionedResources":[{"resource":{"uid":"k-restricted","displayName":"server key","createTime":"2025-02-01T00:00:00Z",
    "restrictions":{"apiTargets":[{"service":"generativelanguage.googleapis.com"}]}}}]},
 {"project":"projects/111","name":"projects/111/locations/global/keys/k-deleted",
  "versionedResources":[{"resource":{"uid":"k-deleted","displayName":"old key","createTime":"2024-01-01T00:00:00Z","deleteTime":"2026-06-02T00:00:00Z"}}]}
]
JSON
jq --slurpfile map /tmp/map.json '
  [ .[] | (.versionedResources[0].resource) as $r
    | select((($r.deleteTime) // "") == "")          # drop soft-deleted keys (Task 1 finding)
    | {
      type: "api_key",
      project: (.project | sub("projects/";"") as $n | ($map[0][$n] // $n)),
      uid: ($r.uid // (.name | sub(".*/keys/";""))),
      displayName: ($r.displayName // .displayName // ""),
      createTime: ($r.createTime // $r.create_time),
      restrictions: ($r.restrictions // null),
      lastUsedAt: null
  } ]' /tmp/cai-apikeys.sample.json
```

Expected (the soft-deleted `k-deleted` is filtered out — the loop never lists deleted keys, so the fast path must not either):
```json
[
  {"type":"api_key","project":"alpha","uid":"k-unrestricted","displayName":"web key","createTime":"2025-01-01T00:00:00Z","restrictions":null,"lastUsedAt":null},
  {"type":"api_key","project":"alpha","uid":"k-restricted","displayName":"server key","createTime":"2025-02-01T00:00:00Z","restrictions":{"apiTargets":[{"service":"generativelanguage.googleapis.com"}]},"lastUsedAt":null}
]
```

(Two correctness properties: the unrestricted key yields `restrictions: null` → `CRITICAL` in Step E; the soft-deleted key is excluded to match `gcloud services api-keys list`.)

- [ ] **Step 2: Write the verification first — SA-key mapping jq (incl. USER_MANAGED filter)**

```bash
# NB (Task 1 finding): the SA-key `name` uses the SA's NUMERIC id; the email lives in
# the result-level `displayName`. Parse serviceAccount from displayName, keyId from name.
cat > /tmp/cai-sakeys.sample.json <<'JSON'
[
 {"project":"projects/111",
  "name":"//iam.googleapis.com/projects/alpha/serviceAccounts/110432393508830098446/keys/key-aaa",
  "displayName":"projects/alpha/serviceAccounts/svc@alpha.iam.gserviceaccount.com/keys/key-aaa",
  "versionedResources":[{"resource":{"keyType":"USER_MANAGED","validAfterTime":"2024-06-01T00:00:00Z"}}]},
 {"project":"projects/111",
  "name":"//iam.googleapis.com/projects/alpha/serviceAccounts/110432393508830098446/keys/key-sys",
  "displayName":"projects/alpha/serviceAccounts/svc@alpha.iam.gserviceaccount.com/keys/key-sys",
  "versionedResources":[{"resource":{"keyType":"SYSTEM_MANAGED","validAfterTime":"2024-01-01T00:00:00Z"}}]}
]
JSON
jq --slurpfile map /tmp/map.json '
  [ .[] | . as $row | ($row.versionedResources[0].resource) as $r
    | ($r.keyType // $r.key_type) as $kt
    | select($kt == "USER_MANAGED")
    | (($row.displayName // $row.name) | capture("serviceAccounts/(?<sa>[^/]+)/keys/")) as $m
    | {
        type: "sa_key",
        project: ($row.project | sub("projects/";"") as $n | ($map[0][$n] // $n)),
        serviceAccount: $m.sa,                          # email — from result-level displayName
        keyId: ($row.name | sub(".*/keys/";"")),
        createTime: ($r.validAfterTime // $r.valid_after_time),
        lastUsedAt: null
    } ]' /tmp/cai-sakeys.sample.json
```

Expected (SYSTEM_MANAGED filtered out; email parsed from `displayName`, not the numeric `name`):
```json
[
  {"type":"sa_key","project":"alpha","serviceAccount":"svc@alpha.iam.gserviceaccount.com","keyId":"key-aaa","createTime":"2024-06-01T00:00:00Z","lastUsedAt":null}
]
```

- [ ] **Step 3: Run both verifications**

Run the two jq pipelines above. Expected: outputs match exactly (modulo whitespace). If a field is wrong, fix the jq here before embedding it.

- [ ] **Step 4: Insert Step C1 into the skill**

Insert this new section immediately before the current `### Step C: Inventory each project` heading:

````markdown
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
      '{context:"cai_fallback", message:("CAI query failed for \($s): \($r). Falling back to per-project loop for its projects. To enable the fast path: gcloud services enable cloudasset.googleapis.com --project=<quota-project> ; gcloud \($s|split("/")[0]) add-iam-policy-binding \($s|split("/")[1]) --member=user:<you> --role=roles/cloudasset.viewer")}' \
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
jq -s 'add // [] | unique_by(.uid // "\(.project)/\(.serviceAccount)/\(.keyId)")' \
  "${SESSION_DIR}/creds.cai.json.parts" > "${SESSION_DIR}/creds.cai.json" 2>/dev/null || echo '[]' > "${SESSION_DIR}/creds.cai.json"
# De-dupe uncovered (a project listed standalone won't also be covered, but guard anyway).
sort -u "${SESSION_DIR}/uncovered.txt" -o "${SESSION_DIR}/uncovered.txt"
echo "cai_credentials=$(jq length "${SESSION_DIR}/creds.cai.json") covered_projects=$(sort -u "${SESSION_DIR}/covered.txt" 2>/dev/null | wc -l)"
```

**Resilience:** if Task 1 found `restrictions` (keys) or `keyType` (SA keys) absent from `versionedResources`, replace that one `gcloud asset search-all-resources … --read-mask='*'` call with
`gcloud asset list --$(echo "$SCOPE" | sed 's#s/.*##')=$(echo "$SCOPE" | cut -d/ -f2) --content-type=resource --asset-types="$TYPE" --format=json`
and read the resource from `.[].resource.data` instead of `.versionedResources[0].resource`.
````

- [ ] **Step 5: Validate CI + commit**

Run: `python .github/scripts/validate_schemas.py` → expected `All schemas + frontmatter OK.`

```bash
git add skills/gcp-credentials-audit/SKILL.md
git commit -m "feat(credentials-audit): add CAI fast-path inventory (Step C1)" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Step C2 — per-project loop over the uncovered set, emitting the unified record shape

The existing loop is kept verbatim except (a) it iterates `uncovered.txt` instead of `projects.txt`, and (b) a closing assembly turns its raw files into `creds.loop.json` with the same record shape as `creds.cai.json`.

**Files:** Modify `skills/gcp-credentials-audit/SKILL.md` (the current Step C block, lines ~57–87).

- [ ] **Step 1: Rename the heading and change the loop input**

Change `### Step C: Inventory each project` to `### Step C2: Per-project fallback (uncovered projects)` and its intro to: *"For each `$P` in `uncovered.txt` (standalone projects + any scope CAI couldn't read), run the original per-project inventory. This path is unchanged and READ-ONLY."*

In the loop's `done < "${SESSION_DIR}/projects.txt"` line, change the input to `done < "${SESSION_DIR}/uncovered.txt"`.

Also make the existing `PERMISSION_DENIED` handling write a file (Task 6 reads it): where the loop records a skipped project, append `{"projectId":"$P","reason":"no_access"}` to `${SESSION_DIR}/skipped.json.parts`, and after the loop add:
```bash
jq -s '.' "${SESSION_DIR}/skipped.json.parts" > "${SESSION_DIR}/skipped.json" 2>/dev/null \
  || echo '[]' > "${SESSION_DIR}/skipped.json"
```

- [ ] **Step 2: Append the loop→record assembly (verification first)**

Verify the assembly jq against sample describe-output before embedding. The per-key describe files (`raw/${P}.key.${uid}.json`) are full `Key` resources; SA-key list files (`raw/${P}.sakeys.${sa}.json`) are arrays of `{name, validAfterTime, keyType}`.

```bash
cat > /tmp/key.describe.json <<'JSON'
{"uid":"k1","displayName":"legacy","createTime":"2023-01-01T00:00:00Z"}
JSON
jq -n --slurpfile k /tmp/key.describe.json --arg p "gamma" \
  '[$k[0] | {type:"api_key",project:$p,uid:.uid,displayName:(.displayName//""),createTime:.createTime,restrictions:(.restrictions//null),lastUsedAt:null}]'
```
Expected:
```json
[{"type":"api_key","project":"gamma","uid":"k1","displayName":"legacy","createTime":"2023-01-01T00:00:00Z","restrictions":null,"lastUsedAt":null}]
```

- [ ] **Step 3: Insert the assembly block after the loop**

After the `done < "${SESSION_DIR}/uncovered.txt"` block, add:

````markdown
```bash
# Assemble loop raw files into the unified record shape (same as creds.cai.json).
: > "${SESSION_DIR}/creds.loop.json.parts"
while read P; do
  for KF in "${SESSION_DIR}"/raw/"${P}".key.*.json; do
    [ -e "$KF" ] || continue
    jq --arg p "$P" '[{type:"api_key",project:$p,uid:.uid,
      displayName:(.displayName//""),createTime:.createTime,
      restrictions:(.restrictions//null),lastUsedAt:null}]' "$KF" \
      >> "${SESSION_DIR}/creds.loop.json.parts"
  done
  for SF in "${SESSION_DIR}"/raw/"${P}".sakeys.*.json; do
    [ -e "$SF" ] || continue
    jq --arg p "$P" '[ .[] | select((.keyType//.key_type)=="USER_MANAGED")
      | {type:"sa_key",project:$p,
         serviceAccount:(.name|capture("serviceAccounts/(?<sa>[^/]+)/keys/")|.sa),
         keyId:(.name|sub(".*/keys/";"")),
         createTime:(.validAfterTime//.valid_after_time),lastUsedAt:null} ]' "$SF" \
      >> "${SESSION_DIR}/creds.loop.json.parts"
  done
done < "${SESSION_DIR}/uncovered.txt"
jq -s 'add // []' "${SESSION_DIR}/creds.loop.json.parts" > "${SESSION_DIR}/creds.loop.json" 2>/dev/null \
  || echo '[]' > "${SESSION_DIR}/creds.loop.json"
```
````

- [ ] **Step 4: Validate CI + commit**

Run: `python .github/scripts/validate_schemas.py` → `All schemas + frontmatter OK.`

```bash
git add skills/gcp-credentials-audit/SKILL.md
git commit -m "feat(credentials-audit): scope loop to uncovered set + unify record shape (Step C2)" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Step D — batched per-project last-used

Replace the per-key Monitoring loop with one `timeSeries.list` per project, grouped by `credential_id`. **API-key semantics only** (the metric keys API usage as `apikey:<uid>`); SA-key `lastUsedAt` stays `null`, exactly as today.

**Files:** Modify `skills/gcp-credentials-audit/SKILL.md` (Step D, lines ~89–110).

- [ ] **Step 1: Verify the response-parsing jq first**

```bash
cat > /tmp/ts.sample.json <<'JSON'
{"timeSeries":[
 {"metric":{"labels":{"credential_id":"apikey:k-unrestricted"}},
  "points":[{"interval":{"endTime":"2026-06-01T00:00:00Z"},"value":{"int64Value":"5"}},
            {"interval":{"endTime":"2026-05-30T00:00:00Z"},"value":{"int64Value":"2"}}]},
 {"metric":{"labels":{"credential_id":"apikey:k-idle"}},
  "points":[{"interval":{"endTime":"2026-05-01T00:00:00Z"},"value":{"int64Value":"0"}}]}
]}
JSON
jq '[ .timeSeries[]?
      | { cid: .metric.labels.credential_id,
          last: ([ .points[]? | select(((.value.int64Value // .value.doubleValue // 0)|tonumber) > 0)
                   | .interval.endTime ] | sort | last) }
      | select(.last != null) ]
    | map({(.cid): .last}) | add // {}' /tmp/ts.sample.json
```
Expected (idle key with only zero-points is dropped):
```json
{"apikey:k-unrestricted":"2026-06-01T00:00:00Z"}
```

- [ ] **Step 2: Run it** — confirm the output matches exactly.

- [ ] **Step 3: Replace Step D in the skill**

Replace the Step D body (the per-key comment block) with one query per project that has ≥1 api_key credential, then a join back onto `creds.json`:

````markdown
```bash
TOKEN=$(gcloud auth application-default print-access-token)
LOOKBACK_DAYS="${LOOKBACK_DAYS:-30}"
START=$(date -u -v-${LOOKBACK_DAYS}d +%Y-%m-%dT00:00:00Z 2>/dev/null \
        || date -u -d "${LOOKBACK_DAYS} days ago" +%Y-%m-%dT00:00:00Z)
END=$(date -u +%Y-%m-%dT00:00:00Z)

# Merge both inventory paths first (Step E consumes creds.json).
jq -s 'add // []' "${SESSION_DIR}/creds.cai.json" "${SESSION_DIR}/creds.loop.json" \
  > "${SESSION_DIR}/creds.json"

# One Monitoring query per project holding api_key credentials; group by credential_id.
echo '{}' > "${SESSION_DIR}/lastused.json"
for P in $(jq -r '[.[]|select(.type=="api_key")|.project]|unique[]' "${SESSION_DIR}/creds.json"); do
  RESP=$(curl -s -G "https://monitoring.googleapis.com/v3/projects/${P}/timeSeries" \
    -H "Authorization: Bearer ${TOKEN}" \
    --data-urlencode 'filter=metric.type="serviceruntime.googleapis.com/api/request_count"' \
    --data-urlencode "interval.startTime=${START}" \
    --data-urlencode "interval.endTime=${END}" \
    --data-urlencode 'aggregation.alignmentPeriod=86400s' \
    --data-urlencode 'aggregation.perSeriesAligner=ALIGN_SUM' \
    --data-urlencode 'aggregation.groupByFields=metric.label.credential_id' 2>/dev/null)
  echo "$RESP" | jq '[ .timeSeries[]?
        | { cid:.metric.labels.credential_id,
            last:([ .points[]? | select(((.value.int64Value // .value.doubleValue // 0)|tonumber)>0)
                    | .interval.endTime ]|sort|last) }
        | select(.last!=null) ] | map({(.cid):.last}) | add // {}' \
    > "${SESSION_DIR}/lastused.${P}.json" 2>/dev/null || echo '{}' > "${SESSION_DIR}/lastused.${P}.json"
  jq -s '.[0]*.[1]' "${SESSION_DIR}/lastused.json" "${SESSION_DIR}/lastused.${P}.json" \
    > "${SESSION_DIR}/lastused.tmp" && mv "${SESSION_DIR}/lastused.tmp" "${SESSION_DIR}/lastused.json"
done

# Join: api_key.lastUsedAt = lastused["apikey:"+uid]; sa_key stays null (unchanged behaviour).
jq --slurpfile lu "${SESSION_DIR}/lastused.json" '
  [ .[] | if .type=="api_key"
          then .lastUsedAt = ($lu[0]["apikey:" + .uid] // null)
          else . end ]' "${SESSION_DIR}/creds.json" > "${SESSION_DIR}/creds.enriched.json"
mv "${SESSION_DIR}/creds.enriched.json" "${SESSION_DIR}/creds.json"
```

Treat any missing/empty Monitoring response as `lastUsedAt: null` and append a non-fatal entry to `errors[]`.
````

- [ ] **Step 4: Update Step E's input reference**

In Step E, ensure the classification reads `${SESSION_DIR}/creds.json` (the merged+enriched array) as `$CREDS_JSON` source — i.e. the records to classify are `creds.json`, each gaining `riskClass` + `riskReason`. If Step E previously described building `$CREDS_JSON` ad hoc, change that sentence to: *"Load the merged, enriched records from `creds.json`; for each, add `riskClass` + `riskReason` per the taxonomy."*

- [ ] **Step 5: Validate CI + commit**

Run: `python .github/scripts/validate_schemas.py` → `All schemas + frontmatter OK.`

```bash
git add skills/gcp-credentials-audit/SKILL.md
git commit -m "perf(credentials-audit): batch last-used to one Monitoring query per project (Step D)" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Wire the CAI-fallback errors into `audit.json`

The `cai-errors.json.parts` entries emitted in Step C1 must reach `audit.json`'s `errors[]`.

**Files:** Modify `skills/gcp-credentials-audit/SKILL.md` (Step E's final `jq -n` assembly, lines ~117–125).

- [ ] **Step 1: Verify the errors-merge jq**

```bash
printf '%s\n' '{"context":"cai_fallback","message":"CAI query failed for organizations/700: ..."}' > /tmp/cai-errors.parts
jq -s '.' /tmp/cai-errors.parts
```
Expected: a one-element array with that object. Confirm it validates as an `errors[]` item (has `context` + `message`).

- [ ] **Step 2: Fold cai-errors into the final assembly**

In Step E's `jq -n … '{schemaVersion…, errors:$errs}'`, build `$errs` to include the CAI fallback entries. Change the assembly to read both the run's other errors and `cai-errors.json.parts`:

````markdown
```bash
CAI_ERRS=$(jq -s '.' "${SESSION_DIR}/cai-errors.json.parts" 2>/dev/null || echo '[]')
jq -n --argjson creds "$CREDS_JSON" --argjson scope "$SCOPE_JSON" \
      --argjson errs "$ERRS_JSON" --argjson caiErrs "$CAI_ERRS" '
{
  schemaVersion: 1,
  generatedAt: (now | strftime("%Y-%m-%dT%H:%M:%SZ")),
  scope: $scope,
  credentials: $creds,
  errors: ($errs + $caiErrs)
}' > "${SESSION_DIR}/audit.json.tmp" \
  && mv "${SESSION_DIR}/audit.json.tmp" "${SESSION_DIR}/audit.json"
```
````

- [ ] **Step 3: Build `$SCOPE_JSON` from the coverage files**

Replace Step E's scope construction with this self-contained build (it depends only on files this plan defines, so it doesn't matter how the old Step E named its intermediates). `projectsScanned` = CAI-covered ∪ (loop-attempted − skipped); `projectsSkipped` = the loop's `no_access` projects.

```bash
USER=$(jq -r '.user // empty' "${SESSION_DIR}/scope.local.json" 2>/dev/null)
[ -n "$USER" ] || USER=$(gcloud config get-value account 2>/dev/null)
SKIPPED=$(cat "${SESSION_DIR}/skipped.json" 2>/dev/null || echo '[]')
SCANNED=$(jq -n --argjson skip "$SKIPPED" \
  --rawfile cov "${SESSION_DIR}/covered.txt" \
  --rawfile unc "${SESSION_DIR}/uncovered.txt" '
  (($cov/"\n") + ($unc/"\n") | map(select(length>0))) as $all
  | ($skip | map(.projectId)) as $sk
  | ($all - $sk) | unique')
SCOPE_JSON=$(jq -n --arg u "$USER" --argjson scanned "$SCANNED" --argjson skipped "$SKIPPED" \
  '{user:$u, projectsScanned:$scanned, projectsSkipped:$skipped}')
```

(`covered.txt`, `uncovered.txt`, and `skipped.json` are always created — empty if unused — by Tasks 3, 2, and 4 respectively, so the `--rawfile` reads never fail.)

- [ ] **Step 4: Validate CI + commit**

Run: `python .github/scripts/validate_schemas.py` → `All schemas + frontmatter OK.`

```bash
git add skills/gcp-credentials-audit/SKILL.md
git commit -m "feat(credentials-audit): surface CAI-fallback recommendations in errors[]" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: Step F — coverage summary + runtime schema self-check

**Files:** Modify `skills/gcp-credentials-audit/SKILL.md` (Step F).

- [ ] **Step 1: Verify the self-check command both ways**

```bash
python3 - <<'PY'  # ensure jsonschema present
import importlib,sys; sys.exit(0 if importlib.util.find_spec("jsonschema") else 1)
PY
echo "jsonschema present: $?"
# good doc passes, bad doc fails:
printf '{"schemaVersion":1,"generatedAt":"2026-06-05T00:00:00Z","scope":{"user":"u","projectsScanned":[],"projectsSkipped":[]},"credentials":[],"errors":[]}' > /tmp/good.json
printf '{"schemaVersion":2}' > /tmp/bad.json
for f in /tmp/good.json /tmp/bad.json; do
  python3 -m jsonschema -i "$f" skills/gcp-credentials-audit/output.schema.json \
    && echo "$f OK" || echo "$f INVALID"
done
```
Expected: `/tmp/good.json OK` and `/tmp/bad.json INVALID`. (If `python3 -m jsonschema` CLI is unavailable, the skill's self-check falls back to a structural `jq -e` check — see Step 2.)

- [ ] **Step 2: Append the self-check + coverage summary to Step F**

Replace Step F's summary block with:

````markdown
```bash
# Runtime self-check: the produced audit.json must match output.schema.json.
SCHEMA=""
for c in "skills/gcp-credentials-audit/output.schema.json" \
         "${HOME}/.claude/skills/gcp-credentials-audit/output.schema.json"; do
  [ -f "$c" ] && SCHEMA="$c" && break
done
if [ -n "$SCHEMA" ] && python3 -m jsonschema -i "${SESSION_DIR}/audit.json" "$SCHEMA" >/dev/null 2>&1; then
  echo "audit.json: schema-valid"
else
  # Fallback structural check if the jsonschema CLI isn't installed.
  jq -e '.schemaVersion==1 and (.credentials|type=="array") and (.errors|type=="array")' \
    "${SESSION_DIR}/audit.json" >/dev/null \
    && echo "audit.json: structural check OK (install 'jsonschema' for full validation)" \
    || { echo "audit.json: FAILED validation"; }
fi

CAI_N=$(sort -u "${SESSION_DIR}/covered.txt" 2>/dev/null | wc -l | tr -d ' ')
LOOP_N=$(sort -u "${SESSION_DIR}/uncovered.txt" 2>/dev/null | wc -l | tr -d ' ')
echo "Coverage: ${CAI_N} project(s) via CAI fast path, ${LOOP_N} via per-project fallback."
```

Then print the one-paragraph summary (counts by risk class), appended with the coverage line above.
````

- [ ] **Step 3: Document the inputs note** — in the skill's "Inputs" section, add: *"`AUDIT_VERIFY_PARITY` (optional): when `1`, also runs the per-project loop over CAI-covered projects and diffs the inventories (see Parity mode). Off by default."*

- [ ] **Step 4: Validate CI + commit**

Run: `python .github/scripts/validate_schemas.py` → `All schemas + frontmatter OK.`

```bash
git add skills/gcp-credentials-audit/SKILL.md
git commit -m "feat(credentials-audit): coverage summary + runtime audit.json self-check (Step F)" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: Parity mode (`AUDIT_VERIFY_PARITY`)

A documented, opt-in correctness gate that proves the CAI path and the loop agree on raw inventory.

**Files:** Modify `skills/gcp-credentials-audit/SKILL.md` (new "## Parity mode" section near the end).

- [ ] **Step 1: Verify the diff jq**

```bash
cat > /tmp/a.json <<'JSON'
[{"type":"api_key","project":"alpha","uid":"k1","createTime":"2025-01-01T00:00:00Z","restrictions":null}]
JSON
cat > /tmp/b.json <<'JSON'
[{"type":"api_key","project":"alpha","uid":"k1","createTime":"2025-01-01T00:00:00Z","restrictions":null}]
JSON
norm='sort_by(.uid // "\(.project)/\(.serviceAccount)/\(.keyId)")
      | map({type,project,uid,serviceAccount,keyId,createTime,restrictions})'
diff <(jq -S "$norm" /tmp/a.json) <(jq -S "$norm" /tmp/b.json) && echo "PARITY OK" || echo "PARITY MISMATCH"
```
Expected: `PARITY OK`. (Flip one field in `/tmp/b.json` and confirm it prints `PARITY MISMATCH`.)

- [ ] **Step 2: Add the Parity mode section**

````markdown
## Parity mode (`AUDIT_VERIFY_PARITY=1`)

A one-time correctness check that the CAI fast path and the per-project loop produce the **same raw inventory**. Off by default (it runs both paths, defeating the speedup). When `AUDIT_VERIFY_PARITY=1`:

1. After Step C1, also run the Step C2 loop over the **covered** projects into a separate `creds.loopcheck.json` (do not let it touch `creds.json`).
2. Diff against the CAI records on the raw inventory fields only:

```bash
norm='sort_by(.uid // "\(.project)/\(.serviceAccount)/\(.keyId)")
      | map({type,project,uid,serviceAccount,keyId,createTime,restrictions})'
if diff <(jq -S "$norm" "${SESSION_DIR}/creds.cai.json") \
        <(jq -S "$norm" "${SESSION_DIR}/creds.loopcheck.json"); then
  echo "PARITY OK — CAI inventory matches the loop."
else
  echo "PARITY MISMATCH — investigate the field mapping before trusting the fast path."
fi
```

A mismatch is a real defect in the CAI field mapping; fix before relying on the fast path.
````

- [ ] **Step 3: Validate CI + commit**

Run: `python .github/scripts/validate_schemas.py` → `All schemas + frontmatter OK.`

```bash
git add skills/gcp-credentials-audit/SKILL.md
git commit -m "test(credentials-audit): add opt-in CAI/loop parity mode" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Update `docs/design.md`

**Files:** Modify `docs/design.md`.

- [ ] **Step 1: Remove the cross-org non-goal**

Delete the line (currently `:171`):
```
- Cross-org / multi-tenant operation.
```
from the "Not in v1 (PRs welcome)" list.

- [ ] **Step 2: Add a fast-path note to the architecture section**

After the "Execution: four phases" text block (before "## Auto-apply safety matrix"), add:

```markdown
### Inventory fast-path (Cloud Asset Inventory)

`gcp-credentials-audit` inventories keys via org/folder-scoped Cloud Asset Inventory
(`apikeys.googleapis.com/Key`, `iam.googleapis.com/ServiceAccountKey`) when
`cloudasset.googleapis.com` is enabled and the caller has `roles/cloudasset.viewer` on
the scope — collapsing the per-project loop into a few queries across many projects.
Projects not covered by a successful CAI query (standalone projects, or scopes the
caller can't read) transparently fall back to the per-project loop. The audit never
enables CAI itself (READ-ONLY); when CAI is absent it completes via the loop and emits
the exact `gcloud services enable …` / `add-iam-policy-binding …` commands to unlock the
fast path next run.
```

- [ ] **Step 3: Add an edge-case row**

In the "## Errors & edge cases" table, add:
```markdown
| CAI not enabled / no `cloudasset.viewer` on a scope | That scope's projects fall back to the per-project loop; a recommendation with the exact enable/grant commands is added to `errors[]`. |
```

- [ ] **Step 4: Commit**

```bash
git add docs/design.md
git commit -m "docs(design): promote cross-org inventory to scope; document CAI fast-path" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: Update `docs/threat-model.md`

**Files:** Modify `docs/threat-model.md`.

- [ ] **Step 1: Update the cross-org limitation row**

Change the "Known limitations" row (currently `:77`):
```
| Cross-org operation unsupported | Out of v1 scope; PR welcome. |
```
to:
```
| Cross-org *apply* unsupported | The audit inventory now reads across orgs/folders via Cloud Asset Inventory; the APPLY phases (guardrails, key-restrictions) remain per-project. |
```

- [ ] **Step 2: Note the CAI read scope in the trust-boundary diagram**

In the GCP box of the trust-boundary diagram, add `Cloud Asset Inventory (read-only)` under `Cloud Monitoring`.

- [ ] **Step 3: Add a mitigations note**

In "Concrete mitigations in place", add:
```markdown
| Over-broad access for the fast path | CAI access is **read-only** and requires only `roles/cloudasset.viewer` at the org/folder; the audit never enables the API or modifies IAM — missing access degrades to the per-project loop, it does not escalate. |
```

- [ ] **Step 4: Commit**

```bash
git add docs/threat-model.md
git commit -m "docs(threat-model): note CAI read scope; clarify cross-org apply remains out of scope" \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: Live integration check (real multi-org account)

**Files:** none (verification).

- [ ] **Step 1: Run the audit standalone**

```bash
SESSION_DIR=/tmp/gcp-ironclad/cai-test-$(date -u +%Y%m%dT%H%M%SZ)
mkdir -p "$SESSION_DIR/raw"; export SESSION_DIR
# Invoke the gcp-credentials-audit skill (or run its Steps A–F).
```
Expected: completes; final line reads `Coverage: <N> project(s) via CAI fast path, <M> via per-project fallback.` with N > 0 on an org where CAI is enabled.

- [ ] **Step 2: Confirm the recommendation path**

On an org where CAI is **not** enabled, confirm `audit.json`'s `errors[]` contains a `cai_fallback` entry with the exact enable/grant commands, and those projects still appear in `credentials`/`projectsScanned` (loop ran).

- [ ] **Step 3: Run parity mode once**

```bash
AUDIT_VERIFY_PARITY=1 SESSION_DIR="$SESSION_DIR" # re-run the skill
```
Expected: `PARITY OK — CAI inventory matches the loop.` If `PARITY MISMATCH`, fix the field mapping (Task 3) before merging.

- [ ] **Step 4: Confirm schema validity**

```bash
python3 -m jsonschema -i "$SESSION_DIR/audit.json" skills/gcp-credentials-audit/output.schema.json && echo VALID
```
Expected: `VALID`.

- [ ] **Step 5: Open the PR**

```bash
git push -u origin feat/cai-inventory-fast-path
gh pr create --fill --base main
```
Include the Task 1 field-shape findings and the parity result in the PR body.

---

## Self-review notes

- **Spec coverage:** discovery/coverage map → T2; CAI fast path + field mapping + dedupe + resilience → T3; loop fallback over uncovered → T4; batched Step D → T5; read-only recommendation in errors[] → T3 (emit) + T6 (wire); schema-stable `audit.json` → record shape + T6/T7; coverage summary + self-check → T7; parity check → T8; design.md non-goal + note → T9; threat-model read scope → T10; live parity/verification items → T1 + T11. No spec section is unmapped.
- **READ-ONLY:** no task enables an API or mutates IAM; CAI failure → loop + recommendation only.
- **Type/name consistency:** `creds.cai.json`, `creds.loop.json`, `creds.json`, `projnum-to-id.json`, `cai-scopes.txt`, `covered.txt`, `uncovered.txt`, `lastused.json`, `cai-errors.json.parts` are used consistently across T2–T8; the record shape is identical in T3 and T4; the parity normalizer (T8) compares the same fields the records define.
