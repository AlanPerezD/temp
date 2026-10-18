"""Pre-registered: intraday momentum into the 16:00 ET close on US equity-index futures.

Rule (fixed before looking at any index data; same idea as the oil edge):
  signal = price change from the previous evening session start to 15:00 ET (day so far,
           incl. overnight; hourly bars, same contract only)
  trade  = long if signal > 0, short if < 0, from 15:00 ET to 16:00 ET (the bar's open -> close)
  variants: both directions (B) | long only when up (L) | short only when down (S)
Markets: ES, NQ primary; YM, RTY replication. DEV = before 2018, TEST = 2018 on.
Costs scenarios per round trip (in ticks): 1.0 / 1.5 / 2.0 (1 spread tick + commission/fees for micros).
FTMO fit: flat by 16:00 ET, inside the 16:10 ET cutoff; micros MES/MNQ/MYM/M2K exist.
"""
import glob
import sys

import numpy as np
import pandas as pd

import registry
from late_session import hourly_moves

SPLIT = pd.Timestamp("2018-01-01").date()
TICK = {"ES": 0.25, "NQ": 0.25, "YM": 1.0, "RTY": 0.1, "GC": 0.1}
POINT_USD_MICRO = {"ES": 5.0, "NQ": 2.0, "YM": 0.5, "RTY": 5.0, "GC": 10.0}  # MES, MNQ, MYM, M2K, MGC $/point
BEFORE15 = [18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]


def load(root):
    f = glob.glob(f"data/ohlcv-1h_{root}_c_0_*.parquet")
    if not f:
        return None
    m = hourly_moves(f[0])
    return m[m.wd < 5]


def day_frame(m):
    day = m[m.hr.isin(BEFORE15)].groupby("day")["dp"].sum()
    last = m[m.hr == 15].groupby("day")["dp"].sum()
    px = m[m.hr == 15].groupby("day").size()  # bars present
    ref = m[m.hr == 14].groupby("day")["dp"].count()
    f = pd.DataFrame({"sig": day, "last": last}).dropna()
    return f[(f.index.map(lambda d: pd.Timestamp(d).weekday() < 5))]


def tstat(x):
    x = np.asarray(x, float)
    return x.mean() / x.std() * np.sqrt(len(x)) if len(x) > 20 and x.std() > 0 else np.nan


def run(root):
    m = load(root)
    if m is None:
        print(f"{root}: no data yet"); return
    f = day_frame(m)
    tick = TICK[root]
    f["pos"] = np.sign(f["sig"])
    f = f[f.pos != 0]
    print(f"\n=== {root}: {len(f)} sessions {f.index.min()} .. {f.index.max()} ===")
    for lab, mask in (("B both directions", f.pos != 0), ("L long only when up", f.pos > 0), ("S short only when down", f.pos < 0)):
        sub = f[mask]
        g = (sub["pos"] * sub["last"]) / tick  # gross ticks
        dev = g[[d < SPLIT for d in g.index]]
        tst = g[[d >= SPLIT for d in g.index]]
        yrs = g.groupby([d.year for d in g.index]).mean()
        print(f"  {lab:24s} n={len(g):4d} gross {g.mean():+5.2f} ticks (t {tstat(g):+.2f}) win {(g > 0).mean():.0%} | "
              f"DEV {dev.mean():+.2f} (t {tstat(dev):+.2f}) TEST {tst.mean():+.2f} (t {tstat(tst):+.2f}) | yrs+ {(yrs > 0).sum()}/{len(yrs)}")
        print(f"      net of 1.0/1.5/2.0 ticks: {g.mean()-1.0:+.2f} / {g.mean()-1.5:+.2f} / {g.mean()-2.0:+.2f} ticks")
        registry.log("index_close", f"{root} {lab}", "ticks/trade gross", len(g), g.mean(), tstat(g), tstat(dev), tstat(tst), "pre-registered; 15:00-16:00 ET")


if __name__ == "__main__":
    for r in (sys.argv[1:] or ("ES", "NQ", "YM", "RTY")):
        run(r)
