#!/usr/bin/env python3
"""Turn leads_clean.csv into a ready-to-send WhatsApp outreach batch.

    python3 make_outreach.py --sender "Alan" --limit 30
    -> data/outreach_batch1.csv   (name, district, phone, message, wa_link)
    -> data/outreach_batch1.md    (same, readable; each wa_link opens WhatsApp with the text pre-filled)

Only mobile numbers (WhatsApp-able), highest score first, skipping anyone already in --exclude-file.
You still press "send" yourself, one chat at a time (keeps the account safe and the tone human).
"""
import argparse
import csv
import os
import re
import sys
from urllib.parse import quote

TEMPLATE = (
    "Hola, buen día 👋 Soy {sender}. Vi {detail}, muy buen trabajo.\n\n"
    "Noté que su ficha de Google no tiene página web, así que quienes buscan "
    "\"dentista en {district}\" no pueden ver sus tratamientos ni agendar desde ahí. "
    "Armo páginas web para consultorios dentales y esta semana estoy tomando solo 5 "
    "para prepararles el borrador de su web sin costo ni compromiso.\n\n"
    "¿Le envío una mini auditoría de su ficha de Google (3 puntos concretos para atraer más pacientes)? "
    "Si prefiere que no le escriba más, me avisa y listo 🙏"
)


def detail_for(row):
    rating, reviews = row.get("rating", ""), row.get("reviews", "")
    if rating and reviews:
        return f"que tienen {rating}⭐ con {reviews} reseñas en Google"
    return "su consultorio en Google"


def build_message(row, sender):
    district = row.get("district") or "Lima"
    return TEMPLATE.format(sender=sender, detail=detail_for(row), district=district)


def wa_link(phone, message):
    return f"https://wa.me/{phone.lstrip('+')}?text={quote(message)}"


def select(rows, limit, min_reviews=0, exclude=()):
    out = []
    for r in rows:
        if r.get("phone_type") != "mobile" or r["phone"] in exclude:
            continue
        if min_reviews and int(r["reviews"] or 0) < min_reviews:
            continue
        out.append(r)
        if len(out) >= limit:
            break
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--leads", default="data/leads_clean.csv")
    ap.add_argument("--sender", default="[TU NOMBRE]")
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--min-reviews", type=int, default=0)
    ap.add_argument("--out", default="data/outreach_batch1")
    ap.add_argument("--exclude-file", help="CSV with a 'phone' column of numbers already contacted")
    args = ap.parse_args(argv)

    with open(args.leads, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    exclude = set()
    if args.exclude_file and os.path.exists(args.exclude_file):
        with open(args.exclude_file, newline="", encoding="utf-8-sig") as f:
            exclude = {r["phone"] for r in csv.DictReader(f)}

    chosen = select(rows, args.limit, args.min_reviews, exclude)
    batch = []
    for r in chosen:
        msg = build_message(r, args.sender)
        batch.append({"tier": r["tier"], "score": r["score"], "name": r["name"], "district": r["district"],
                      "phone": r["phone"], "message": msg, "wa_link": wa_link(r["phone"], msg),
                      "maps_url": r["maps_url"], "sent": "", "replied": "", "notes": ""})

    with open(args.out + ".csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(batch[0].keys()) if batch else ["name"])
        w.writeheader()
        w.writerows(batch)
    with open(args.out + ".md", "w", encoding="utf-8") as f:
        f.write(f"# Lote de WhatsApp ({len(batch)} consultorios)\n\n"
                "Toca el enlace → se abre WhatsApp con el mensaje listo → revisa → envía. "
                "Marca `sent` en el CSV. Envía en tandas pequeñas (20–30 al día al inicio).\n\n")
        for i, b in enumerate(batch, 1):
            f.write(f"## {i}. {b['name']} · {b['district'] or 's/d'} · {b['tier']}/{b['score']}\n"
                    f"[Abrir WhatsApp]({b['wa_link']}) · [Ver ficha en Maps]({b['maps_url']})\n\n"
                    f"> {b['message'].replace(chr(10), chr(10) + '> ')}\n\n")
    print(f"{len(batch)} messages -> {args.out}.csv / {args.out}.md (sender={args.sender!r})")
    if "[TU NOMBRE]" in args.sender:
        print("NOTE: pass --sender 'Your name' before sending.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
