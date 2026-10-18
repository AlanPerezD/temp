import unittest

import numpy as np
import pandas as pd

import edge_lab as e
import strategy_lab as lab


def sample(n=3000):
    t0 = pd.Timestamp("2026-10-05 11:00:00", tz="UTC")  # 08:00 BA
    rng = np.random.default_rng(0)
    px = 90 + np.cumsum(rng.normal(0, 0.01, n))
    return pd.DataFrame({"ts_event": [t0 + pd.Timedelta(seconds=5 * i) for i in range(n)],
                         "price": px.round(2), "size": rng.integers(1, 20, n),
                         "side": rng.choice(["A", "B"], n)})


class EdgeTests(unittest.TestCase):
    def test_minute_bars_delta_and_grid(self):
        b = e.minute_bars(sample())
        self.assertTrue((b["delta"] == b["buy"] - b["sell"]).all())
        self.assertTrue((b.index.to_series().diff().dropna() == pd.Timedelta("1min")).all())

    def test_gross_respects_side_and_coverage(self):
        tr = sample(); m = lab.Mkt(tr)
        g_long, _ = e.gross(m, [(100, 1)], 15); g_short, _ = e.gross(m, [(100, -1)], 15)
        self.assertAlmostEqual(g_long[0], -g_short[0])
        far, _ = e.gross(m, [(len(m.ts) - 2, 1)], 60)  # horizon beyond data
        self.assertTrue(np.isnan(far[0]))

    def test_combos_build(self):
        tr = sample(); m = lab.Mkt(tr); b = e.minute_bars(tr)
        c = e.build_combos(m, b)
        self.assertGreater(len(c), 40)


if __name__ == "__main__":
    unittest.main()
