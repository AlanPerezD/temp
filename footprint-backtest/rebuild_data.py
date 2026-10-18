"""Re-create the market data this project used (it is git-ignored and was paid for per download).

    python rebuild_data.py --tier nq            # PLAN only: commands and approximate cost, nothing is bought
    python rebuild_data.py --tier nq --download # buy and download (needs DATABENTO_API_KEY or footprint-backtest/.env)
    python rebuild_data.py --free --download    # free files only: EIA inventories, CFTC COT, FRED OVX

Tiers (approximate Databento cost at the prices we paid in Oct 2026):
  nq    ~$13   Nasdaq/S&P hourly + NQ 1-minute 2018-2026 -> the FTMO Nasdaq close-momentum edge
  oil   ~$21   CL/HO/RB/BZ/NG/ES/ZN/GC daily + hourly bars, CL 1-minute 2018-2026 -> the oil/energy research
  mcl   ~$5    MCL tick trades (08-18 Buenos Aires), CL book sample, contract definitions -> footprint/spike work
Every command has its own --max-cost guard (see fetch_data.py / fetch_chunks.py); the script runs them
a few at a time because Databento's server is slow for long ranges.
"""
import argparse
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable
YEARS_1M = [("2018-01-01", "2021-01-01"), ("2021-01-01", "2024-01-01"), ("2024-01-01", "2026-10-16")]
END = "2026-10-16"


def chunks(symbol, schema, cap, start="2010-06-07", end=END):
    return [PY, "fetch_chunks.py", "--symbol", symbol, "--schema", schema, "--start", start, "--end", end, "--max-cost", str(cap)]


def daily(symbol):
    return [PY, "fetch_data.py", "--symbol", symbol, "--start", "2010-06-07", "--end", END, "--schemas", "ohlcv-1d",
            "--max-cost", "0.2", "--download"]


def minute_cmds(symbol, cap=4.2):
    return [chunks(symbol, "ohlcv-1m", cap, a, b) for a, b in YEARS_1M]


TIERS = {
    "nq": (13.2, [chunks("NQ.c.0", "ohlcv-1h", 1.3), chunks("ES.c.0", "ohlcv-1h", 1.3)] + minute_cmds("NQ.c.0")),
    "oil": (21.0,
            [daily(f"{r}.c.{k}") for r in ("CL", "BZ", "HO", "RB", "NG") for k in (0, 1, 2)]
            + [daily("ES.c.0"), daily("ZN.c.0"), daily("GC.c.0")]
            + [chunks(s, "ohlcv-1h", 1.3) for s in ("CL.c.0", "CL.c.1", "HO.c.0", "HO.c.1", "RB.c.0", "RB.c.1", "BZ.c.0", "NG.c.0", "YM.c.0", "GC.c.0")]
            + minute_cmds("CL.c.0")),
    "mcl": (5.0,
            [[PY, "fetch_data.py", "--symbol", "MCL.v.0", "--start", "2026-07-15", "--end", END, "--schemas", "trades",
              "--daily-window", w, "--max-cost", cap, "--download"] for w, cap in (("08:00-13:00", "2.6"), ("13:00-18:00", "1.6"))]
            + [[PY, "fetch_data.py", "--symbol", "CL.v.0", "--start", "2026-10-12", "--end", "2026-10-14",
                "--schemas", "trades", "mbp-10", "definition", "--max-cost", "1.1", "--download"]]
            + [[PY, "build_catalog.py"]]),
}
FREE = {
    "data/ext/WCESTUS1w.xls": "https://www.eia.gov/dnav/pet/hist_xls/WCESTUS1w.xls",
    "data/ext/W_EPC0_SAX_YCUOK_MBBLw.xls": "https://www.eia.gov/dnav/pet/hist_xls/W_EPC0_SAX_YCUOK_MBBLw.xls",
    "data/ext/WPULEUS3w.xls": "https://www.eia.gov/dnav/pet/hist_xls/WPULEUS3w.xls",
    "data/ext/cot_2006_2016.zip": "https://www.cftc.gov/files/dea/history/fut_disagg_txt_hist_2006_2016.zip",
    "data/ext/ovx/fred_ovx.csv": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=OVXCLS",
    **{f"data/ext/cot_{y}.zip": f"https://www.cftc.gov/files/dea/history/fut_disagg_txt_{y}.zip" for y in range(2017, 2027)},
}


def run_parallel(cmds, workers):
    running, failed = [], 0
    queue = list(cmds)
    while queue or running:
        while queue and len(running) < workers:
            cmd = queue.pop(0)
            print("  start:", " ".join(cmd[1:])[:140], flush=True)
            running.append((cmd, subprocess.Popen(cmd, cwd=HERE)))
        for item in list(running):
            if item[1].poll() is not None:
                running.remove(item)
                if item[1].returncode != 0:
                    failed += 1
                    print("  FAILED:", " ".join(item[0][1:])[:120], flush=True)
        if running:
            import time
            time.sleep(2)
    return failed


def download_free():
    for rel, url in FREE.items():
        dest = HERE / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.stat().st_size > 1000:
            continue
        print("  free:", rel, flush=True)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        dest.write_bytes(urllib.request.urlopen(req, timeout=120).read())


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--tier", choices=sorted(TIERS), action="append", help="data tier(s) to rebuild; repeatable")
    p.add_argument("--free", action="store_true", help="free files only (EIA, CFTC, FRED)")
    p.add_argument("--download", action="store_true", help="actually buy/download (default: print the plan)")
    p.add_argument("--workers", type=int, default=3)
    a = p.parse_args()
    if not a.tier and not a.free:
        p.error("pick --tier nq|oil|mcl and/or --free")
    if a.download and a.tier and not (os.environ.get("DATABENTO_API_KEY") or (HERE / ".env").exists()):
        sys.exit("Set DATABENTO_API_KEY or create footprint-backtest/.env first (see .env.example)")
    for t in a.tier or []:
        cost, cmds = TIERS[t]
        print(f"\nTier '{t}': {len(cmds)} commands, approx ${cost:.0f} of Databento credit")
        if not a.download:
            for c in cmds:
                print("   ", " ".join(c[1:]))
            continue
        # catalog build must wait for the downloads in its tier
        build = [c for c in cmds if c[1] == "build_catalog.py"]
        main_cmds = [c for c in cmds if c[1] != "build_catalog.py"]
        bad = run_parallel(main_cmds, a.workers)
        if build and not bad:
            bad += run_parallel(build, 1)
        print(f"Tier '{t}' finished with {bad} failed command(s)")
    if a.free:
        print("\nFree files (EIA, CFTC, FRED)")
        if a.download:
            download_free()
        else:
            for rel, url in FREE.items():
                print("   ", rel, "<-", url)
    if not a.download:
        print("\nPlan only. Add --download to run it.")


if __name__ == "__main__":
    main()
