# EMERGENCY STOP — spend is spiking RIGHT NOW

Evidence can wait. The meter can't. Do these in order; every command is safe to run and reversible.

1. **Disable the abused key(s) now** (reversible — this does not delete):
   ```bash
   gcloud services api-keys list --project=PROJECT_ID --format="table(uid,displayName,restrictions)"
   gcloud services api-keys update KEY_UID --project=PROJECT_ID \
     --api-target=service=nonexistent.googleapis.com   # restricts key to a no-op service immediately
   ```
   If you know the key is abused and unneeded, disable at the API instead:
   ```bash
   gcloud services disable generativelanguage.googleapis.com --project=PROJECT_ID
   ```
   (Re-enable later with `gcloud services enable …` — nothing is deleted.)
2. **Check every other project for unrestricted keys:** run the `gcp-credentials-audit` skill (READ-ONLY).
3. **Screenshot the Billing console** (Reports page, last 48h, hourly view) — timestamped evidence of the live spike.
4. **Note the current UTC time** — this becomes your `discovery_datetime` in the dispute.
5. When the spend curve is flat again, re-run this kit: you'll be classified FRESH and get the full evidence packet + dispute letter.

Then harden everything: run the `gcp-ironclad` driver.
