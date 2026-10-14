#!/usr/bin/env python3
"""Clean, dedupe, qualify and score Google Maps leads for the dental-clinic campaign.

    python3 clean_leads.py data/raw_places.csv [more.csv ...] \
        -o data/leads_clean.csv --rejected data/leads_rejected.csv

Input: output of fetch_places.py, or an export from Outscraper/Apify/etc. (common
column names are auto-detected, see ALIASES).

What it does
  1. Normalizes columns and Peruvian phone numbers (+51, mobile vs landline, wa.me link).
  2. Rejects: closed businesses, non-dental places, big institutions, no contact channel.
  3. Dedupes by place id, by phone (when names overlap) and by name + district.
  4. Classifies the Maps "website": none / social / free_builder / directory / own.
  5. Scores 0-100 and assigns tier A/B/C. Best leads = good reputation, reachable on
     WhatsApp and NO real website (the audit video writes itself).
Every rejected row goes to --rejected with a reason, so nothing disappears silently.
"""
import argparse
import csv
import re
import sys
import unicodedata
from urllib.parse import urlparse

# ---------- column detection ----------
ALIASES = {
    "place_id": ["place_id", "placeid", "google_id", "id", "cid", "place_cid"],
    "name": ["name", "title", "business_name", "displayname", "nombre"],
    "address": ["address", "full_address", "formatted_address", "direccion", "street"],
    "phone": ["phone", "phone_national", "phone_1", "phones", "telefono", "phone_number"],
    "phone_international": ["phone_international", "international_phone_number", "phoneunformatted"],
    # NOTE: never alias bare "url" here: in Apify exports it is the Google Maps link, not the clinic site.
    "website": ["website", "site", "web", "websiteuri"],
    "rating": ["rating", "reviews_rating", "stars", "totalscore"],
    "reviews": ["reviews", "reviews_count", "user_ratings_total", "reviewscount", "reviews_total"],
    "business_status": ["business_status", "status"],
    "closed_flag": ["permanently_closed", "temporarily_closed", "is_closed",
                    "permanentlyclosed", "temporarilyclosed"],
    "maps_url": ["maps_url", "googlemapsuri", "location_link", "google_maps_url", "link", "url"],
    "category": ["primary_type", "category", "type", "main_category", "categoryname"],
    "types": ["types", "categories", "subtypes"],
    "district_col": ["district", "distrito", "city", "neighborhood"],
}


def norm_header(h):
    return re.sub(r"[^a-z0-9]+", "_", h.strip().lower()).strip("_")


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def fold(s):
    return re.sub(r"\s+", " ", strip_accents(s or "").lower()).strip()


def canon_row(raw):
    """Map one raw CSV row to canonical keys."""
    low = {norm_header(k): (v or "").strip() for k, v in raw.items() if k}
    out = {}
    for canon, names in ALIASES.items():
        out[canon] = ""
        if canon == "closed_flag":  # several flag columns: closed if ANY is truthy
            if any(fold(low.get(n, "")) in ("true", "1", "yes", "si") for n in names):
                out[canon] = "true"
            continue
        for n in names:
            if low.get(n):
                out[canon] = low[n]
                break
    return out


# ---------- phones (Peru) ----------
def parse_phones(*fields):
    """Return list of (e164, type) with type in mobile|landline_lima|landline_other."""
    found, seen = [], set()
    for field in fields:
        for chunk in re.split(r"[,;/|\n]+", field or ""):
            d = re.sub(r"\D", "", chunk)
            if not d:
                continue
            if d.startswith("00"):
                d = d[2:]
            if d.startswith("51") and len(d) in (10, 11):
                d = d[2:]
            elif d.startswith("0"):
                d = d[1:]
            if len(d) == 9 and d.startswith("9"):
                kind = "mobile"
            elif len(d) == 8 and d.startswith("1"):
                kind = "landline_lima"
            elif len(d) == 7 and d[0] in "2345678":
                d, kind = "1" + d, "landline_lima"  # bare Lima number, add area code
            elif len(d) == 8 and d[0] in "234567":
                kind = "landline_other"  # other provinces (2-digit area code + 6)
            else:
                continue
            e164 = "+51" + d
            if e164 not in seen:
                seen.add(e164)
                found.append((e164, kind))
    order = {"mobile": 0, "landline_lima": 1, "landline_other": 2}
    return sorted(found, key=lambda t: order[t[1]])


# ---------- websites ----------
SOCIAL = ("instagram.com", "facebook.com", "fb.com", "fb.me", "m.facebook.com", "linktr.ee",
          "linktree", "beacons.ai", "wa.me", "api.whatsapp.com", "whatsapp.com", "tiktok.com",
          "youtube.com", "youtu.be", "twitter.com", "x.com", "taplink", "bio.link", "linkin.bio",
          "campsite.bio", "lnk.bio", "linktr.")
FREE_BUILDER = ("wixsite.com", "business.site", "negocio.site", "weebly.com", "webnode.",
                "blogspot.com", "wordpress.com", "godaddysites.com", "site123.me", "jimdosite.com",
                "mystrikingly.com", "carrd.co", "sites.google.com", "my.canva.site", "canva.site",
                "webflow.io", "framer.website", "ueniweb.com", "ueni.com")
DIRECTORY = ("doctoralia.", "docplanner", "paginasamarillas", "yelp.", "tripadvisor", "cylex",
             "miclinica", "topdoctors", "mapcarta", "foursquare", "infobel", "guiaempresas")


def host_of(url):
    u = url.strip()
    if not re.match(r"^[a-z]+://", u, re.I):
        u = "http://" + u
    try:
        return (urlparse(u).hostname or "").lower().removeprefix("www.")
    except ValueError:
        return ""


def classify_website(url):
    if not url.strip():
        return "none", ""
    h = host_of(url)
    if not h or "." not in h:
        return "none", ""
    if any(s in h for s in SOCIAL):
        return "social", url.strip()
    if any(s in h for s in FREE_BUILDER):
        return "free_builder", ""
    if any(s in h for s in DIRECTORY):
        return "directory", ""
    return "own", ""


# ---------- districts ----------
DISTRICTS = [
    "Santiago de Surco", "San Juan de Lurigancho", "San Juan de Miraflores", "San Martin de Porres",
    "Villa Maria del Triunfo", "Villa El Salvador", "Magdalena del Mar", "Jesus Maria", "Miraflores",
    "San Isidro", "San Borja", "La Molina", "Barranco", "Lince", "Pueblo Libre", "San Miguel",
    "Surquillo", "Brena", "La Victoria", "Chorrillos", "San Luis", "Los Olivos", "Independencia",
    "Comas", "Ate", "Santa Anita", "El Agustino", "Rimac", "Carabayllo", "Puente Piedra", "Callao",
]
# "Lima" alone is NOT a district (every address says "Lima"); only the Cercado phrasing counts.
CERCADO_RE = re.compile(r"\b(cercado de lima|lima cercado|cercado)\b")
DISTRICT_SYNONYMS = {"surco": "Santiago de Surco", "sjl": "San Juan de Lurigancho",
                     "sjm": "San Juan de Miraflores", "smp": "San Martin de Porres",
                     "vmt": "Villa Maria del Triunfo", "ves": "Villa El Salvador"}
DISPLAY = {"Brena": "Breña", "Rimac": "Rímac", "San Martin de Porres": "San Martín de Porres",
           "Jesus Maria": "Jesús María", "Villa Maria del Triunfo": "Villa María del Triunfo"}


def find_district(address):
    a = fold(address)
    best = ""
    for d in DISTRICTS:
        if re.search(r"\b" + re.escape(fold(d)) + r"\b", a):
            if len(d) > len(best):
                best = d
    if best:
        return DISPLAY.get(best, best)
    for syn, d in DISTRICT_SYNONYMS.items():
        if re.search(r"\b" + syn + r"\b", a):
            return DISPLAY.get(d, d)
    if CERCADO_RE.search(a):
        return "Lima Cercado"
    return ""


# ---------- qualification ----------
DENTAL_RE = re.compile(r"dent|odont|ortodon|estomat|sonris|implant|endodon|periodon|carilla|blanqueamiento")
NOT_CLINIC_RE = re.compile(r"deposito|distribuidor|insumo|supply|laboratorio|protesis dental lab|"
                           r"escuela|instituto|universidad|academia|importador|ventas? de")
INSTITUTION_RE = re.compile(r"essalud|minsa|hospital|policlinico (naval|militar)|universidad|"
                            r"clinica (internacional|ricardo palma|san felipe|anglo americana|javier prado|"
                            r"san pablo|delgado)|\bsanna\b|oncosalud|pacifico seguros|rimac seguros")
NAME_STOP = {"dental", "dentista", "dentistas", "clinica", "odontologia", "odontologico", "odontologica",
             "centro", "consultorio", "estetica", "sonrisa", "de", "del", "la", "el", "y", "e", "dr", "dra",
             "dr.", "dra.", "los", "las", "lima", "peru", "especialidades", "integral"}


def name_tokens(name):
    return {t for t in re.findall(r"[a-z0-9]+", fold(name)) if len(t) > 2 and t not in NAME_STOP}


def to_float(s):
    try:
        return float(str(s).replace(",", "."))
    except ValueError:
        return 0.0


def to_int(s):
    d = re.sub(r"\D", "", str(s))
    return int(d) if d else 0


def score(r):
    s, why = 0, []
    wt = r["website_type"]
    if wt in ("none", "directory"):
        s += 40; why.append("sin web propia")
    elif wt in ("social", "free_builder"):
        s += 32; why.append("solo redes/web gratuita")
    if r["phone_type"] == "mobile":
        s += 20; why.append("WhatsApp")
    elif r["phone"]:
        s += 6
    rating, reviews = r["rating_f"], r["reviews_i"]
    if rating >= 4.5: s += 15
    elif rating >= 4.2: s += 11
    elif rating >= 3.8: s += 5
    if reviews >= 100: s += 15
    elif reviews >= 40: s += 11
    elif reviews >= 15: s += 7
    elif reviews >= 5: s += 3
    if r["social"]:
        s += 5
    s = min(s, 100)
    tier = "A" if s >= 70 else "B" if s >= 50 else "C"
    if wt == "own":
        tier = "C"  # already has a website: weak fit for a first-website offer (pitch speed/mobile instead)
    return s, tier, why


def note_for(r):
    bits = []
    if r["rating_f"] and r["reviews_i"]:
        bits.append(f"{r['rating_f']:.1f} estrellas, {r['reviews_i']} reseñas en Google")
    elif r["rating_f"]:
        bits.append(f"{r['rating_f']:.1f} estrellas en Google")
    bits.append({"none": "su ficha no tiene web", "directory": "su ficha solo enlaza a un directorio",
                 "social": "su ficha solo enlaza a redes sociales",
                 "free_builder": "su web es una página gratuita básica",
                 "own": "ya tiene web propia (revisar velocidad/móvil)"}[r["website_type"]])
    return "; ".join(bits)


OUT_COLUMNS = [
    "tier", "score", "name", "district", "phone", "phone_type", "whatsapp_link", "other_phones",
    "website", "website_type", "social", "rating", "reviews", "address", "maps_url", "place_id",
    "personalization_note",
    # tracker columns, filled by hand while doing outreach
    "channel", "touch1_date", "touch2_date", "touch3_date", "replied", "audit_accepted",
    "call_booked", "won", "notes",
]


def process(rows, extra_exclude=()):
    kept, rejected = [], []
    extra = [fold(x) for x in extra_exclude]

    def reject(row, reason):
        rejected.append({"reason": reason, **{k: row.get(k, "") for k in ("name", "address", "phone", "website", "place_id")}})

    for c in rows:
        name = c["name"]
        fname, fcat = fold(name), fold(c["category"] + " " + c["types"])
        if not name:
            reject(c, "no_name"); continue
        status = fold(c["business_status"])
        closed = ("closed" in status or "cerrad" in status) and "operational" not in status
        if closed or fold(c["closed_flag"]) in ("true", "1", "yes", "si"):
            reject(c, "closed"); continue
        if not (DENTAL_RE.search(fname) or DENTAL_RE.search(fcat)):
            reject(c, "not_dental"); continue
        if NOT_CLINIC_RE.search(fname) and "clinica" not in fname:
            reject(c, "not_a_clinic(supplier/lab/school)"); continue
        if INSTITUTION_RE.search(fname) or any(x and x in fname for x in extra):
            reject(c, "institution_or_chain"); continue

        phones = parse_phones(c["phone"], c["phone_international"])
        wtype, social = classify_website(c["website"])
        if not phones and not social:
            reject(c, "no_contact_channel"); continue

        main = phones[0] if phones else ("", "")
        r = {
            "name": name, "address": c["address"],
            "district": find_district(c["address"]) or find_district(c["district_col"]),
            "phone": main[0], "phone_type": main[1],
            "whatsapp_link": f"https://wa.me/{main[0].lstrip('+')}" if main[1] == "mobile" else "",
            "other_phones": "; ".join(p for p, _ in phones[1:]),
            "website": c["website"] if wtype == "own" else "", "website_type": wtype, "social": social,
            "rating_f": to_float(c["rating"]), "reviews_i": to_int(c["reviews"]),
            "maps_url": c["maps_url"] or (f"https://www.google.com/maps/place/?q=place_id:{c['place_id']}" if c["place_id"] else ""),
            "place_id": c["place_id"],
        }
        r["rating"], r["reviews"] = (r["rating_f"] or ""), (r["reviews_i"] or "")
        r["_tokens"] = name_tokens(name)
        r["_namekey"] = (re.sub(r"[^a-z0-9]", "", fname), r["district"])
        r["score"], r["tier"], _ = score(r)
        r["personalization_note"] = note_for(r)
        r["channel"] = "whatsapp" if r["phone_type"] == "mobile" else ("instagram/facebook" if social else "llamada")
        kept.append(r)

    # ---- dedupe: keep the most informative record per clinic ----
    kept.sort(key=lambda r: (-(r["reviews_i"]), -bool(r["phone"]), -bool(r["place_id"])))
    final, ids, phones_seen, names_seen = [], {}, {}, set()
    for r in kept:
        dup = None
        if r["place_id"] and r["place_id"] in ids:
            dup = "duplicate_place_id"
        elif r["_namekey"] in names_seen and r["_namekey"][0]:
            dup = "duplicate_name_district"
        elif r["phone"] and r["phone"] in phones_seen and (phones_seen[r["phone"]] & r["_tokens"] or not r["_tokens"]):
            dup = "duplicate_phone"
        if dup:
            rejected.append({"reason": dup, "name": r["name"], "address": r["address"],
                             "phone": r["phone"], "website": r["website"], "place_id": r["place_id"]})
            continue
        if r["place_id"]:
            ids[r["place_id"]] = True
        names_seen.add(r["_namekey"])
        if r["phone"]:
            phones_seen.setdefault(r["phone"], set()).update(r["_tokens"])
        final.append(r)

    final.sort(key=lambda r: (-r["score"], r["district"], r["name"]))
    return final, rejected


def read_inputs(paths):
    rows = []
    for p in paths:
        with open(p, newline="", encoding="utf-8-sig") as f:
            sample = f.read(4096)
            f.seek(0)
            if p.lower().endswith(".tsv"):
                dialect = csv.excel_tab
            else:
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
                except csv.Error:
                    dialect = csv.excel
            rows.extend(canon_row(r) for r in csv.DictReader(f, dialect=dialect))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", default="data/leads_clean.csv")
    ap.add_argument("--rejected", default="data/leads_rejected.csv")
    ap.add_argument("--exclude", nargs="*", default=[], help="extra name keywords to drop (e.g. chains)")
    args = ap.parse_args(argv)

    rows = read_inputs(args.inputs)
    final, rejected = process(rows, args.exclude)
    with open(args.out, "w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig so Excel shows accents
        w = csv.DictWriter(f, fieldnames=OUT_COLUMNS, extrasaction="ignore")
        w.writeheader()
        w.writerows(final)
    with open(args.rejected, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["reason", "name", "address", "phone", "website", "place_id"])
        w.writeheader()
        w.writerows(rejected)

    n = len(final)
    tiers = {t: sum(r["tier"] == t for r in final) for t in "ABC"}
    wa = sum(r["phone_type"] == "mobile" for r in final)
    noweb = sum(r["website_type"] != "own" for r in final)
    print(f"Read {len(rows)} rows -> kept {n}, rejected {len(rejected)}")
    print(f"Tiers: A={tiers['A']}  B={tiers['B']}  C={tiers['C']}")
    print(f"WhatsApp-able (mobile): {wa}   Without own website: {noweb}")
    reasons = {}
    for r in rejected:
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    print("Rejected by reason:", ", ".join(f"{k}={v}" for k, v in sorted(reasons.items())) or "none")
    print(f"Wrote {args.out} and {args.rejected}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
