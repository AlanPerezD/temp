import unittest

import pandas as pd

import spike_study as s


def trades():
    t0 = pd.Timestamp("2026-10-05 12:00:00", tz="UTC")
    rows = [(0, 100.0, 10), (60, 100.0, 10), (200, 101.0, 2000),  # spike bar 12:00 closes at 101 (+1%)
            (330, 101.0, 1), (700, 100.5, 1), (1000, 100.0, 1), (1240, 100.0, 1), (3900, 99.0, 1)]
    return pd.DataFrame({"ts_event": [t0 + pd.Timedelta(seconds=x) for x, *_ in rows],
                         "price": [r[1] for r in rows], "size": [r[2] for r in rows]})


class SpikeTests(unittest.TestCase):
    def test_detects_and_measures_reversal(self):
        tr = trades()
        b = s.spike_bars(tr, vol_min=1500, move_min=0.5)
        self.assertEqual(len(b), 1)
        f = s.forward(tr, b, cost_ticks=0)
        r = f.iloc[0]
        self.assertAlmostEqual(r.move_pct, 1.0)
        self.assertLess(r.ret15, 0)   # price came back down after the up-spike: fade wins
        self.assertLess(r.ret60, -1)  # 99.0 vs 101.0 entry


    def test_horizon_past_data_is_dropped(self):
        tr = trades().iloc[:5]  # data ends ~17 min after entry: 60m horizon is not covered
        f = s.forward(tr, s.spike_bars(tr, 1500, 0.5), cost_ticks=0)
        self.assertTrue(f.iloc[0].ret60 != f.iloc[0].ret60)  # NaN
        self.assertFalse(f.iloc[0].ret5 != f.iloc[0].ret5)

if __name__ == "__main__":
    unittest.main()
