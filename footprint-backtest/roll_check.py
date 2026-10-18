"""Is the late-session edge a contract-roll artifact? Direct checks on the hourly data.

1. Where (New York hour) does the continuous series switch to the next contract month?
2. How many bars inside the 15:00-17:00 ET window involve a switch?
3. Re-run the rule (long 15:00-17:00 ET if day up) excluding roll days and the 5 sessions before
   and 2 after each roll (expiry period).
4. Per contract month: in how many individual contracts is the average late gain positive?
Price changes are always measured within ONE contract (never across the roll gap).
"""
import glob
import sys

import numpy as np
import pandas as pd

TICK = {"CL": 0.01, "HO": 0.0001, "RB": 0.0001, "NG": 0.001, "BZ": 0.01}
BEFORE15 = set([18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14])


def check(root, k=0):
    h = pd.read_parquet(glob.glob(f"data/ohlcv-1h_{root}_c_{k}_*.parquet")[0])[["instrument_id", "open", "close"]]
    h = h[(h.open > 0) & (h.close > 0)].copy()
    et = h.index.tz_convert("America/New_York")
    h["hr"], h["day"] = et.hour, (et + pd.Timedelta(hours=6)).date
    h["wd"] = [pd.Timestamp(d).weekday() for d in h["day"]]
    switch = h["instrument_id"].ne(h["instrument_id"].shift())
    same = ~switch & (h.index.to_series().diff() <= pd.Timedelta(hours=3))
    h["dp"] = np.where(same, h["close"] - h["close"].shift(), h["close"] - h["open"]) / TICK[root]
    sw = h[switch].iloc[1:]
    print(f"\n=== {root} (contract #{k+1}): {sw.shape[0]} contract switches in the continuous series ===")
    print("  switches by New York hour: " + ", ".join(f"{k:02d}h:{v}" for k, v in sw["hr"].value_counts().sort_index().items()))
    print(f"  switches inside 15:00-17:00 ET window: {int(sw['hr'].isin([15, 16]).sum())}")
    h = h[h.wd < 5]
    sess = h.groupby("day").agg(inst=("instrument_id", "last"), ninst=("instrument_id", "nunique"))
    sess["roll"] = sess["inst"].ne(sess["inst"].shift()) | (sess["ninst"] > 1)
    pos = np.arange(len(sess))
    roll_pos = pos[sess["roll"].values]
    near = np.zeros(len(sess), bool)
    for p in roll_pos:
        near[max(0, p - 5):p + 3] = True
    sess["near_roll"] = near
    late = h[h.hr.isin([15, 16])].groupby("day")["dp"].sum()
    day = h[h.hr.isin(BEFORE15)].groupby("day")["dp"].sum().reindex(late.index)
    f = pd.DataFrame({"late": late, "up": day > 0}).join(sess)
    f = f[f.up]
    def line(lab, x):
        print(f"  {lab:52s} n={len(x):4d}  {x.mean():+6.2f} ticks  t {x.mean()/x.std()*np.sqrt(len(x)):+.2f}")
    line("all up days (as reported)", f["late"])
    line("excluding roll days", f[~f["roll"]]["late"])
    line("excluding 5 sessions before / 2 after every roll", f[~f["near_roll"]]["late"])
    line("ONLY the sessions near a roll", f[f["near_roll"]]["late"])
    per = f[~f["near_roll"]].groupby("inst")["late"].mean()
    print(f"  per contract month (away from rolls): positive in {(per > 0).sum()} of {len(per)} contracts "
          f"({(per > 0).mean():.0%}); median {per.median():+.2f} ticks")


if __name__ == "__main__":
    for arg in (sys.argv[1:] or ("CL", "HO", "RB", "NG")):
        root, _, k = arg.partition(":")
        check(root, int(k or 0))
