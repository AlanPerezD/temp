"""Near-expiry vs normal weeks, split DEV (<2018) / TEST (2018+), for the late-session rule.
'Near roll' = 5 sessions before to 2 sessions after the continuous series switches contract.
Found after the fact for HO/RB, so treat the near-roll subgroup as a NEW hypothesis to confirm."""
import sys

import numpy as np
import pandas as pd

import registry
import roll_check as rc

SPLIT = pd.Timestamp("2018-01-01").date()


def frame(root, k):
    import glob
    h = pd.read_parquet(glob.glob(f"data/ohlcv-1h_{root}_c_{k}_*.parquet")[0])[["instrument_id", "open", "close"]]
    h = h[(h.open > 0) & (h.close > 0)].copy()
    et = h.index.tz_convert("America/New_York")
    h["hr"], h["day"] = et.hour, (et + pd.Timedelta(hours=6)).date
    h["wd"] = [pd.Timestamp(d).weekday() for d in h["day"]]
    switch = h["instrument_id"].ne(h["instrument_id"].shift())
    same = ~switch & (h.index.to_series().diff() <= pd.Timedelta(hours=3))
    h["dp"] = np.where(same, h["close"] - h["close"].shift(), h["close"] - h["open"]) / rc.TICK[root]
    h = h[h.wd < 5]
    sess = h.groupby("day").agg(inst=("instrument_id", "last"), ninst=("instrument_id", "nunique"))
    roll = (sess["inst"].ne(sess["inst"].shift()) | (sess["ninst"] > 1)).values
    near = np.zeros(len(sess), bool)
    for p in np.nonzero(roll)[0]:
        near[max(0, p - 5):p + 3] = True
    sess["near"] = near
    late = h[h.hr.isin([15, 16])].groupby("day")["dp"].sum()
    day = h[h.hr.isin(rc.BEFORE15)].groupby("day")["dp"].sum().reindex(late.index)
    f = pd.DataFrame({"late": late, "up": day > 0}).join(sess)
    return f[f.up]


def t(x):
    return x.mean() / x.std() * np.sqrt(len(x)) if len(x) > 10 else np.nan


if __name__ == "__main__":
    for arg in (sys.argv[1:] or ("CL:0", "CL:1", "HO:0", "HO:1", "RB:0", "RB:1", "NG:0")):
        root, _, k = arg.partition(":")
        f = frame(root, int(k))
        for lab, sub in (("near expiry", f[f.near]), ("normal weeks", f[~f.near])):
            dv = sub[[d < SPLIT for d in sub.index]]["late"]; ts = sub[[d >= SPLIT for d in sub.index]]["late"]
            print(f"  {root} #{int(k)+1} {lab:13s} DEV {dv.mean():+6.2f} (t {t(dv):+.2f}, n{len(dv)})  TEST {ts.mean():+6.2f} (t {t(ts):+.2f}, n{len(ts)})")
            registry.log("roll_split", f"{root} c{k} {lab}", "ticks/trade gross", len(sub), sub["late"].mean(), t(sub["late"]), t(dv), t(ts),
                         "post-hoc subgroup check")
