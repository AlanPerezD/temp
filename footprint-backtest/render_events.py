"""Draw footprint charts of volume-spike moments so a trader can annotate what they would do.

Each chart: 1-minute footprint columns from 5 min before the spike candle to 5 min after it.
Cell text = sell volume (hit the bid) x buy volume (lifted the ask), prices grouped by `step` ticks.
Green = buyers dominate (3x), red = sellers dominate (3x). Times are Buenos Aires.
"""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import spike_study

BA = "America/Argentina/Buenos_Aires"


def draw(trades, bar_start, out, step=5, tick=0.01, pre=5, post=5, bar_min=5, title=""):
    t0 = bar_start - pd.Timedelta(minutes=pre)
    t1 = bar_start + pd.Timedelta(minutes=bar_min + post)
    w = trades[(trades.ts_event >= t0) & (trades.ts_event < t1) & trades.side.isin(["A", "B"])].copy()
    w["col"] = ((w.ts_event - t0).dt.total_seconds() // 60).astype(int)
    w["row"] = (w.price / (tick * step)).round().astype(int)
    w["buy"] = w["size"].where(w.side == "B", 0)
    w["sell"] = w["size"].where(w.side == "A", 0)
    g = w.groupby(["col", "row"])[["buy", "sell"]].sum().reset_index()
    ncol = pre + bar_min + post
    rmin, rmax = g.row.min(), g.row.max()
    fig, ax = plt.subplots(figsize=(13, max(6, 0.42 * (rmax - rmin + 3))), dpi=100)
    for r in g.itertuples():
        tot = r.buy + r.sell
        col = "#b9d9b0" if r.buy >= 3 * max(r.sell, 1) else "#e5aaaa" if r.sell >= 3 * max(r.buy, 1) else "#e8e8e8"
        ax.add_patch(plt.Rectangle((r.col, r.row - 0.5), 1, 1, color=col, ec="white"))
        ax.text(r.col + 0.5, r.row, f"{int(r.sell)}x{int(r.buy)}", ha="center", va="center",
                fontsize=7 if tot >= 5 else 6, color="black" if tot >= 5 else "#777")
    ax.axvline(pre, color="k", ls="--", lw=1)
    ax.axvline(pre + bar_min, color="k", ls="--", lw=1)
    ax.set_xlim(0, ncol); ax.set_ylim(rmin - 1.5, rmax + 1.5)
    labels = [(t0 + pd.Timedelta(minutes=i)).tz_convert(BA).strftime("%H:%M") for i in range(ncol)]
    ax.set_xticks(np.arange(ncol) + 0.5); ax.set_xticklabels(labels, rotation=90, fontsize=8)
    ax.set_yticks(range(rmin, rmax + 1)); ax.set_yticklabels([f"{r * tick * step:.2f}" for r in range(rmin, rmax + 1)], fontsize=8)
    ax.set_title(title + "\nsell x buy per price band; dashed lines = the 5-min spike candle; times Buenos Aires", fontsize=10)
    fig.tight_layout(); fig.savefig(out); plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("trades_parquet"); ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--vol", type=int, default=2500); ap.add_argument("--move", type=float, default=0.3)
    ap.add_argument("--post", type=int, default=5, help="minutes shown after the candle (0 hides the outcome)")
    ap.add_argument("--random", type=int, default=None, help="seed: pick events at random instead of evenly")
    ap.add_argument("--prefix", default="example")
    ap.add_argument("--exclude", nargs="*", default=[], help="candle starts (UTC) to skip")
    a = ap.parse_args()
    tr = pd.read_parquet(a.trades_parquet).sort_values("ts_event")
    bars = spike_study.cluster_first(spike_study.spike_bars(tr, a.vol, a.move))
    bars = bars[~bars.index.strftime("%Y-%m-%d %H:%M").isin(a.exclude)]
    if a.random is None:
        pick = bars.iloc[np.linspace(0, len(bars) - 1, a.n).astype(int)]
    else:
        pick = bars.iloc[sorted(np.random.default_rng(a.random).choice(len(bars), a.n, replace=False))]
    out_dir = Path(__file__).parent / "data" / "examples"; out_dir.mkdir(exist_ok=True)
    for k, (ts, r) in enumerate(pick.iterrows(), 1):
        d = "UP" if r.move_pct > 0 else "DOWN"
        title = (f"#{k}  {ts.tz_convert(BA):%a %d %b %H:%M} BA  |  5-min volume {int(r.vol)}  |  "
                 f"candle {r.move_pct:+.2f}% ({d})  |  close {r.close:.2f}")
        draw(tr, ts, out_dir / f"{a.prefix}_{k}.png", post=a.post, title=title)
        print(title)
    pick.assign(chart=range(1, len(pick) + 1)).to_csv(out_dir / f"{a.prefix}_events.csv")
