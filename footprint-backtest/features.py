"""Turn raw CME trades (Databento `trades` schema) into footprint bars and AI-ready rows.

Databento `side` on trades is the aggressor: 'B' = buy aggressor (lifts the ask),
'A' = sell aggressor (hits the bid). Footprint columns: ask_vol = buy-aggressor volume,
bid_vol = sell-aggressor volume at that price.
"""
import argparse
import json
from pathlib import Path

import pandas as pd

CL_TICK = 0.01


def footprint_levels(trades, freq="1min", tick=CL_TICK):
    """One row per (bar, price level) with bid_vol / ask_vol / n_trades."""
    df = trades[trades["side"].isin(["A", "B"])].copy()
    df["bar"] = df["ts_event"].dt.floor(freq)
    df["level"] = (df["price"] / tick).round().astype("int64")
    df["ask_vol"] = df["size"].where(df["side"] == "B", 0)
    df["bid_vol"] = df["size"].where(df["side"] == "A", 0)
    df["n_trades"] = 1
    lv = df.groupby(["bar", "level"], as_index=False)[["bid_vol", "ask_vol", "n_trades"]].sum()
    lv["price"] = (lv["level"] * tick).round(10)
    return lv


def bar_summary(trades, levels, freq="1min", ratio=3.0, min_vol=1):
    """OHLC, volume, delta, POC and diagonal imbalance counts per bar."""
    df = trades[trades["side"].isin(["A", "B"])].sort_values("ts_event")
    df = df.assign(bar=df["ts_event"].dt.floor(freq))
    g = df.groupby("bar")["price"]
    out = pd.DataFrame({"open": g.first(), "high": g.max(), "low": g.min(), "close": g.last()})

    lv = levels.copy()
    lv["vol"] = lv["bid_vol"] + lv["ask_vol"]
    by_bar = lv.groupby("bar")
    out["volume"] = by_bar["vol"].sum()
    out["delta"] = by_bar["ask_vol"].sum() - by_bar["bid_vol"].sum()
    out["poc"] = lv.loc[by_bar["vol"].idxmax(), ["bar", "price"]].set_index("bar")["price"]

    # diagonal imbalances: ask at L vs bid at L-1 (buy), bid at L vs ask at L+1 (sell)
    idx = lv.set_index(["bar", "level"])
    def shifted(col, step):
        key = pd.MultiIndex.from_arrays([lv["bar"], lv["level"] + step])
        return idx[col].reindex(key).fillna(0).to_numpy()
    buy = (lv["ask_vol"] >= min_vol) & (lv["ask_vol"] >= ratio * shifted("bid_vol", -1).clip(min=1e-9))
    sell = (lv["bid_vol"] >= min_vol) & (lv["bid_vol"] >= ratio * shifted("ask_vol", 1).clip(min=1e-9))
    out["buy_imbalances"] = buy.groupby(lv["bar"]).sum()
    out["sell_imbalances"] = sell.groupby(lv["bar"]).sum()
    return out.reset_index()


def book_imbalance(mbp):
    """Top-10 depth imbalance in [-1, 1] per row: (bid - ask) / (bid + ask)."""
    # sizes are uint32 in DBN files; cast first or the subtraction wraps around
    bid = sum(mbp[f"bid_sz_{i:02d}"].astype("float64") for i in range(10))
    ask = sum(mbp[f"ask_sz_{i:02d}"].astype("float64") for i in range(10))
    return (bid - ask) / (bid + ask).where(bid + ask > 0)


def to_jsonl(summary, levels, path):
    """One JSON line per bar: summary fields + [[price, bid_vol, ask_vol], ...] ladder."""
    ladders = {b: g.sort_values("price")[["price", "bid_vol", "ask_vol"]].values.tolist()
               for b, g in levels.groupby("bar")}
    with open(path, "w") as f:
        for row in summary.to_dict("records"):
            row["bar"] = row["bar"].isoformat()
            row["ladder"] = ladders[pd.Timestamp(row["bar"])]
            f.write(json.dumps(row) + "\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("trades_parquet")
    p.add_argument("--freq", default="1min")
    p.add_argument("--tick", type=float, default=CL_TICK)
    p.add_argument("--ratio", type=float, default=3.0)
    args = p.parse_args()
    trades = pd.read_parquet(args.trades_parquet)
    trades = trades.sort_values("ts_event")
    levels = footprint_levels(trades, args.freq, args.tick)
    summary = bar_summary(trades, levels, args.freq, args.ratio)
    base = Path(args.trades_parquet).with_suffix("")
    levels.to_parquet(f"{base}_levels.parquet")
    summary.to_parquet(f"{base}_bars.parquet")
    to_jsonl(summary, levels, f"{base}_bars.jsonl")
    print(f"{len(summary)} bars, {len(levels)} levels -> {base}_*")


if __name__ == "__main__":
    main()
