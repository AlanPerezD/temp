"""Edge #1 as a tradable basket: NYMEX energy late-session momentum.

Rule (pre-registered on CL, replicated on HO and RB): at 15:00 ET (16:00 Buenos Aires), for each
market whose price is above its previous 17:00 ET close... more precisely above the price at the
previous session's start (prev 18:00 ET), buy 1 contract; sell at 17:00 ET (18:00 BA) before the halt.
Variant: buy at 16:00 ET instead (last hour only).

Dollar P&L per contract (CL $10/tick, HO/RB $4.20/tick). Costs per round trip per contract:
  normal  = 1 tick spread + $5 commissions
  stressed = 2 ticks + $5
"""
import glob

import numpy as np
import pandas as pd

from hourly_lab import SPLIT, seg
from late_session import hourly_moves

MK = {"CL": (0.01, 10.0), "HO": (0.0001, 4.2), "RB": (0.0001, 4.2)}
BEFORE15 = [18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]


def market_pnl(root, hours, cost_ticks):
    tick, tv = MK[root]
    m = hourly_moves(glob.glob(f"data/ohlcv-1h_{root}_c_0_*.parquet")[0])
    m = m[m.wd < 5]
    m["dp"] = m["dp"] * 0.01 / tick
    day = seg(m, BEFORE15)
    late = seg(m, hours)
    up = day.reindex(late.index) > 0
    gross = (late * tv).where(up, 0.0)
    cost = up.astype(float) * (cost_ticks * tv + 5.0)
    return gross - cost, up


def summary(name, pnl, trades):
    pnl = pnl.dropna()
    sh = pnl.mean() / pnl.std() * np.sqrt(252)
    t = pnl.mean() / pnl.std() * np.sqrt(len(pnl))
    dv, ts = pnl[[d < SPLIT for d in pnl.index]], pnl[[d >= SPLIT for d in pnl.index]]
    eq = pnl.cumsum()
    mdd = (eq - eq.cummax()).min()
    yrs = pnl.groupby([d.year for d in pnl.index]).sum()
    per_year = pnl.sum() / (len(pnl) / 252)
    print(f"  {name:34s} ${per_year:8,.0f}/yr  Sharpe {sh:+.2f} (DEV {dv.mean()/dv.std()*np.sqrt(252):+.2f}, TEST {ts.mean()/ts.std()*np.sqrt(252):+.2f})"
          f"  t {t:+.2f}  maxDD ${mdd:,.0f}  yrs+ {(yrs > 0).sum()}/{len(yrs)}  trades/yr {trades/(len(pnl)/252):.0f}")
    return yrs


def main():
    for hours, lab in (([15, 16], "buy 15:00 ET, sell 17:00 ET"), ([16], "buy 16:00 ET, sell 17:00 ET")):
        for ct, clab in ((1, "normal costs"), (2, "stressed costs")):
            print(f"\n{lab} | {clab}")
            legs, ntr = {}, 0
            for root in MK:
                p, up = market_pnl(root, hours, ct)
                legs[root] = p
                ntr += up.sum()
                summary(f"{root} (1 contract)", p, up.sum())
            basket = pd.DataFrame(legs).fillna(0).sum(axis=1)
            yrs = summary("BASKET CL+HO+RB (1 each)", basket, ntr)
            if ct == 1 and hours == [15, 16]:
                print("  basket by year ($): " + " ".join(f"{y}:{v:+,.0f}" for y, v in yrs.items()))


if __name__ == "__main__":
    main()
