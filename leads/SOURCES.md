# Where to get the Google Maps lead data: options and costs

Researched 13 Oct 2026. **Prices change; confirm on each vendor's page before you pay.** "Verified" = read on the vendor's own page; "Unverified" = only seen in third-party articles or not checked.

## Scale assumption
I don't know how many dental listings Lima has on Maps (my guess: a few thousand; that is a guess). Costs below are shown per 1,000 places and for a hypothetical **5,000-place** pull. Your first pull will be smaller (5–8 good districts).

## Comparison

| Option | Cost | Free allowance | Effort | Status |
|---|---|---|---|---|
| **Google Places API (New)**, our `fetch_places.py` | Text Search **Enterprise** $35 per 1,000 *requests* (phone/website/rating fields); each request returns ≤20 places. Text Search **Pro** $32 per 1,000 | **1,000 Enterprise** requests/month and 5,000 Pro requests/month free (per-SKU caps, not pooled) | Create key (10 min), run script | Prices/caps **verified** on Google's pricing page (updated 2026-10-08). Which fields count as Enterprise vs Pro: **unverified** (a third-party source says phone + website + rating = Enterprise; check Google's field docs) |
| **Outscraper** (hosted scraper, CSV export) | **$3 / 1,000 places**, $1 / 1,000 after 100k. Email/contact scraping is a separate product ($3 / 1,000 domains) | First **500 places/month** free; no subscription | Easiest: web form → CSV | **Verified** (outscraper.com/pricing) |
| **Apify** "Google Maps Scraper" (compass) | **from $1.50 / 1,000 places**; extras per place: details ~$0.002, contacts enrichment ~$0.002 (my arithmetic from their example table) | Apify has a monthly free credit; **amount not verified** | Web form → CSV/JSON | Base price **verified**; free credit **unverified** |
| **DataForSEO** Google Maps SERP API | $0.0006 per task (standard queue), $0.002 live; **one task returns up to 100 listings** | Not stated | Needs API integration (I can write it) | Price **verified**; deposit/minimum **unverified** |
| **Serper.dev** (Maps endpoint) | Prepaid credits; price per 1,000 not read | **2,500 free queries, no card** | API integration | Free credits **verified**; per-query cost of Maps **unverified** |
| **SerpApi** | Reports conflict ($0.01–0.025/search vs. $25 per 1,000) | unknown | API | **Unverified**, skip unless others fail |
| **OpenStreetMap / Overpass** | Free | n/a | Easy | **I tested it live** (below): not usable for contacts |
| **Manual copy from Maps** | Free (your time) | n/a | ~2–3 min per clinic | Fine for the first 50–100 |

### My live test: OpenStreetMap for Lima
Overpass query for `amenity=dentist` in a Lima + Callao bounding box returned **814** places, but only **41 with a phone and 16 with a website** (47 with any contact). Verdict: OSM is good as a free name cross-check, useless as a contact source.

## What it would cost for you

**Google API (our script).** The default run is 32 districts × 5 search phrases = 160 queries, ≤3 pages each → **at most 480 requests**. That's under the 1,000 free Enterprise requests/month, so **it should cost $0** if the free cap applies to your account. Worst case with no free cap: 480 × $0.035 ≈ **$17**. Even a 5,000-place pull via this route would stay in the "tens of dollars" at the very most.

**Outscraper for 5,000 places:** (5,000 − 500 free) × $3 / 1,000 ≈ **$13.50**.
**Apify for 5,000 places:** ≈ **$7.50** base (+≈$10 if you add contact enrichment).
**DataForSEO:** 5,000 places ≈ 50 tasks ≈ **pennies**, but needs code and an account top-up.

So all the paid options are in the **$0–$20** range for your first full Lima pass. The price difference is not what should decide this; **convenience and risk** are.

## Recommendation
1. **Start with Outscraper or Apify** if you want zero code and no cloud setup: export dentists for 5 districts → CSV → `clean_leads.py`. Both stay inside or near their free allowances for a first batch (Outscraper: 500 places free). The cleaner already maps their column names and has tests for both formats.
2. **Use the Google API route** if you want the cleanest, most "legit" data and repeatable monthly refreshes. It's likely free at this scale, but it **needs a billing account with a card**, so set protections first:
   - In Google Cloud → *APIs & Services → Quotas*, cap **Text Search requests per day** (e.g., 100) so a bug can't overspend.
   - Create a **budget alert** at, say, $5.
   - Restrict the API key to Places API only.
3. **Don't use OSM** for contacts. **Skip** SerpApi.
4. Supplement with free sources the scripts don't cover (unverified, check each): the dentists' Instagram/Facebook search by district, Doctoralia Perú listings, and Páginas Amarillas. These are good for clinics whose Maps listing has no phone.

## Legal/ToS note
Google's terms restrict scraping Maps pages. Hosted scrapers (Outscraper/Apify) operate in that grey zone and responsibility for how you use the data is yours; the official API is the only fully sanctioned route. Either way the data is public business info used for one-to-one B2B outreach: personalize, offer an opt-out, and follow the cautions in `../PLAN.md` (Ley 29733; check with a lawyer/contador).

## Sources
- [Google Maps Platform pricing](https://developers.google.com/maps/billing-and-pricing/pricing) (Text Search Pro/Enterprise SKUs, free caps)
- [Outscraper pricing](https://outscraper.com/pricing/)
- [Apify, Google Maps Scraper (compass)](https://apify.com/compass/crawler-google-places)
- [DataForSEO, Google Maps SERP API pricing](https://dataforseo.com/pricing/serp/google-maps-serp-api)
- [Serper.dev](https://serper.dev/)
- OSM figures: my own Overpass query, 13 Oct 2026 (bbox −12.30,−77.20 → −11.80,−76.80).
