# GCP API-Key Ironclad Suite

A driver skill (`gcp-ironclad`) plus six focused skills that together audit, safely harden, and recover from API-key fraud across all GCP projects you can access.

## Skills in this suite

| Skill | Phase | Purpose |
|---|---|---|
| `gcp-ironclad` | Driver | Runs the four sub-skills in order; merges outputs into one report |
| `gcp-credentials-audit` | READ-ONLY | Inventory of every API key + user-managed SA key with risk class |
| `gcp-cost-anomaly-scan` | READ-ONLY | Detects past spend spikes in your billing-export data |
| `gcp-spend-guardrails` | APPLY | Quota caps on Gemini API + budget alerts + disable idle paid APIs |
| `gcp-key-restrictions` | APPLY | Restrict unrestricted API keys to APIs they actually use |
| `gcp-spend-cap-setup` | GUIDED | Walks you through Google's console-only hard spend caps (Preview) with discovery, sizing, and verification |
| `gcp-dispute-kit` | READ-ONLY | Assembles a dispute-grade evidence packet + ready-to-file letters after fraud |

## Directory layout

All seven skills live together inside this suite folder:

```
~/.claude/skills/gcp-ironclad-suite/
├── README.md                       (this file)
├── gcp-ironclad/                   driver
│   ├── SKILL.md
│   └── final-report.template.md
├── gcp-credentials-audit/          READ-ONLY
│   ├── SKILL.md
│   └── output.schema.json
├── gcp-cost-anomaly-scan/          READ-ONLY
│   ├── SKILL.md
│   └── output.schema.json
├── gcp-spend-guardrails/           APPLY
│   ├── SKILL.md
│   └── output.schema.json
├── gcp-key-restrictions/           APPLY
│   ├── SKILL.md
│   └── output.schema.json
├── gcp-spend-cap-setup/            GUIDED
│   ├── SKILL.md
│   └── output.schema.json
└── gcp-dispute-kit/                READ-ONLY
    ├── SKILL.md
    ├── templates/
    └── output.schema.json
```

For Claude Code skill discovery (which scans the immediate children of `~/.claude/skills/`), each of the seven sub-folders is also exposed at `~/.claude/skills/<skill-name>/` via a symlink that points back into this suite folder. You can edit either path — both resolve to the same files. To remove the suite cleanly:

```bash
rm -rf ~/.claude/skills/gcp-ironclad-suite
for d in gcp-ironclad gcp-credentials-audit gcp-cost-anomaly-scan \
         gcp-spend-guardrails gcp-key-restrictions \
         gcp-spend-cap-setup gcp-dispute-kit; do
  rm -f ~/.claude/skills/$d
done
```

## Usage

In Claude Code, invoke the driver:

> "Use the gcp-ironclad skill to harden my GCP API keys"

The driver auto-discovers project + billing scope from your `gcloud` context (no IDs to hard-code).

## Safety guarantees

- Two READ-ONLY phases run first; you see the audit before anything mutates.
- Active-spike halt: if any project is currently bleeding (>10× baseline in last 24h), Phase 3 (mutating) does NOT run.
- Every action is gated on "current state ≠ desired state" — re-runs are no-ops.
- `--dry-run` flag runs all phases without mutating.
- Destructive items (key deletion, IAM changes, billing-account close) are NEVER auto-applied — only flagged with the exact `gcloud` command for human review.

See `docs/superpowers/specs/2026-05-24-gcp-api-key-ironclad-skill-design.md` in the source repo for the full design.

## Requirements

- `gcloud` SDK ≥ 470
- `bq` CLI
- `jq`
- ADC credentials (`gcloud auth application-default login`)
- The `gcp-finops` MCP server, OR direct BigQuery access to billing-export tables
