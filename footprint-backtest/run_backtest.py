"""Run RuleStrategy on the Nautilus catalog built by build_catalog.py.

Example: python3 run_backtest.py --imb-thr 0.3 --delta-thr 20 --hold-s 120
"""
import argparse
from pathlib import Path

import pandas as pd
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.config import (BacktestDataConfig, BacktestEngineConfig, BacktestRunConfig,
                                    BacktestVenueConfig, ImportableFeeModelConfig,
                                    ImportableStrategyConfig, LoggingConfig)
from nautilus_trader.model.data import OrderBookDepth10, TradeTick
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.persistence.catalog import ParquetDataCatalog

HERE = Path(__file__).resolve().parent
CATALOG = HERE / "data" / "catalog_cl"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--instrument", default=None, help="e.g. CLX6.GLBX (default: the one in the catalog)")
    p.add_argument("--qty", type=int, default=1)
    p.add_argument("--imb-thr", type=float, default=0.3)
    p.add_argument("--delta-thr", type=float, default=20.0)
    p.add_argument("--delta-window-s", type=int, default=30)
    p.add_argument("--hold-s", type=int, default=120)
    p.add_argument("--cooldown-s", type=int, default=30)
    p.add_argument("--fee-per-contract", default="2.50 USD", help="commission per contract per fill")
    p.add_argument("--start"), p.add_argument("--end")
    args = p.parse_args()

    catalog = ParquetDataCatalog(CATALOG)
    inst_id = args.instrument or str(catalog.instruments()[0].id)

    data = [BacktestDataConfig(catalog_path=str(CATALOG), data_cls=cls, instrument_id=InstrumentId.from_str(inst_id))
            for cls in (OrderBookDepth10, TradeTick)]
    venue = BacktestVenueConfig(
        name="GLBX", oms_type="NETTING", account_type="MARGIN", base_currency="USD",
        starting_balances=["100000 USD"], book_type="L2_MBP", default_leverage=1.0,
        fee_model=ImportableFeeModelConfig(
            fee_model_path="nautilus_trader.backtest.models:PerContractFeeModel",
            config_path="nautilus_trader.backtest.config:PerContractFeeModelConfig",
            config={"commission": args.fee_per_contract}),
    )
    strategy = ImportableStrategyConfig(
        strategy_path="rule_strategy:RuleStrategy", config_path="rule_strategy:RuleConfig",
        config=dict(instrument_id=inst_id, qty=args.qty, imb_thr=args.imb_thr,
                    delta_thr=args.delta_thr, delta_window_s=args.delta_window_s,
                    hold_s=args.hold_s, cooldown_s=args.cooldown_s))
    cfg = BacktestRunConfig(
        venues=[venue], data=data, start=args.start, end=args.end, chunk_size=200_000, dispose_on_completion=False,
        engine=BacktestEngineConfig(strategies=[strategy], logging=LoggingConfig(log_level="ERROR")))

    node = BacktestNode(configs=[cfg])
    result = node.run()[0]
    engine = node.get_engine(cfg.id)
    fills = engine.trader.generate_order_fills_report()
    positions = engine.trader.generate_positions_report()
    print({k: getattr(result, k) for k in ("iterations","total_events","total_orders","total_positions","elapsed_time")})
    print(f"fills: {len(fills)}  positions: {len(positions)}")
    if len(positions):
        pnl = positions["realized_pnl"].astype(str).str.split().str[0].astype(float)
        print(f"net PnL (after fees): ${pnl.sum():.2f}  win rate: {(pnl > 0).mean():.1%}  avg: ${pnl.mean():.2f}")
        positions.to_csv(HERE / "data" / "last_positions.csv")


if __name__ == "__main__":
    main()
