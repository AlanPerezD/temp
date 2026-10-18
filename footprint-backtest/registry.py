"""Append-only log of every hypothesis tested in the edge search, so multiple testing is counted.

Each row: when, program, test name, n, mean (in the test's unit), t (full sample), t_dev, t_test.
Prior programs (before this registry) are counted in PRIOR_TESTS for the correction.
"""
import csv
import datetime as dt
from math import erf, sqrt
from pathlib import Path

LOG = Path(__file__).resolve().parent / "strategies" / "registry.csv"
PRIOR_TESTS = 250  # strategy_lab 54 + edge_lab 150 + research_lab 18 + macro_lab ~25 + misc
FIELDS = ["logged", "program", "name", "unit", "n", "mean", "t", "t_dev", "t_test", "note"]


def log(program, name, unit, n, mean, t, t_dev=float("nan"), t_test=float("nan"), note=""):
    new = not LOG.exists()
    with LOG.open("a", newline="") as f:
        w = csv.DictWriter(f, FIELDS)
        if new:
            w.writeheader()
        w.writerow(dict(logged=dt.datetime.now().isoformat(timespec="seconds"), program=program, name=name, unit=unit,
                        n=n, mean=round(mean, 4), t=round(t, 3), t_dev=round(t_dev, 3), t_test=round(t_test, 3), note=note))


def p_two_sided(t):
    return 2 * (1 - 0.5 * (1 + erf(abs(t) / sqrt(2))))


def bonferroni_t(alpha=0.05):
    """|t| needed for family-wise significance across everything tried so far."""
    import csv as _c
    n = PRIOR_TESTS + (sum(1 for _ in _c.reader(LOG.open())) - 1 if LOG.exists() else 0)
    lo, hi = 0.0, 10.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if p_two_sided(mid) * n > alpha else (lo, mid)
    return hi, n
