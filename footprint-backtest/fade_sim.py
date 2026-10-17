"""Simulate the discretionary design: fade a violent spike toward its origin with a tight stop.

Trigger: forming 5-min candle with volume >= vol_min and move >= move_min % from its open
(live_study.triggers). Entry: first trade `delay_s` after the trigger, against the move.
Target: price returns `target_frac` of the way back to the candle open (1.0 = the open itself).
Stop: `stop_ticks` against the entry. Time stop: `max_min` minutes. Round-trip cost in ticks.
Tick-by-tick path, so whichever of stop/target trades first wins.
"""
import argparse

import numpy as np
import pandas as pd

import live_study


def simulate(ev, ts, px, open_px, stop_ticks, target_frac, max_min=60, tick=0.01, cost_ticks=2):
    out = []
    for r, o in zip(ev.itertuples(), open_px):
        entry = px[r.k]
        d = -r.dir  # trade direction (fade)
        target = entry + target_frac * (o - entry)
        tgt_ticks = (target - entry) * d / tick
        if tgt_ticks <= 0:
            continue
        end = np.searchsorted(ts, ts[r.k] + max_min * 60 * 10**9, side="right")
        path = (px[r.k:end] - entry) * d / tick
        hit_t = np.nonzero(path >= tgt_ticks)[0]
        hit_s = np.nonzero(path <= -stop_ticks)[0]
        t_i = hit_t[0] if len(hit_t) else 10**12
        s_i = hit_s[0] if len(hit_s) else 10**12
        if t_i < s_i:
            res, kind = tgt_ticks, "target"
        elif s_i < t_i:
            res, kind = -stop_ticks, "stop"
        else:
            res, kind = path[-1], "time"
        out.append(dict(bar=r.bar, dir=d, kind=kind, ticks=res - cost_ticks, risk=stop_ticks, tgt=tgt_ticks))
    return pd.DataFrame(out)


def open_prices(ev, trades, bar="5min"):
    t = trades.sort_values("ts_event")
    first = t.groupby(t["ts_event"].dt.floor(bar))["price"].first()
    return first.reindex(ev["bar"]).to_numpy()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("trades_parquet")
    ap.add_argument("--vol", type=int, default=2500)
    ap.add_argument("--move", type=float, default=0.45)
    a = ap.parse_args()
    tr = pd.read_parquet(a.trades_parquet)
    ev, ts, px = live_study.triggers(tr, a.vol, a.move)
    ev = live_study.dedupe(ev)
    op = open_prices(ev, tr)
    print(f"{len(ev)} spike triggers (vol>={a.vol}, move>={a.move}%)")
    for stop in (20, 30):
        for frac in (0.5, 1.0):
            s = simulate(ev, ts, px, op, stop, frac)
            win = (s.kind == "target").mean()
            print(f"stop {stop}t target {int(frac*100)}% of move: n={len(s)} win {win:.0%} stopped {(s.kind=='stop').mean():.0%} "
                  f"timeout {(s.kind=='time').mean():.0%} | avg {s.ticks.mean():+.1f} ticks (${s.ticks.mean():+.1f}/MCL) "
                  f"avg target {s.tgt.mean():.0f}t | total {s.ticks.sum():+.0f}t")
