#!/usr/bin/env python3
"""Run Apify's Google Maps Scraper for dental clinics in Lima, via Apify's REST API.

    export APIFY_TOKEN="..."                 # or put APIFY_TOKEN=... in leads/.env (git-ignored)
    python3 fetch_apify.py --test            # tiny run: 1 district, 5 places, hard $ cap
    python3 fetch_apify.py --dry-run         # print the exact inputs, spend nothing
    python3 fetch_apify.py                   # default: 5 best districts, $4 total budget
    python3 clean_leads.py data/apify_places.csv

Spending is capped THREE ways: --max-per-search (places), --max-usd-per-run (Apify's
maxTotalChargeUsd) and --budget-usd (stop starting runs once total spend reaches it).
On the Free plan with no card on file you cannot be billed beyond the monthly credit.
Get a token: Apify Console -> Settings -> API & Integrations.
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://api.apify.com/v2"
ACTOR = "compass~crawler-google-places"
DEFAULT_DISTRICTS = ["Miraflores", "San Isidro", "Santiago de Surco", "San Borja", "La Molina"]
DEFAULT_SEARCHES = ["dentista", "clínica dental", "ortodoncia"]
TERMINAL = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
CSV_COLUMNS = ["title", "address", "phone", "phoneUnformatted", "website", "totalScore", "reviewsCount",
               "categoryName", "categories", "placeId", "url", "permanentlyClosed", "temporarilyClosed",
               "neighborhood", "city", "searchString"]


class ApiError(Exception):
    pass


def load_token():
    tok = os.environ.get("APIFY_TOKEN", "").strip()
    if tok:
        return tok
    envfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(envfile):
        with open(envfile, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("APIFY_TOKEN="):
                    return line.split("=", 1)[1].strip().strip("'\"")
    return ""


def explain(code, body):
    try:
        err = json.loads(body).get("error", {})
    except ValueError:
        err = {}
    msg = err.get("message") or body[:300]
    low = (msg + " " + err.get("type", "")).lower()
    if code == 401 or "token" in low and "invalid" in low:
        hint = "Token missing/invalid. Copy it again from Console > Settings > API & Integrations."
    elif code == 402 or "credit" in low or "usage" in low and "limit" in low:
        hint = "Out of monthly credit (Free plan). Wait for renewal or use another source (SOURCES.md)."
    elif "max-total-charge" in low:
        hint = "The per-run $ cap is below this actor's minimum; raise --max-usd-per-run a little."
    elif code == 404:
        hint = "Actor or run not found (the actor may have been renamed). Check apify.com/compass/crawler-google-places."
    elif code == 429:
        hint = "Rate limited; wait a minute and re-run."
    else:
        hint = "See the message above."
    return f"Apify API error {code}: {msg}\n  -> {hint}"


def api(method, path, token, body=None, params=None):
    url = API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise ApiError(explain(e.code, e.read().decode(errors="replace"))) from None
    except urllib.error.URLError as e:
        raise ApiError(f"Network error reaching Apify ({e.reason}). Is api.apify.com allowed by your network?") from None


def build_input(district, searches, max_per_search):
    return {
        "searchStringsArray": searches,
        "locationQuery": f"{district}, Lima, Perú",
        "maxCrawledPlacesPerSearch": max_per_search,
        "language": "es",
        "countryCode": "pe",
        # Only clinics WITHOUT a website: the ones we can sell to. Costs +$0.001/place on the Free plan
        # but we then pay only for relevant places (verified live: Free plan = $0.004/place + $0.001 per filter).
        "website": "withoutWebsite",
        # NOT skipClosedPlaces: it is a paid filter and clean_leads.py drops closed places for free.
        # Enrichments stay OFF (extra per place); reviews are the biggest cost driver.
    }


def run_actor(token, run_input, max_usd, poll_every=5, max_wait=900):
    """Start one run, wait for it, return (run_object, items)."""
    run = api("POST", f"/acts/{ACTOR}/runs", token, run_input,
              {"maxTotalChargeUsd": max_usd, "waitForFinish": 60})["data"]
    waited = 0
    while run.get("status") not in TERMINAL:
        if waited > max_wait:
            api("POST", f"/actor-runs/{run['id']}/abort", token)
            raise ApiError(f"Run {run['id']} took over {max_wait}s; aborted it.")
        run = api("GET", f"/actor-runs/{run['id']}", token, params={"waitForFinish": 60})["data"]
        waited += poll_every
    items = []
    if run.get("defaultDatasetId"):
        items = api("GET", f"/datasets/{run['defaultDatasetId']}/items", token,
                    params={"format": "json", "clean": "true"})
    return run, items


def flat(item):
    row = {k: item.get(k, "") for k in CSV_COLUMNS}
    cats = item.get("categories")
    row["categories"] = "|".join(cats) if isinstance(cats, list) else (cats or "")
    return row


def run_cost(run):
    for k in ("usageTotalUsd", "totalChargeUsd"):
        if isinstance(run.get(k), (int, float)):
            return float(run[k])
    return 0.0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--districts", nargs="*", default=DEFAULT_DISTRICTS)
    ap.add_argument("--searches", nargs="*", default=DEFAULT_SEARCHES)
    ap.add_argument("--max-per-search", type=int, default=40)
    ap.add_argument("--max-usd-per-run", type=float, default=1.0)
    ap.add_argument("--budget-usd", type=float, default=4.0, help="stop starting new runs once spend reaches this")
    ap.add_argument("--out", default="data/apify_places.csv")
    ap.add_argument("--test", action="store_true", help="1 district, 5 places per search, $0.50 cap")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.test:
        args.districts, args.searches = ["Miraflores"], ["dentista"]
        args.max_per_search, args.max_usd_per_run, args.budget_usd = 5, 0.5, 0.5

    plan = [(d, build_input(d, args.searches, args.max_per_search)) for d in args.districts]
    print(f"{len(plan)} run(s); caps: {args.max_per_search} places/search, "
          f"${args.max_usd_per_run:.2f}/run, ${args.budget_usd:.2f} total.")
    if args.dry_run:
        for d, inp in plan:
            print(f"--- {d}\n{json.dumps(inp, ensure_ascii=False)}")
        return 0

    token = load_token()
    if not token:
        sys.exit("No token found. Set APIFY_TOKEN (or put it in leads/.env). Console > Settings > API & Integrations.")

    seen, rows, spent, notes = set(), [], 0.0, []
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    try:
        for d, inp in plan:
            remaining = args.budget_usd - spent
            if remaining < 0.05:
                notes.append(f"Budget reached before {d}; remaining districts skipped.")
                break
            run, items = run_actor(token, inp, min(args.max_usd_per_run, remaining))
            cost = run_cost(run)
            spent += cost
            new = 0
            for it in items:
                pid = it.get("placeId") or it.get("url")
                if pid and pid not in seen:
                    seen.add(pid)
                    rows.append(flat(it))
                    new += 1
            print(f"{d}: status={run.get('status')} items={len(items)} new={new} cost=${cost:.3f} "
                  f"(total ${spent:.3f}) run={run.get('id')}")
            if run.get("status") != "SUCCEEDED":
                notes.append(f"{d}: run ended as {run.get('status')} ({run.get('statusMessage', '')})")
    except ApiError as e:
        notes.append(str(e))
    except KeyboardInterrupt:
        notes.append("Interrupted; saving what we have.")

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} places -> {args.out}; total spend reported by Apify: ${spent:.3f}")
    if rows and spent:
        print(f"Real price on your plan: about ${spent / len(rows) * 1000:.2f} per 1,000 places.")
    for n in notes:
        print("NOTE:", n)
    return 1 if notes and not rows else 0


if __name__ == "__main__":
    sys.exit(main())
