> **Note:** This is a template prepared from your own billing data. It is not legal advice.
<!-- FILE VIA: your bank's card-dispute channel (branch, net-banking dispute form, or written letter to the card division). RBI's limited-liability framework for unauthorized electronic transactions rewards PROMPT reporting — file this as soon as possible after discovery. -->

**To:** The Manager, Card Disputes — {{bank_name}}
**From:** {{victim_name}}, card ending **{{card_last4}}**
**Date:** {{filing_date}}

**Subject: Dispute of unauthorized charges — Google Cloud — {{currency_symbol}}{{disputed_amount}} — statement dated {{statement_date}}**

Dear Sir/Madam,

I dispute charges of **{{currency_symbol}}{{disputed_amount}}** ({{currency_code}}) by GOOGLE CLOUD appearing on my card ending {{card_last4}} (statement dated {{statement_date}}). These charges arise from **third-party fraud**: a stolen API credential was used by an automated abuse service to run charges on my Google Cloud account between {{incident_start}} and {{incident_end}} — **not** from any purchase or usage authorized by me.

Facts supporting the dispute:

1. My normal, authorized spend with this merchant was {{currency_symbol}}{{baseline_daily_spend}}/day. The disputed charges ran at **{{spike_multiplier}} times** that rate within {{incident_hours}} hours — an unmistakable fraud pattern.
2. {{impossible_volume_summary}}
3. I discovered the fraud at {{discovery_datetime}} and immediately secured the account ({{mitigation_summary}}).
4. I have an open fraud dispute with the merchant (Google case {{case_number}}). Supporting evidence is enclosed:
{{exhibit_list_summary}}

Under the RBI's framework on limited customer liability for unauthorized electronic banking transactions, I request that you:
1. Register a chargeback/dispute for {{currency_symbol}}{{disputed_amount}};
2. Provide a written acknowledgement with a reference number today;
3. Confirm the applicable provisional-credit timeline.

I certify the above is true to the best of my knowledge.

{{victim_name}}
{{victim_email}}
