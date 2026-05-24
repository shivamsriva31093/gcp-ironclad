# GCP Ironclad Report — {{generatedAt}}

**Caller:** {{scope.user}}
**Projects scanned:** {{scope.projectsScanned | length}} accessible, {{scope.projectsSkipped | length}} skipped
**Mode:** {{ dryRun ? "DRY-RUN (no changes applied)" : "APPLY" }}
**Session dir:** `{{sessionDir}}`

## 1. Executive summary

Risk profile **before**: {{criticalBefore}} CRITICAL · {{highBefore}} HIGH · {{mediumBefore}} MEDIUM
Risk profile **after**:  {{criticalAfter}} CRITICAL · {{highAfter}} HIGH · {{mediumAfter}} MEDIUM
Anomalies detected (last 60d): {{anomalyCount}} ({{activeAnomalies}} active in last 24h)
Money at risk (approx.): {{moneyAtRisk}}
Actions applied: {{actionsApplied}} · Flagged: {{actionsFlagged}}

{{#activeSpike}}🚨 ACTIVE SPIKE — Phase 3 did NOT run. See §3 for details.{{/activeSpike}}

## 2. Audit findings

| Project | API keys | SA keys | CRIT | HIGH | MED | LOW |
|---|---|---|---|---|---|---|
{{#projects}}
| {{id}} | {{apiKeys}} | {{saKeys}} | {{c}} | {{h}} | {{m}} | {{l}} |
{{/projects}}

### CRITICAL credentials
{{#critical}}
- `{{type}}` `{{project}}/{{displayName}}` ({{uid}}) — {{riskReason}}
{{/critical}}

## 3. Cost anomaly check (last 60 days)

{{#anomalies}}
- **{{date}}** · `{{project}}` · `{{billingAccount}}` · gross **{{gross}}** ({{multipleOver}}× baseline) · top SKU: `{{topSku}}` {{#activeIn24h}}🚨 STILL ACTIVE{{/activeIn24h}}
{{/anomalies}}
{{^anomalies}}
No anomalies in the last 60 days.
{{/anomalies}}

## 4. Actions applied

| Kind | Target | Outcome | Reason / Detail |
|---|---|---|---|
{{#actionsAppliedList}}
| {{kind}} | {{target}} | {{outcome}} | {{reason}} |
{{/actionsAppliedList}}

### Rollback commands
{{#rollbacks}}
```bash
{{cmd}}
```
{{/rollbacks}}

## 5. ⚠ Flagged for human review

{{#flaggedList}}
- **{{kind}}** `{{target}}` — _{{reason}}_

  Run this if you want to act on it:
  ```bash
  {{recommendedCommand}}
  ```
{{/flaggedList}}

## 6. Re-run hygiene checklist

- [ ] In the Cloud Console, verify the quota changes on `generativelanguage.googleapis.com` for each affected project.
- [ ] Verify the three budget alerts per billing account in the Billing → Budgets & alerts page.
- [ ] If any APIs were disabled on a project you expected to use, re-enable per the rollback commands above.
- [ ] For each `Flagged for human review` item: decide whether to run the suggested command.
- [ ] Rotate any SA keys older than 90 days using your normal rotation process.
- [ ] Re-run this skill in 30 days for a clean re-audit.

---

> ⚠ **Redact before sharing.** This report contains GCP identifiers (project IDs, key UIDs, billing-account IDs, sometimes service-account emails). Strip them before pasting into issues, PRs, support tickets, or chat. See [`SECURITY.md`](../../SECURITY.md) for the threat-model summary.
