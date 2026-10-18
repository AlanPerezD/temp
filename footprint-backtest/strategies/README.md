# Saved strategies and research artifacts

| File | What |
|---|---|
| `range_fade.md` | The range-fade rule, parameters, results and caveats (saved for later) |
| `lab_results.csv` | Every parameter combination tried by `strategy_lab.py` (dev Jul-Aug vs test Sep-Oct) |
| `labels.csv` | The trader's take/skip decisions on 21 real spike charts, with entries/targets/reasons |

Rerun: `python3 strategy_lab.py` (needs the data in `../data/`, see top-level README).

| `edge_search_results.txt` | Output of `edge_lab.py`: 52 order-flow / momentum / breakout / VWAP / large-trade variants x 3 horizons, dev/test split and a randomised "luck check" (result: no edge found on 67 days) |
| `research_results.txt` | Output of `research_lab.py`: 18 literature-motivated daily variants (intraday momentum, EIA reaction, settlement, pit-open ORB) with CIs, dev/test, permutation p and Holm adjustment (result: nothing significant on 67 days) |
