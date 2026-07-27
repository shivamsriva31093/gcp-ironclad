> **Note:** This is a template prepared from your own billing data. It is not legal advice.
<!-- FILE VIA: incident@cert-in.org.in (CERT-In incident reporting email). CERT-In's mandate covers reporting of cyber-security incidents; unauthorized access to cloud credentials qualifies. A CERT-In acknowledgement number strengthens the bank and NCH tracks — file this even if no investigation follows. -->

**To:** CERT-In (incident@cert-in.org.in)
**Subject:** Incident report — compromised cloud API credential and resulting financial fraud

**Reporting entity:** {{company_name}} ({{victim_name}}, {{victim_email}})
**Date of report:** {{filing_date}}

**Incident type:** Unauthorized access — compromised API credential (Google Cloud Platform).

**Summary:** An API key ({{abused_key_display_name}}) belonging to our Google Cloud account (project(s) {{project_ids}}) was compromised and exploited by an automated abuse service between **{{incident_start}}** and **{{incident_end}}** (UTC). The attacker generated machine-scale API usage — {{impossible_volume_summary}} — resulting in fraudulent charges of {{currency_symbol}}{{disputed_amount}}.

**Detection:** Discovered {{discovery_datetime}} via billing alerts. Traffic peaked at {{currency_symbol}}{{peak_hourly_cost}}/hour against a normal baseline of {{currency_symbol}}{{baseline_daily_spend}}/day.

**Containment:** {{mitigation_summary}} (completed {{mitigation_datetime}}).

**Impact:** Financial only (fraudulent usage charges, disputed with the provider — case {{case_number}}). No personal data was exfiltrated to our knowledge.

**Evidence available on request:**
{{exhibit_list_summary}}

Please acknowledge receipt with an incident/reference number.

{{victim_name}}
{{company_name}}
