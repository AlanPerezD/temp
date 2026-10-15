"""Rule-driven order-flow strategy: the AI edits the thresholds (or the `signal` method).

Signal (checked at most once per `eval_ms`):
  long  when book imbalance >  imb_thr and rolling trade delta >  delta_thr
  short when book imbalance < -imb_thr and rolling trade delta < -delta_thr
Exit after `hold_s` seconds, with a market order. One position at a time.
"""
from collections import deque

from nautilus_trader.config import StrategyConfig
from nautilus_trader.model.data import OrderBookDepth10, TradeTick
from nautilus_trader.model.enums import AggressorSide, OrderSide
from nautilus_trader.model.identifiers import InstrumentId
from nautilus_trader.model.objects import Quantity
from nautilus_trader.trading.strategy import Strategy


class RuleConfig(StrategyConfig, frozen=True):
    instrument_id: InstrumentId
    qty: int = 1
    imb_thr: float = 0.3         # top-10 book imbalance in [-1, 1]
    delta_thr: float = 20.0      # contracts, over delta_window_s
    delta_window_s: int = 30
    hold_s: int = 120
    cooldown_s: int = 30
    eval_ms: int = 500


class RuleStrategy(Strategy):
    def __init__(self, config: RuleConfig):
        super().__init__(config)
        self.instrument = None
        self.flow = deque()       # (ts_ns, signed size)
        self.delta = 0.0
        self.last_eval = 0
        self.entry_ts = None
        self.no_entry_before = 0

    def on_start(self):
        self.instrument = self.cache.instrument(self.config.instrument_id)
        self.subscribe_trade_ticks(self.config.instrument_id)
        self.subscribe_order_book_depth(self.config.instrument_id, depth=10)

    def on_trade_tick(self, tick: TradeTick):
        if tick.aggressor_side == AggressorSide.BUYER:
            signed = float(tick.size)
        elif tick.aggressor_side == AggressorSide.SELLER:
            signed = -float(tick.size)
        else:
            return
        self.flow.append((tick.ts_event, signed))
        self.delta += signed
        self._trim(tick.ts_event)

    def _trim(self, now):
        cutoff = now - self.config.delta_window_s * 1_000_000_000
        while self.flow and self.flow[0][0] < cutoff:
            self.delta -= self.flow.popleft()[1]

    def on_order_book_depth(self, depth: OrderBookDepth10):
        now = depth.ts_event
        if now - self.last_eval < self.config.eval_ms * 1_000_000:
            return
        self.last_eval = now
        self._trim(now)
        if self.portfolio.is_flat(self.config.instrument_id):
            if now >= self.no_entry_before:
                self._maybe_enter(depth, now)
        elif self.entry_ts is not None and now - self.entry_ts >= self.config.hold_s * 1_000_000_000:
            self.close_all_positions(self.config.instrument_id)
            self.entry_ts = None
            self.no_entry_before = now + self.config.cooldown_s * 1_000_000_000

    def signal(self, imbalance: float, delta: float):
        """Return OrderSide.BUY / SELL / None. Override or edit to try new rules."""
        c = self.config
        if imbalance > c.imb_thr and delta > c.delta_thr:
            return OrderSide.BUY
        if imbalance < -c.imb_thr and delta < -c.delta_thr:
            return OrderSide.SELL
        return None

    def _maybe_enter(self, depth, now):
        bid = sum(float(l.size) for l in depth.bids)
        ask = sum(float(l.size) for l in depth.asks)
        if bid + ask == 0:
            return
        side = self.signal((bid - ask) / (bid + ask), self.delta)
        if side is None:
            return
        order = self.order_factory.market(
            instrument_id=self.config.instrument_id,
            order_side=side,
            quantity=Quantity.from_int(self.config.qty),
        )
        self.submit_order(order)
        self.entry_ts = now

    def on_stop(self):
        self.close_all_positions(self.config.instrument_id)
