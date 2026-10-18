"""Edge #2: energy carry (term-structure) portfolio, implementable version.

Each month (first trading day), for CL, BZ, HO, RB, NG: go long the 2nd-month contract if the curve
is in backwardation (2nd > 3rd month price at the previous close), short if in contango.
Size each market to the same risk: $10k annualised volatility per market (60-day vol).
P&L in $ from same-contract daily price changes (roll-safe). Costs: every contract traded at a
rebalance and every contract rolled each month pays 1 tick + $5.
Variants (robustness, not selection): weekly rebalance, front-spread signal (1st-2nd), no NG,
equal-notional instead of equal-risk.
"""
import numpy as np
import pandas as pd

import registry
from energy_lab import MULT, TICKV, changes, panel

SPLIT = pd.Timestamp("2018-01-01").date()
TARGET = 10_000.0


def build(roots=("CL", "BZ", "HO", "RB", "NG"), freq="M", signal="12", sizing="risk"):
    P = {k: panel(k) for k in roots}
    idx = sorted(set.intersection(*[set(v.index) for v in P.values()]))
    total = pd.Series(0.0, index=idx)
    legs = {}
    for k, d in P.items():
        d = d.reindex(idx)
        ch, prev = changes(d)
        dollar = ch * MULT[k]                                  # $ change per contract
        slope = (d["c1"] - d["c2"]) if signal == "12" else (d["c0"] - d["c1"])
        sig = np.sign(slope).shift(1)
        vol_d = dollar.rolling(60).std().shift(1)              # $ daily vol per contract
        if sizing == "risk":
            n = TARGET / (vol_d * np.sqrt(252))
        else:
            notional = (d["c1"].abs() * MULT[k]).shift(1)
            n = 100_000.0 / notional
        reb = pd.Series(False, index=idx)
        keys = pd.Series([(i.year, i.month) if freq == "M" else (i.isocalendar()[0], i.isocalendar()[1]) for i in idx], index=idx)
        reb[keys.ne(keys.shift())] = True
        pos = (sig * n).where(reb).ffill().fillna(0)
        traded = pos.diff().abs().fillna(pos.abs())
        rolled = pos.abs().where(d["id1"].ne(d["id1"].shift()), 0)    # contract roll days
        cost = (traded + rolled) * (TICKV[k] + 5.0)
        legs[k] = (pos * dollar).fillna(0) - cost
        total = total.add(legs[k], fill_value=0)
    return total, legs


def stats(name, pnl, log=False):
    pnl = pnl[pnl.index >= pnl.index[60]]
    sh = pnl.mean() / pnl.std() * np.sqrt(252)
    t = pnl.mean() / pnl.std() * np.sqrt(len(pnl))
    dv, ts = pnl[[d < SPLIT for d in pnl.index]], pnl[[d >= SPLIT for d in pnl.index]]
    shd, sht = dv.mean() / dv.std() * np.sqrt(252), ts.mean() / ts.std() * np.sqrt(252)
    eq = pnl.cumsum()
    mdd = (eq - eq.cummax()).min()
    yrs = pnl.groupby([d.year for d in pnl.index]).sum()
    print(f"  {name:44s} ${pnl.mean()*252:8,.0f}/yr  Sharpe {sh:+.2f} (DEV {shd:+.2f}, TEST {sht:+.2f})  t {t:+.2f}  "
          f"maxDD ${mdd:,.0f}  yrs+ {(yrs > 0).sum()}/{len(yrs)}")
    if log:
        registry.log("edge2_carry", name, "$/day", len(pnl), pnl.mean(), t, shd, sht, "Sharpe in t_dev/t_test columns")
    return pnl, yrs


def main():
    print("Energy carry, $10k annual risk per market (5 markets):")
    base, legs = build()
    p, yrs = stats("BASE monthly, 2nd-3rd slope, equal risk", base, log=True)
    print("  by year ($): " + " ".join(f"{y}:{v:+,.0f}" for y, v in yrs.items()))
    for k, leg in legs.items():
        stats(f"    leg {k}", leg)
    print("Robustness variants:")
    stats("weekly rebalance", build(freq="W")[0], log=True)
    stats("front spread signal (1st-2nd)", build(signal="01")[0], log=True)
    stats("without NG", build(roots=("CL", "BZ", "HO", "RB"))[0], log=True)
    stats("equal notional ($100k per market)", build(sizing="notional")[0], log=True)
    base.to_frame("carry").to_parquet("data/edge2_carry_pnl.parquet")


if __name__ == "__main__":
    main()
