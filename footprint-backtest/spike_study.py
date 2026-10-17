"""Event study: volume-spike 5-min bars, then reverse (fade) or follow the spike.

Spike = bar volume >= vol_min and |close-open|/open >= move_min (in %). Entry is at the first
trade at least `delay_s` after the bar closes (the bar is only known once it closes).
Reported per direction: average % return after 5/15/60 min, share of winners, and the median
best/worst excursion within 60 min. Cost = `cost_ticks` ticks round trip, in %.
"""
import argparse

import numpy as np
import pandas as pd

import session

HORIZONS = (5, 15, 60)  # minutes
GAP_NS = 10 * 60 * 10**9  # a horizon landing in a gap longer than this is dropped


def spike_bars(trades, vol_min=1500, move_min=0.25, bar="5min"):
    t = trades.sort_values("ts_event")
    g = t.groupby(t["ts_event"].dt.floor(bar))
    b = pd.DataFrame({"vol": g["size"].sum(), "open": g["price"].first(), "close": g["price"].last()})
    b["move_pct"] = (b["close"] - b["open"]) / b["open"] * 100
    b = b[(b["vol"] >= vol_min) & (b["move_pct"].abs() >= move_min)]
    return b[[session.can_enter(ix) for ix in b.index]]


def cluster_first(bars, gap="30min"):
    """Keep the first spike of each cluster so overlapping follow-up windows are not double counted."""
    keep, last = [], None
    for ts in bars.index:
        if last is None or ts - last > pd.Timedelta(gap):
            keep.append(ts)
        last = ts
    return bars.loc[keep]


def forward(trades, bars, bar="5min", delay_s=5, tick=0.01, cost_ticks=2):
    t = trades.sort_values("ts_event")
    ts = t["ts_event"].dt.as_unit("ns").astype("int64").to_numpy()
    px = t["price"].to_numpy()
    rows = []
    for start, r in bars.iterrows():
        end = start + pd.Timedelta(bar) + pd.Timedelta(seconds=delay_s)
        i0 = np.searchsorted(ts, end.value)
        if i0 >= len(ts):
            continue
        entry, side = px[i0], np.sign(r["move_pct"])  # side = spike direction
        cost = cost_ticks * tick / entry * 100
        row = {"bar": start, "vol": r["vol"], "move_pct": r["move_pct"], "side": side}
        for m in HORIZONS:
            target = ts[i0] + m * 60 * 10**9
            j = np.searchsorted(ts, target, side="right") - 1
            # the horizon must fall inside the data (not past the window end / a gap)
            nxt = ts[j + 1] if j + 1 < len(ts) else None
            covered = (nxt is not None and nxt - target <= GAP_NS) or (nxt is None and target - ts[j] <= GAP_NS)
            row[f"ret{m}"] = (px[j] - entry) / entry * 100 * side if covered else np.nan  # >0 = spike continued
        j60 = np.searchsorted(ts, ts[i0] + 60 * 60 * 10**9, side="right")
        path = (px[i0:j60] - entry) / entry * 100 * side
        ok = not np.isnan(row["ret60"])
        row["mfe_follow"] = path.max() if ok else np.nan  # follow: up = good
        row["mae_follow"] = -path.min() if ok else np.nan
        row["cost"] = cost
        rows.append(row)
    return pd.DataFrame(rows)


def report(f, label):
    if f.empty:
        print(label, "no events"); return
    print(f"\n{label}: {len(f)} events")
    for m in HORIZONS:
        d = f.dropna(subset=[f"ret{m}"])
        fade = -d[f"ret{m}"] - d["cost"]
        follow = d[f"ret{m}"] - d["cost"]
        print(f"  {m:>2}m (n={len(d)}) FADE avg {fade.mean():+.3f}% win {(fade > 0).mean():.0%} | "
              f"FOLLOW avg {follow.mean():+.3f}% win {(follow > 0).mean():.0%}")
    print(f"  60m excursion vs spike direction: median up-side {f.mfe_follow.median():.2f}% / "
          f"down-side {f.mae_follow.median():.2f}%  (fade: swap them)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("trades_parquet")
    a = p.parse_args()
    tr = session.load_trades() if a.trades_parquet == "all" else pd.read_parquet(a.trades_parquet)
    for vmin in (1500, 2500):
        for mmin in (0.0, 0.3, 0.5):
            b = cluster_first(spike_bars(tr, vmin, mmin))
            report(forward(tr, b), f"vol>={vmin} move>={mmin}%")
