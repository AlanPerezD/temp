"""Walk-forward model on ~25 pre-registered daily features -> next-week CL return.

No look-ahead: every feature uses data available at that day's close (COT from its Friday release,
EIA stocks from the Wednesday release, OVX same-day). Target = sum of next 5 daily returns of the
rolled 2nd-month CL contract. Models (fixed hyper-parameters, chosen before running):
  A ridge regression (alpha=10, standardised features)
  B gradient boosting (depth 3, 200 trees, lr 0.05, min 100 per leaf)
Walk-forward: for each year 2014..2026 train on all earlier data (5-day purge), predict that year.
Trade once every 5 trading days: long if prediction > 0 else short (and a long/flat variant).
Cost 0.03% per unit of position change. OOS "DEV" = 2014-2017, OOS "TEST" = 2018-2026.
"""
import glob
import io
import zipfile

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

import registry
from energy_lab import changes, panel

D = "data"


def series(root):
    f = glob.glob(f"{D}/ohlcv-1d_{root}_c_0_*.parquet")[0]
    x = pd.read_parquet(f)[["instrument_id", "close"]]
    x.index = x.index.date
    r = (x["close"] / x["close"].shift() - 1).where(x["instrument_id"].eq(x["instrument_id"].shift()))
    return r


def seasonal_dev(path):
    x = pd.read_excel(path, "Data 1", header=2)
    x.columns = ["date", "v"]
    x = x.dropna().set_index("date")["v"]
    dI = x.diff()
    wk = pd.Series([t.isocalendar()[1] for t in x.index], index=x.index)
    yr = pd.Series([t.year for t in x.index], index=x.index)
    dev, surp = pd.Series(np.nan, index=x.index), pd.Series(np.nan, index=x.index)
    for t in x.index:
        prior = (yr < t.year) & (yr >= t.year - 5) & ((wk - wk[t]).abs() <= 1)
        if prior.sum() >= 10:
            dev[t] = x[t] / x[prior].mean() - 1
            surp[t] = (dI[t] - dI[prior].mean()) / 1000
    rel = [(t + pd.Timedelta(days=5)).date() for t in x.index]  # Wednesday release
    return pd.Series(dev.values, index=rel), pd.Series(surp.values, index=rel)


def cot_features():
    frames = []
    for f in sorted(glob.glob(f"{D}/ext/cot_*.zip")):
        z = zipfile.ZipFile(f)
        c = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), low_memory=False)
        c = c[c["CFTC_Contract_Market_Code"].astype(str).str.strip().str.zfill(6) == "067651"]
        frames.append(c[["Report_Date_as_YYYY-MM-DD", "M_Money_Positions_Long_All", "M_Money_Positions_Short_All",
                         "Open_Interest_All"]])
    c = pd.concat(frames).drop_duplicates("Report_Date_as_YYYY-MM-DD")
    c.index = pd.to_datetime(c["Report_Date_as_YYYY-MM-DD"])
    c = c.sort_index()
    net = (c["M_Money_Positions_Long_All"] - c["M_Money_Positions_Short_All"]) / c["Open_Interest_All"]
    rank = net.rolling(156, min_periods=104).apply(lambda w: (w[:-1] < w[-1]).mean(), raw=True)
    rel = [(t + pd.Timedelta(days=3)).date() for t in net.index]  # Friday release
    return pd.Series(rank.values, index=rel), pd.Series(net.diff().values, index=rel)


def build():
    P = {k: panel(k) for k in ("CL", "BZ", "HO", "RB")}
    idx = sorted(set.intersection(*[set(v.index) for v in P.values()]))
    P = {k: v.reindex(idx) for k, v in P.items()}
    dP, ret = {}, {}
    for k, d in P.items():
        ch, prev = changes(d)
        dP[k], ret[k] = ch, (ch / prev.abs()).where(prev > 0)
    cl, r = P["CL"], ret["CL"]
    F = pd.DataFrame(index=idx)
    lr = np.log1p(r.clip(lower=-0.9)).fillna(0)
    F["r1"] = r
    for n in (5, 21, 63, 126, 252):
        F[f"m{n}"] = lr.rolling(n).sum()
    F["rv21"] = r.rolling(21).std() * np.sqrt(252)
    F["rv_ratio"] = F["rv21"] / (r.rolling(126).std() * np.sqrt(252))
    F["slope12"] = (cl["c1"] - cl["c2"]) / cl["c2"].abs()
    F["slope01"] = (cl["c0"] - cl["c1"]) / cl["c1"].abs()
    F["dslope21"] = F["slope12"] - F["slope12"].shift(21)
    bx = (dP["BZ"] - dP["CL"]).fillna(0).cumsum()
    F["brent_z60"] = (bx - bx.rolling(60).mean()) / bx.rolling(60).std()
    crack = (2 * P["RB"]["c1"] * 42 + P["HO"]["c1"] * 42 - 3 * cl["c1"]) / 3
    F["crack_z252"] = (crack - crack.rolling(252).mean()) / crack.rolling(252).std()
    cx = ((2 * dP["RB"] * 42 + dP["HO"] * 42 - 3 * dP["CL"]) / 3).fillna(0).cumsum()
    F["crack_m21"] = cx - cx.shift(21)
    ovx = pd.read_csv(f"{D}/ext/ovx/fred_ovx.csv")
    ovx = pd.Series(pd.to_numeric(ovx.iloc[:, 1], errors="coerce").values, index=pd.to_datetime(ovx.iloc[:, 0]).dt.date)
    ovx = ovx.reindex(idx).ffill(limit=3)
    F["ovx"] = ovx
    F["vrp"] = ovx / 100 - F["rv21"]
    F["dovx5"] = ovx - ovx.shift(5)
    for k in ("ES", "ZN", "GC"):
        s = series(k).reindex(idx)
        ls = np.log1p(s.clip(lower=-0.9)).fillna(0)
        F[f"{k.lower()}_m5"] = ls.rolling(5).sum()
        F[f"{k.lower()}_m21"] = ls.rolling(21).sum()
    rank, dnet = cot_features()
    F["cot_rank"] = rank[~rank.index.duplicated()].sort_index().reindex(idx, method="ffill")
    F["cot_dnet"] = dnet[~dnet.index.duplicated()].sort_index().reindex(idx, method="ffill")
    dev, surp = seasonal_dev(f"{D}/ext/WCESTUS1w.xls")
    F["eia_dev"] = dev[~dev.index.duplicated()].sort_index().reindex(idx, method="ffill")
    F["eia_surp"] = surp[~surp.index.duplicated()].sort_index().reindex(idx, method="ffill")
    y = r[::-1].rolling(5).sum()[::-1].shift(-1)  # sum of returns t+1..t+5
    return F, y, r


def walk_forward(F, y, model_fn, years):
    preds = pd.Series(np.nan, index=F.index)
    for Y in years:
        start = pd.Timestamp(Y, 1, 1).date()
        end = pd.Timestamp(Y + 1, 1, 1).date()
        tr = [i for i in F.index if i < start][:-6]  # purge 5 days of overlapping targets
        te = [i for i in F.index if start <= i < end]
        Xtr, ytr = F.loc[tr], y.loc[tr]
        ok = Xtr.notna().all(axis=1) & ytr.notna()
        Xtr, ytr = Xtr[ok], ytr[ok]
        Xte = F.loc[te]
        okte = Xte.notna().all(axis=1)
        sc = StandardScaler().fit(Xtr)
        m = model_fn().fit(sc.transform(Xtr), ytr.values)
        preds.loc[Xte[okte].index] = m.predict(sc.transform(Xte[okte]))
    return preds


def trade(preds, y, long_flat=False, step=5, cost=0.0003):
    p = preds.dropna()
    p = p.iloc[::step]
    pos = (p > 0).astype(float) if long_flat else np.sign(p)
    pnl = pos * y.reindex(p.index) - pos.diff().abs().fillna(pos.abs()) * cost
    return pnl.dropna()


def stats(pnl):
    t = lambda x: x.mean() / x.std() * np.sqrt(len(x)) if len(x) > 10 and x.std() > 0 else np.nan
    split = pd.Timestamp("2018-01-01").date()
    dv, ts = pnl[[i < split for i in pnl.index]], pnl[[i >= split for i in pnl.index]]
    sh = lambda x: x.mean() / x.std() * np.sqrt(52) if x.std() > 0 else np.nan
    return dict(n=len(pnl), mean=pnl.mean(), t=t(pnl), t_dev=t(dv), t_test=t(ts), sh=sh(pnl), sh_dev=sh(dv), sh_test=sh(ts),
                hit=(pnl > 0).mean())


def main():
    F, y, r = build()
    print(f"{F.shape[1]} features: {', '.join(F.columns)}")
    years = list(range(2014, 2027))
    models = {"A ridge": lambda: Ridge(alpha=10.0),
              "B boosting": lambda: HistGradientBoostingRegressor(max_depth=3, learning_rate=0.05, max_iter=200,
                                                                   min_samples_leaf=100, l2_regularization=1.0, random_state=0)}
    bh = y.reindex(F.index).iloc[::5].dropna()
    bh = bh[[i >= pd.Timestamp("2014-01-01").date() for i in bh.index]]
    s = stats(bh)
    print(f"\n{'buy & hold weekly (reference)':40s} n={s['n']} Sharpe {s['sh']:+.2f} (DEV {s['sh_dev']:+.2f}, TEST {s['sh_test']:+.2f})")
    for name, fn in models.items():
        preds = walk_forward(F, y, fn, years)
        ic = preds.corr(y.reindex(preds.index))
        for lf in (False, True):
            pnl = trade(preds, y, long_flat=lf)
            s = stats(pnl)
            lab = f"ML {name} {'long/flat' if lf else 'long/short'}"
            print(f"{lab:40s} n={s['n']} Sharpe {s['sh']:+.2f} t {s['t']:+.2f} | DEV Sh {s['sh_dev']:+.2f} (t {s['t_dev']:+.2f}) "
                  f"TEST Sh {s['sh_test']:+.2f} (t {s['t_test']:+.2f}) | hit {s['hit']:.0%} | daily IC {ic:+.3f}")
            registry.log("ml_lab", lab, "return/week", s["n"], s["mean"], s["t"], s["t_dev"], s["t_test"])


if __name__ == "__main__":
    main()
