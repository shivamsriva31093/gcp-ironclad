# Security Policy

## Supported versions

`gcp-ironclad` is early-stage open source. Only the latest tagged release receives security fixes.

| Version | Supported |
|---------|-----------|
| `main` HEAD | ✅ |
| Tagged releases | latest patch only |

## Reporting a vulnerability

**Please do not file a public issue for security vulnerabilities.**

Use GitHub's private security advisory feature:

→ **https://github.com/`<owner>`/gcp-ironclad/security/advisories/new**

You can expect:

- Acknowledgement within 72 hours.
- A confidential triage discussion via the security advisory.
- A coordinated disclosure timeline once a fix lands.

## Threat model

The short version (full document in [`docs/threat-model.md`](docs/threat-model.md)):

**In scope**

- Leaked or unrestricted Google Cloud API keys (the project's primary purpose).
- Idle paid APIs left enabled on projects.
- Runaway spend and historical cost anomalies.
- SQL injection through the `gcp-finops` MCP tool surface.
- Skill-side bash that could be subverted by attacker-influenced inputs.

**Not in scope**

- A compromised local developer machine (your `gcloud` ADC, your shell, your dotfiles).
- A compromised fork or PR of this repository (standard "do not run untrusted code" applies).
- GCP platform-level vulnerabilities (report those to Google directly).
- Supply-chain attacks via PyPI (we ship major-version upper bounds; we do not ship a lockfile).

**Assumes**

- You invoke the suite intentionally with `gcloud` auth you control.
- The `gcp-finops` MCP server runs locally on your developer machine, not network-exposed.
- Your Claude Code session is your own (not a shared / multi-tenant deployment).

## Hardening recommendations

If you run `gcp-ironclad` in production / CI / a shared environment:

### Run as a dedicated least-privilege identity

Create a dedicated service account with only the permissions the suite actually needs:

```bash
gcloud iam service-accounts create gcp-ironclad-auditor \
  --display-name="gcp-ironclad audit identity"

# Read-only roles for the audit and anomaly phases:
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member=serviceAccount:gcp-ironclad-auditor@$PROJECT.iam.gserviceaccount.com \
  --role=roles/billing.viewer
gcloud projects add-iam-policy-binding "$PROJECT" \
  --member=serviceAccount:gcp-ironclad-auditor@$PROJECT.iam.gserviceaccount.com \
  --role=roles/iam.securityReviewer

# Add only if you want Phase 3 (APPLY) to actually mutate:
#   roles/billing.admin
#   roles/serviceusage.serviceUsageAdmin
#   roles/apikeys.admin (for key-restrictions)

# Then impersonate when you run:
gcloud auth application-default login \
  --impersonate-service-account=gcp-ironclad-auditor@$PROJECT.iam.gserviceaccount.com
```

### Never share generated reports unredacted

The report at `~/.claude/reports/gcp-ironclad-*.md` contains project IDs, API key UIDs, and billing-account IDs. Redact before pasting into issues, PRs, or chat.

### Pin dependencies tightly

The published `pyproject.toml` uses major-version upper bounds. For production use, generate a lockfile post-install:

```bash
pip freeze > requirements.lock
pip install --no-deps -r requirements.lock
```

## Disclosed vulnerabilities

None to date.
