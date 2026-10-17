"""Estimate, then download, Databento CME data (default: WTI crude, CL) as Parquet.

Default run only prints the cost. Nothing is downloaded without --download, and the
download aborts if the total estimate exceeds --max-cost (USD).
"""
import argparse
import os
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

import databento as db

HERE = Path(__file__).resolve().parent
DATASET = "GLBX.MDP3"


def load_key():
    key = os.environ.get("DATABENTO_API_KEY")
    env_file = HERE / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text().splitlines():
            name, _, value = line.partition("=")
            if name.strip() == "DATABENTO_API_KEY":
                key = value.strip().strip("\"'")
    if not key:
        sys.exit("DATABENTO_API_KEY not set (export it or put it in footprint-backtest/.env)")
    return key


def retry(fn, tries=4, **kw):
    """Databento occasionally returns 5xx on long runs; back off and retry."""
    import time as _t
    for n in range(tries):
        try:
            return fn(**kw)
        except db.common.error.BentoServerError:
            if n == tries - 1:
                raise
            _t.sleep(2 ** (n + 1))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbol", default="CL.v.0",
                   help="CL.v.0 = front month by volume (continuous); or a raw symbol like CLZ6")
    p.add_argument("--start", required=True, help="e.g. 2026-10-05")
    p.add_argument("--end", required=True, help="exclusive, e.g. 2026-10-07")
    p.add_argument("--schemas", nargs="+", default=["trades", "mbp-10"])
    p.add_argument("--daily-window", help="local HH:MM-HH:MM each weekday only, e.g. 08:00-13:00 (cuts cost)")
    p.add_argument("--tz", default="America/Argentina/Buenos_Aires", help="timezone of --daily-window")
    p.add_argument("--max-cost", type=float, default=1.0, help="abort if total estimate > this USD")
    p.add_argument("--download", action="store_true", help="actually download (default: estimate only)")
    args = p.parse_args()

    stype = "continuous" if "." in args.symbol else "raw_symbol"
    client = db.Historical(load_key())
    common = dict(dataset=DATASET, symbols=[args.symbol], stype_in=stype)

    # list of (start, end) request ranges: one per weekday window, or the whole range
    if args.daily_window:
        a, b = (time.fromisoformat(x) for x in args.daily_window.split("-"))
        tz = ZoneInfo(args.tz)
        ranges, day = [], datetime.fromisoformat(args.start).date()
        while day < datetime.fromisoformat(args.end).date():
            if day.weekday() < 5:
                ranges.append((datetime.combine(day, a, tz).astimezone(ZoneInfo("UTC")).isoformat(),
                               datetime.combine(day, b, tz).astimezone(ZoneInfo("UTC")).isoformat()))
            day += timedelta(days=1)
    else:
        ranges = [(args.start, args.end)]

    total = 0.0
    for schema in args.schemas:
        cost = sum(retry(client.metadata.get_cost, schema=schema, start=s0, end=e0, **common) for s0, e0 in ranges)
        size_gb = sum(retry(client.metadata.get_billable_size, schema=schema, start=s0, end=e0, **common)
                      for s0, e0 in ranges) / 1e9
        print(f"{schema:10s} {len(ranges):3d} range(s) ~{size_gb:7.3f} GB   ${cost:8.4f}")
        total += cost
    print(f"total    ${total:.4f}  (limit ${args.max_cost:.2f})")

    if not args.download:
        print("estimate only; re-run with --download to fetch")
        return
    if total > args.max_cost:
        sys.exit("estimate above --max-cost; shorten the range or raise the limit")

    out = HERE / "data"
    out.mkdir(exist_ok=True)
    tag = f"{args.symbol.replace('.', '_')}_{args.start}_{args.end}"
    if args.daily_window:
        tag += "_w" + args.daily_window.replace(":", "").replace("-", "to")
    for schema in args.schemas:
        parts = []
        for k, (s0, e0) in enumerate(ranges):
            dbn = out / f"{schema}_{tag}_{k:03d}.dbn.zst"
            store = retry(client.timeseries.get_range, schema=schema, start=s0, end=e0, path=dbn, **common)
            if store.metadata.limit != 0 or dbn.stat().st_size > 0:
                df = store.to_df()
                if len(df):
                    parts.append(df)
        pq = out / f"{schema}_{tag}.parquet"
        pd.concat(parts).to_parquet(pq)
        print(f"saved {pq}")


if __name__ == "__main__":
    main()
