#!/usr/bin/env python3
"""Fetch dental clinics in Lima from the Google Places API (New) - Text Search.

This is the Google-sanctioned way to get Maps data (scraping Maps pages directly
breaks Google's terms and gets blocked). You need your own API key:

    export GOOGLE_MAPS_API_KEY="..."        # Places API (New) enabled, billing on
    python3 fetch_places.py --dry-run         # see the planned queries first
    python3 fetch_places.py --max-requests 150

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
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data/raw_places.csv")
    ap.add_argument("--districts", nargs="*", default=DISTRICTS)
    ap.add_argument("--queries", nargs="*", default=QUERIES)
    ap.add_argument("--max-requests", type=int, default=150, help="hard cap on API calls (cost guard)")
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    plan = [f"{q} en {d}, Lima, Perú" for d in args.districts for q in args.queries]
    print(f"{len(plan)} queries planned (each can use up to 3 paged requests; cap = {args.max_requests}).")
    if args.dry_run:
        print("\n".join(plan[:15]) + ("\n..." if len(plan) > 15 else ""))
        return 0

    key = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not key:
        sys.exit("Set GOOGLE_MAPS_API_KEY first (see header of this file).")

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    seen, rows, calls = set(), [], 0
    try:
        for q in plan:
            token = None
            for _page in range(3):  # Text Search returns at most 3 pages (60 results)
                if calls >= args.max_requests:
                    raise StopIteration
                calls += 1
                try:
                    data = search(key, q, token)
                except urllib.error.HTTPError as e:
                    sys.exit(f"API error {e.code}: {e.read().decode(errors='replace')[:400]}")
                for p in data.get("places", []):
                    if p.get("id") and p["id"] not in seen:
                        seen.add(p["id"])
                        rows.append(place_to_row(p, q))
                token = data.get("nextPageToken")
                time.sleep(args.sleep)
                if not token:
                    break
            print(f"{q!r}: {len(rows)} unique places so far ({calls} calls)")
    except StopIteration:
        print(f"Stopped at --max-requests={args.max_requests}. Re-run with a higher cap to continue.")
    except KeyboardInterrupt:
        print("Interrupted; saving what we have.")

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=RAW_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} places -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
