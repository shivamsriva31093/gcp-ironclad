> **Note:** This is a template prepared from your own billing data. It is not legal advice.

# Evidence summary — fraudulent API usage, {{incident_start}} → {{incident_end}}

**Account:** {{company_name}} ({{victim_email}}) — billing account {{billing_account_id}} — project(s) {{project_ids}}
**Disputed amount:** {{currency_symbol}}{{disputed_amount}} ({{currency_code}})
**Prepared:** {{filing_date}}

## 1. Baseline vs. spike

Median daily spend over the 30 days before the incident: **{{currency_symbol}}{{baseline_daily_spend}}/day**. During the {{incident_hours}}-hour incident window the account spent at **{{spike_multiplier}}× that rate**, peaking at **{{currency_symbol}}{{peak_hourly_cost}} in a single hour**.

## 2. Model-variety fingerprint

**{{distinct_skus_count}} distinct SKUs** were billed in the window — {{model_variety_summary}}. Automated abuse services spray requests across every available model; legitimate applications do not.

## 3. Impossible volumes

{{impossible_volume_summary}}

## 4. Attribution

The traffic is attributable to API key **{{abused_key_display_name}}** based on per-credential request metrics for the incident window. (Source-IP attribution is generally not available for API-key traffic; no IP claims are made.)

## 5. Timeline of discovery and mitigation

| When (UTC) | What |
|------------|------|
| {{incident_start}} | Fraudulent usage begins |
| {{incident_end}} | Fraudulent usage ends |
| {{discovery_datetime}} | Charges discovered by account holder |
| {{mitigation_datetime}} | Mitigation completed: {{mitigation_summary}} |

## Exhibits

Every claim above is backed by a file in `exhibits/`; each exhibit records the exact command or query that produced it.

{{exhibit_list_summary}}
