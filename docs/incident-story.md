# The story this came from

## Eight hours, eighty thousand dollars

A developer went to bed with a roughly **$1,400/day** GCP spend — a normal pattern that had held for months. They woke up to a bank alert about ~**$80,000** (≈₹67 lakh) of charges racked up overnight.

It hadn't run away gradually. It had run away in *eight hours*. At one point the meter hit roughly **$20,000 in a single hour**. Then it stopped — abruptly, around 08:00 UTC. No alert from Google. No threshold tripped. No fraud-detection email. The first signal of trouble was the bank.

The first instinct was the obvious one: *"Disable everything. Disable the Gemini API. Lock down every key."* That's where the story should have ended.

## What actually happened

A reconstruction from the billing export later showed:

- A leaked, **unrestricted** API key in the developer's GCP project. They had created six API keys in that project over the prior year; **two had no restrictions at all.**
- The key was used by an automated abuse service to call **nearly every Gemini model** — Pro, Flash, Flash-Lite, 2.5, 3, 3.1 — for **image generation**, hundreds of millions of generations across an eight-hour window.
- The volumes were physically impossible for any legitimate application: ~**291 million image-output token units** on a single SKU; over **a billion text tokens** on another.

A textbook leaked-key abuse run, of a shape that had been [documented in The Register](https://www.theregister.com/2026/03/03/gemini_api_key_82314_dollar_charge/) for months. The developer was not the first; they were one of many.

## Where the platform fell short

Across the dispute and the post-mortem, several Google-side gaps surfaced:

1. **Unrestricted is the default.** Google's own [May 2026 post on API-key security](https://cloud.google.com/blog/topics/developers-practitioners/api-keys-are-open-secrets) says, in the same article: *"DO NOT create unrestricted keys"* and *"by default a new API key is created without restriction."* The dangerous configuration is what new users get.

2. **Budgets don't cap spending.** Per Google's own docs, a budget *"does not automatically cap usage/spending."* It emails you while the meter runs.

3. **Spend tiers auto-upgrade.** The Register documented a developer who set a `$250` spending cap and woke up to a `$10,000` bill, after which their tier was automatically raised to `$100,000`.

4. **Key-scope expansion.** [Truffle Security](https://www.theregister.com/2026/03/03/gemini_api_key_82314_dollar_charge/) reported that Google had quietly broadened the scope of certain API keys to also access Gemini models. Their initial report was dismissed as *"intended behavior"*, then **reclassified as a Bug** after Truffle showed examples on Google's own infrastructure.

5. **No real-time abuse block.** A jump from $1,400/day to $20,000/hour is, by any measure, anomalous. The detection signal exists in Cloud Monitoring (`serviceruntime.googleapis.com/api/request_count` by `credential_id`) but the platform did not act on it.

## What changed since (mid-2026)

Google has retired the design this incident exploited — for Gemini specifically. Unrestricted standard keys are rejected by the Gemini API since **June 19, 2026**, and from **September 2026** it accepts only service-account-backed **auth keys** with, in Google's words, *"fast-acting leaked key enforcement that quickly stops the usage of leaked keys detected by our systems."* Gaps 1 and 5 above are closing for this one API — an acknowledgment, in product form, that the defaults were unsafe. The rest of the platform still works the old way, and none of this retroactively helps the victims disputing charges from before the change.

## The dispute

Reported the same day via the official Cloud Console support channel, the charges were ultimately disputed as fraud. Google's documented practice — confirmed in [The Register](https://www.theregister.com/devops/2026/05/15/google-reimburses-register-sources-who-were-victims-of-api-fraud/5241429) — is to reimburse victims of API-key fraud when reported promptly with evidence. If you find yourself here: state the spike magnitude, the model variety, the impossible volumes, the mitigation taken; explicitly request a billing adjustment; **do not pay while disputing.**

## Why this tooling exists

The first attempt at remediation was a flurry of `gcloud services api-keys list / delete / update` and `gcloud services disable` commands done in panic, by a developer who'd never had to run them under fire before. It worked, but it was ad-hoc, and it didn't scale to *"harden every project against this happening again."*

This tooling is that playbook crystallized — an automated, idempotent, safe-by-default version of what should have been the standard hygiene pass from day one.

If you've never been hit, run it now. If you've been hit, run it after you've stopped the bleeding.

> *Securing API keys is a user's responsibility. So is making that responsibility actionable.*
