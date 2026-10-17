"""Trading-session helpers (Buenos Aires): entries only before 13:00, trades may run to the 18:00 close."""
import glob
from datetime import time
from pathlib import Path

import pandas as pd

BA = "America/Argentina/Buenos_Aires"
ENTRY_END = time(13, 0)   # he stops watching the chart here
MARKET_CLOSE = time(18, 0)  # CME halt (17:00 ET); open orders can still fill until then


def load_trades(data_dir=None, pattern="trades_MCL_v_0_2026-07-15_2026-10-16_w*.parquet"):
    """All window files (08-13 and 13-18 BA) concatenated and sorted by event time."""
    d = Path(data_dir) if data_dir else Path(__file__).resolve().parent / "data"
    files = sorted(glob.glob(str(d / pattern)))
    return pd.concat(pd.read_parquet(f) for f in files).sort_values("ts_event").reset_index(drop=True)


def can_enter(ts):
    """True if a Timestamp is before 13:00 Buenos Aires (when he is at the chart)."""
    local = ts.tz_convert(BA)
    return (local.hour, local.minute) < (ENTRY_END.hour, ENTRY_END.minute)


def close_ns(ts_ns):
    """Nanosecond epoch of the 18:00 BA close on the same Buenos Aires day as ts_ns."""
    local = pd.Timestamp(ts_ns, tz="UTC").tz_convert(BA)
    return pd.Timestamp.combine(local.date(), MARKET_CLOSE).tz_localize(BA).value
