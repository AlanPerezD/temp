#!/usr/bin/env python3
"""Fetch dental clinics in Lima from the Google Places API (New) - Text Search.

This is the Google-sanctioned way to get Maps data (scraping Maps pages directly
breaks Google's terms and gets blocked). You need your own API key:

    export GOOGLE_MAPS_API_KEY="..."        # or put it in leads/.env (git-ignored)
    python3 fetch_places.py --test            # 1 request: checks key, API, billing
    python3 fetch_places.py --dry-run         # see the planned queries first
    python3 fetch_places.py --max-requests 150
    python3 fetch_places.py --resume          # continue after a daily-quota stop

Full setup walkthrough: GOOGLE_SETUP.md

Phone and website fields are billed at a higher Places tier, so check the current
Google Maps Platform pricing/free allowance and keep --max-requests low at first.
Output: data/raw_places.csv  (feed it to clean_leads.py)

If you'd rather not use the API, any Maps export tool (Outscraper, Apify, etc.)
works too: clean_leads.py understands their common column names.
"""
import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request

ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join(
    "places." + f
    for f in (
        "id,displayName,formattedAddress,nationalPhoneNumber,internationalPhoneNumber,"
        "websiteUri,rating,userRatingCount,businessStatus,googleMapsUri,"
        "primaryType,types,location"
    ).split(",")
) + ",nextPageToken"

# Lima Metropolitana districts, most promising for private dental clinics first.
DISTRICTS = [
    "Miraflores", "San Isidro", "Santiago de Surco", "San Borja", "La Molina",
    "Barranco", "Jesús María", "Lince", "Magdalena del Mar", "Pueblo Libre",
    "San Miguel", "Surquillo", "Lima Cercado", "Breña", "La Victoria",
    "Chorrillos", "San Luis", "Los Olivos", "San Martín de Porres", "Independencia",
    "Comas", "San Juan de Lurigancho", "San Juan de Miraflores",
    "Villa María del Triunfo", "Villa El Salvador", "Ate", "Santa Anita",
    "El Agustino", "Rímac", "Carabayllo", "Puente Piedra", "Callao",
]
QUERIES = ["dentista", "clínica dental", "odontología", "ortodoncia", "estética dental"]

RAW_COLUMNS = [
    "place_id", "name", "address", "phone_national", "phone_international",
    "website", "rating", "reviews", "business_status", "maps_url",
    "primary_type", "types", "lat", "lng", "query",
]


class ApiError(Exception):
    pass


def load_key():
    """GOOGLE_MAPS_API_KEY from the environment, else from leads/.env (never committed)."""
    key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if key:
        return key
    envfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(envfile):
        with open(envfile, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GOOGLE_MAPS_API_KEY="):
                    return line.split("=", 1)[1].strip().strip("'\"")
    return ""


def explain_error(code, body):
    """Turn a Google error response into a plain-language fix."""
    try:
        err = json.loads(body).get("error", {})
    except ValueError:
        err = {}
    msg = err.get("message") or body[:300]
    status = err.get("status", "")
    low = (msg + " " + status).lower()
    if "api key not valid" in low or "api_key_invalid" in low:
        hint = "The key is wrong or was copied incompletely. Create/copy it again in Credentials."
    elif "has not been used" in low or "service_disabled" in low or "is disabled" in low:
        hint = "Enable 'Places API (New)' for the project that owns this key (APIs & Services > Library)."
    elif "billing" in low:
        hint = "Billing is not enabled on the project. Link a billing account (the free allowance still applies)."
    elif code == 403 and ("referer" in low or "ip" in low or "restrict" in low or "blocked" in low):
        hint = "Key restrictions block this request. Use 'None' under Application restrictions for a server-side script and restrict by API instead."
    elif code == 429 or "quota" in low or "resource_exhausted" in low:
        hint = "Quota reached (possibly the daily cap YOU set). Wait for reset or raise the quota, then run with --resume."
    elif code == 403:
        hint = "Permission denied. Check that the key is allowed to call Places API (New)."
    else:
        hint = "See the message above."
    return f"API error {code} {status}: {msg}\n  -> {hint}"


def place_to_row(p, query):
    loc = p.get("location") or {}
    return {
        "place_id": p.get("id", ""),
        "name": (p.get("displayName") or {}).get("text", ""),
        "address": p.get("formattedAddress", ""),
        "phone_national": p.get("nationalPhoneNumber", ""),
        "phone_international": p.get("internationalPhoneNumber", ""),
        "website": p.get("websiteUri", ""),
        "rating": p.get("rating", ""),
        "reviews": p.get("userRatingCount", ""),
        "business_status": p.get("businessStatus", ""),
        "maps_url": p.get("googleMapsUri", ""),
        "primary_type": p.get("primaryType", ""),
        "types": "|".join(p.get("types") or []),
        "lat": loc.get("latitude", ""),
        "lng": loc.get("longitude", ""),
        "query": query,
    }


def search(api_key, text_query, page_token=None):
    body = {"textQuery": text_query, "languageCode": "es", "regionCode": "PE", "pageSize": 20}
    if page_token:
        body["pageToken"] = page_token
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        raise ApiError(explain_error(e.code, e.read().decode(errors="replace"))) from None
    except urllib.error.URLError as e:
        raise ApiError(f"Network error reaching Google ({e.reason}). Check internet/proxy access to places.googleapis.com.") from None


def run_test(key):
    """One cheap request to prove key + API + billing work, and show which fields come back."""
    data = search(key, "dentista en Miraflores, Lima, Perú")
    places = data.get("places", [])
    print(f"OK: Google answered with {len(places)} places (1 request used).")
    for p in places[:3]:
        print("  -", (p.get("displayName") or {}).get("text"), "|", p.get("nationalPhoneNumber", "(no phone)"),
              "|", p.get("websiteUri", "(no website)"), "|", p.get("rating", "-"), "stars")
    has_phone = any(p.get("nationalPhoneNumber") for p in places)
    has_web = any(p.get("websiteUri") for p in places)
    print(f"Phone field returned: {has_phone}; website field returned: {has_web}.")
    print("Next: python3 fetch_places.py --dry-run, then a small first run (--max-requests 30).")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/raw_places.csv")
    ap.add_argument("--districts", nargs="*", default=DISTRICTS)
    ap.add_argument("--queries", nargs="*", default=QUERIES)
    ap.add_argument("--max-requests", type=int, default=150, help="hard cap on API calls (cost guard)")
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--test", action="store_true", help="make ONE request to verify the setup")
    ap.add_argument("--resume", action="store_true", help="keep existing --out rows and skip finished queries")
    args = ap.parse_args(argv)

    plan = [f"{q} en {d}, Lima, Perú" for d in args.districts for q in args.queries]
    done_path = args.out + ".done"

    if args.test:
        key = load_key()
        if not key:
            sys.exit("No key found. Set GOOGLE_MAPS_API_KEY (or put it in leads/.env). See GOOGLE_SETUP.md.")
        try:
            run_test(key)
        except ApiError as e:
            sys.exit(str(e))
        return 0

    worst = args.max_requests * 0.035
    print(f"{len(plan)} queries planned (each can use up to 3 paged requests).")
    print(f"Cap: {args.max_requests} requests -> worst case ${worst:.2f} at $35/1,000 "
          f"(1,000 Enterprise requests/month are free per Google's table; confirm in your Billing report).")
    if args.dry_run:
        print("\n".join(plan[:15]) + ("\n..." if len(plan) > 15 else ""))
        return 0

    key = load_key()
    if not key:
        sys.exit("No key found. Set GOOGLE_MAPS_API_KEY (or put it in leads/.env). See GOOGLE_SETUP.md.")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    seen, rows, finished, calls = set(), [], set(), 0
    if args.resume and os.path.exists(args.out):
        with open(args.out, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        seen = {r["place_id"] for r in rows if r.get("place_id")}
        if os.path.exists(done_path):
            with open(done_path, encoding="utf-8") as f:
                finished = {line.strip() for line in f if line.strip()}
        print(f"Resuming: {len(rows)} places and {len(finished)} finished queries already saved.")

    stop = ""
    try:
        for q in plan:
            if q in finished:
                continue
            token = None
            for _page in range(3):  # Text Search returns at most 3 pages (60 results)
                if calls >= args.max_requests:
                    raise StopIteration
                calls += 1
                data = search(key, q, token)
                for p in data.get("places", []):
                    if p.get("id") and p["id"] not in seen:
                        seen.add(p["id"])
                        rows.append(place_to_row(p, q))
                token = data.get("nextPageToken")
                time.sleep(args.sleep)
                if not token:
                    break
            finished.add(q)
            print(f"{q!r}: {len(rows)} unique places so far ({calls} calls)")
    except StopIteration:
        stop = f"Stopped at --max-requests={args.max_requests}. Re-run with --resume (and a higher cap) to continue."
    except ApiError as e:
        stop = f"{e}\nSaving what we have; fix the issue and re-run with --resume."
    except KeyboardInterrupt:
        stop = "Interrupted; saving what we have. Re-run with --resume to continue."

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=RAW_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    with open(done_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(finished)))
    print(f"Wrote {len(rows)} places -> {args.out}  ({len(finished)}/{len(plan)} queries finished)")
    if stop:
        print(stop)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
