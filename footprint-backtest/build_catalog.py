"""Convert the downloaded Databento DBN files into a Nautilus Parquet catalog.

Writes the CL instrument (from the `definition` file), TradeTick (from `trades`) and
OrderBookDepth10 (from `mbp-10`) into data/catalog_cl/. Run once per data pull.
"""
import argparse
import glob
from pathlib import Path

from nautilus_trader.adapters.databento.loaders import DatabentoDataLoader
import pandas as pd
import pyarrow.parquet as pq
from nautilus_trader.persistence.catalog import ParquetDataCatalog
from nautilus_trader.persistence.wranglers_v2 import OrderBookDepth10DataWranglerV2

HERE = Path(__file__).resolve().parent


def one(pattern):
    files = sorted(glob.glob(str(HERE / "data" / pattern)))
    if not files:
        raise SystemExit(f"no file matching data/{pattern}; run fetch_data.py first")
    return files


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tag", default="CL_v_0_*", help="file tag from fetch_data.py (glob ok)")
    p.add_argument("--chunk", type=int, default=250_000, help="depth rows per write")
    args = p.parse_args()

    catalog_dir = HERE / "data" / "catalog_cl"
    catalog_dir.mkdir(exist_ok=True)
    catalog = ParquetDataCatalog(catalog_dir)
    loader = DatabentoDataLoader()

    instruments = []
    for f in one(f"definition_{args.tag}.dbn.zst"):
        instruments += loader.from_dbn_file(f, as_legacy_cython=True)
    unique = {i.id: i for i in instruments}
    catalog.write_data(list(unique.values()))
    print("instruments:", [str(i) for i in unique])
    if len(unique) != 1:
        raise SystemExit("range spans a contract roll; pull each contract separately")
    inst = next(iter(unique.values()))
    # records are keyed CL.v.0 (continuous); relabel them as the real contract
    kw = dict(instrument_id=inst.id, price_precision=inst.price_precision, as_legacy_cython=False)

    for f in one(f"trades_{args.tag}.dbn.zst"):
        ticks = loader.from_dbn_file(f, **kw)
        catalog.write_data(ticks)
        print(f"trades: {len(ticks)} from {Path(f).name}")

    # 4M+ depth updates do not fit in memory through the DBN loader, so stream the
    # mbp-10 Parquet through the pyo3 wrangler in chunks.
    wrangler = OrderBookDepth10DataWranglerV2.from_instrument(inst)
    rename = {}
    for i in range(10):
        rename.update({f"bid_px_{i:02d}": f"bid_price_{i}", f"ask_px_{i:02d}": f"ask_price_{i}",
                       f"bid_sz_{i:02d}": f"bid_size_{i}", f"ask_sz_{i:02d}": f"ask_size_{i}",
                       f"bid_ct_{i:02d}": f"bid_count_{i}", f"ask_ct_{i:02d}": f"ask_count_{i}"})
    for f in one(f"mbp-10_{args.tag}.parquet"):
        pf = pq.ParquetFile(f)
        total = 0
        carry = None

        def write(df):
            df = df.rename(columns=rename)
            price_cols = [c for c in df if "_price_" in c]
            df[price_cols] = df[price_cols].fillna(0.0)  # empty levels
            df = df.rename_axis("ts_init").reset_index()
            depth = wrangler.from_pandas(df)
            catalog.write_data(depth)
            return len(depth)

        for batch in pf.iter_batches(batch_size=args.chunk):
            df = batch.to_pandas()  # index = ts_recv
            if carry is not None:
                df = pd.concat([carry, df])
            # catalog files must not share a boundary timestamp: hold back the last ts run
            last = df.index[-1]
            keep = df.index < last
            carry = df[~keep]
            if keep.any():
                total += write(df[keep])
        if carry is not None and len(carry):
            total += write(carry)
        print(f"depth10: {total} from {Path(f).name}")


if __name__ == "__main__":
    main()
