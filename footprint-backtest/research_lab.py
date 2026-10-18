"""Literature-motivated daily strategies, tested one trade per day with proper statistics.

All times Buenos Aires; New York time = BA - 1 h while US daylight time lasts (true for the whole
sample, Jul 15 - Oct 15 2026): 09:00 ET pit open = 10:00 BA, 10:30 ET EIA = 11:30 BA,
14:30 ET settlement = 15:30 BA, 17:00 ET close = 18:00 BA.

Variants are fixed in advance (no tuning). Per variant: n, net avg ticks (2-tick round-trip cost),
t-stat, bootstrap 95% CI, dev (before Sep 1) vs test (from Sep 1) averages, a sign-flip permutation
p-value, and Holm-adjusted p across ALL variants.
"""
import argparse

import numpy as np
import pandas as pd

import session
import strategy_lab as lab

TICK, COST = 0.01, 2


class Days:
    def __init__(self, tr):
        self.m = lab.Mkt(tr)
        dates = tr["ts_event"].dt.tz_convert(session.BA).dt.date.to_numpy()
        self.ix, self.date = {}, {}
        for d in np.unique(self.m.day):
            ix = np.nonzero(self.m.day == d)[0]
            self.ix[d], self.date[d] = ix, dates[ix[0]]
        self.ids = sorted(self.ix)

    def px_before(self, d, minute, fresh=10):
        """price of the last trade before HH:MM:00 (minute = minutes since midnight BA)."""
        ix = self.ix[d]
        j = np.searchsorted(self.m.lm[ix], minute, side="left") - 1
        return (self.m.px[ix[j]], ix[j]) if j >= 0 and minute - self.m.lm[ix[j]] <= fresh else (np.nan, -1)

    def px_after(self, d, minute, fresh=10):
        """first trade at/after HH:MM:00 (+1 s of latency)."""
        ix = self.ix[d]
        j = np.searchsorted(self.m.lm[ix], minute, side="left")
        if j >= len(ix) or self.m.lm[ix[j]] - minute > fresh:
            return np.nan, -1
        k = self.m.after(ix[j])
        return (self.m.px[k], k) if k < len(self.m.px) and self.m.day[k] == d else (np.nan, -1)

    def weekday(self, d):
        return pd.Timestamp(self.date[d]).weekday()


def hm(h, m=0):
    return h * 60 + m


def trade(D, d, side, t_in, t_out):
    """one trade: in at t_in, out at t_out (minutes), returns net ticks or NaN."""
    p0, _ = D.px_after(d, t_in)
    p1, _ = D.px_before(d, t_out)
    return side * (p1 - p0) / TICK - COST if not (np.isnan(p0) or np.isnan(p1)) else np.nan, side * (p1 - p0) / TICK


def momentum_variants(D):
    out = {}
    rows = {"prevclose_to_1100": [], "ny_first30": [], "eia_wed_1130": []}
    prev_close = None
    for d in D.ids:
        p_close, _ = D.px_before(d, hm(17, 59))
        if prev_close is not None:
            a, _ = D.px_before(d, hm(11, 0))
            rows["prevclose_to_1100"].append((d, np.sign(a - prev_close)))
        prev_close = p_close
        a, _ = D.px_before(d, hm(10, 30)); b, _ = D.px_before(d, hm(11, 0))
        rows["ny_first30"].append((d, np.sign(b - a)))
        if D.weekday(d) == 2:
            a, _ = D.px_before(d, hm(11, 30)); b, _ = D.px_before(d, hm(12, 0))
            rows["eia_wed_1130"].append((d, np.sign(b - a)))
    for name, lst in rows.items():
        out[f"mom_{name}->last30(16:30-17:00)"] = [(d, s, hm(16, 30), hm(17, 0)) for d, s in lst if s != 0 and not np.isnan(s)]
    return out


def eia_variants(D):
    out = {}
    for hold in (5, 15, 25):
        fade, follow = [], []
        for d in D.ids:
            if D.weekday(d) != 2:
                continue
            a, _ = D.px_before(d, hm(11, 30)); b, _ = D.px_before(d, hm(11, 35))
            s = np.sign(b - a)
            if s != 0 and not np.isnan(s):
                fade.append((d, -s, hm(11, 35), hm(11, 35 + hold))); follow.append((d, s, hm(11, 35), hm(11, 35 + hold)))
        out[f"eia_react_FADE hold{hold}m"], out[f"eia_react_FOLLOW hold{hold}m"] = fade, follow
    pre = []
    for d in D.ids:
        if D.weekday(d) != 2:
            continue
        a, _ = D.px_before(d, hm(11, 20)); b, _ = D.px_before(d, hm(11, 25))
        s = np.sign(b - a)
        if s != 0 and not np.isnan(s):
            pre.append((d, s, hm(11, 25), hm(11, 40)))
    out["eia_prerelease_follow (11:20-11:25 -> hold to 11:40)"] = pre
    return out


def settlement_variants(D):
    out = {}
    for lab_, sg in (("follow", 1), ("fade", -1)):
        rows = []
        for d in D.ids:
            a, _ = D.px_before(d, hm(15, 0)); b, _ = D.px_before(d, hm(15, 30))
            s = np.sign(b - a)
            if s != 0 and not np.isnan(s):
                rows.append((d, sg * s, hm(15, 30), hm(16, 30)))
        out[f"settlement_{lab_} (15:00-15:30 -> 15:30-16:30)"] = rows
    return out


def orb_pit(D, or_min, follow=True):
    """pit-open (10:00 BA) opening range: first break within 3h, stop at the other side, out at 17:00 BA."""
    res = []
    for d in D.ids:
        ix = D.ix[d]
        lm_d, px_d = D.m.lm[ix], D.m.px[ix]
        win = (lm_d >= hm(10)) & (lm_d < hm(10) + or_min)
        post = np.nonzero((lm_d >= hm(10) + or_min) & (lm_d < hm(13)))[0]
        if win.sum() < 20 or not len(post):
            continue
        hi, lo = px_d[win].max(), px_d[win].min()
        up, dn = np.nonzero(px_d[post] > hi)[0], np.nonzero(px_d[post] < lo)[0]
        fu, fd = (up[0] if len(up) else 10**9), (dn[0] if len(dn) else 10**9)
        if fu == fd == 10**9:
            continue
        brk = post[min(fu, fd)]
        s = (1 if fu < fd else -1) * (1 if follow else -1)
        k = ix[brk]
        stop = max(20, (hi - lo) / TICK) if follow else max(20, (hi - lo) / TICK)
        end_t = np.searchsorted(D.m.ts, session.close_ns(D.m.ts[k]) - 3600 * 10**9, side="right")  # 17:00 BA
        path = (D.m.px[k:end_t] - D.m.px[k]) * s / TICK
        hs = np.nonzero(path <= -stop)[0]
        res.append((d, (-stop if len(hs) else path[-1] if len(path) else np.nan) - COST))
    return res


def stats(net, dates, gross=None, perms=5000, rng=None):
    net = np.asarray(net, float)
    ok = ~np.isnan(net)
    net, dates = net[ok], np.asarray(dates)[ok]
    n = len(net)
    if n < 5:
        return None
    sd = net.std(ddof=1)
    t = net.mean() / (sd / np.sqrt(n)) if sd > 0 else np.nan
    boot = np.percentile([rng.choice(net, n).mean() for _ in range(2000)], [2.5, 97.5])
    split = pd.Timestamp("2026-09-01").date()
    dev = net[np.array([d < split for d in dates])]
    test = net[np.array([d >= split for d in dates])]
    p = np.nan
    if gross is not None:
        g = np.asarray(gross, float)[ok]
        null = np.array([(g * rng.choice([-1, 1], n)).mean() - COST for _ in range(perms)])
        p = (null >= net.mean()).mean()
    return dict(n=n, avg=net.mean(), t=t, lo=boot[0], hi=boot[1], win=(net > 0).mean(),
                dev=dev.mean() if len(dev) else np.nan, ndev=len(dev), test=test.mean() if len(test) else np.nan,
                ntest=len(test), p=p)


def holm(ps):
    order = np.argsort(ps)
    adj = np.empty(len(ps)); run = 0.0
    for r, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - r) * ps[i])); adj[i] = run
    return adj


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="strategies/research_results.txt")
    a = ap.parse_args()
    D = Days(session.load_trades())
    rng = np.random.default_rng(7)
    variants = {}
    for fn in (momentum_variants, eia_variants, settlement_variants):
        variants.update(fn(D))
    rows = []
    for name, lst in variants.items():
        net, gross, dts = [], [], []
        for d, s, t_in, t_out in lst:
            n_, g_ = trade(D, d, s, t_in, t_out)
            net.append(n_); gross.append(g_); dts.append(D.date[d])
        st = stats(net, dts, gross, rng=rng)
        if st: rows.append((name, st))
    for or_min in (5, 15, 30):
        for follow in (True, False):
            r = orb_pit(D, or_min, follow)
            st = stats([x for _, x in r], [D.date[d] for d, _ in r], None, rng=rng)
            if st: rows.append((f"orb_pit {'follow' if follow else 'fade'} OR{or_min}m (stop=OR width, out 17:00)", st))
    # ORB has no permutation p: use the one-sided normal p from its t-stat
    from math import erf, sqrt
    ps = np.array([s["p"] if not np.isnan(s["p"]) else 0.5 * (1 - erf(s["t"] / sqrt(2))) for _, s in rows])
    adj = holm(ps)
    lines = [f"{len(rows)} pre-defined variants; net of {COST}-tick cost; 1 tick = $1/MCL", ""]
    for (name, s), pr, pa in sorted(zip(rows, ps, adj), key=lambda x: x[1]):
        lines.append(f"{name:62s} n={s['n']:3d} avg {s['avg']:+7.1f}t t={s['t']:+5.2f} CI[{s['lo']:+6.1f},{s['hi']:+6.1f}] "
                     f"win {s['win']:.0%} | dev {s['dev']:+6.1f} (n{s['ndev']}) test {s['test']:+6.1f} (n{s['ntest']}) | p={pr:.3f} Holm={pa:.2f}")
    txt = "\n".join(lines); print(txt); open(a.out, "w").write(txt + "\n")


if __name__ == "__main__":
    main()
