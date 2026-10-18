"""Out-of-market replication of edge #1 (late-session momentum) on Brent (BZ), heating oil (HO),
gasoline (RB) front-month hourly bars. Same pre-registered rules as on CL:
  H1a     long 15:00-17:00 ET only if the day so far (prev 18:00 -> 15:00 ET) is up
  H1-last long 16:00-17:00 ET only if the day so far is up
Results in ticks of each contract (BZ $10, HO/RB $4.20 per tick) and as % of price.
"""
import glob

import numpy as np
import pandas as pd

import registry
from hourly_lab import SPLIT, seg, stat
from late_session import hourly_moves

TICK = {"CL": 0.01, "BZ": 0.01, "HO": 0.0001, "RB": 0.0001, "NG": 0.001}
BEFORE15 = [18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]


def run(root):
    f = glob.glob(f"data/ohlcv-1h_{root}_c_0_*.parquet")
    if not f:
        print(f"{root}: no hourly data"); return
    m = hourly_moves(f[0])
    m = m[m.wd < 5]
    tick = TICK[root]
    m["dp"] = m["dp"] * 0.01 / tick  # seg() divides by 0.01, so rescale to this market's tick
    day = seg(m, BEFORE15)
    for lab, hrs in (("H1a 15-17 ET if day up", [15, 16]), ("H1-last 16-17 ET if day up", [16])):
        late = seg(m, hrs)
        x = late[day.reindex(late.index) > 0]
        mean, t, n = stat(x)
        dv = x[[d < SPLIT for d in x.index]]; ts = x[[d >= SPLIT for d in x.index]]
        md, td, _ = stat(dv); mt, tt, _ = stat(ts)
        print(f"  {root} {lab:28s} n={n} {mean:+6.2f} ticks (t {t:+.2f}) | DEV {md:+.2f} (t {td:+.2f}) TEST {mt:+.2f} (t {tt:+.2f})")
        registry.log("hourly_multi", f"{root} {lab}", "ticks/trade gross", n, mean, t, td, tt, "replication of CL edge #1")


if __name__ == "__main__":
    import sys
    for r in (sys.argv[1:] or ("BZ", "HO", "RB")):
        run(r)
