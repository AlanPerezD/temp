"""Edge #1 magnitude filter, chosen on DEV only and judged on TEST only.

For each market: threshold = 75th percentile of the day-so-far move on DEV up-days (pre-2018).
Compare TEST (2018+) net P&L of 'all up days' vs 'up days above the DEV threshold'.
Net of normal costs (1 tick + $5 per round trip). Window 15:00-17:00 ET.
"""
import glob

import numpy as np
import pandas as pd

import registry
from edge1_portfolio import BEFORE15, MK
from hourly_lab import SPLIT, seg
from late_session import hourly_moves


def main():
    legs_all, legs_f = {}, {}
    for root, (tick, tv) in MK.items():
        m = hourly_moves(glob.glob(f"data/ohlcv-1h_{root}_c_0_*.parquet")[0])
        m = m[m.wd < 5]
        m["dp"] = m["dp"] * 0.01 / tick
        day = seg(m, BEFORE15)
        late = seg(m, [15, 16])
        day = day.reindex(late.index)
        dev_up = day[(day > 0) & np.array([d < SPLIT for d in day.index])]
        q = dev_up.quantile(0.75)
        test = np.array([d >= SPLIT for d in late.index])
        for lab, cond, store in (("all up days", day > 0, legs_all), (f"up > DEV q75 ({q:.0f} ticks)", day > q, legs_f)):
            pnl = (late * tv - (1 * tv + 5)).where(cond, 0.0)[test]
            store[root] = pnl
            tr = pnl[cond[test]]
            t = tr.mean() / tr.std() * np.sqrt(len(tr))
            print(f"  {root} TEST {lab:28s} trades {len(tr):4d}  net ${tr.mean():+7.2f}/trade  t {t:+.2f}  total ${pnl.sum():+,.0f}")
            if store is legs_f:
                registry.log("edge1_filter", f"{root} TEST up>DEVq75", "$ net/trade", len(tr), tr.mean(), t, np.nan, t, "threshold from DEV")
    for lab, legs in (("basket all up days", legs_all), ("basket filtered", legs_f)):
        b = pd.DataFrame(legs).fillna(0).sum(axis=1)
        print(f"  TEST {lab:22s} ${b.sum()/ (len(b)/252):,.0f}/yr  Sharpe {b.mean()/b.std()*np.sqrt(252):+.2f}  t {b.mean()/b.std()*np.sqrt(len(b)):+.2f}")


if __name__ == "__main__":
    main()
