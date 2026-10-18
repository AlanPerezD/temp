"""Does the late-session edge fit the FTMO 50K rules? CL 1-minute bars, 2018-2026.

Rules to respect (from the trader's risk plan): flat and orders cancelled by 16:10 ET (own deadline
15:50 ET), a real stop and a target on every trade (min 1:2), MCL micros, one trade at a time.
Edge rule: long only if the day so far (session open -> 15:00 ET) is up. Entry at the open of the
15:00 ET bar. Stops are conservative: if stop and target are inside the same minute the stop
counts first, and a stop fills 1 tick worse. Results in ticks per CL contract (= per 10 MCL x $1).
"""
import glob

import numpy as np
import pandas as pd

TICK = 0.01


def load_minutes():
    files = sorted(glob.glob("data/ohlcv-1m_CL_c_0_*.parquet"))
    df = pd.concat(pd.read_parquet(f)[["instrument_id", "open", "high", "low", "close", "volume"]] for f in files)
    df = df[~df.index.duplicated()].sort_index()
    df = df[(df.open > 0) & (df.close > 0)]
    et = df.index.tz_convert("America/New_York")
    df["mod"] = et.hour * 60 + et.minute
    df["day"] = (et + pd.Timedelta(hours=6)).date
    df["wd"] = [pd.Timestamp(d).weekday() for d in df["day"]]
    same = df["instrument_id"].eq(df["instrument_id"].shift()) & (df.index.to_series().diff() <= pd.Timedelta(hours=6))
    df["dp"] = np.where(same, df["close"] - df["close"].shift(), df["close"] - df["open"])
    return df[df.wd < 5]


def simulate(opens, highs, lows, closes, stop_ticks, target_ticks, slip_ticks=1.0):
    """long trade entered at opens[0]; bars after that; returns (ticks, kind). Time exit at last close."""
    entry = opens[0]
    for h, l in zip(highs, lows):
        hit_s = l <= entry - stop_ticks * TICK + 1e-9
        hit_t = h >= entry + target_ticks * TICK - 1e-9
        if hit_s:                                   # stop first when both fall in one minute
            return -stop_ticks - slip_ticks, "stop"
        if hit_t:
            return target_ticks, "target"
    return (closes[-1] - entry) / TICK, "time"


def build_days(df):
    out = {}
    for d, g in df.groupby("day"):
        pre = g[(g["mod"] < 15 * 60) | (g["mod"] >= 18 * 60)]
        aft = g[(g["mod"] >= 15 * 60) & (g["mod"] < 17 * 60)]
        if len(aft) < 90 or aft["mod"].iloc[0] != 15 * 60:
            continue
        out[d] = dict(day_move=pre["dp"].sum() / TICK, aft=aft)
    return out


def window(aft, m0, m1):
    w = aft[(aft["mod"] >= m0) & (aft["mod"] < m1)]
    return w if len(w) >= (m1 - m0) * 0.6 else None


def tstat(x):
    x = np.asarray(x, float)
    return x.mean() / x.std() * np.sqrt(len(x)) if len(x) > 5 and x.std() > 0 else np.nan


def month_end(dates):
    alls = pd.bdate_range(min(dates), max(dates) + pd.Timedelta(days=40))
    s = pd.Series(1, index=alls)
    ym = s.index.to_period("M")
    me = set(d.date() for d in alls[(s.groupby(ym).cumcount(ascending=False).values < 5) | (s.groupby(ym).cumcount().values < 2)])
    return me


def main():
    df = load_minutes()
    days = build_days(df)
    dates = sorted(days)
    me = month_end(dates)
    up = [d for d in dates if days[d]["day_move"] > 0]
    print(f"CL minute bars {df.index[0].date()}..{df.index[-1].date()}: {len(dates)} sessions, {len(up)} up-days at 15:00 ET\n")
    wins = {"15:00-15:50 (inside your own rule)": (900, 950), "15:50-16:10 (past your deadline, inside FTMO)": (950, 970),
            "16:10-17:00 (FTMO forbids)": (970, 1020), "15:00-16:10 (all FTMO allows)": (900, 970), "15:00-17:00 (original edge)": (900, 1020)}
    print("1) Where does the gain happen? (ticks per CL, long on up-days, no costs)")
    for per, lo, hi in (("2018-2022", 2018, 2022), ("2023-2026", 2023, 2026), ("2018-2026", 2018, 2026)):
        print(f"  {per}:")
        sel = [d for d in up if lo <= d.year <= hi]
        for lab, (m0, m1) in wins.items():
            xs = []
            for d in sel:
                w = window(days[d]["aft"], m0, m1)
                if w is not None:
                    xs.append((w["close"].iloc[-1] - w["open"].iloc[0]) / TICK)
            print(f"    {lab:46s} n={len(xs):4d} {np.mean(xs):+6.2f} ticks  t={tstat(xs):+.2f}")
    print("\n   Month-end window only (last 5 + first 2 business days), 2018-2026:")
    for lab, (m0, m1) in wins.items():
        xs = []
        for d in up:
            if d.year >= 2018 and d in me:
                w = window(days[d]["aft"], m0, m1)
                if w is not None:
                    xs.append((w["close"].iloc[-1] - w["open"].iloc[0]) / TICK)
        print(f"    {lab:46s} n={len(xs):4d} {np.mean(xs):+6.2f} ticks  t={tstat(xs):+.2f}")

    print("\n2) The trades your plan would allow: stop + target on every order, flat by the deadline")
    print("   (ticks per CL = 10 MCL; costs: spread+fees 2.5 ticks per CL round trip assumed, i.e. $25 per 10 MCL)")
    for lab, m_end, stop, tgt in (("stop 20 / target 40, flat 15:50", 950, 20, 40), ("stop 20 / target 40, flat 16:09", 969, 20, 40),
                                  ("stop 30 / target 60, flat 16:09", 969, 30, 60), ("stop 15 / target 30, flat 15:50", 950, 15, 30)):
        for per, lo, hi in (("2018-2022", 2018, 2022), ("2023-2026", 2023, 2026)):
            res, kinds = [], []
            for d in up:
                if lo <= d.year <= hi:
                    w = window(days[d]["aft"], 900, m_end)
                    if w is None:
                        continue
                    r, k = simulate(w["open"].values, w["high"].values, w["low"].values, w["close"].values, stop, tgt)
                    res.append(r - 2.5); kinds.append(k)
            res = np.array(res)
            kc = pd.Series(kinds).value_counts(normalize=True)
            print(f"  {lab:34s} {per}: n={len(res):4d} net {res.mean():+6.2f} ticks (${res.mean()*10:+6.1f} per 10 MCL) t={tstat(res):+.2f} "
                  f"win {(res > 0).mean():.0%} | target {kc.get('target', 0):.0%} stop {kc.get('stop', 0):.0%} time {kc.get('time', 0):.0%}")
    print("\n3) Same, month-end days only (2018-2026), stop 20 / target 40, flat 16:09:")
    res = []
    for d in up:
        if d.year >= 2018 and d in me:
            w = window(days[d]["aft"], 900, 969)
            if w is not None:
                r, _ = simulate(w["open"].values, w["high"].values, w["low"].values, w["close"].values, 20, 40)
                res.append(r - 2.5)
    res = np.array(res)
    print(f"  n={len(res)} net {res.mean():+.2f} ticks (${res.mean()*10:+.1f} per 10 MCL) t={tstat(res):+.2f} win {(res > 0).mean():.0%}")

    print("\n4) For reference, NOT allowed on FTMO: hold to 16:59 ET with only a protective stop (no target)")
    for stop in (25, 40, 60, None):
        for per, lo, hi in (("2018-2022", 2018, 2022), ("2023-2026", 2023, 2026)):
            res = []
            for d in up:
                if lo <= d.year <= hi:
                    w = window(days[d]["aft"], 900, 1019)
                    if w is None:
                        continue
                    r, _ = simulate(w["open"].values, w["high"].values, w["low"].values, w["close"].values,
                                    stop if stop else 10_000, 10_000)
                    res.append(r - 2.5)
            res = np.array(res)
            print(f"  stop {str(stop) + ' ticks' if stop else 'none':10s} {per}: n={len(res)} net {res.mean():+6.2f} ticks "
                  f"(${res.mean()*10:+6.1f} per CL) t={tstat(res):+.2f} win {(res > 0).mean():.0%} worst {res.min():.0f} ticks")


if __name__ == "__main__":
    main()
