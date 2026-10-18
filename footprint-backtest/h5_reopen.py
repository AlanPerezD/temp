"""H5 (pre-registered): after an up day (prev session close -> 15:00 ET up), the late pre-halt push
fades after the 18:00 ET reopen. Trade: short at the reopen (open of the 18:00 ET bar), cover at the
20:00 ET close (end of the 19:00 bar). Reference: same window on all days / down days.
Ticks of CL front month; same contract required."""
import numpy as np
import pandas as pd

import registry

SPLIT = pd.Timestamp("2018-01-01").date()


def main():
    h = pd.read_parquet("data/ohlcv-1h_CL_c_0_2010-06-07_2026-10-16.parquet")[["instrument_id", "open", "close"]]
    h = h[(h.open > 0) & (h.close > 0)]
    et = h.index.tz_convert("America/New_York")
    h = h.assign(d=et.date, hr=et.hour)
    cl = h.set_index(["d", "hr"])
    dates = sorted(set(h.d))
    rows = []
    for i in range(1, len(dates)):
        d, prev = dates[i], dates[i - 1]
        if pd.Timestamp(d).weekday() > 4:
            continue
        try:
            p_prev = cl.loc[(prev, 16)]   # price at prev 17:00 ET (close of 16:00 bar)
            p15 = cl.loc[(d, 14)]         # price at 15:00 ET
            o18 = cl.loc[(d, 18)]         # 18:00 ET bar: reopen
            c20 = cl.loc[(d, 19)]         # close of 19:00 bar = 20:00 ET
        except KeyError:
            continue
        ids = {p_prev.instrument_id, p15.instrument_id, o18.instrument_id, c20.instrument_id}
        if len(ids) > 1:
            continue
        rows.append(dict(d=d, up=np.sign(p15.close - p_prev.close), short=-(c20.close - o18.open) / 0.01))
    f = pd.DataFrame(rows)
    for lab, sub in (("H5 short reopen->20:00 ET after up day", f[f.up > 0]), ("  (reference) same window all days", f),
                     ("  (reference) after down day", f[f.up < 0])):
        x = sub["short"]
        t = x.mean() / x.std() * np.sqrt(len(x))
        dv = sub[[d < SPLIT for d in sub.d]]["short"]; ts = sub[[d >= SPLIT for d in sub.d]]["short"]
        td = dv.mean() / dv.std() * np.sqrt(len(dv)); tt = ts.mean() / ts.std() * np.sqrt(len(ts))
        print(f"{lab:42s} n={len(x)} gross {x.mean():+.2f} ticks (t {t:+.2f}) DEV {dv.mean():+.2f} (t {td:+.2f}) TEST {ts.mean():+.2f} (t {tt:+.2f})")
        if lab.startswith("H5"):
            registry.log("h5_reopen", lab, "ticks/trade gross", len(x), x.mean(), t, td, tt)


if __name__ == "__main__":
    main()
