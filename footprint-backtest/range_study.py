"""Rule from the trader's labeled charts: wide-range 5-min candle, then fade once price pulls back.

Setup (all known live, inside the forming candle):
  1. candle range (running high - running low) reaches `range_ticks`          [his "price drop"]
  2. spike direction = the side of the open where the extreme is; extreme = running high/low
  3. entry = first trade where price has pulled back `pullback_ticks` from that extreme,
     still inside the candle; entry `delay_s` later, AGAINST the spike
Exit: fixed stop / target in ticks (his typical target 55-110 ticks), `max_min` time stop.
The range threshold was read off the labeled examples, so those dates are in-sample.
"""
import argparse

import numpy as np
import pandas as pd

TICK = 0.01


def setups(trades, range_ticks=80, pullback_ticks=20, bar="5min", delay_s=1):
    t = trades.sort_values("ts_event").reset_index(drop=True)
    ts = t["ts_event"].dt.as_unit("ns").astype("int64").to_numpy()
    px = t["price"].to_numpy()
    b = t["ts_event"].dt.floor(bar)
    g = t.groupby(b)
    hi, lo = g["price"].cummax().to_numpy(), g["price"].cummin().to_numpy()
    op = g["price"].transform("first").to_numpy()
    wide = (hi - lo) / TICK >= range_ticks
    rows = []
    for bar_start, idx in pd.Series(np.arange(len(t)))[wide].groupby(b[wide].to_numpy()):
        i = idx.iloc[0]
        end = g.indices[bar_start][-1]
        d = 1 if (hi[i] - op[i]) >= (op[i] - lo[i]) else -1
        seg = np.arange(i, end + 1)
        ext = hi[seg] if d > 0 else lo[seg]
        pulled = (ext - px[seg]) * d / TICK >= pullback_ticks
        if not pulled.any():
            continue
        j = seg[np.argmax(pulled)]
        k = np.searchsorted(ts, ts[j] + delay_s * 10**9)
        if k < len(ts):
            rows.append(dict(bar=bar_start, dir=d, k=k, extreme=ext[np.argmax(pulled)],
                             range_t=(hi[j] - lo[j]) / TICK))
    return pd.DataFrame(rows), ts, px


def run(ev, ts, px, stop_ticks, target_ticks, max_min=60, cost_ticks=2):
    out = []
    for r in ev.itertuples():
        entry, side = px[r.k], -r.dir
        end = np.searchsorted(ts, ts[r.k] + max_min * 60 * 10**9, side="right")
        path = (px[r.k:end] - entry) * side / TICK
        ht = np.nonzero(path >= target_ticks)[0]
        hs = np.nonzero(path <= -stop_ticks)[0]
        t_i = ht[0] if len(ht) else 10**12
        s_i = hs[0] if len(hs) else 10**12
        res, kind = ((target_ticks, "target") if t_i < s_i else (-stop_ticks, "stop") if s_i < t_i
                     else (path[-1], "time"))
        out.append(dict(bar=r.bar, kind=kind, ticks=res - cost_ticks))
    return pd.DataFrame(out)


def dedupe(ev, gap="30min"):
    keep, last = [], None
    for idx, b in ev["bar"].items():
        if last is None or b - last > pd.Timedelta(gap):
            keep.append(idx)
        last = b
    return ev.loc[keep]


def show(s, label):
    print(f"{label}: n={len(s)} win {(s.kind=='target').mean():.0%} stop {(s.kind=='stop').mean():.0%} "
          f"time {(s.kind=='time').mean():.0%} | avg {s.ticks.mean():+.1f}t (${s.ticks.mean():+.1f}/MCL) total {s.ticks.sum():+.0f}t")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("trades_parquet")
    a = ap.parse_args()
    tr = pd.read_parquet(a.trades_parquet)
    ev, ts, px = setups(tr)
    ev = dedupe(ev)
    print(f"{len(ev)} setups (range>=80t, pullback>=20t)")
    for stop in (30, 45):
        for tgt in (60, 90):
            show(run(ev, ts, px, stop, tgt), f"stop {stop} target {tgt}")
    s = run(ev, ts, px, 45, 90); s["m"] = s.bar.dt.strftime("%Y-%m")
    print(s.groupby("m").ticks.agg(["count", "mean"]).round(1).T.to_string())
    for rt in (60, 100):
        e2, ts2, px2 = setups(tr, range_ticks=rt); e2 = dedupe(e2)
        show(run(e2, ts2, px2, 45, 90), f"sensitivity range>={rt}t stop 45 target 90")
