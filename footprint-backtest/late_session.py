"""Robustness of the late-session drift (15:00-17:00 New York, after the 14:30 settlement).

For each hourly CL file: mean return by New York hour, the late segment per year, and the late
segment in ticks per day net of 1/2/3-tick round-trip costs (a fresh long each day at 15:00 ET,
flat at 17:00 ET). Plus an independent check on the MCL tick data (Jul 15 - Oct 15 2026).
"""
import glob

import numpy as np
import pandas as pd

import session

TICK = 0.01


def hourly_moves(path):
    h = pd.read_parquet(path)[["instrument_id", "open", "close"]]
    h = h[(h["open"] > 0) & (h["close"] > 0)]
    same = h["instrument_id"].eq(h["instrument_id"].shift())
    gap_ok = h.index.to_series().diff() <= pd.Timedelta(hours=3)
    dp = (h["close"] - h["close"].shift()).where(same & gap_ok, h["close"] - h["open"])
    et = h.index.tz_convert("America/New_York")
    return pd.DataFrame({"dp": dp.values, "ret": (dp / h["close"].shift().where(same & gap_ok, h["open"])).values,
                         "hr": et.hour, "day": (et + pd.Timedelta(hours=6)).date, "wd": (et + pd.Timedelta(hours=6)).weekday})


def report(path):
    m = hourly_moves(path)
    m = m[m.wd < 5]
    print(f"\n=== {path.split('/')[-1]} ===")
    by_hr = m.groupby("hr")["ret"].agg(["mean", "std", "count"])
    by_hr["t"] = by_hr["mean"] / (by_hr["std"] / np.sqrt(by_hr["count"]))
    print("mean return by New York hour (bps), t:")
    print("  " + " ".join(f"{h:02d}:{r['mean']*1e4:+.1f}({r['t']:+.1f})" for h, r in by_hr.iterrows()))
    late = m[m.hr.isin([15, 16])].groupby("day")[["dp", "ret"]].sum()
    ticks = late["dp"] / TICK
    t = ticks.mean() / ticks.std() * np.sqrt(len(ticks))
    print(f"late 15-17 ET: n={len(ticks)} days, gross {ticks.mean():+.2f} ticks/day (t={t:+.2f}), win {(ticks > 0).mean():.0%}")
    for c in (1, 2, 3):
        net = ticks - c
        print(f"   net of {c} tick(s): {net.mean():+.2f} ticks/day = ${net.mean():+.2f}/MCL/day, ~${net.mean()*250:+.0f}/MCL/year")
    yrs = ticks.groupby([d.year for d in ticks.index]).agg(["mean", "count"])
    print("   by year (gross ticks/day): " + " ".join(f"{y}:{r['mean']:+.1f}" for y, r in yrs.iterrows()))
    return ticks


def mcl_check():
    tr = session.load_trades()
    loc = tr["ts_event"].dt.tz_convert(session.BA)
    tr = tr.assign(d=loc.dt.date, lm=loc.dt.hour * 60 + loc.dt.minute)
    out = []
    for d, g in tr.groupby("d"):
        a = g[g.lm < 16 * 60]
        b = g[g.lm < 18 * 60]
        if len(a) and len(b) and a.lm.iloc[-1] >= 15 * 60 + 50:
            out.append((b.price.iloc[-1] - a.price.iloc[-1]) / TICK)
    x = np.array(out)
    print(f"\nMCL tick data 16:00-18:00 BA (=15-17 ET), {len(x)} days: gross {x.mean():+.2f} ticks/day, "
          f"t={x.mean()/x.std()*np.sqrt(len(x)):+.2f}, win {(x>0).mean():.0%}")


if __name__ == "__main__":
    for p in sorted(glob.glob("data/ohlcv-1h_CL_c_*.parquet")):
        report(p)
    mcl_check()
