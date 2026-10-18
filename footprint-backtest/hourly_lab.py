"""Pre-registered intraday hypotheses on 16 years of hourly CL bars (front month; 2nd month 2010-2020).

All in ticks of price change per trade ($1/tick/MCL, $10/tick/CL), New York time.
H1  late drift 15:00-17:00 ET conditioned on the day so far (prev 18:00 ET open -> 15:00 ET):
    H1a long late only if day is up; H1b long if up / short if down.
H2  European-morning weakness: short 06:00-09:00 ET.
H3  API (Tue 16:30 ET): follow the Tue 16:00-17:00 ET bar from Tue 18:00 ET to Wed 10:00 ET.
H4  EIA (Wed 10:30 ET): Wed 10:00-11:00 ET bar -> H4a follow / H4b fade over 11:00-15:00 ET.
DEV = sessions before 2018, TEST = 2018 on. Gross and net of 1 and 2 ticks.
"""
import glob

import numpy as np
import pandas as pd

import registry
from late_session import hourly_moves

SPLIT = pd.Timestamp("2018-01-01").date()


def seg(m, hours):
    return m[m.hr.isin(hours)].groupby("day")["dp"].sum() / 0.01


def stat(x):
    x = x.dropna()
    if len(x) < 20 or x.std() == 0:
        return np.nan, np.nan, len(x)
    return x.mean(), x.mean() / x.std() * np.sqrt(len(x)), len(x)


def show(prog, name, ticks, note=""):
    mean, t, n = stat(ticks)
    dv = ticks[[d < SPLIT for d in ticks.index]]
    ts = ticks[[d >= SPLIT for d in ticks.index]]
    md, td, _ = stat(dv)
    mt, tt, _ = stat(ts)
    print(f"  {name:58s} n={n:4d} gross {mean:+5.2f}t (t {t:+.2f}) | DEV {md:+5.2f} (t {td:+.2f}) TEST {mt:+5.2f} (t {tt:+.2f}) "
          f"| net1 {mean-1:+.2f} net2 {mean-2:+.2f}")
    registry.log(prog, name, "ticks/trade gross", n, mean, t, td, tt, note)


def run(path):
    m = hourly_moves(path)
    m = m[m.wd < 5]
    tag = "c0" if "_c_0_" in path else "c1"
    print(f"\n=== {tag}: {path.split('/')[-1]} ===")
    late = seg(m, [15, 16])
    day_so_far = seg(m, [18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14])
    up = np.sign(day_so_far.reindex(late.index))
    show(f"hourly_{tag}", "H0 late 15-17 ET unconditional (reference)", late)
    show(f"hourly_{tag}", "H1a long late only if day up", late.where(up > 0).dropna())
    show(f"hourly_{tag}", "H1b late follows day direction (long up / short down)", (late * up).dropna())
    show(f"hourly_{tag}", "H2 short 06:00-09:00 ET", -seg(m, [6, 7, 8]))
    wd = m.groupby("day")["wd"].first()
    # H3 API: Tuesday session's 16:00 bar; follow from Wed session start (18:00 ET Tue) to 10:00 ET Wed
    api_bar = m[(m.hr == 16)].groupby("day")["dp"].sum()
    api = api_bar[[wd.get(d, -1) == 1 for d in api_bar.index]]
    nxt = m[m.hr.isin([18, 19, 20, 21, 22, 23, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9])].groupby("day")["dp"].sum() / 0.01
    days = sorted(nxt.index)
    follow = {}
    for d, v in api.items():
        i = np.searchsorted(days, d, side="right")
        if i < len(days) and (pd.Timestamp(days[i]) - pd.Timestamp(d)).days <= 3 and v != 0:
            follow[days[i]] = np.sign(v) * nxt[days[i]]
    show(f"hourly_{tag}", "H3 follow API bar (Tue 16-17 ET) into Wed 10:00 ET", pd.Series(follow))
    eia_bar = m[m.hr == 10].groupby("day")["dp"].sum()
    eia = eia_bar[[wd.get(d, -1) == 2 for d in eia_bar.index]]
    rest = seg(m, [11, 12, 13, 14])
    sgn = np.sign(eia).replace(0, np.nan)
    show(f"hourly_{tag}", "H4a follow EIA bar (Wed 10-11 ET) for 11-15 ET", (rest.reindex(sgn.index) * sgn).dropna())
    show(f"hourly_{tag}", "H4b fade EIA bar (Wed 10-11 ET) for 11-15 ET", (-rest.reindex(sgn.index) * sgn).dropna())


if __name__ == "__main__":
    for p in sorted(glob.glob("data/ohlcv-1h_CL_c_*.parquet")):
        run(p)
    t_need, n = registry.bonferroni_t()
    print(f"\nFamily-wise bar after {n} tests in the whole search: |t| > {t_need:.2f}")
