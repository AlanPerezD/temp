import tempfile
import unittest

import pandas as pd

import features


def trades():
    t0 = pd.Timestamp("2026-10-05 12:00:00", tz="UTC")
    rows = [  # (sec, price, size, side)
        (1, 70.00, 2, "A"), (2, 70.01, 10, "B"), (3, 70.01, 1, "A"),
        (4, 70.02, 5, "B"), (5, 70.00, 4, "A"),
        (61, 70.05, 3, "B"), (62, 70.05, 1, "N"),  # N = no aggressor, ignored
    ]
    return pd.DataFrame({
        "ts_event": [t0 + pd.Timedelta(seconds=s) for s, *_ in rows],
        "price": [r[1] for r in rows], "size": [r[2] for r in rows], "side": [r[3] for r in rows],
    })


class FootprintTests(unittest.TestCase):
    def setUp(self):
        self.t = trades()
        self.lv = features.footprint_levels(self.t)
        self.bars = features.bar_summary(self.t, self.lv, ratio=3.0)

    def test_levels_split_by_aggressor(self):
        b = self.lv[self.lv["bar"] == self.lv["bar"].min()].set_index("price")
        self.assertEqual((b.loc[70.00, "bid_vol"], b.loc[70.00, "ask_vol"]), (6, 0))
        self.assertEqual((b.loc[70.01, "bid_vol"], b.loc[70.01, "ask_vol"]), (1, 10))
        self.assertEqual((b.loc[70.02, "bid_vol"], b.loc[70.02, "ask_vol"]), (0, 5))

    def test_summary(self):
        first = self.bars.iloc[0]
        self.assertEqual(len(self.bars), 2)
        self.assertEqual((first["open"], first["high"], first["low"], first["close"]),
                         (70.00, 70.02, 70.00, 70.00))
        self.assertEqual(first["volume"], 22)
        self.assertEqual(first["delta"], 15 - 7)
        self.assertEqual(first["poc"], 70.01)  # 11 contracts, vs 6 and 5
        self.assertEqual(self.bars.iloc[1]["delta"], 3)  # side N ignored

    def test_diagonal_imbalances(self):
        first = self.bars.iloc[0]
        # buy: ask@70.01=10 vs bid@70.00=6 -> no; ask@70.02=5 vs bid@70.01=1 -> yes
        self.assertEqual(first["buy_imbalances"], 1)
        # sell: bid@70.00=6 vs ask@70.01=10 -> no; bid@70.01=1 vs ask@70.02=5 -> no
        self.assertEqual(first["sell_imbalances"], 0)

    def test_book_imbalance(self):
        cols = {f"bid_sz_{i:02d}": [10, 0] for i in range(10)}
        cols.update({f"ask_sz_{i:02d}": [10, 0] for i in range(10)})
        cols["bid_sz_00"] = [30, 0]
        imb = features.book_imbalance(pd.DataFrame(cols))
        self.assertAlmostEqual(imb[0], (120 - 100) / 220)
        self.assertTrue(pd.isna(imb[1]))

    def test_book_imbalance_unsigned_sizes(self):
        cols = {f"bid_sz_{i:02d}": pd.Series([1], dtype="uint32") for i in range(10)}
        cols.update({f"ask_sz_{i:02d}": pd.Series([5], dtype="uint32") for i in range(10)})
        imb = features.book_imbalance(pd.DataFrame(cols))
        self.assertAlmostEqual(imb[0], -40 / 60)

    def test_jsonl_roundtrip(self):
        import json
        with tempfile.NamedTemporaryFile("r", suffix=".jsonl") as f:
            features.to_jsonl(self.bars, self.lv, f.name)
            rows = [json.loads(l) for l in f]
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["ladder"][0], [70.0, 6, 0])


if __name__ == "__main__":
    unittest.main()
