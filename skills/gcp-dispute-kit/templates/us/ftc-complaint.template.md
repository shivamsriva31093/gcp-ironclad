> **Note:** This is a template prepared from your own billing data. It is not legal advice.
> **Status: NOT FIELD-VALIDATED** — this track has not yet been used in a real resolved case. Adapt with care.
<!-- FILE VIA: reportfraud.ftc.gov — "Report Now", category "Something else". The FTC does not resolve individual disputes, but a complaint on record documents the pattern and supports any later action. Also consider your card issuer's dispute process (same evidence packet applies). -->

**Complaint to the Federal Trade Commission**
**Complainant:** {{victim_name}} ({{company_name}}), {{victim_email}}
**Company complained about:** Google LLC (Google Cloud Platform)
**Date:** {{filing_date}}
**Amount:** {{currency_symbol}}{{disputed_amount}} ({{currency_code}})

**What happened:**

A leaked API credential for my Google Cloud account (billing account {{billing_account_id}}) was exploited by an automated abuse service between {{incident_start}} and {{incident_end}}, generating {{currency_symbol}}{{disputed_amount}} in fraudulent charges — **{{spike_multiplier}} times** my established daily spend of {{currency_symbol}}{{baseline_daily_spend}}, in {{incident_hours}} hours, peaking at {{currency_symbol}}{{peak_hourly_cost}} in one hour. {{impossible_volume_summary}}

Product defaults contributed to the loss: Google issues API keys **unrestricted by default**, its "budget" feature alerts but does not cap spending, and no fraud control interrupted a spend rate dozens of times above baseline. This is a documented, recurring pattern affecting many customers.

I reported promptly (Google case {{case_number}}), provided complete evidence from Google's own billing data, and mitigated immediately ({{mitigation_summary}}). Status after {{days_since_filing}} days: {{prior_response_summary}}

**Relief sought:** Full adjustment of the fraudulent charges; review of billing practices that leave consumers liable for machine-scale fraud enabled by unsafe defaults.

{{victim_name}}
