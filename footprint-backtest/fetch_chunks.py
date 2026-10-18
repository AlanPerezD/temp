"""Download one Databento symbol/schema in yearly chunks (long streams sometimes get cut off),
then merge into one Parquet. Prints the total cost estimate first and aborts above --max-cost."""
import argparse
import sys
from pathlib import Path

import databento as db
import pandas as pd

from fetch_data import DATASET, HERE, load_key, retry


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--symbol", required=True)
    p.add_argument("--schema", default="ohlcv-1h")
    p.add_argument("--start", default="2010-06-07")
    p.add_argument("--end", default="2026-10-16")
    p.add_argument("--max-cost", type=float, default=1.5)
    a = p.parse_args()
    client = db.Historical(load_key())
    stype = "continuous" if "." in a.symbol else "raw_symbol"
    years = pd.date_range(a.start, a.end, freq="YS").strftime("%Y-%m-%d").tolist()
    bounds = [a.start] + [y for y in years if y > a.start] + [a.end]
    ranges = list(zip(bounds[:-1], bounds[1:]))
    common = dict(dataset=DATASET, symbols=[a.symbol], stype_in=stype, schema=a.schema)
    cost = sum(retry(client.metadata.get_cost, start=s, end=e, **common) for s, e in ranges)
    print(f"{a.symbol} {a.schema} {len(ranges)} chunks ${cost:.4f}")
    if cost > a.max_cost:
        sys.exit("above --max-cost")
    out = HERE / "data"
    tag = f"{a.symbol.replace('.', '_')}_{a.start}_{a.end}"
    parts = []
    for s, e in ranges:
        store = retry(client.timeseries.get_range, start=s, end=e, **common)
        df = store.to_df()
        parts.append(df)
        print(f"  {s}..{e}: {len(df)} rows")
    pd.concat(parts).sort_index().to_parquet(out / f"{a.schema}_{tag}.parquet")
    print(f"saved {a.schema}_{tag}.parquet")


if __name__ == "__main__":
    main()
