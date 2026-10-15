"""Estimate, then download, Databento CME data (default: WTI crude, CL) as Parquet.

Default run only prints the cost. Nothing is downloaded without --download, and the
download aborts if the total estimate exceeds --max-cost (USD).
"""
import argparse
import os
import sys
from pathlib import Path

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


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbol", default="CL.v.0",
                   help="CL.v.0 = front month by volume (continuous); or a raw symbol like CLZ6")
    p.add_argument("--start", required=True, help="e.g. 2026-10-05")
    p.add_argument("--end", required=True, help="exclusive, e.g. 2026-10-07")
    p.add_argument("--schemas", nargs="+", default=["trades", "mbp-10"])
    p.add_argument("--max-cost", type=float, default=1.0, help="abort if total estimate > this USD")
    p.add_argument("--download", action="store_true", help="actually download (default: estimate only)")
    args = p.parse_args()

    stype = "continuous" if "." in args.symbol else "raw_symbol"
    client = db.Historical(load_key())
    common = dict(dataset=DATASET, symbols=[args.symbol], stype_in=stype,
                  start=args.start, end=args.end)

    total = 0.0
    for schema in args.schemas:
        cost = client.metadata.get_cost(schema=schema, **common)
        size_gb = client.metadata.get_billable_size(schema=schema, **common) / 1e9
        print(f"{schema:8s} ~{size_gb:7.3f} GB   ${cost:8.4f}")
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
    for schema in args.schemas:
        dbn = out / f"{schema}_{tag}.dbn.zst"
        pq = out / f"{schema}_{tag}.parquet"
        store = client.timeseries.get_range(schema=schema, path=dbn, **common)
        store.to_parquet(pq)  # prices as float, timestamps as datetimes, symbols mapped
        print(f"saved {pq}")


if __name__ == "__main__":
    main()
