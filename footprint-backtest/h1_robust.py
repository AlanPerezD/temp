"""Robustness of H1a (long 15:00-17:00 ET only when the day so far is up), front-month hourly CL.

Perturbations are reported, not selected: if the effect is real most of them should be positive.
"""
import numpy as np
import pandas as pd

import registry
from hourly_lab import SPLIT, seg, stat
from late_session import hourly_moves

PATH = "data/ohlcv-1h_CL_c_0_2010-06-07_2026-10-16.parquet"
ALL_BEFORE_15 = [18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]


def line(name, x, log=True):
    mean, t, n = stat(x)
    dv = x[[d < SPLIT for d in x.index]]; ts = x[[d >= SPLIT for d in x.index]]
    md, td, _ = stat(dv); mt, tt, _ = stat(ts)
    print(f"  {name:55s} n={n:4d} {mean:+5.2f}t (t {t:+.2f}) DEV {md:+5.2f} TEST {mt:+5.2f} (t {tt:+.2f})")
    if log:
        registry.log("h1_robust", name, "ticks/trade gross", n, mean, t, td, tt, "robustness check, not selection")


def main():
    m = hourly_moves(PATH)
    m = m[m.wd < 5]
    late = seg(m, [15, 16])
    print("Signal definition perturbations (trade = long late when signal up):")
    for name, hrs in (("day so far: prev 18:00 -> 15:00 ET (pre-registered)", ALL_BEFORE_15),
                      ("NY session only: 09:00 -> 15:00 ET", [9, 10, 11, 12, 13, 14]),
                      ("overnight only: 18:00 -> 09:00 ET", [18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7, 8]),
                      ("last 2 hours: 13:00 -> 15:00 ET", [13, 14]),
                      ("settlement hour: 14:00 -> 15:00 ET", [14])):
        sig = seg(m, hrs).reindex(late.index)
        line(name, late[sig > 0])
    sig = seg(m, ALL_BEFORE_15).reindex(late.index)
    print("Exit window perturbations (signal = pre-registered):")
    line("15:00-16:00 ET only", seg(m, [15]).reindex(late.index)[sig > 0])
    line("16:00-17:00 ET only", seg(m, [16]).reindex(late.index)[sig > 0])
    print("Complement / magnitude (pre-registered signal):")
    line("days DOWN so far (should be weaker)", late[sig < 0], log=False)
    q = sig[[d < SPLIT for d in sig.index]].quantile(0.75)  # threshold from DEV only
    line(f"day up by more than DEV 75th pct ({q:.0f} ticks)", late[sig > q])
    line(f"day up but by less than that", late[(sig > 0) & (sig <= q)], log=False)
    up = late[sig > 0]
    yrs = up.groupby([d.year for d in up.index]).agg(["mean", "count"])
    print("By year (gross ticks/trade): " + " ".join(f"{y}:{r['mean']:+.1f}" for y, r in yrs.iterrows()))
    print(f"  positive years: {(yrs['mean'] > 0).sum()}/{len(yrs)}")
    wd = m.groupby("day")["wd"].first()
    byw = up.groupby([wd[d] for d in up.index]).agg(["mean", "count"])
    print("By weekday (0=Mon): " + " ".join(f"{int(w)}:{r['mean']:+.1f}(n{int(r['count'])})" for w, r in byw.iterrows()))
    sd = up.std()
    print(f"Per-trade sd {sd:.1f} ticks; per-trade Sharpe {up.mean()/sd:.3f}; trades/yr ~{len(up)/16.3:.0f}; "
          f"annualised Sharpe gross {up.mean()/sd*np.sqrt(len(up)/16.3):.2f}, net 1.5t {(up.mean()-1.5)/sd*np.sqrt(len(up)/16.3):.2f}")


if __name__ == "__main__":
    main()
