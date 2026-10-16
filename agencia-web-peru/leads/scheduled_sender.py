#!/usr/bin/env python3
"""Scheduled, paced WhatsApp sender for a DEDICATED always-on PC that you own (never the cloud).

It talks to the local whatsapp-mcp bridge (github.com/lharries/whatsapp-mcp, REST on localhost:8080) and
reads/updates the outreach CSV. Dry-run by default; nothing is sent without --live.

    python3 scheduled_sender.py --batch data/outreach_batch1.csv                 # dry-run, shows what it would do
    python3 scheduled_sender.py --test-to 5491159339911 --live                   # one test message to your own number
    python3 scheduled_sender.py --batch data/outreach_batch1.csv --live \\
        --db ../../whatsapp-mcp/whatsapp-bridge/store/messages.db --followups     # the real, paced loop

Safeguards (all on by default): Lima working hours, daily cap, random 10-30 min gap, one follow-up max,
replies/opt-outs read from the bridge DB and written to the CSV (`replied`, `stop`), a STOP file that halts
everything, and a circuit breaker after 3 failed sends in a row. Only rows with `opt_in` filled are contacted
when --require-opt-in is set (recommended: fill it only for leads that asked to be contacted).
"""
import argparse
import json
import os
import random
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from send_queue import LIMA, delay_seconds, in_hours, load, parse_hours, sent_today

EXTRA_COLUMNS = ("sent", "replied", "followup_sent", "stop", "notes")
OPT_OUT = re.compile(
    r"\b(no me (escrib|moles|contact|vuelv|manden|envi)\w*|no (me )?interesa\w*|no gracias|"
    r"(dej\w+|deje) de (escrib|molest|contact)\w*|(dar|dame|darme|den|denme)\w* de baja|baja|stop|spam|"
    r"quien (le )?(dio|dió)|bloque\w*)\b|^\s*no\s*[.!]*\s*$",
    re.I,
)


def is_opt_out(text):
    return bool(OPT_OUT.search(text or ""))


def save(path, rows):
    import csv
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def parse_ts(s):
    """Parse our own `sent` stamps and the bridge's sqlite timestamps; None if unreadable."""
    s = (s or "").replace("skipped ", "").strip()
    if not s:
        return None
    s = s.replace(" ", "T", 1)
    s = re.sub(r"(\.\d{6})\d+", r"\1", s)
    s = re.sub(r"([+-]\d\d)(\d\d)$", r"\1:\2", s)
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def digits(phone):
    return re.sub(r"\D", "", phone or "")


def sync_replies(rows, db_path, now):
    """Mark `replied`/`stop` from incoming messages in the bridge DB. Returns how many rows changed."""
    if not db_path or not os.path.exists(db_path):
        return 0
    changed = 0
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        for r in rows:
            sent = (r.get("sent") or "").strip()
            if not sent or sent.startswith("skipped") or (r.get("stop") or "").strip():
                continue
            since = parse_ts(sent)
            jid = digits(r["phone"]) + "@s.whatsapp.net"
            msgs = con.execute(
                "SELECT content, timestamp FROM messages WHERE chat_jid = ? AND is_from_me = 0 ORDER BY timestamp",
                (jid,),
            ).fetchall()
            for content, ts in msgs:
                t = parse_ts(ts)
                if since and t and t < since - timedelta(minutes=1):
                    continue
                if not (r.get("replied") or "").strip():
                    r["replied"] = now.astimezone(LIMA).isoformat(timespec="minutes")
                    changed += 1
                if is_opt_out(content):
                    r["stop"] = "optout " + now.astimezone(LIMA).date().isoformat()
                    changed += 1
                    break
    finally:
        con.close()
    return changed


def followup_due(r, now, days=3):
    sent = (r.get("sent") or "").strip()
    if not sent or sent.startswith("skipped") or (r.get("followup_sent") or "").strip():
        return False
    if (r.get("replied") or "").strip() or (r.get("stop") or "").strip() or not (r.get("followup") or "").strip():
        return False
    t = parse_ts(sent)
    return bool(t) and now - t >= timedelta(days=days)


def next_job(rows, now, followups, require_opt_in):
    blocked = lambda r: (r.get("stop") or "").strip() or (require_opt_in and not (r.get("opt_in") or "").strip())
    if followups:
        for r in rows:
            if not blocked(r) and followup_due(r, now):
                return r, "followup"
    for r in rows:
        if not blocked(r) and not (r.get("sent") or "").strip():
            return r, "first"
    return None, None


def http_send(url, recipient, message):
    body = json.dumps({"recipient": recipient, "message": message}).encode()
    req = urllib.request.Request(url.rstrip("/") + "/api/send", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode() or "{}")
            return bool(data.get("success")), data.get("message", "")
    except (urllib.error.URLError, OSError, ValueError) as e:
        return False, str(e)


def main(argv=None, now_fn=lambda: datetime.now(timezone.utc), sleep=time.sleep, send=http_send, rng=random):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--batch", default="data/outreach_batch1.csv")
    ap.add_argument("--bridge-url", default="http://localhost:8080")
    ap.add_argument("--db", default="", help="path to whatsapp-bridge/store/messages.db (enables reply/opt-out sync)")
    ap.add_argument("--live", action="store_true", help="actually send (default: dry-run)")
    ap.add_argument("--test-to", default="", help="send one test message to this number and exit")
    ap.add_argument("--daily-cap", type=int, default=10)
    ap.add_argument("--min-minutes", type=float, default=10)
    ap.add_argument("--max-minutes", type=float, default=30)
    ap.add_argument("--hours", default="9-18", help="allowed window, Lima time (24h)")
    ap.add_argument("--followups", action="store_true", help="also send the single follow-up after 3+ days")
    ap.add_argument("--require-opt-in", action="store_true", help="only contact rows whose `opt_in` column is filled")
    ap.add_argument("--stop-file", default="STOP")
    ap.add_argument("--once", action="store_true", help="do at most one send, then exit")
    args = ap.parse_args(argv)
    start, end = parse_hours(args.hours)

    if args.test_to:
        msg = "Hola, esto es una prueba de mensaje."
        if not args.live:
            print(f"[dry-run] enviaría a {digits(args.test_to)}: {msg}")
            return 0
        ok, info = send(args.bridge_url, digits(args.test_to), msg)
        print("Enviado." if ok else f"Falló: {info}")
        return 0 if ok else 1

    rows = load(args.batch)
    for r in rows:
        for c in EXTRA_COLUMNS:
            r.setdefault(c, "")
    if args.require_opt_in:
        for r in rows:
            r.setdefault("opt_in", "")
    failures = 0
    while True:
        now = now_fn()
        if os.path.exists(args.stop_file):
            print(f"Archivo {args.stop_file} presente: detenido.")
            return 0
        if sync_replies(rows, args.db, now):
            save(args.batch, rows)
        if not in_hours(now, start, end):
            print(f"Fuera de horario ({args.hours} hora de Lima).")
            if args.once or not args.live:
                return 0
            sleep(300)
            continue
        if sent_today(rows, now) >= args.daily_cap:
            print(f"Tope diario ({args.daily_cap}) alcanzado.")
            if args.once or not args.live:
                return 0
            sleep(900)
            continue
        r, kind = next_job(rows, now, args.followups, args.require_opt_in)
        if not r:
            print("Nada pendiente.")
            return 0
        text = r["followup"] if kind == "followup" else r["message"]
        stamp = now.astimezone(LIMA).isoformat(timespec="minutes")
        print(f"[{kind}] {r['name']} · {r['phone']}\n  {text}")
        if not args.live:
            print("[dry-run] no se envió. Usa --live para enviar.")
            return 0
        ok, info = send(args.bridge_url, digits(r["phone"]), text)
        if ok:
            failures = 0
            r["followup_sent" if kind == "followup" else "sent"] = stamp
            save(args.batch, rows)
        else:
            failures += 1
            r["notes"] = (r.get("notes") or "") + f" send_fail {stamp}: {info}"
            save(args.batch, rows)
            print(f"Falló el envío: {info}")
            if failures >= 3:
                print("3 fallos seguidos: me detengo (revisa el puente / la sesión de WhatsApp).")
                return 1
        if args.once:
            return 0
        sleep(delay_seconds(rng, args.min_minutes, args.max_minutes))


if __name__ == "__main__":
    sys.exit(main())
