"""Compare several strategy families on the 08:00-18:00 BA MCL trades, with an honest split.

Entries only before 13:00 BA (when the trader watches); stop/target hold until the 18:00 close.
Round trip cost 2 ticks ($2 per MCL). 1 tick = $1 per MCL.
Parameters are chosen on the DEV period (before 2026-09-01); the TEST period (from 2026-09-01)
is reported for the dev-selected combination only, so it is not tuned on.
"""
import argparse
import itertools

import numpy as np
import pandas as pd

import session

TICK = 0.01
SPLIT = pd.Timestamp("2026-09-01", tz=session.BA).value
DELAY_NS = 10**9
COST = 2


class Mkt:
    def __init__(self, tr):
        self.tr = tr
        self.ts = tr["ts_event"].dt.as_unit("ns").astype("int64").to_numpy()
        self.px = tr["price"].to_numpy()
        self.sz = tr["size"].to_numpy().astype(float)
        loc = tr["ts_event"].dt.tz_convert(session.BA)
        self.lm = (loc.dt.hour * 60 + loc.dt.minute).to_numpy()  # minute of day, Buenos Aires
        self.day = pd.factorize(loc.dt.date)[0]
        b = tr["ts_event"].dt.floor("5min")
        g = tr.groupby(b)
        self.bar = b
        self.g = g
        self.hi = g["price"].cummax().to_numpy()
        self.lo = g["price"].cummin().to_numpy()
        self.op = g["price"].transform("first").to_numpy()
        self.idx = g.indices

    def after(self, i, ns=DELAY_NS):
        return int(np.searchsorted(self.ts, self.ts[i] + ns))

    def can_enter(self, k):
        return k < len(self.ts) and self.lm[k] < 13 * 60


def simulate(m, k, side, stop, target, cost=COST):
    end = np.searchsorted(m.ts, session.close_ns(m.ts[k]), side="right")
    path = (m.px[k:end] - m.px[k]) * side / TICK
    ht, hs = np.nonzero(path >= target)[0], np.nonzero(path <= -stop)[0]
    t_i, s_i = (ht[0] if len(ht) else 10**12), (hs[0] if len(hs) else 10**12)
    res = target if t_i < s_i else -stop if s_i < t_i else path[-1]
    return res - cost


def gap_filter(ks, m, gap_min=30):
    out, last = [], None
    for k, s in ks:
        if last is None or m.ts[k] - last > gap_min * 60 * 10**9:
            out.append((k, s))
        last = m.ts[k]
    return out


# ---------- entry generators: return list of (entry_index, side) ----------
def wide_bars(m, R):
    wide = (m.hi - m.lo) / TICK >= R
    rows = []
    for b, idx in pd.Series(np.arange(len(m.ts)))[wide].groupby(m.bar[wide].to_numpy()):
        i = idx.iloc[0]
        rows.append((b, i, m.idx[b][-1]))
    return rows


def spike_dir(m, i):
    return 1 if (m.hi[i] - m.op[i]) >= (m.op[i] - m.lo[i]) else -1


def ev_fade_pullback(m, R, P):
    out = []
    for b, i, end in wide_bars(m, R):
        d = spike_dir(m, i)
        seg = np.arange(i, end + 1)
        ext = m.hi[seg] if d > 0 else m.lo[seg]
        pulled = (ext - m.px[seg]) * d / TICK >= P
        if pulled.any():
            k = m.after(seg[np.argmax(pulled)])
            if m.can_enter(k):
                out.append((k, -d))
    return gap_filter(out, m)


def ev_follow_trigger(m, R):
    out = []
    for b, i, end in wide_bars(m, R):
        k = m.after(i)
        if m.can_enter(k):
            out.append((k, spike_dir(m, i)))
    return gap_filter(out, m)


def ev_fade_wait(m, R, W):
    out = []
    for b, i, end in wide_bars(m, R):
        d = spike_dir(m, end)
        k = m.after(end, (W * 60 + 1) * 10**9)
        if m.can_enter(k):
            out.append((k, -d))
    return gap_filter(out, m)


def ev_orb(m, pre_end=9 * 60 + 30):
    out = []
    for d in np.unique(m.day):
        ix = np.nonzero(m.day == d)[0]
        pre = ix[(m.lm[ix] >= 8 * 60) & (m.lm[ix] < pre_end)]
        post = ix[(m.lm[ix] >= pre_end) & (m.lm[ix] < 13 * 60)]
        if len(pre) < 50 or not len(post):
            continue
        hi, lo = m.px[pre].max(), m.px[pre].min()
        up, dn = np.nonzero(m.px[post] > hi)[0], np.nonzero(m.px[post] < lo)[0]
        first_up, first_dn = (up[0] if len(up) else 10**9), (dn[0] if len(dn) else 10**9)
        if first_up == first_dn == 10**9:
            continue
        out.append((int(post[min(first_up, first_dn)]), 1 if first_up < first_dn else -1))
    return out


def ev_vwap_fade(m, D):
    pv = pd.Series(m.px * m.sz).groupby(m.day).cumsum().to_numpy()
    vv = pd.Series(m.sz).groupby(m.day).cumsum().to_numpy()
    dev = (m.px - pv / vv) / TICK
    ok = (m.lm >= 9 * 60) & (m.lm < 13 * 60) & (np.abs(dev) >= D)
    out = [(m.after(i), -int(np.sign(dev[i]))) for i in np.nonzero(ok)[0]]
    out = [(k, s) for k, s in out if m.can_enter(k)]
    return gap_filter(out, m, gap_min=60)


# ---------- evaluation ----------
def evaluate(m, entries, stop, target):
    res = [(m.ts[k], simulate(m, k, s, stop, target)) for k, s in entries]
    return pd.DataFrame(res, columns=["ts", "ticks"])


def stats(df):
    if len(df) == 0:
        return dict(n=0, avg=np.nan, win=np.nan, t=np.nan)
    sd = df.ticks.std() if len(df) > 1 else np.nan
    return dict(n=len(df), avg=df.ticks.mean(), win=(df.ticks > 0).mean(),
                t=df.ticks.mean() / (sd / np.sqrt(len(df))) if sd and sd > 0 else np.nan)


EXITS = [(30, 60), (30, 90), (45, 90)]


def families(m):
    for R, P in itertools.product((60, 80, 100), (20,)):
        yield "fade_pullback", dict(R=R, P=P), ev_fade_pullback(m, R, P)
    for R in (60, 80, 100):
        yield "follow_trigger", dict(R=R), ev_follow_trigger(m, R)
    for R, W in itertools.product((60, 80, 100), (0, 3, 6)):
        yield "fade_wait", dict(R=R, W=W), ev_fade_wait(m, R, W)
    yield "orb_0930", dict(), ev_orb(m)
    for D in (80, 120):
        yield "vwap_fade", dict(D=D), ev_vwap_fade(m, D)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="strategies/lab_results.csv")
    a = ap.parse_args()
    m = Mkt(session.load_trades())
    rows = []
    for fam, params, ent in families(m):
        for stop, tgt in (EXITS if fam != "orb_0930" else [(40, 80), (80, 160), (80, 80)]):
            df = evaluate(m, ent, stop, tgt)
            dev, test = df[df.ts < SPLIT], df[df.ts >= SPLIT]
            sd, st = stats(dev), stats(test)
            rows.append(dict(family=fam, **params, stop=stop, target=tgt, n_dev=sd["n"], avg_dev=sd["avg"],
                             t_dev=sd["t"], n_test=st["n"], avg_test=st["avg"], win_test=st["win"], t_test=st["t"]))
    r = pd.DataFrame(rows)
    r.to_csv(a.out, index=False)
    print(f"{len(r)} parameter combinations tried\n")
    print("Per family: combo with the best DEV average (n_dev>=12), then its untouched TEST result")
    for fam, grp in r.groupby("family"):
        g = grp[grp.n_dev >= 12]
        if g.empty:
            print(f"{fam}: too few trades"); continue
        b = g.loc[g.avg_dev.idxmax()]
        keys = [c for c in ("R", "P", "W", "D") if c in b and pd.notna(b[c])]
        p = ", ".join(f"{c}={int(b[c])}" for c in keys)
        print(f"{fam:15s} [{p}] stop {int(b.stop)} tgt {int(b.target)}: DEV n={int(b.n_dev)} avg {b.avg_dev:+.1f}t | "
              f"TEST n={int(b.n_test)} avg {b.avg_test:+.1f}t win {b.win_test:.0%} t={b.t_test:+.1f}")


if __name__ == "__main__":
    main()
