# Free route: Apify (no card, no code)

Apify's **Free plan gives $5 of usage per month, no credit card required**, and the credit renews each monthly cycle (unused credit expires; verified on apify.com/pricing, 13 Oct 2026). Its "Google Maps Scraper" actor is `compass/crawler-google-places`.

## Real pricing (read from the actor's pricing, Oct 2026)
On the Free plan: **$0.004 per place**, **+$0.001 per place for each filter** you turn on (e.g. `website`, `skipClosedPlaces`), +$0.002 for contact enrichment. We use only the `website: withoutWebsite` filter ($0.005/place, ≈ **$5 per 1,000 places**, so the $5 credit ≈ 1,000 places) and skip `skipClosedPlaces` because `clean_leads.py` removes closed places for free. Live test: 5 Lima districts × 80 places ≈ $2.

## What $5 buys (older estimate, superseded by the real pricing above)
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
  "website": "withoutWebsite"
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

---

## Let Claude run it (no copy-paste of CSVs): `fetch_apify.py`

Instead of using the Apify website, the runner calls Apify's API with the same actor and the same input as above, with **three spending caps** (places per search, `$` per run, `$` total). It prints the *real* price per 1,000 places after each run.

1. Apify Console → **Settings → API & Integrations** → copy your **API token** (a password; **never paste it in chat**).
2. **On your computer:** `echo 'APIFY_TOKEN=...' >> leads/.env`, then:
   ```bash
   python3 fetch_apify.py --test        # 1 district, 5 places, $0.50 cap
   python3 fetch_apify.py               # 5 best districts, $4 total budget
   python3 clean_leads.py data/apify_places.csv
   ```
3. **In this Claude session:** add `APIFY_TOKEN` as an environment variable in the cloud environment's settings (environment menu in the session title bar → Edit; use "Network secrets" if offered), start a **new session**, and tell me. I'll run `--test`, look at the output with you, then the full pull, clean it, and send you the CSV. I confirmed this environment can reach `api.apify.com`.

## "Is there an MCP for this?"

- **Apify has an official MCP server**: hosted at `https://mcp.apify.com` (OAuth login) or local via `npx -y @apify/actors-mcp-server` with `APIFY_TOKEN`. It lets an assistant search Apify's Store and run any Actor. It is **not** in the claude.ai connector directory I can see, and nothing is connected in this session. To use it you'd add it yourself as a custom connector at <https://claude.ai/customize/connectors> and start a new session.
- **Honest comparison:** for *this* job the runner script is better than the MCP: same actor, same data, but with hard cost caps and a repeatable CSV. The MCP is useful later to explore *other* Apify actors (Facebook pages, Instagram profiles, website contact finders).
- **Browser-driving MCPs** (Playwright MCP, Browserbase, Chrome DevTools MCP, Firecrawl MCP) are good for *visiting* sites, e.g., checking a clinic's site speed or taking screenshots for your audit videos. They are the wrong tool for bulk Google Maps: fragile, against Google's terms, and cloud IPs get blocked. (Popularity claims in articles are from vendor blogs; I didn't verify star counts.)
