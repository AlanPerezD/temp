"""Cross-commodity / curve / fundamental hypotheses on 16 years of daily energy futures.

All rules are fixed before running (see the list below); every result is logged to the registry.
P&L uses the rolled 2nd-month contract of each market (price changes within the same contract);
signals use only data up to the previous close. DEV < 2018 <= TEST.

E1 WTI-Brent spread mean reversion (z of 20/60/120-day window; enter |z|>2, exit |z|<0.5)
E2 3-2-1 crack mean reversion (same rule) + gasoline (RB-CL) and diesel (HO-CL) cracks (60-day)
E3 crack level (1y z) -> CL direction (refining margins high => long crude)
E4 energy trend portfolio (CL BZ HO RB NG; 3m and 12m sign, vol-scaled)
E5 energy carry portfolio (sign of 2nd-3rd month slope, vol-scaled) and cross-sectional carry
E6 Cushing stock surprise (vs 5y seasonal) -> next week front calendar spread
E7 S&P 500 futures day return -> next-day CL
E8 CL 2nd-3rd month calendar spread mean reversion (60-day z)
E9 expiry week: short the front spread (front - 2nd) over the last 5 trading days of the front
E10 seasonal gasoline crack: long RB-CL crack Feb 1 - Apr 30 (summer-grade / driving-season build)
E11 seasonal diesel crack: long HO-CL crack Sep 1 - Dec 31 (heating season)
E12 oil variance risk premium: sell 1-month variance at OVX^2 vs realised CL variance
    (monthly, non-overlapping; unconditional and only when OVX > last month's realised vol)
"""
import glob

import numpy as np
import pandas as pd

import registry

D = "data"
SPLIT = pd.Timestamp("2018-01-01").date()
MULT = {"CL": 1000, "BZ": 1000, "HO": 42000, "RB": 42000, "NG": 10000}  # contract size
TICKV = {"CL": 10, "BZ": 10, "HO": 4.2, "RB": 4.2, "NG": 10}            # $ per tick per contract


def panel(root):
    parts = []
    for k in (0, 1, 2):
        f = glob.glob(f"{D}/ohlcv-1d_{root}_c_{k}_*.parquet")
        if not f:
            return None
        x = pd.read_parquet(f[0])[["instrument_id", "close"]]
        x.columns = [f"id{k}", f"c{k}"]
        parts.append(x)
    d = pd.concat(parts, axis=1, join="inner")
    d.index = d.index.date
    return d[[pd.Timestamp(i).weekday() < 5 for i in d.index]]


def changes(d, k=1):
    """price change of the k-th contract, using the same contract's previous close (roll-safe)."""
    same = d[f"id{k}"].eq(d[f"id{k}"].shift())
    prev = d[f"c{k}"].shift().where(same, d[f"c{k+1}"].shift().where(d[f"id{k+1}"].shift().eq(d[f"id{k}"])))
    return d[f"c{k}"] - prev, prev


def tstats(pnl):
    pnl = pnl.dropna()
    pnl = pnl[pnl.index.map(lambda x: True)]
    def t(x):
        return x.mean() / x.std() * np.sqrt(len(x)) if len(x) > 20 and x.std() > 0 else np.nan
    dv = pnl[[i < SPLIT for i in pnl.index]]; ts = pnl[[i >= SPLIT for i in pnl.index]]
    sh = pnl.mean() / pnl.std() * np.sqrt(252) if pnl.std() > 0 else np.nan
    return dict(n=len(pnl), mean=pnl.mean(), t=t(pnl), t_dev=t(dv), t_test=t(ts), sharpe=sh,
                sh_dev=dv.mean() / dv.std() * np.sqrt(252) if dv.std() > 0 else np.nan,
                sh_test=ts.mean() / ts.std() * np.sqrt(252) if ts.std() > 0 else np.nan)


RESULTS = []


def report(name, pnl, unit, note=""):
    s = tstats(pnl)
    RESULTS.append((name, s, unit))
    registry.log("energy_lab", name, unit, s["n"], s["mean"], s["t"], s["t_dev"], s["t_test"], note)


def mr_positions(x, L, enter=2.0, exit_=0.5):
    """mean-reversion state machine on series x (known at close t-1 for trading day t)."""
    z = ((x - x.rolling(L).mean()) / x.rolling(L).std()).shift(1)
    pos, out = 0.0, []
    for v in z:
        if np.isnan(v):
            pos = 0.0
        elif pos == 0 and abs(v) > enter:
            pos = -np.sign(v)
        elif pos != 0 and abs(v) < exit_:
            pos = 0.0
        out.append(pos)
    return pd.Series(out, index=x.index)


def spread_pnl(pos, dspread_dollars, cost_rt):
    """daily $ P&L of a spread position; cost charged per unit of position change (half round trip)."""
    return pos * dspread_dollars - pos.diff().abs().fillna(0) * cost_rt / 2


def vol_scaled(r, target=0.10):
    vol = r.rolling(60).std().shift(1) * np.sqrt(252)
    return (target / vol).clip(upper=3)


def main():
    P = {r: panel(r) for r in MULT}
    P = {k: v for k, v in P.items() if v is not None}
    print("markets:", list(P))
    idx = sorted(set.intersection(*[set(v.index) for v in P.values()]))
    P = {k: v.reindex(idx) for k, v in P.items()}
    dP, ret = {}, {}
    for k, d in P.items():
        ch, prev = changes(d)
        dP[k] = ch
        ret[k] = (ch / prev.abs()).where(prev > 0)

    if {"CL", "BZ"} <= set(P):  # E1
        dsp = dP["BZ"] - dP["CL"]
        x = dsp.fillna(0).cumsum()
        for L in (20, 60, 120):
            pos = mr_positions(x, L)
            report(f"E1 WTI-Brent spread MR z{L}", spread_pnl(pos, dsp * 1000, 40), "$/day per spread")
    if {"CL", "RB", "HO"} <= set(P):  # E2, E3
        dcr = (2 * dP["RB"] * 42 + dP["HO"] * 42 - 3 * dP["CL"]) / 3
        x = dcr.fillna(0).cumsum()
        for L in (20, 60, 120):
            report(f"E2 3-2-1 crack MR z{L}", spread_pnl(mr_positions(x, L), dcr * 3000, 85), "$/day per 3-2-1 package")
        for prod in ("RB", "HO"):
            dc = dP[prod] * 42 - dP["CL"]
            report(f"E2 {prod}-CL crack MR z60", spread_pnl(mr_positions(dc.fillna(0).cumsum(), 60), dc * 1000, 30),
                   "$/day per 1:1 crack")
        lvl = (2 * P["RB"]["c1"] * 42 + P["HO"]["c1"] * 42 - 3 * P["CL"]["c1"]) / 3
        z = ((lvl - lvl.rolling(252).mean()) / lvl.rolling(252).std()).shift(1)
        pos = np.sign(z)
        pnl = pos * ret["CL"] - pos.diff().abs().fillna(0) * 0.0003
        report("E3 crack 1y-z -> CL long/short", pnl, "return/day")
        report("E3 crack 1y-z -> CL long/flat", pos.clip(lower=0) * ret["CL"] - pos.clip(lower=0).diff().abs().fillna(0) * 0.0003,
               "return/day")
    # E4 / E5 portfolios
    for L, lab in ((63, "3m"), (252, "12m")):
        legs = []
        for k in P:
            idxv = (1 + ret[k].fillna(0)).cumprod()
            w = np.sign(idxv / idxv.shift(L) - 1).shift(1) * vol_scaled(ret[k])
            legs.append(w * ret[k] - w.diff().abs().fillna(0) * 0.0003)
        report(f"E4 energy trend portfolio {lab}", pd.concat(legs, axis=1).mean(axis=1), "return/day")
    legs, slopes = [], {}
    for k, d in P.items():
        slopes[k] = ((d["c1"] - d["c2"]) / d["c2"].abs()).shift(1)
        w = np.sign(slopes[k]) * vol_scaled(ret[k])
        legs.append(w * ret[k] - w.diff().abs().fillna(0) * 0.0003)
    report("E5 energy carry portfolio (sign of slope)", pd.concat(legs, axis=1).mean(axis=1), "return/day")
    S = pd.DataFrame(slopes)
    rk = S.rank(axis=1)
    n = S.notna().sum(axis=1)
    cs = []
    for k in P:
        w = (rk[k] >= n - 1).astype(float) - (rk[k] <= 2).astype(float)
        w = w * vol_scaled(ret[k])
        cs.append(w * ret[k] - w.diff().abs().fillna(0) * 0.0003)
    report("E5 cross-sectional carry (long top2 / short bottom2)", pd.concat(cs, axis=1).mean(axis=1), "return/day")
    # E6 Cushing -> front calendar spread
    cu = pd.read_excel(f"{D}/ext/W_EPC0_SAX_YCUOK_MBBLw.xls", "Data 1", header=2)
    cu.columns = ["date", "stk"]
    cu = cu.dropna().set_index("date")["stk"]
    dI = cu.diff()
    wk = pd.Series([t.isocalendar()[1] for t in dI.index], index=dI.index)
    yr = pd.Series([t.year for t in dI.index], index=dI.index)
    surp = pd.Series(np.nan, index=dI.index)
    for t in dI.index:
        prior = (yr < t.year) & (yr >= t.year - 5) & ((wk - wk[t]).abs() <= 1)
        if prior.sum() >= 10:
            surp[t] = dI[t] - dI[prior].mean()
    cl = P["CL"]
    ok = cl["id0"].eq(cl["id0"].shift()) & cl["id1"].eq(cl["id1"].shift())
    dfs = ((cl["c0"] - cl["c1"]).diff()).where(ok)
    pos = pd.Series(0.0, index=cl.index)
    days = list(cl.index)
    for t, s in surp.dropna().items():
        i = np.searchsorted(days, (t + pd.Timedelta(days=5)).date())
        if i < len(days) - 6:
            pos.iloc[i + 1:i + 6] = -np.sign(s)
    report("E6 Cushing surprise -> next week front spread", spread_pnl(pos, dfs * 1000, 20), "$/day per spread")
    # E7 ES -> next day CL
    es = glob.glob(f"{D}/ohlcv-1d_ES_c_0_*.parquet")
    if es:
        e = pd.read_parquet(es[0])[["instrument_id", "close"]]
        e.index = e.index.date
        e = e.reindex(idx)
        er = (e["close"] / e["close"].shift() - 1).where(e["instrument_id"].eq(e["instrument_id"].shift()))
        pos = np.sign(er).shift(1)
        report("E7 S&P day return -> next-day CL", pos * ret["CL"] - pos.diff().abs().fillna(0) * 0.0003, "return/day")
    # E8 calendar spread MR (2nd - 3rd)
    ok2 = cl["id1"].eq(cl["id1"].shift()) & cl["id2"].eq(cl["id2"].shift())
    dcs = ((cl["c1"] - cl["c2"]).diff()).where(ok2)
    report("E8 CL 2nd-3rd spread MR z60", spread_pnl(mr_positions(dcs.fillna(0).cumsum(), 60), dcs * 1000, 20),
           "$/day per spread")
    # E9 expiry week: front contract's last 5 trading days
    last_day = cl["id0"].ne(cl["id0"].shift(-1))
    pos = pd.Series(0.0, index=cl.index)
    for i in np.nonzero(last_day.values)[0]:
        pos.iloc[max(0, i - 4):i + 1] = -1.0
    report("E9 short front spread, last 5 days before expiry", spread_pnl(pos, dfs * 1000, 20), "$/day per spread")

    # E10 / E11 seasonal cracks
    if {"RB", "HO"} <= set(P):
        months = pd.Series([i.month for i in idx], index=idx)
        for prod, mset, lab in (("RB", {2, 3, 4}, "E10 seasonal RB crack long Feb-Apr"),
                                ("HO", {9, 10, 11, 12}, "E11 seasonal HO crack long Sep-Dec")):
            dc = dP[prod] * 42 - dP["CL"]
            pos = months.isin(mset).astype(float)
            report(lab, spread_pnl(pos, dc * 1000, 30), "$/day per 1:1 crack")
    # E12 variance risk premium
    ovx = pd.read_csv(f"{D}/ext/ovx/fred_ovx.csv")
    ovx = pd.Series(pd.to_numeric(ovx.iloc[:, 1], errors="coerce").values,
                    index=pd.to_datetime(ovx.iloc[:, 0]).dt.date).dropna()
    r = ret["CL"]
    days = [i for i in idx if i in ovx.index]
    pnl_u, pnl_c, dts = [], [], []
    for j in range(21, len(days) - 21, 21):
        t0 = days[j]
        k = idx.index(t0)
        fut = r.iloc[k + 1:k + 22].dropna()
        past = r.iloc[k - 20:k + 1].dropna()
        if len(fut) < 18 or len(past) < 18:
            continue
        rv = (fut ** 2).mean() * 252
        kvar = (ovx[t0] / 100) ** 2
        pnl = (kvar - rv) * 100  # variance points x100 (1.0 = 0.01 annual variance)
        pnl_u.append(pnl)
        pnl_c.append(pnl if ovx[t0] / 100 > np.sqrt((past ** 2).mean() * 252) else 0.0)
        dts.append(t0)
    report("E12 short oil variance at OVX (monthly)", pd.Series(pnl_u, index=dts), "var-pts x100 per month")
    report("E12 short variance only when OVX > past realised", pd.Series(pnl_c, index=dts), "var-pts x100 per month")

    bar, ntests = registry.bonferroni_t()
    print(f"\n{'hypothesis':55s} {'mean':>9} {'t':>6} {'tDEV':>6} {'tTEST':>6} {'Sharpe':>6} {'ShDEV':>6} {'ShTEST':>6}  unit")
    for name, s, unit in RESULTS:
        flag = " <== passes" if abs(s["t"]) > bar and s["t_dev"] > 1.5 and s["t_test"] > 1.5 else ""
        print(f"{name:55s} {s['mean']:+9.4f} {s['t']:+6.2f} {s['t_dev']:+6.2f} {s['t_test']:+6.2f} {s['sharpe']:+6.2f} "
              f"{s['sh_dev']:+6.2f} {s['sh_test']:+6.2f}  {unit}{flag}")
    print(f"\nFamily-wise bar after {ntests} tests: |t| > {bar:.2f}")


if __name__ == "__main__":
    main()
