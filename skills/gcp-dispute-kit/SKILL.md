---
name: gcp-dispute-kit
description: Use to assemble a dispute-grade evidence packet and ready-to-file letters after GCP API-key fraud (leaked-key abuse, runaway Gemini/Vertex charges). READ-ONLY — mutates nothing. Triggers on "dispute gcp charges", "google cloud fraud refund", "gemini api fraud dispute", "gcp billing dispute", "chargeback google cloud".
---

# GCP Dispute Kit (READ-ONLY)

## Overview

Assembles everything a fraud victim needs to file: an exhibit-backed evidence
summary, ready-to-file letters for their situation and jurisdiction (Google +
India + US tracks), and a filing-sequence README with a deadline tracker.
Formalizes the practice in `docs/incident-story.md`. **Mutates no cloud state.**

Three entry states, three different products:

| State | Meaning | You get |
|---|---|---|
| `BLEEDING` | Spend is spiking right now | `checklists/emergency-stop.md` — nothing else until the bleeding stops |
| `FRESH` | Incident over, nothing filed | Full packet + Google console-dispute letter |
| `STUCK` | Dispute filed but stalled | Packet + escalation letters (Google reply + IN/US external tracks) |

## When to Use

- After a leaked-key incident, once spend is back to normal, to prepare the dispute.
- When an existing dispute is stalled: ghosted, partial offer, denied, or a refund that never landed.
- NOT while spend is actively spiking — the kit will hand you the emergency-stop checklist and halt.

## Inputs

- `SESSION_DIR` env var (optional): defaults to `/tmp/gcp-dispute-kit/$(date -u +%Y-%m-%dT%H-%M-%SZ)/`.
- Intake answers from the victim (Phase 0). Everything else is discovered.

## Outputs

`${SESSION_DIR}/packet/` — `README.md`, `evidence-summary.md`, `letters/`, `exhibits/`, `manifest.json` (validated against this skill's `output.schema.json`).

## Safety

- Every command in this skill is read-only (`list` / `describe` / `query`). No `update`, `enable`, `disable`, `create`, or `delete` verbs anywhere except inside `checklists/emergency-stop.md`, which the *victim* runs by hand in a live emergency.
- A letter with an unresolved `{{placeholder}}` is never emitted — `scripts/render.py` hard-errors instead.
- Claims are confidence-marked: billing-export-backed > CSV-backed > victim-stated. Never present a victim-stated number as data-backed.

## Execution

`SKILL_DIR` below is this skill's directory (where SKILL.md lives).

### Phase 0 — Intake and classification

Ask the victim (conversationally, all of it):

1. Is spend still spiking **right now**? (check: Console → Billing → Reports, last 48h hourly — or run the query in Phase 1c)
2. Has a dispute already been filed with Google? Case number? How many days ago? What was Google's last response?
3. Incident window (start/end, UTC, best known), discovery time, disputed amount + currency.
4. What mitigation was taken, and when (key disabled/restricted, APIs disabled)?
5. Jurisdictions that apply: India (IN), United States (US), both, or neither.
6. Which data sources exist: BigQuery billing export? Console access for a CSV/invoice download? A prior `gcp-credentials-audit` run (`audit.json`)?

Write the answers to `${SESSION_DIR}/intake.json` with at minimum:

```json
{ "activeSpike": false, "disputeFiled": true, "jurisdictions": ["IN"] }
```

Classify:

```bash
SESSION_DIR="${SESSION_DIR:-/tmp/gcp-dispute-kit/$(date -u +%Y-%m-%dT%H-%M-%SZ)}"
mkdir -p "${SESSION_DIR}/packet/letters" "${SESSION_DIR}/packet/exhibits" "${SESSION_DIR}/raw"
python3 "${SKILL_DIR}/scripts/classify_state.py" --intake "${SESSION_DIR}/intake.json" \
  | tee "${SESSION_DIR}/classification.json"
```

**If state is `BLEEDING`: STOP.** Show the victim `checklists/emergency-stop.md` verbatim and end the run. Do not collect evidence while the meter runs.

### Phase 1 — Evidence collection (read-only, every source optional)

Record every source's availability; a missing source becomes a `gaps[]` entry with a manual action, never a failure.

**1a. BigQuery billing export (preferred).** Discover, then extract the baseline + incident rows in canonical form:

```bash
bq ls --format=json | jq -r '.[].datasetReference.datasetId' | grep -i billing || echo "NO EXPORT"
# If a table exists (gcp_billing_export_v1_XXXXXX):
bq query --use_legacy_sql=false --format=csv '
SELECT
  FORMAT_TIMESTAMP("%Y-%m-%dT%H:00:00Z", usage_start_time) AS usage_start_time,
  service.description AS service,
  sku.description AS sku,
  SUM(cost) AS cost,
  currency
FROM `PROJECT.DATASET.TABLE`
WHERE usage_start_time >= TIMESTAMP("BASELINE_START")
  AND usage_start_time <  TIMESTAMP("INCIDENT_END")
GROUP BY 1,2,3,5 ORDER BY 1' > "${SESSION_DIR}/raw/billing-normalized.csv"
```

**1b. Billing CSV (fallback).** Have the victim download the cost table CSV (Console → Billing → Reports → filter to the baseline+incident date range → Download CSV). Then **normalize it yourself** to the canonical header `usage_start_time,service,sku,cost,currency` (map/rename columns, ISO-ify dates; daily granularity is acceptable — peak-hour metrics will then be unavailable and must be marked as such). Save as `${SESSION_DIR}/raw/billing-normalized.csv`.

**1c. Per-key attribution (Cloud Monitoring).**

```bash
for P in $(echo "$PROJECT_IDS" | tr ',' ' '); do
  gcloud monitoring time-series list --project="$P" \
    --filter='metric.type="serviceruntime.googleapis.com/api/request_count"' \
    --interval-start-time="INCIDENT_START" --interval-end-time="INCIDENT_END" \
    --format=json > "${SESSION_DIR}/raw/request-count-${P}.json" || echo "monitoring unavailable for $P"
done
```

**1d. Key inventory.** Reuse a prior audit if present, else list directly:

```bash
ls /tmp/gcp-ironclad/*/audit.json 2>/dev/null | tail -1   # reuse if found
gcloud services api-keys list --project="$P" --format=json > "${SESSION_DIR}/raw/api-keys-${P}.json"
```

**1e. Key lifecycle timestamps (mitigation timeline).**

```bash
gcloud services api-keys describe KEY_UID --project="$P" --format=json   # createTime / updateTime
```

Copy each collected raw file into `packet/exhibits/` as `EX-NN-<name>`, and record in the manifest: exhibit id, file, and the **exact command** that produced it (`producedBy`).

### Phase 2 — Fraud-signature analysis

```bash
python3 "${SKILL_DIR}/scripts/analyze_billing.py" \
  --csv "${SESSION_DIR}/raw/billing-normalized.csv" \
  --baseline-start "BASELINE_START" --baseline-end "INCIDENT_DATE" \
  --incident-start "INCIDENT_START" --incident-end "INCIDENT_END" \
  | tee "${SESSION_DIR}/analysis.json"
cp "${SESSION_DIR}/analysis.json" "${SESSION_DIR}/packet/exhibits/EX-02-analysis.json"
```

Interpretation duties (yours, not the script's):

- Write `model_variety_summary` from `topSkus` (name the model families).
- Write `impossible_volume_summary` from usage volumes if the export has them; otherwise from cost-implied volumes — and mark the claim CSV-backed or victim-stated accordingly.
- **Never claim source IPs.** Attribution is per-key, per-window only.
- If only daily granularity exists, omit peak-hour language from the narrative values (write "within a single day" phrasing instead).

### Phase 3 — Packet assembly

Build `${SESSION_DIR}/values.json` covering every placeholder in
`templates/placeholders.json` that the selected templates use (check a
template's needs with `render.py --template T --list`). Numeric values come
from `analysis.json`; narrative values you write per Phase 2; victim facts
from intake.

Render each selected letter (list from `classification.json`) plus the README
and evidence summary:

```bash
for T in $(jq -r '.letters[]' "${SESSION_DIR}/classification.json") \
         templates/packet-README.template.md templates/evidence-summary.template.md; do
  OUT="${SESSION_DIR}/packet/$(basename "$T" | sed 's/\.template//')"
  case "$T" in templates/google/*|templates/india/*|templates/us/*) OUT="${SESSION_DIR}/packet/letters/$(basename "$T" | sed 's/\.template//')";; esac
  python3 "${SKILL_DIR}/scripts/render.py" --template "${SKILL_DIR}/${T}" \
    --values "${SESSION_DIR}/values.json" --out "$OUT" || exit 1
done
mv "${SESSION_DIR}/packet/packet-README.md" "${SESSION_DIR}/packet/README.md"
```

Write `${SESSION_DIR}/packet/manifest.json` per `output.schema.json`
(state, jurisdictions, amounts, incidentWindow, analysis numbers, sources with
availability, letters emitted, exhibits with `producedBy`, gaps with manual
actions). Validate — house pattern, jsonschema with jq structural fallback:

```bash
python3 - <<EOF || jq -e '.schemaVersion==1 and .state and (.letters|length>0) and (.exhibits|length>0)' "${SESSION_DIR}/packet/manifest.json"
import json, sys, pathlib
try:
    import jsonschema
except ImportError:
    sys.exit(1)
skill = pathlib.Path("${SKILL_DIR}")
jsonschema.validate(
    json.loads(pathlib.Path("${SESSION_DIR}/packet/manifest.json").read_text()),
    json.loads((skill / "output.schema.json").read_text()),
)
print("manifest OK")
EOF
```

Finally, walk the victim through `packet/README.md`: the filing order, the
deadline tracker (fill `deadline_tracker_rows` with real dates — the India
bank track runs from the statement date and is the most time-sensitive), the
do-not-pay rule, and the manual-attachments list.
