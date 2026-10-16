"""Intrabar trigger study: act while the 5-min candle is still forming.

Trigger = first trade in a bar where the running bar volume >= vol_min AND price has moved
>= move_min % from the bar open. Direction = sign(price - open). Entry = first trade
`delay_s` after the trigger (so only information known at trigger time is used).

At trigger we record what happened inside the candle so far:
  delta_bar    buy-aggressor minus sell-aggressor volume since the bar open
  delta_60s    the same over the last 60 s (is the aggression still there?)
  pullback_t   ticks price has already retreated from the bar's extreme in the move direction
  elapsed_s    seconds since the bar open
"Stall" (the exhaustion read, fixed before testing): last-60s delta opposes the move AND
pullback >= stall_ticks.
"""
import argparse

import numpy as np
import pandas as pd

HORIZONS = (1, 5, 15, 60)  # minutes
GAP_NS = 10 * 60 * 10**9


def triggers(trades, vol_min, move_min, bar="5min", delay_s=1, tick=0.01, stall_ticks=3):
    t = trades[trades["side"].isin(["A", "B"])].sort_values("ts_event").reset_index(drop=True)
    ts = t["ts_event"].dt.as_unit("ns").astype("int64").to_numpy()
    px = t["price"].to_numpy()
    b = t["ts_event"].dt.floor(bar)
    g = t.groupby(b)
    open_px = g["price"].transform("first").to_numpy()
    cumvol = g["size"].cumsum().to_numpy()
    sign = np.where(t["side"].to_numpy() == "B", 1.0, -1.0)
    sdelta = sign * t["size"].to_numpy()
    cumdelta = pd.Series(sdelta).groupby(b.to_numpy()).cumsum().to_numpy()
    run_hi = g["price"].cummax().to_numpy()
    run_lo = g["price"].cummin().to_numpy()
    move = (px - open_px) / open_px * 100
    hit = (cumvol >= vol_min) & (np.abs(move) >= move_min)
    first = pd.Series(np.arange(len(t)))[hit].groupby(b[hit].to_numpy()).first()
    # rolling 60 s delta via cumulative sum over the whole stream
    allcum = np.cumsum(sdelta)
    rows = []
    for bar_start, i in first.items():
        d = np.sign(move[i])
        j0 = np.searchsorted(ts, ts[i] - 60 * 10**9, side="left")
        d60 = allcum[i] - (allcum[j0 - 1] if j0 > 0 else 0)
        extreme = run_hi[i] if d > 0 else run_lo[i]
        pullback = abs(extreme - px[i]) / tick
        k = np.searchsorted(ts, ts[i] + delay_s * 10**9)
        if k >= len(ts):
            continue
        rows.append(dict(bar=bar_start, i=i, k=k, dir=d, vol=cumvol[i], move=move[i],
                         delta_bar=cumdelta[i] * d, delta_60s=d60 * d, pullback_t=pullback,
                         elapsed_s=(ts[i] - bar_start.value) / 1e9,
                         stall=bool(d60 * d < 0 and pullback >= stall_ticks)))
    ev = pd.DataFrame(rows)
    return ev, ts, px


def outcomes(ev, ts, px, tick=0.01, cost_ticks=2):
    out = []
    for r in ev.itertuples():
        entry = px[r.k]
        row = r._asdict()
        row["cost"] = cost_ticks * tick / entry * 100
        for m in HORIZONS:
            target = ts[r.k] + m * 60 * 10**9
            j = np.searchsorted(ts, target, side="right") - 1
            nxt = ts[j + 1] if j + 1 < len(ts) else None
            ok = (nxt is not None and nxt - target <= GAP_NS) or (nxt is None and target - ts[j] <= GAP_NS)
            row[f"fade{m}"] = -(px[j] - entry) / entry * 100 * r.dir - row["cost"] if ok else np.nan
        out.append(row)
    return pd.DataFrame(out)


def dedupe(ev, gap="30min"):
    keep, last = [], None
    for idx, ts_ in ev["bar"].items():
        if last is None or ts_ - last > pd.Timedelta(gap):
            keep.append(idx)
        last = ts_
    return ev.loc[keep]


def line(f, label):
    parts = []
    for m in HORIZONS:
        d = f[f"fade{m}"].dropna()
        parts.append(f"{m}m {d.mean():+.3f}% w{(d > 0).mean():.0%} n{len(d)}" if len(d) else f"{m}m -")
    print(f"  {label:<14}", " | ".join(parts))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("trades_parquet")
    a = ap.parse_args()
    tr = pd.read_parquet(a.trades_parquet)
    for vmin, mmin in ((1500, 0.3), (2500, 0.3), (1500, 0.5)):
        ev, ts, px = triggers(tr, vmin, mmin)
        f = outcomes(dedupe(ev), ts, px)
        print(f"\nTrigger vol>={vmin} move>={mmin}%: {len(f)} events, median trigger at "
              f"{f.elapsed_s.median():.0f}s into the bar (FADE = reverse the move)")
        line(f, "all")
        line(f[f.stall], "stall")
        line(f[~f.stall], "no stall")
