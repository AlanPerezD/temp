"""FTMO-compliant version of the index close-momentum trade, on 1-minute bars.

Trade: at 15:30 ET (or 15:00 ET) if the day so far (previous 18:00 ET open -> entry) is up go long,
down go short; stop + target attached; forced exit at 15:59 ET (inside FTMO's 16:10 cutoff and the
trader's own 15:50 rule is shown as a variant). Conservative bar logic: stop first if stop and target
share a minute; stop fills 1 tick worse. Costs and sizing follow the trader's plan:
risk = $150-200, contracts = risk / (stop ticks x tick value), rounded down.
Results in ticks per contract and in dollars per trade for the sized position.
"""
import glob
import sys

import numpy as np
import pandas as pd

import registry

TICK = {"ES": 0.25, "NQ": 0.25}
TICK_USD_MICRO = {"ES": 1.25, "NQ": 0.5}   # MES / MNQ
COST_TICKS = 1.0 + 0.45 / 1.0              # 1 spread tick + commissions&fees expressed in ticks (set per market below)
SPLIT = pd.Timestamp("2018-01-01").date()


def load_minutes(root):
    files = sorted(glob.glob(f"data/ohlcv-1m_{root}_c_0_*.parquet"))
    if not files:
        return None
    df = pd.concat(pd.read_parquet(f)[["instrument_id", "open", "high", "low", "close"]] for f in files)
    df = df[~df.index.duplicated()].sort_index()
    df = df[(df.open > 0) & (df.close > 0)]
    et = df.index.tz_convert("America/New_York")
    df["mod"] = et.hour * 60 + et.minute
    df["day"] = (et + pd.Timedelta(hours=6)).date
    df["wd"] = [pd.Timestamp(d).weekday() for d in df["day"]]
    same = df["instrument_id"].eq(df["instrument_id"].shift()) & (df.index.to_series().diff() <= pd.Timedelta(hours=6))
    df["dp"] = np.where(same, df["close"] - df["close"].shift(), df["close"] - df["open"])
    return df[df.wd < 5]


def simulate(side, opens, highs, lows, closes, tick, stop_ticks, target_ticks, slip=1.0):
    entry = opens[0]
    for h, l in zip(highs, lows):
        if side > 0:
            hit_s, hit_t = l <= entry - stop_ticks * tick + 1e-9, h >= entry + target_ticks * tick - 1e-9
        else:
            hit_s, hit_t = h >= entry + stop_ticks * tick - 1e-9, l <= entry - target_ticks * tick + 1e-9
        if hit_s:
            return -stop_ticks - slip, "stop"
        if hit_t:
            return target_ticks, "target"
    return side * (closes[-1] - entry) / tick, "time"


def tstat(x):
    x = np.asarray(x, float)
    return x.mean() / x.std() * np.sqrt(len(x)) if len(x) > 20 and x.std() > 0 else np.nan


def main(root, entry_min=15 * 60 + 30, exit_min=15 * 60 + 59):
    df = load_minutes(root)
    if df is None:
        print(f"{root}: no minute data"); return
    tick = TICK[root]
    tv = TICK_USD_MICRO[root]
    cost_ticks = 1.0 + (0.20 * 2 + 0.5) / tv  # spread tick + (commission both sides + ~$0.50 fees) in ticks for one micro
    print(f"\n=== {root} micro: tick ${tv}, assumed round-trip cost {cost_ticks:.2f} ticks (${cost_ticks*tv:.2f}) per contract ===")
    days = {}
    for d, g in df.groupby("day"):
        pre = g[(g["mod"] < entry_min) & ((g["mod"] < 15 * 60 + 30) | True)]
        pre = g[(g["mod"] >= 18 * 60) | (g["mod"] < entry_min)]
        win = g[(g["mod"] >= entry_min) & (g["mod"] <= exit_min)]
        if len(win) < (exit_min - entry_min) * 0.8 or win["mod"].iloc[0] != entry_min:
            continue
        days[d] = (pre["dp"].sum(), win)
    print(f"  {len(days)} sessions with a full window; entry {entry_min//60}:{entry_min%60:02d} ET, flat {exit_min//60}:{exit_min%60:02d} ET")
    for stop, tgt in ((12, 24), (20, 40), (30, 60)):
        for per, lo, hi in (("2018-2022", 2018, 2022), ("2023-2026", 2023, 2026), ("2011-2017", 2011, 2017)):
            res, kinds = [], []
            for d, (sig, win) in days.items():
                if not (lo <= d.year <= hi) or sig == 0:
                    continue
                r, k = simulate(1 if sig > 0 else -1, win["open"].values, win["high"].values, win["low"].values, win["close"].values,
                                tick, stop, tgt)
                res.append(r - cost_ticks); kinds.append(k)
            if len(res) < 30:
                continue
            res = np.array(res)
            kc = pd.Series(kinds).value_counts(normalize=True)
            risk_usd = stop * tv
            n_ctr = int(200 // risk_usd) if risk_usd <= 200 else 0
            print(f"  stop {stop:2d}/target {tgt:2d} {per}: n={len(res):4d} net {res.mean():+5.2f} ticks (${res.mean()*tv:+5.2f}/micro; "
                  f"{n_ctr} micros at $200 risk = ${res.mean()*tv*n_ctr:+6.1f}/trade) t={tstat(res):+.2f} win {(res>0).mean():.0%} | "
                  f"target {kc.get('target',0):.0%} stop {kc.get('stop',0):.0%} time {kc.get('time',0):.0%}")
            if per == "2018-2022" or per == "2023-2026":
                registry.log("index_ftmo_sim", f"{root} {entry_min//60}:{entry_min%60:02d} stop{stop}/tgt{tgt} {per}", "ticks/trade net",
                             len(res), res.mean(), tstat(res))


if __name__ == "__main__":
    roots = sys.argv[1:] or ["ES", "NQ"]
    for r in roots:
        main(r)
