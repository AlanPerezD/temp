# Google Places API setup (about 15 minutes)

You do steps 1–5 in Google's website (they need your Google account and a card; I can't do them for you). Everything after that is already scripted.

> **Security:** the API key is a password that can spend money. Never paste it in chat, in a file that is committed, or in a screenshot. Section 6 shows the safe places for it.

## 1. Create a project
1. Go to <https://console.cloud.google.com/> and sign in with your Google account (accept the terms if asked).
2. Top bar → project picker → **New project** → name it `lima-leads` → **Create**, then make sure that project is selected.

## 2. Turn on billing
Google requires a billing account (a card) even though the free monthly allowance should cover our first pull.
1. Menu → **Billing** → **Link a billing account** (or create one).
2. Complete the account details. A prepaid/virtual card with a low limit is a good idea.

## 3. Enable the right API
1. Menu → **APIs & Services → Library**.
2. Search **Places API (New)** (the one marked "New", *not* the old "Places API").
3. Open it → **Enable**.

## 4. Create the key and lock it down
1. **APIs & Services → Credentials → Create credentials → API key**. Copy the key somewhere private.
2. Click the new key → **API restrictions → Restrict key → Places API (New)** → Save.
3. **Application restrictions: None.** (The script runs from a computer/cloud container whose IP changes, so IP/website restrictions would block it. The API restriction above is what protects you.)

## 5. Put hard limits on spend (do this BEFORE the first big run)
- **Daily quota cap (a real hard stop):** *APIs & Services → Places API (New) → Quotas & system limits*. Find the **Text Search** per-day request quota and set it to something small like **100/day**. Names in the console vary slightly; look for "Text Search". When the cap is hit, the script saves its progress and you continue the next day with `--resume`.
- **Budget alert (a notification, *not* a stop):** *Billing → Budgets & alerts → Create budget* → $5 with alerts at 50% and 100%.

## 6. Give the script the key (pick one)

**A. Run it on your own computer (recommended; your lead data stays with you)**
```bash
cd leads
echo 'GOOGLE_MAPS_API_KEY=PASTE_YOUR_KEY_HERE' > .env     # .env is git-ignored
python3 fetch_places.py --test
```

**B. Run it inside this Claude cloud session**
Don't paste the key in the chat. Open the cloud environment's settings (the environment menu in the session's title bar → *Edit*), add an environment variable named exactly `GOOGLE_MAPS_API_KEY` with your key, and start a **new session**. Then tell me, and I'll run the commands below and send you the cleaned CSV. (Files created in a cloud session are temporary, so download what I send you.)

## 7. Verify, then run

```bash
python3 fetch_places.py --test        # 1 request. Should print "OK: Google answered with N places"
python3 fetch_places.py --dry-run     # shows the query plan and the worst-case cost

# First real pull: your 5 best districts only (≈ 25 queries, well under 100 requests)
python3 fetch_places.py --max-requests 100 \
  --districts Miraflores "San Isidro" "Santiago de Surco" "San Borja" "La Molina"

python3 clean_leads.py data/raw_places.csv -o data/leads_clean.csv --rejected data/leads_rejected.csv
```
If a run stops (quota, error, Ctrl-C) it **saves what it has**; continue with the same command plus `--resume`.

## 8. After the first run, check the bill
*Billing → Reports*, group by SKU. You should see Text Search requests counted against a free allowance. Tell me the numbers and I'll update `SOURCES.md` with your real cost per 1,000 places.

## Troubleshooting

| Message | Fix |
|---|---|
| `API key not valid` | Key copied wrong or deleted. Re-copy from Credentials. |
| `has not been used… or it is disabled` / `SERVICE_DISABLED` | Enable **Places API (New)** in the *same project* as the key (step 3). Takes a minute to propagate. |
| `BILLING_DISABLED` | Link a billing account to the project (step 2). |
| `PERMISSION_DENIED` after adding restrictions | In the key's *API restrictions*, make sure **Places API (New)** is ticked; set *Application restrictions* to **None**. |
| `429` / `RESOURCE_EXHAUSTED` | You hit your own daily cap (step 5). Wait for the reset or raise it, then `--resume`. |
| `Network error reaching Google` | Your network/proxy blocks `places.googleapis.com`. In the cloud environment, allow that host in *Network access*. |
