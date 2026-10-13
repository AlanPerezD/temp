# Free route: Apify (no card, no code)

Apify's **Free plan gives $5 of usage per month, no credit card required**, and the credit renews each monthly cycle (unused credit expires; verified on apify.com/pricing, 13 Oct 2026). Its "Google Maps Scraper" actor is `compass/crawler-google-places`.

## What $5 buys (an estimate, not a promise)
The actor is billed per place. Apify lists "from $1.50 per 1,000 places" but that is the *best-plan* price; **the Free-plan rate isn't shown on the page I could read**, and one third-party claim says $4–7 per 1,000 (unverified). So $5 ≈ **700 to 3,300 places**. Check the real rate after your first run (the run page shows "Total cost").

That is enough for a good first batch: after the cleaner removes closed/non-dental/duplicate rows, expect a fraction of those to be usable leads, mostly Tier A/B.

## Steps
1. Sign up at <https://apify.com/> (email, no card). Do NOT create extra accounts to farm more credit: it breaks most platforms' terms, risks a ban, and the free credit already renews every month.
2. Open the actor: <https://apify.com/compass/crawler-google-places> → **Try for free**.
3. Switch the input to **JSON** and paste this **first test** (one district, small cap):

```json
{
  "searchStringsArray": ["dentista", "clínica dental", "ortodoncia"],
  "locationQuery": "Miraflores, Lima, Perú",
  "maxCrawledPlacesPerSearch": 40,
  "language": "es",
  "countryCode": "pe",
  "skipClosedPlaces": true
}
```
   - Leave **enrichments off** (contacts, social profiles, leads, reviews). They cost extra per place; reviews are the biggest cost driver.
   - Field names come from the actor's input schema, but Apify changes its UI; if a field is rejected, set the same options in the form instead.
4. **Start.** When it finishes, note the **total cost** on the run page. Divide by places found to get your real price per 1,000.
5. **Storage / Dataset → Export → CSV** (all fields). Save into `leads/data/`.
6. Clean it:
```bash
python3 clean_leads.py data/dataset_*.csv -o data/leads_clean.csv --rejected data/leads_rejected.csv
```
   The cleaner already understands Apify's columns (`title`, `totalScore`, `reviewsCount`, `categoryName`, `placeId`, `permanentlyClosed`, …). Its `url` column is the Maps link; the clinic's site is `website`.
7. If the test run was cheap and the data looks good, repeat for the next districts: **San Isidro**, **Santiago de Surco**, **San Borja**, **La Molina**, **Jesús María**, **Lince**. Raise `maxCrawledPlacesPerSearch` to 100 for dense districts. When the monthly credit is gone, wait for the renewal, or switch to Outscraper's free 500 or the Google API.

## Compare the free allowances (all verified Oct 2026 unless noted)

| Option | Free amount | Card needed? |
|---|---|---|
| **Apify** Free plan | $5 credit per month (≈700–3,300 places) | **No** |
| **Outscraper** | first 500 places per month | **Unclear**: sources conflict; check at signup |
| **Google Places API** | 1,000 Enterprise requests per month (≈ the whole default Lima crawl) | **Yes** (billing account) |
| **Serper.dev** | 2,500 queries on signup | No (per their page); Maps cost per query unverified |

Practical plan: use **Apify's $5** now (no risk), then **Outscraper's 500** for a second batch if you want, and keep the Google API (already scripted, `GOOGLE_SETUP.md`) as the monthly refresh once you have a card you're comfortable with.
