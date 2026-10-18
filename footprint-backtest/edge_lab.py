"""Broad strategy search on 1-minute order-flow features, with a luck check.

Each signal family yields (entry trade index, side) events from information known at a minute
close (entry 1 s later, only 08:30-13:00 BA). Outcome = signed price change after H minutes
(15/30/60, never past the 18:00 close) minus a 2-tick round-trip cost, in ticks ($1/tick/MCL).

Honesty machinery:
  * dev = before 2026-09-01, test = from 2026-09-01; a combination is *selected* on dev only
    (dev t >= 1.5, n >= 15) and judged on test.
  * Luck check: the same selection is repeated on 300 randomised copies of the data (each minute's
    signal direction flipped at random, shared across combinations), showing how good selected
    combinations look when there is no information in the signals.
"""
import argparse

import numpy as np
import pandas as pd

import session
import strategy_lab as lab

TICK, COST = 0.01, 2
HORIZONS = (15, 30, 60)
LARGE = 10  # contracts: "large" trade in MCL


def minute_bars(tr):
    t = tr.reset_index(drop=True).copy()
    t["pos"] = np.arange(len(t))
    t["min"] = t["ts_event"].dt.floor("1min")
    t["buy"] = t["size"].where(t["side"] == "B", 0)
    t["sell"] = t["size"].where(t["side"] == "A", 0)
    big = t["size"] >= LARGE
    t["lbuy"] = t["buy"].where(big, 0)
    t["lsell"] = t["sell"].where(big, 0)
    g = t.groupby("min")
    b = pd.DataFrame({"high": g["price"].max(), "low": g["price"].min(), "close": g["price"].last(),
                      "vol": g["size"].sum(), "buy": g["buy"].sum(), "sell": g["sell"].sum(),
                      "lbuy": g["lbuy"].sum(), "lsell": g["lsell"].sum()})
    loc = b.index.tz_convert(session.BA)
    b["date"] = loc.date
    frames = []
    for d, f in b.groupby("date"):
        full = f.reindex(pd.date_range(f.index.min(), f.index.max(), freq="1min"))
        full[["vol", "buy", "sell", "lbuy", "lsell"]] = full[["vol", "buy", "sell", "lbuy", "lsell"]].fillna(0)
        full[["close", "high", "low"]] = full[["close", "high", "low"]].ffill()
        full["date"] = d
        frames.append(full)
    b = pd.concat(frames)
    loc = b.index.tz_convert(session.BA)
    b["lm"] = loc.hour * 60 + loc.minute
    gd = b.groupby("date")
    b["delta"] = b["buy"] - b["sell"]
    b["ldelta"] = b["lbuy"] - b["lsell"]
    pv = (b["close"] * b["vol"]).groupby(b["date"]).cumsum()
    vv = b["vol"].groupby(b["date"]).cumsum()
    b["vwap_dev"] = (b["close"] - pv / vv.replace(0, np.nan)) / TICK
    day_hi, day_lo = gd["high"].transform("max"), gd["low"].transform("min")
    daily = pd.DataFrame({"hi": day_hi.groupby(b["date"]).first(), "lo": day_lo.groupby(b["date"]).first()})
    prev = daily.shift(1)
    b["prev_hi"] = b["date"].map(prev["hi"])
    b["prev_lo"] = b["date"].map(prev["lo"])
    return b


def roll(b, col, n, how="sum", shift=0):
    f = {"sum": lambda s: s.rolling(n, min_periods=n).sum(), "max": lambda s: s.rolling(n, min_periods=n).max(),
         "min": lambda s: s.rolling(n, min_periods=n).min()}[how]
    out = b.groupby("date")[col].transform(f)
    return out.groupby(b["date"]).shift(shift) if shift else out


def sides_to_events(m, b, side_series, gap_min=30):
    """minute-close signals -> (entry trade index, side), entries 08:30-13:00 BA, spaced by gap_min."""
    sig = side_series.fillna(0)
    sig = sig[(sig != 0) & (b["lm"] >= 8 * 60 + 30) & (b["lm"] < 13 * 60)]
    out = []
    for ts, s in sig.items():
        k = int(np.searchsorted(m.ts, ts.value + 60 * 10**9 + lab.DELAY_NS))
        if m.can_enter(k):
            out.append((k, int(s)))
    return lab.gap_filter(out, m, gap_min)


def build_combos(m, b):
    c = {}
    ret = lambda n: (b["close"] - b.groupby("date")["close"].shift(n)) / TICK
    for N in (5, 15, 30):
        dr = roll(b, "delta", N) / roll(b, "vol", N).replace(0, np.nan)
        for thr in (0.1, 0.2):
            s = np.sign(dr).where(dr.abs() >= thr)
            c[f"delta_follow N{N} thr{thr}"] = sides_to_events(m, b, s)
            c[f"delta_fade N{N} thr{thr}"] = sides_to_events(m, b, -s)
    for N in (15, 30):
        r, dr = ret(N), roll(b, "delta", N) / roll(b, "vol", N).replace(0, np.nan)
        for x in (30, 60):
            s = pd.Series(0.0, index=b.index)
            s[(r >= x) & (dr <= -0.05)] = -1   # price up on selling delta -> fade
            s[(r <= -x) & (dr >= 0.05)] = 1
            c[f"delta_divergence N{N} x{x}"] = sides_to_events(m, b, s)
    v5, d5 = roll(b, "vol", 5), roll(b, "delta", 5)
    rng5 = (roll(b, "high", 5, "max") - roll(b, "low", 5, "min")) / TICK
    for vt in (1000, 1500):
        for rm in (30, 45):
            ok = (v5 >= vt) & (rng5 <= rm) & ((d5 / v5.replace(0, np.nan)).abs() >= 0.2)
            c[f"absorption vol{vt} rng{rm}"] = sides_to_events(m, b, -np.sign(d5).where(ok))
    for N in (30, 60):
        hi = roll(b, "high", N, "max", shift=1)
        lo = roll(b, "low", N, "min", shift=1)
        for vt in (800, 1500):
            s = pd.Series(0.0, index=b.index)
            s[(b["close"] > hi) & (v5 >= vt)] = 1
            s[(b["close"] < lo) & (v5 >= vt)] = -1
            c[f"breakout_follow N{N} vol{vt}"] = sides_to_events(m, b, s)
            c[f"breakout_fade N{N} vol{vt}"] = sides_to_events(m, b, -s)
    for N in (30, 60):
        r = ret(N)
        for x in (60, 120):
            s = np.sign(r).where(r.abs() >= x)
            c[f"momentum_follow N{N} x{x}"] = sides_to_events(m, b, s)
            c[f"momentum_fade N{N} x{x}"] = sides_to_events(m, b, -s)
    for D in (80, 120):
        s = np.sign(b["vwap_dev"]).where(b["vwap_dev"].abs() >= D)
        c[f"vwap_follow D{D}"] = sides_to_events(m, b, s, 60)
        c[f"vwap_fade D{D}"] = sides_to_events(m, b, -s, 60)
    for N in (15, 30):
        ld, vv = roll(b, "ldelta", N), roll(b, "vol", N).replace(0, np.nan)
        for thr in (0.05, 0.1):
            s = np.sign(ld).where((ld / vv).abs() >= thr)
            c[f"large_follow N{N} thr{thr}"] = sides_to_events(m, b, s)
            c[f"large_fade N{N} thr{thr}"] = sides_to_events(m, b, -s)
    s = pd.Series(0.0, index=b.index)
    s[b["close"] > b["prev_hi"]] = 1
    s[b["close"] < b["prev_lo"]] = -1
    first = s.ne(0) & (s.groupby([b["date"], s]).cumcount() == 0)
    s = s.where(first, 0)
    c["prevday_break_follow"] = sides_to_events(m, b, s, 120)
    c["prevday_break_fade"] = sides_to_events(m, b, -s, 120)
    orb = lab.ev_orb(m)
    c["orb_follow"], c["orb_fade"] = orb, [(k, -s) for k, s in orb]
    return c


def gross(m, ev, H):
    """side-adjusted price change (ticks) after H minutes; NaN if the horizon is not covered."""
    ks = np.array([k for k, _ in ev], dtype=int)
    sd = np.array([s for _, s in ev], dtype=float)
    tgt = m.ts[ks] + H * 60 * 10**9
    cap = np.array([session.close_ns(m.ts[k]) for k in ks])
    j = np.searchsorted(m.ts, np.minimum(tgt, cap), side="right") - 1
    nxt = np.where(j + 1 < len(m.ts), m.ts[np.minimum(j + 1, len(m.ts) - 1)], 0)
    ok = (tgt <= cap) & (nxt - tgt <= 10 * 60 * 10**9) & (nxt >= tgt)
    g = (m.px[j] - m.px[ks]) / TICK * sd
    return np.where(ok, g, np.nan), m.ts[ks]


def table(m, combos):
    rows = []
    for name, ev in combos.items():
        if len(ev) < 10:
            continue
        for H in HORIZONS:
            g, ts = gross(m, ev, H)
            mk = ts // 60_000_000_000
            rows.append((name, H, g, ts, mk))
    return rows


def select_and_judge(rows, flips=None, tmin=1.5, nmin=15):
    sel = []
    for name, H, g, ts, mk in rows:
        if flips is not None:
            g = g * flips[mk - flips_base]
        net = g - COST
        dev, test = net[(ts < lab.SPLIT) & ~np.isnan(net)], net[(ts >= lab.SPLIT) & ~np.isnan(net)]
        if len(dev) < nmin or len(test) < 8 or dev.std() == 0:
            continue
        t = dev.mean() / (dev.std() / np.sqrt(len(dev)))
        if t >= tmin:
            sel.append((name, H, len(dev), dev.mean(), t, len(test), test.mean(),
                        test.mean() / (test.std() / np.sqrt(len(test))) if test.std() > 0 else np.nan))
    return sel


flips_base = 0


def main():
    global flips_base
    ap = argparse.ArgumentParser()
    ap.add_argument("--perms", type=int, default=300)
    a = ap.parse_args()
    tr = session.load_trades()
    m = lab.Mkt(tr)
    b = minute_bars(tr)
    combos = build_combos(m, b)
    rows = table(m, combos)
    print(f"{len(combos)} signal variants x {len(HORIZONS)} horizons = {len(rows)} tests; "
          f"events per variant: median {int(np.median([len(v) for v in combos.values()]))}")
    sel = select_and_judge(rows)
    print(f"\nSelected on DEV (t>=1.5, n>=15): {len(sel)} of {len(rows)}")
    for s in sorted(sel, key=lambda x: -x[4]):
        print(f"  {s[0]:34s} H{s[1]:>2}m dev n={s[2]:3d} avg {s[3]:+6.1f}t t={s[4]:.1f} | TEST n={s[5]:3d} avg {s[6]:+6.1f}t t={s[7]:+.1f}")
    obs = np.mean([s[6] for s in sel]) if sel else np.nan
    pos = sum(s[6] > 0 for s in sel)
    print(f"\nObserved: mean TEST avg of selected = {obs:+.2f} ticks; {pos}/{len(sel)} positive")
    allmk = np.concatenate([r[4] for r in rows]); flips_base = allmk.min()
    rng = np.random.default_rng(1)
    null, nsel, npos = [], [], []
    for _ in range(a.perms):
        flips = rng.choice([-1.0, 1.0], size=allmk.max() - flips_base + 1)
        sl = select_and_judge(rows, flips)
        nsel.append(len(sl))
        if sl:
            null.append(np.mean([s[6] for s in sl])); npos.append(sum(s[6] > 0 for s in sl) / len(sl))
    null = np.array(null)
    print(f"Luck check ({a.perms} randomised copies): selected {np.mean(nsel):.1f} combos on average by chance; "
          f"their mean TEST avg = {null.mean():+.2f}t (sd {null.std():.2f}); positive share {np.mean(npos):.0%}")
    print(f"P(luck gives >= observed mean test avg) = {(null >= obs).mean():.2f}")


if __name__ == "__main__":
    main()
