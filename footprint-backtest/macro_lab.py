"""Bigger-picture oil edges, tested on 16 years (Jun 2010 - Oct 2026) of CL futures.

Instrument: the 2nd-month CL contract, rolled to the next contract when it becomes the front
(avoids expiry squeezes such as Apr 20 2020). Daily close-to-close returns, weekdays only.
Positions use information known by the previous close. Cost: 0.03% per unit of position change
(~2 ticks at $70). DEV = 2010-2017, TEST = 2018-2026 (not used to choose anything).

Families (all fixed in advance, mostly from published research):
  trend (time-series momentum), carry (curve slope), seasonality (month / weekday),
  index-roll calendar spread, EIA inventory surprise & level, CFTC managed-money positioning,
  session returns (overnight / NY day / late).
"""
import glob
import io
import zipfile
from math import erf, sqrt

import numpy as np
import pandas as pd

D = "data"
COST = 0.0003
SPLIT = pd.Timestamp("2018-01-01").date()


# ---------------------------------------------------------------- data
def load_daily():
    parts = []
    for k in (0, 1, 2):
        f = glob.glob(f"{D}/ohlcv-1d_CL_c_{k}_*.parquet")[0]
        x = pd.read_parquet(f)[["instrument_id", "close", "volume"]]
        x.columns = [f"id{k}", f"c{k}", f"v{k}"]
        parts.append(x)
    d = pd.concat(parts, axis=1, join="inner")
    d.index = d.index.date
    d = d[[pd.Timestamp(x).weekday() < 5 for x in d.index]]
    return d


def cont_returns(d, k=1):
    """roll-adjusted daily return of the k-th contract series (k=1: 2nd month)."""
    same = d[f"id{k}"].eq(d[f"id{k}"].shift())
    prev = d[f"c{k}"].shift().where(same, d[f"c{k+1}"].shift().where(d[f"id{k+1}"].shift().eq(d[f"id{k}"])))
    r = (d[f"c{k}"] - prev) / prev.abs()
    return r.where(prev > 0)


# ---------------------------------------------------------------- evaluation
def pstat(t):
    return 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))


def pnl_series(pos, r, cost=COST):
    """daily P&L: position (decided at the previous close) x return, minus cost per unit of change."""
    pos = pos.reindex(r.index).fillna(0)
    pnl = (pos * r - cost * pos.diff().abs().fillna(0)).dropna()
    return pnl[r.reindex(pnl.index).notna()], pos


def evaluate(name, pos, r, cost=COST):
    pnl, pos = pnl_series(pos, r, cost)
    def s(x):
        if len(x) < 30 or x.std() == 0:
            return np.nan, np.nan, np.nan
        return x.mean() * 252, x.mean() / x.std() * np.sqrt(252), x.mean() / x.std() * np.sqrt(len(x))
    ar, sh, t = s(pnl)
    dv = pnl[[i < SPLIT for i in pnl.index]]
    ts = pnl[[i >= SPLIT for i in pnl.index]]
    _, sh_d, _ = s(dv)
    _, sh_t, t_t = s(ts)
    yrs = pnl.groupby([i.year for i in pnl.index]).sum()
    return dict(name=name, ann=ar, sharpe=sh, t=t, p=pstat(t) if not np.isnan(t) else np.nan,
                sh_dev=sh_d, sh_test=sh_t, t_test=t_t, yrs_pos=(yrs > 0).mean(), exposure=(pos != 0).mean())


def evaluate_events(name, pnl, dates):
    """for per-event P&L (e.g. $ per spread), t-stat over events, dev/test means."""
    pnl, dates = np.asarray(pnl, float), np.asarray(dates)
    ok = ~np.isnan(pnl)
    pnl, dates = pnl[ok], dates[ok]
    t = pnl.mean() / (pnl.std(ddof=1) / np.sqrt(len(pnl)))
    dv, ts = pnl[[x < SPLIT for x in dates]], pnl[[x >= SPLIT for x in dates]]
    return dict(name=name, n=len(pnl), avg=pnl.mean(), t=t, p=pstat(t), dev=dv.mean(), test=ts.mean(),
                t_test=ts.mean() / (ts.std(ddof=1) / np.sqrt(len(ts))) if len(ts) > 2 else np.nan,
                win=(pnl > 0).mean())


# ---------------------------------------------------------------- families
def trend(d, r):
    idx = (1 + r.fillna(0)).cumprod()
    out = []
    for L in (21, 63, 126, 252):
        sig = np.sign(idx / idx.shift(L) - 1).shift(1)  # known at previous close
        out.append(evaluate(f"trend L={L}d long/short", sig, r))
        out.append(evaluate(f"trend L={L}d long/flat", sig.clip(lower=0), r))
    return out


def carry(d, r):
    slope = ((d["c1"] - d["c2"]) / d["c2"]).shift(1)
    back = np.sign(slope)
    idx = (1 + r.fillna(0)).cumprod()
    tr = np.sign(idx / idx.shift(252) - 1).shift(1)
    return [evaluate("carry backwardation long / contango short", back, r),
            evaluate("carry long only in backwardation", back.clip(lower=0), r),
            evaluate("carry + 12m trend agree (else flat)", back.where(back == tr, 0), r),
            evaluate("buy & hold (benchmark)", pd.Series(1.0, index=r.index), r, cost=0)]


def seasonality(d, r):
    m = pd.Series([x.month for x in r.index], index=r.index)
    wd = pd.Series([x.weekday() for x in r.index], index=r.index)
    month_tab = r.groupby(m).agg(["mean", "std", "count"])
    month_tab["t"] = month_tab["mean"] / (month_tab["std"] / np.sqrt(month_tab["count"]))
    wd_tab = r.groupby(wd).agg(["mean", "std", "count"])
    wd_tab["t"] = wd_tab["mean"] / (wd_tab["std"] / np.sqrt(wd_tab["count"]))
    out = [evaluate("season: long Mar-Jun (driving-season build-up)", m.isin([3, 4, 5, 6]).astype(float), r),
           evaluate("season: short Sep-Oct (refinery maintenance)", -m.isin([9, 10]).astype(float), r)]
    return out, month_tab, wd_tab


def business_day(d):
    s = pd.Series(1, index=d.index)
    ym = pd.Series([x.year * 100 + x.month for x in d.index], index=d.index)
    return s.groupby(ym).cumsum()


def index_roll(d):
    """Goldman roll: index funds sell front / buy 2nd on business days 5-9.
    P&L in $ per calendar spread (1000 bbl), short front/long 2nd, net $20 round trip."""
    bd = business_day(d)
    spread = d["c0"] - d["c1"]
    ok = d["id0"].eq(d["id0"].shift()) & d["id1"].eq(d["id1"].shift())
    ds = spread.diff().where(ok)
    out = []
    ym = pd.Series([x.year * 100 + x.month for x in d.index], index=d.index)
    for lo, hi, side, lab in ((5, 9, -1, "short front-spread BD5-9 (during index roll)"),
                              (1, 4, -1, "short front-spread BD1-4 (front-run the roll)"),
                              (10, 14, 1, "long front-spread BD10-14 (post-roll reversion)")):
        pnl, dates = [], []
        win = ds[(bd >= lo) & (bd <= hi)]
        for key, chunk in win.groupby(ym[win.index]):
            if chunk.notna().sum() >= 3:
                pnl.append(side * chunk.sum() * 1000 - 20)
                dates.append(pd.Timestamp(key // 100, key % 100, 1).date())
        out.append(evaluate_events(f"index roll: {lab} [$/spread/month]", pnl, dates))
    return out


def eia(d, r):
    x = pd.read_excel(f"{D}/ext/WCESTUS1w.xls", "Data 1", header=2)
    x.columns = ["date", "stocks"]
    x = x.dropna().set_index("date")["stocks"]
    dI = x.diff()
    wk = pd.Series([t.isocalendar()[1] for t in dI.index], index=dI.index)
    yr = pd.Series([t.year for t in dI.index], index=dI.index)
    norm, lvl_norm = pd.Series(np.nan, index=dI.index), pd.Series(np.nan, index=dI.index)
    for t in dI.index:
        prior = (yr < t.year) & (yr >= t.year - 5) & ((wk - wk[t]).abs() <= 1)
        if prior.sum() >= 10:
            norm[t] = dI[prior].mean()
            lvl_norm[t] = x[prior].mean()
    surprise = dI - norm
    level_dev = x / lvl_norm - 1
    dates = list(r.index)
    pos_s, pos_l = pd.Series(0.0, index=r.index), pd.Series(0.0, index=r.index)
    react = []
    for t in surprise.dropna().index:
        rel = (t + pd.Timedelta(days=5)).date()  # Wednesday release
        i = np.searchsorted(dates, rel)
        if i >= len(dates) - 6 or dates[i] < pd.Timestamp("2010-06-08").date():
            continue
        react.append((surprise[t], r.iloc[i]))
        pos_s.iloc[i + 1:i + 6] = -np.sign(surprise[t])          # next 5 days after release
        pos_l.iloc[i + 1:i + 6] = -np.sign(level_dev[t])
    rc = pd.DataFrame(react, columns=["s", "r"]).dropna()
    corr = rc.s.corr(rc.r)
    return [evaluate("EIA surprise (vs 5y seasonal) -> next 5 days, against the build", pos_s, r),
            evaluate("EIA stock level vs 5y seasonal -> next 5 days, low stocks long", pos_l, r)], corr, len(rc)


def cot(d, r):
    frames = []
    for f in sorted(glob.glob(f"{D}/ext/cot_*.zip")):
        z = zipfile.ZipFile(f)
        c = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), low_memory=False)
        c = c[c["CFTC_Contract_Market_Code"].astype(str).str.strip().str.zfill(6) == "067651"]
        frames.append(c[["Report_Date_as_YYYY-MM-DD", "M_Money_Positions_Long_All",
                         "M_Money_Positions_Short_All", "Open_Interest_All"]])
    c = pd.concat(frames).drop_duplicates("Report_Date_as_YYYY-MM-DD")
    c.index = pd.to_datetime(c["Report_Date_as_YYYY-MM-DD"])
    c = c.sort_index()
    net = (c["M_Money_Positions_Long_All"] - c["M_Money_Positions_Short_All"]) / c["Open_Interest_All"]
    rank = net.rolling(156, min_periods=104).apply(lambda w: (w[:-1] < w[-1]).mean(), raw=True)
    dnet = net.diff()
    dates = list(r.index)
    pc, pm = pd.Series(0.0, index=r.index), pd.Series(0.0, index=r.index)
    for t in net.index:
        rel = (t + pd.Timedelta(days=3)).date()  # Tuesday data, released Friday afternoon
        i = np.searchsorted(dates, rel, side="right")  # first trading day after release
        if i >= len(dates):
            continue
        rk = rank.get(t, np.nan)
        if not np.isnan(rk):
            pc.iloc[i:i + 5] = -1.0 if rk >= 0.9 else 1.0 if rk <= 0.1 else 0.0
        if not np.isnan(dnet.get(t, np.nan)):
            pm.iloc[i:i + 5] = np.sign(dnet[t])
    return [evaluate("COT managed-money extremes (3y pctile 90/10), contrarian", pc, r),
            evaluate("COT weekly change in managed-money net, follow", pm, r)], len(net)


def sessions():
    h = pd.read_parquet(glob.glob(f"{D}/ohlcv-1h_CL_c_0_*.parquet")[0])[["instrument_id", "open", "close"]]
    h = h[(h["open"] > 0) & (h["close"] > 0)]
    same = h["instrument_id"].eq(h["instrument_id"].shift())
    gap_ok = h.index.to_series().diff() <= pd.Timedelta(hours=3)
    rb = np.log(h["close"] / h["close"].shift()).where(same & gap_ok, np.log(h["close"] / h["open"]))
    et = h.index.tz_convert("America/New_York")
    hr = et.hour
    sess_date = (et + pd.Timedelta(hours=6)).date  # 18:00 ET belongs to the next trading day
    seg = np.where((hr >= 18) | (hr < 9), "overnight 18:00-09:00 ET", np.where(hr < 15, "NY day 09:00-15:00 ET", "late 15:00-17:00 ET"))
    df = pd.DataFrame({"r": rb.values, "seg": seg, "day": sess_date})
    daily = df.groupby(["day", "seg"])["r"].sum().unstack()
    daily = daily[[pd.Timestamp(x).weekday() < 5 for x in daily.index]]
    out = []
    for s in daily.columns:
        x = daily[s].dropna()
        t = x.mean() / x.std() * np.sqrt(len(x))
        dv, ts = x[[i < SPLIT for i in x.index]], x[[i >= SPLIT for i in x.index]]
        yrs = x.groupby([i.year for i in x.index]).sum()
        out.append(dict(name=f"session: long only {s}", ann=x.mean() * 252, sharpe=x.mean() / x.std() * np.sqrt(252),
                        t=t, p=pstat(t), sh_dev=dv.mean() / dv.std() * np.sqrt(252), sh_test=ts.mean() / ts.std() * np.sqrt(252),
                        t_test=ts.mean() / ts.std() * np.sqrt(len(ts)), yrs_pos=(yrs > 0).mean(), exposure=np.nan))
    return out


def holm(ps):
    ps = np.asarray(ps, float)
    order = np.argsort(ps)
    adj, run = np.empty(len(ps)), 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - k) * ps[i]))
        adj[i] = run
    return adj


def main():
    d = load_daily()
    r = cont_returns(d)
    lines = [f"Sample {d.index[0]} .. {d.index[-1]}: {r.notna().sum()} daily returns of the rolled 2nd-month CL contract",
             f"DEV <2018, TEST >=2018. Cost {COST:.2%} per unit position change.", ""]
    rows = trend(d, r) + carry(d, r)
    seas, month_tab, wd_tab = seasonality(d, r)
    rows += seas
    eia_rows, corr, n_eia = eia(d, r)
    rows += eia_rows
    cot_rows, n_cot = cot(d, r)
    rows += cot_rows
    rows += sessions()
    ev = index_roll(d)
    strat = [x for x in rows if not x["name"].startswith("buy & hold")]
    adj = holm([x["p"] for x in strat] + [x["p"] for x in ev])
    for x, a in zip(strat, adj[:len(strat)]):
        x["holm"] = a
    for x, a in zip(ev, adj[len(strat):]):
        x["holm"] = a
    lines.append(f"{'strategy':62s} {'ann%':>6} {'Sharpe':>6} {'t':>5} | {'ShDEV':>6} {'ShTEST':>6} {'tTEST':>5} | yrs+  expo  Holm-p")
    for x in sorted(rows, key=lambda z: -(z["sharpe"] if not np.isnan(z["sharpe"]) else -9)):
        lines.append(f"{x['name'][:62]:62s} {x['ann']*100:6.1f} {x['sharpe']:6.2f} {x['t']:5.1f} | {x['sh_dev']:6.2f} {x['sh_test']:6.2f} "
                     f"{x['t_test']:5.1f} | {x['yrs_pos']:.0%} {x['exposure'] if not np.isnan(x['exposure']) else 1:5.0%}  {x.get('holm', np.nan):.2f}")
    lines += ["", "Index-roll calendar spread (per month, $ per 1000-bbl spread, net $20):"]
    for x in ev:
        lines.append(f"  {x['name']:72s} n={x['n']} avg ${x['avg']:+.0f} t={x['t']:+.2f} win {x['win']:.0%} | DEV ${x['dev']:+.0f} TEST ${x['test']:+.0f} (t {x['t_test']:+.2f}) Holm-p {x['holm']:.2f}")
    lines += ["", f"EIA: correlation of inventory surprise with release-day return = {corr:+.2f} (n={n_eia}; negative = builds push price down, same day, not tradable after the fact)",
              f"COT: {n_cot} weekly reports used", "", "Average daily return by month (%), t-stat:"]
    lines += [f"  {int(mo):2d}: {row['mean']*100:+.3f}%  t={row['t']:+.2f}  n={int(row['count'])}" for mo, row in month_tab.iterrows()]
    lines += ["", "Average daily return by weekday (0=Mon), t-stat:"]
    lines += [f"  {int(w)}: {row['mean']*100:+.3f}%  t={row['t']:+.2f}" for w, row in wd_tab.iterrows()]
    txt = "\n".join(lines)
    print(txt)
    open("strategies/macro_results.txt", "w").write(txt + "\n")


if __name__ == "__main__":
    main()
