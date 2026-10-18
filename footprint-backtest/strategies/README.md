# Saved strategies and research artifacts

| File | What |
|---|---|
| `range_fade.md` | The range-fade rule, parameters, results and caveats (saved for later) |
| `lab_results.csv` | Every parameter combination tried by `strategy_lab.py` (dev Jul-Aug vs test Sep-Oct) |
| `labels.csv` | The trader's take/skip decisions on 21 real spike charts, with entries/targets/reasons |

Rerun: `python3 strategy_lab.py` (needs the data in `../data/`, see top-level README).

| `edge_search_results.txt` | Output of `edge_lab.py`: 52 order-flow / momentum / breakout / VWAP / large-trade variants x 3 horizons, dev/test split and a randomised "luck check" (result: no edge found on 67 days) |
| `research_results.txt` | Output of `research_lab.py`: 18 literature-motivated daily variants (intraday momentum, EIA reaction, settlement, pit-open ORB) with CIs, dev/test, permutation p and Holm adjustment (result: nothing significant on 67 days) |
| `oil_edges.md` | Research summary + 16-year tests of carry, trend, seasonality, index roll, EIA, COT, sessions |
| `macro_results.txt` | Full output of `macro_lab.py` |
| `EDGE_late_session_momentum.md` | **The edge found**: rule, evidence, economics, risks, timetable in Buenos Aires time |
| `registry.csv` | Every hypothesis tested in the edge search (for multiple-testing correction) |
