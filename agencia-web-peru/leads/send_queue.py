#!/usr/bin/env python3
"""Paced, human-in-the-loop WhatsApp queue. Run it on YOUR computer (not in the cloud).

    python3 send_queue.py                      # uses data/outreach_batch1.csv
    python3 send_queue.py --daily-cap 25 --min-minutes 4 --max-minutes 9 --hours 9-18

For each pending lead it opens WhatsApp (Web/Desktop/phone) with the message pre-filled; YOU read it and
press send, then confirm here. Sending is always done by you, by hand. It enforces good habits for a
business number: a daily cap, working hours (Lima time), and a pause between chats. Progress is saved in the CSV (`sent` column), so you can stop and resume.
"""
import argparse
import csv
import random
import sys
import time
import webbrowser
from datetime import datetime, timedelta, timezone

LIMA = timezone(timedelta(hours=-5))  # Peru has no DST


def parse_hours(s):
    a, b = s.split("-")
    return int(a), int(b)


def in_hours(now, start, end):
    return start <= now.astimezone(LIMA).hour < end


def delay_seconds(rng, lo_min, hi_min):
    return rng.uniform(lo_min * 60, hi_min * 60)


def sent_today(rows, now):
    today = now.astimezone(LIMA).date().isoformat()
    return sum(1 for r in rows if (r.get("sent") or "").startswith(today))


def pending(rows):
    return [r for r in rows if not (r.get("sent") or "").strip()]


def load(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def save(path, rows):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def main(argv=None, now_fn=lambda: datetime.now(timezone.utc), sleep=time.sleep, ask=input, opener=webbrowser.open,
         rng=random):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batch", default="data/outreach_batch1.csv")
    ap.add_argument("--daily-cap", type=int, default=25)
    ap.add_argument("--min-minutes", type=float, default=4)
    ap.add_argument("--max-minutes", type=float, default=9)
    ap.add_argument("--hours", default="9-18", help="allowed sending window, Lima time (24h)")
    args = ap.parse_args(argv)
    start, end = parse_hours(args.hours)

    rows = load(args.batch)
    while True:
        now = now_fn()
        if not in_hours(now, start, end):
            print(f"Fuera de horario ({args.hours} hora de Lima). Vuelve más tarde; tu progreso está guardado.")
            return 0
        if sent_today(rows, now) >= args.daily_cap:
            print(f"Tope diario alcanzado ({args.daily_cap}). Hasta mañana 🙂")
            return 0
        todo = pending(rows)
        if not todo:
            print("No quedan pendientes en este lote.")
            return 0
        r = todo[0]
        print(f"\n[{sent_today(rows, now) + 1}/{args.daily_cap}] {r['name']} · {r['district']} · {r['phone']}")
        opener(r["wa_link"])
        ans = ask("Envíalo en WhatsApp y luego: Enter = enviado · s = saltar · q = salir > ").strip().lower()
        if ans == "q":
            save(args.batch, rows)
            return 0
        r["sent"] = ("skipped " if ans == "s" else "") + now.astimezone(LIMA).isoformat(timespec="minutes")
        save(args.batch, rows)
        if ans == "s":
            continue
        wait = delay_seconds(rng, args.min_minutes, args.max_minutes)
        print(f"Pausa de {wait / 60:.1f} min antes del siguiente (Ctrl-C para parar).")
        try:
            sleep(wait)
        except KeyboardInterrupt:
            print("\nParado. Progreso guardado.")
            return 0


if __name__ == "__main__":
    sys.exit(main())
