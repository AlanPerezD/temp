# Lead base: dental clinics in Lima (Google Maps)

Pipeline: **get raw Maps data → clean/qualify/score → work the list from the top.**
Python 3.9+ standard library only (no installs).

```
leads/
  fetch_places.py   Google Places API (New) → data/raw_places.csv
  clean_leads.py    raw CSV(s) → data/leads_clean.csv (+ data/leads_rejected.csv)
  test_leads.py     python3 -m unittest test_leads
  sample_raw.csv    6 fake rows to try the cleaner
  data/             your real lead files (git-ignored on purpose)
```

## Step 1: get raw data (pick ONE route)

> **Costs and alternatives (Outscraper, Apify, DataForSEO, OSM, etc.): see [`SOURCES.md`](SOURCES.md).** Short version: every route is roughly $0–$20 for a first full Lima pass; pick for convenience.

**Route A: Google Places API (recommended, sanctioned by Google)**
> **Follow [`GOOGLE_SETUP.md`](GOOGLE_SETUP.md)** for the exact click-by-click setup, spend limits, and troubleshooting. Then `python3 fetch_places.py --test`.
1. Google Cloud Console → create a project → enable **Places API (New)** → create an API key → restrict it to that API.
2. Billing must be on. Check the current Maps Platform pricing/free allowance first: phone + website fields are billed at a higher tier. The script has a hard `--max-requests` cap (default 150) as a cost guard.
3. ```bash
   export GOOGLE_MAPS_API_KEY="..."
   python3 fetch_places.py --dry-run          # preview the queries
   python3 fetch_places.py --max-requests 150 # ≈ first slice of Lima
   ```
   It searches 5 phrases (dentista, clínica dental, odontología, ortodoncia, estética dental) × 32 districts, dedupes by place id, and writes `data/raw_places.csv`.
   Start with your best districts: `--districts Miraflores "San Isidro" "Santiago de Surco" "San Borja" "La Molina"`.

> I wrote and unit-tested this script against the API's documented request/response shape, but I could not call the live API from my environment (no key). Run `--dry-run`, then a tiny first run (`--max-requests 5`), and tell me if Google returns an error.

**Route B (free, no card): Apify.** Step-by-step with ready-to-paste input in [`APIFY_QUICKSTART.md`](APIFY_QUICKSTART.md).

**Route B: a Maps export tool** (Outscraper, Apify "Google Maps Scraper", etc.). Search "dentista en <distrito>, Lima, Perú", export CSV. `clean_leads.py` auto-detects their usual column names. Check the tool's terms; Google's own terms restrict scraping.

**Route C: manual** (zero cost, fine for your first 50–100): copy Name / Address / Phone / Website / Rating / Reviews from Maps into a CSV with those headers.

## Step 2: clean + qualify

```bash
python3 clean_leads.py data/raw_places.csv -o data/leads_clean.csv --rejected data/leads_rejected.csv
# try it first on the fake data:
python3 clean_leads.py sample_raw.csv -o data/demo_clean.csv --rejected data/demo_rejected.csv
```

What it does to your data:

| Step | Detail |
|---|---|
| Phones | Normalized to `+51…`; **mobile (9 digits starting with 9)** → `whatsapp_link` (`wa.me/…`); Lima landlines `(01)` flagged; extra numbers kept in `other_phones` |
| Reject | closed places · not dental · suppliers/labs/schools · big institutions (EsSalud, Sanna, etc.) · no way to contact |
| Dedupe | by Google place id, by phone (only if the names overlap, since two dentists can share a building line), by name + district |
| Website type | `none` · `social` (Instagram/Facebook/Linktree/wa.me) · `free_builder` (Wix/business.site…) · `directory` (Doctoralia…) · `own` |
| District | parsed from the address ("Lima" alone is *not* a district) |
| Score 0–100 | no real website **+40** (social/free site +32) · mobile/WhatsApp **+20** · rating ≥4.5 **+15** · reviews ≥100 **+15** · has Instagram/FB **+5** |
| Tier | **A ≥ 70**, **B 50–69**, **C < 50**; clinics with their own site are capped at C |
| Note | `personalization_note` pre-fills your first-line detail, e.g. *"4.8 estrellas, 150 reseñas en Google; su ficha no tiene web"* |

Everything dropped goes to `leads_rejected.csv` with a reason. **Skim it once**; if it's wrongly rejecting something (e.g. a chain you do want), tell me and I'll adjust the rules. Use `--exclude "name1" "name2"` to drop more names.

## Step 3: curate by hand (15–20 min per 100 leads)

The script can't judge these; check Tier A and B in Maps:
- Is the clinic **actually small/independent**, and the owner reachable? (Skip multi-branch chains with in-house marketing.)
- Does the website link in Maps really go nowhere / to a dead page?
- Are the photos/reviews recent (alive business)?
- Add one more personal detail to `personalization_note` (a specialty, a recent review, an Instagram post).

Then work the list **top-down**: Tier A first, 100 touches/day (see `../PLAN.md`), logging in `../lead-tracker.csv` (the clean file already has the same outreach columns, so you can use it directly as your tracker).

## Compliance reminders
- It's business contact data already public on Maps, used for one-to-one B2B outreach: personalize, offer an opt-out, never bulk-blast WhatsApp. See the cautions in `../PLAN.md` (Ley 29733 on personal data; verify with a lawyer/contador).
- Keep `data/` private: it contains phone numbers (it is git-ignored).

## Sending the WhatsApp batch (paced, you tap send)
```bash
python3 make_outreach.py --sender "Your name" --limit 30   # builds data/outreach_batch1.csv
python3 send_queue.py                                       # on YOUR computer: opens one chat at a time
```
`send_queue.py` opens each chat with the message pre-filled; you read it, press send and confirm. It enforces a daily cap (25), working hours (9–18 Lima) and a random 4–9 min pause, and saves progress in the CSV. Sending is always done by you, by hand. Start at 10–15 a day for the first week, and prefer inbound channels (see `../INBOUND.md`).
