import unittest

import numpy as np
import pandas as pd

import macro_lab as ml


def panel():
    idx = [pd.Timestamp("2026-01-05").date() + pd.Timedelta(days=i) for i in range(4)]
    # day 3: the 2nd-month contract rolls (id1 changes to the former 3rd month)
    return pd.DataFrame({"id0": [1, 1, 2, 2], "c0": [70, 71, 72, 73], "id1": [2, 2, 3, 3], "c1": [71, 72, 73.5, 74],
                         "id2": [3, 3, 4, 4], "c2": [72, 73, 74, 75]}, index=idx)


class MacroTests(unittest.TestCase):
    def test_roll_uses_same_contract(self):
        r = ml.cont_returns(panel())
        self.assertAlmostEqual(r.iloc[1], 72 / 71 - 1)
        self.assertAlmostEqual(r.iloc[2], 73.5 / 73 - 1)   # new 2nd month vs its own price yesterday (was 3rd)
        self.assertAlmostEqual(r.iloc[3], 74 / 73.5 - 1)

    def test_evaluate_costs_and_sign(self):
        r = pd.Series([0.01, -0.01, 0.02], index=[pd.Timestamp("2026-01-0%d" % i).date() for i in (5, 6, 7)])
        pos = pd.Series([1.0, -1.0, -1.0], index=r.index)
        pnl, _ = ml.pnl_series(pos, r, cost=0.001)
        np.testing.assert_allclose(pnl.values, [0.01, 0.01 - 0.002, -0.02])  # flip long->short costs 2 units

    def test_holm_monotone(self):
        adj = ml.holm([0.01, 0.04, 0.03])
        self.assertTrue(all(a >= p for a, p in zip(adj, [0.01, 0.04, 0.03])))
        self.assertAlmostEqual(adj[0], 0.03)


if __name__ == "__main__":
    unittest.main()
