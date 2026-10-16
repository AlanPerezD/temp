"""Event study for the exhaustion-zone setup (discretionary read, made explicit).

1. High-volume bar: bar volume >= `vol_q` quantile of the previous `lookback` bars.
2. Exhaustion at the bar's high: the top `top_n` price levels hold >= `share` of the bar's volume,
   are ask-dominant (buyers hit hard there), and the bar closes >= `reject` ticks below the high.
   Mirror at the low. Zone = those top (bottom) levels.
3. After the bar closes, follow the next `horizon_s` seconds of trades:
   touch   = price re-enters the zone            (the "bounce back to the zone")
   break   = price trades `break_ticks` beyond the zone extreme (after a touch)
   explode = a further `explode_ticks` within `explode_s` after the break
4. Outcomes in ticks (max favorable / adverse excursion over `horizon_s`):
   fade  = enter against the zone at the touch;  break = enter with the break at the break.
"""
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

import features


@dataclass(frozen=True)
class Params:
    freq: str = "1min"
    tick: float = 0.01
    lookback: int = 60
    vol_q: float = 0.85
    top_n: int = 3
    share: float = 0.20
    reject: int = 3
    break_ticks: int = 2
    explode_ticks: int = 10
    explode_s: int = 60
    horizon_s: int = 300


def find_zones(trades, p=Params()):
    levels = features.footprint_levels(trades, p.freq, p.tick)
    bars = features.bar_summary(trades, levels, p.freq).set_index("bar")
    thr = bars["volume"].rolling(p.lookback, min_periods=p.lookback // 2).quantile(p.vol_q).shift(1)
    zones = []
    for bar, row in bars[bars["volume"] >= thr].iterrows():
        lv = levels[levels["bar"] == bar].sort_values("level")
        top, bot = lv.tail(p.top_n), lv.head(p.top_n)
        vol = row["volume"]
        if (top[["bid_vol", "ask_vol"]].values.sum() >= p.share * vol
                and top["ask_vol"].sum() >= top["bid_vol"].sum()
                and row["high"] - row["close"] >= p.reject * p.tick - 1e-9):
            zones.append(dict(bar=bar, side="high", lo=top["price"].min(), hi=top["price"].max()))
        if (bot[["bid_vol", "ask_vol"]].values.sum() >= p.share * vol
                and bot["bid_vol"].sum() >= bot["ask_vol"].sum()
                and row["close"] - row["low"] >= p.reject * p.tick - 1e-9):
            zones.append(dict(bar=bar, side="low", lo=bot["price"].min(), hi=bot["price"].max()))
    return pd.DataFrame(zones)


def _excursion(ts, px, i0, entry, direction, p):
    """(MFE, MAE) in ticks over horizon_s from index i0; direction +1 long, -1 short."""
    end = np.searchsorted(ts, ts[i0] + p.horizon_s * 10**9, side="right")
    path = (px[i0:end] - entry) * direction / p.tick
    return path.max(), -path.min()


def study(trades, zones, p=Params()):
    t = trades.sort_values("ts_event")
    ts = t["ts_event"].dt.as_unit("ns").astype("int64").to_numpy()  # pandas 3 may infer us
    px = t["price"].to_numpy()
    out = []
    for z in zones.itertuples():
        start = np.searchsorted(ts, (z.bar + pd.Timedelta(p.freq)).value)
        end = np.searchsorted(ts, ts[min(start, len(ts) - 1)] + p.horizon_s * 10**9, side="right")
        if start >= len(ts) or end - start < 2:
            continue
        seg = px[start:end]
        # high zone: price came down, "touch" is a rally back up into it; break is above zone high
        sgn = 1 if z.side == "high" else -1
        touch_hit = seg >= z.lo - 1e-9 if sgn == 1 else seg <= z.hi + 1e-9
        r = dict(bar=z.bar, side=z.side, touched=False, broke=False, exploded=False)
        if touch_hit.any():
            it = start + int(touch_hit.argmax())
            r["touched"] = True
            r["fade_mfe"], r["fade_mae"] = _excursion(ts, px, it, px[it], -sgn, p)
            level = (z.hi + p.break_ticks * p.tick) if sgn == 1 else (z.lo - p.break_ticks * p.tick)
            rest = px[it:end]
            brk = rest >= level - 1e-9 if sgn == 1 else rest <= level + 1e-9
            if brk.any():
                ib = it + int(brk.argmax())
                r["broke"] = True
                r["break_mfe"], r["break_mae"] = _excursion(ts, px, ib, px[ib], sgn, p)
                e_end = np.searchsorted(ts, ts[ib] + p.explode_s * 10**9, side="right")
                far = (px[ib:e_end] - px[ib]) * sgn / p.tick
                r["exploded"] = bool(far.max() >= p.explode_ticks)
        out.append(r)
    return pd.DataFrame(out)


def summarize(res):
    if res.empty:
        return "no setups"
    n = len(res)
    lines = [f"setups {n} | touched {res.touched.sum()} | broke {res.broke.sum()} | exploded {res.exploded.sum()}"]
    for name, cols in (("fade (enter at touch)", ("fade_mfe", "fade_mae")),
                       ("break (enter at break)", ("break_mfe", "break_mae"))):
        d = res.dropna(subset=list(cols))
        if len(d):
            lines.append(f"{name}: n={len(d)} median MFE {d[cols[0]].median():.1f}t / MAE {d[cols[1]].median():.1f}t "
                         f"| MFE>MAE in {(d[cols[0]] > d[cols[1]]).mean():.0%}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    tr = pd.read_parquet(sys.argv[1])
    p = Params()
    z = find_zones(tr, p)
    print(z.side.value_counts().to_dict() if len(z) else "no zones")
    print(summarize(study(tr, z, p)))
