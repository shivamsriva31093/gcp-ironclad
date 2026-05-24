# GCP Ironclad

> Automated API-key audit and safe spend hardening for Google Cloud, run from Claude Code.
> Built after an unrestricted API key racked up **~$80,000 (≈₹67 lakh) of fraudulent Gemini API charges in 8 hours overnight**.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) ![Skills](https://img.shields.io/badge/Claude%20Code%20skills-5-blue) ![MCP server](https://img.shields.io/badge/MCP%20server-gcp--finops-green)

## TL;DR

If you use Google Cloud, you're one leaked API key away from a six-figure bill. Google's "budget caps" only send you an email — they don't actually cap spending. New API keys are created **unrestricted** by default. There is no built-in last line of defense.

This repo provides one:

- **Five Claude Code skills** — a driver plus four sub-skills — that audit every API key and SA key across every accessible project, detect past spend anomalies, and apply safe blast-radius controls (quota caps on Gemini API, billing budget alerts, disabling idle paid APIs, restricting unrestricted keys to APIs they actually use).
- **An MCP server** (`gcp-finops`) for natural-language billing-data analysis through Claude Code.

Every action is idempotent and reversible. Destructive items (key deletion, IAM changes, billing-account close) are *never* auto-applied — only flagged with the exact `gcloud` command for human review. If any project is currently bleeding (>10× baseline in the last 24h) the mutating phase halts automatically.

## The story

A developer woke up to about **$80,000 (≈₹67 lakh) of unauthorized Gemini API charges** racked up in roughly eight hours overnight. The cause: an unrestricted API key, leaked somewhere, picked up by an automated abuse service that ran image generation across nearly every Gemini model — hundreds of millions of generations in one window. Google's own May 2026 post [*"API keys are open secrets"*](https://cloud.google.com/blog/topics/developers-practitioners/api-keys-are-open-secrets) confirms unrestricted is the default state and concludes *"securing API keys is a user's responsibility."*

It is — but the audit checklist should not live in any one developer's head. This repo automates it.

The longer version is in [`docs/incident-story.md`](docs/incident-story.md).

## What's in this repo

```
gcp-ironclad/
├── skills/                        5 Claude Code skills
│   ├── gcp-ironclad/                Driver — orchestrates the run
│   ├── gcp-credentials-audit/       READ-ONLY  inventory + risk classification
│   ├── gcp-cost-anomaly-scan/       READ-ONLY  historical anomaly detection
│   ├── gcp-spend-guardrails/        APPLY      quotas + budgets + idle-API disable
│   └── gcp-key-restrictions/        APPLY      lock down unrestricted keys
├── mcp/gcp-finops/                Python MCP server for billing analysis
├── docs/
│   ├── design.md                    Architecture, safety matrix, phase model
│   └── incident-story.md            The fraud incident that motivated this
└── .mcp.json.example              Template for Claude Code MCP registration
```

## Requirements

- [Claude Code](https://claude.com/claude-code)
- `gcloud` SDK ≥ 470
- `bq` CLI (`gcloud components install bq`)
- `jq`
- Python ≥ 3.11

## Install

```bash
git clone https://github.com/<your-fork-or-shivam>/gcp-ironclad.git
cd gcp-ironclad

# 1. Install the MCP server
pip install ./mcp/gcp-finops
# (use `pip install -e ./mcp/gcp-finops` if you want editable / dev mode)

# 2. Authenticate Application Default Credentials
gcloud auth application-default login

# 3. Register the MCP server with Claude Code
cp .mcp.json.example .mcp.json
# Edit .mcp.json — set GCP_PROJECT_ID and (optionally) BQ_BILLING_TABLE

# 4. Make the 5 skills discoverable to Claude Code
for d in gcp-ironclad gcp-credentials-audit gcp-cost-anomaly-scan \
         gcp-spend-guardrails gcp-key-restrictions; do
  ln -sf "$(pwd)/skills/$d" ~/.claude/skills/$d
done
```

Open Claude Code in any GCP-using project, and ask:

> *"Use the gcp-ironclad skill to audit and harden my GCP API keys."*

The driver auto-discovers your project + billing scope from `gcloud`. No IDs hard-coded.

### Prerequisites for the MCP server

1. **Enable BigQuery billing export** (Console → Billing → Billing Export → Standard usage cost). This is what `cost_summary`, `sku_breakdown`, and `anomalies` read from.
2. **Enable APIs:**
   ```bash
   gcloud services enable bigquery.googleapis.com recommender.googleapis.com cloudbilling.googleapis.com
   ```

## Safety guarantees

- Two READ-ONLY phases run first; you see the audit before anything mutates.
- **Active-spike halt** — if any project shows >10× baseline spend in the last 24h, Phase 3 (mutating) does not run.
- Every action is gated on *"current state ≠ desired state"* — re-runs are no-ops.
- `--dry-run` runs every phase without mutating; `--confirm-each` re-introduces a y/n prompt per applied action.
- **Never auto-applied:** key deletion, IAM changes, billing-account close, lowering a quota below current usage, disabling any API with traffic in the last 30 days. All surfaced for human review with the exact `gcloud` command attached.

See [`docs/design.md`](docs/design.md) for the full safety matrix and phase model, and [`docs/threat-model.md`](docs/threat-model.md) for what the suite does and does **not** protect against.

## Security

Found a vulnerability? Please [report privately](SECURITY.md) rather than filing a public issue.

## Status

**v1.0** — works end-to-end. Tested against a multi-project GCP organization. Pull requests welcome.

## Contributing

This is an MIT-licensed open-source project. Issues, PRs, and ideas welcome. Particular help wanted on:

- Org-policy enforcement (`apikeys.googleapis.com/allowedRestrictions`) — block unrestricted keys at creation time.
- Local-codebase secret scanning — grep checked-out repos for leaked `AIza…` keys.
- Multi-org / cross-tenant operation.
- Documentation, screenshots, recordings of a real run.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for dev setup and PR guidelines.

## License

[MIT](LICENSE) — do anything reasonable with it. Attribution appreciated but not required.
