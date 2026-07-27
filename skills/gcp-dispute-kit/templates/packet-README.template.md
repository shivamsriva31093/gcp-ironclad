> **Note:** This is a template prepared from your own billing data. It is not legal advice.

# Dispute packet — {{company_name}} — {{currency_symbol}}{{disputed_amount}}

Prepared {{filing_date}} for billing account {{billing_account_id}} (project(s): {{project_ids}}).

## Filing sequence

File in this order. Do not wait for one track to conclude before starting the next — the bank track in particular is deadline-sensitive.

| # | Track | Letter | Where to file |
|---|-------|--------|---------------|
| 1 | Google | `letters/` (console-dispute or escalation-reply) | Cloud Console → Billing → Support case {{case_number}} |
| 2 | Bank (IN) | `letters/bank-chargeback.md` (if present) | Your bank's card-dispute channel — TIME-SENSITIVE from statement date |
| 3 | NCH (IN) | `letters/nch-complaint.md` (if present) | consumerhelpline.gov.in |
| 4 | CERT-In (IN) | `letters/cert-in-report.md` (if present) | incident@cert-in.org.in |
| 5 | FTC (US) | `letters/ftc-complaint.md` (if present) | reportfraud.ftc.gov |

## Deadline tracker

| Track | Action | Deadline | Status |
|-------|--------|----------|--------|
{{deadline_tracker_rows}}

## Ground rules while the dispute is open

- **Do not pay the disputed amount.** Paying weakens every track.
- Keep everything in writing; decline phone-only resolutions.
- Reply within 48h to any request from any track (silence is read as abandonment).

## Attach these by hand (the kit could not fetch them)

{{manual_attachments_list}}

## What's in this packet

- `evidence-summary.md` — the master narrative; every claim cites an exhibit.
- `letters/` — ready-to-file letters for your situation and jurisdiction.
- `exhibits/` — raw data, numbered; each records the exact command that produced it.
- `manifest.json` — machine-readable index of everything above.
