# -*- coding: utf-8 -*-
"""
深度方略-Stratapro · Dual Strategy Runtime
AtomCollide-智械工坊 · 2026

Dual strategy execution runtime supporting both vectorized (DataFrame-based)
and event-driven (callback-based) strategy patterns.

Inspired by QuantDinger's dual strategy architecture:
  - IndicatorStrategy: Vectorized DataFrame signals + chart overlays
  - ScriptStrategy: Event-driven on_bar/on_init with explicit order functions

Usage:
    from modules.strategy_runtime import IndicatorStrategy, ScriptStrategy, StrategyRunner

    # Vectorized approach
    class MyIndicator(IndicatorStrategy):
        def compute_signals(self, df):
            df["signal"] = (df["close"] > df["close"].rolling(20).mean()).astype(int)
            return df

    # Event-driven approach
    class MyScript(ScriptStrategy):
        def on_init(self, ctx):
            ctx.set_param("period", 20)

        def on_bar(self, ctx, bar):
            if bar.close > ctx.indicator("sma", 20):
                ctx.buy(bar.symbol, 100)

    # Run
    runner = StrategyRunner()
    result = runner.run(MyIndicator(), data=df)
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


@dataclass
class Order:
    """A trading order."""
    symbol: str
    side: str
    quantity: float
    order_type: str = "market"
    price: Optional[float] = None
    stop_price: Optional[float] = None
    timestamp: str = ""
    order_id: str = ""
    status: str = "pending"


@dataclass
class Bar:
    """A single OHLCV bar."""
    timestamp: Any
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class TradeRecord:
    """An executed trade."""
    order: Order
    fill_price: float
    fill_quantity: float
    timestamp: str
    commission: float = 0.0
    slippage: float = 0.0


@dataclass
class BacktestResult:
    """Backtest execution result."""
    strategy_name: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_pnl: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    equity_curve: List[float]
    trades: List[TradeRecord]
    execution_time_ms: float

    def summary(self) -> str:
        return (
            f"{self.strategy_name}: {self.total_trades} trades, "
            f"Win rate: {self.win_rate:.1%}, PnL: {self.total_pnl:.2f}, "
            f"Sharpe: {self.sharpe_ratio:.2f}, MaxDD: {self.max_drawdown:.2%}"
        )


# ============================================================
# Strategy Context (for event-driven strategies)
# ============================================================

class StrategyContext:
    """Execution context for event-driven strategies."""

    def __init__(self, initial_capital: float = 100000.0):
        self.params: Dict[str, Any] = {}
        self.portfolio: Dict[str, float] = {}  # symbol -> quantity
        self.cash = initial_capital
        self.initial_capital = initial_capital
        self.orders: List[Order] = []
        self.trades: List[TradeRecord] = []
        self.indicators_cache: Dict[str, Any] = {}
        self._bar_history: List[Bar] = []

    def set_param(self, key: str, value: Any) -> None:
        self.params[key] = value

    def get_param(self, key: str, default: Any = None) -> Any:
        return self.params.get(key, default)

    def indicator(self, name: str, period: int, **kwargs) -> float:
        """Compute or retrieve a cached indicator value."""
        cache_key = f"{name}_{period}_{hash(frozenset(kwargs.items()))}"
        if cache_key in self.indicators_cache:
            return self.indicators_cache[cache_key]

        if not self._bar_history:
            return 0.0

        closes = [b.close for b in self._bar_history[-period:]]
        if len(closes) < period:
            return closes[-1] if closes else 0.0

        if name == "sma":
            val = sum(closes) / len(closes)
        elif name == "ema":
            multiplier = 2 / (period + 1)
            val = closes[0]
            for price in closes[1:]:
                val = (price - val) * multiplier + val
        elif name == "highest":
            val = max(closes)
        elif name == "lowest":
            val = min(closes)
        elif name == "std":
            mean = sum(closes) / len(closes)
            val = (sum((x - mean) ** 2 for x in closes) / len(closes)) ** 0.5
        else:
            val = closes[-1]

        self.indicators_cache[cache_key] = val
        return val

    def buy(self, symbol: str, quantity: float, price: Optional[float] = None) -> Order:
        """Place a buy order."""
        order = Order(
            symbol=symbol, side=OrderSide.BUY.value,
            quantity=quantity, order_type=OrderType.MARKET.value if price is None else OrderType.LIMIT.value,
            price=price, timestamp=datetime.now().isoformat(),
            order_id=f"ord_{len(self.orders)+1:06d}",
        )
        self.orders.append(order)
        return order

    def sell(self, symbol: str, quantity: float, price: Optional[float] = None) -> Order:
        """Place a sell order."""
        order = Order(
            symbol=symbol, side=OrderSide.SELL.value,
            quantity=quantity, order_type=OrderType.MARKET.value if price is None else OrderType.LIMIT.value,
            price=price, timestamp=datetime.now().isoformat(),
            order_id=f"ord_{len(self.orders)+1:06d}",
        )
        self.orders.append(order)
        return order

    def position(self, symbol: str) -> float:
        """Get current position for a symbol."""
        return self.portfolio.get(symbol, 0.0)

    def equity(self, prices: Dict[str, float]) -> float:
        """Calculate total equity."""
        holdings = sum(
            qty * prices.get(sym, 0) for sym, qty in self.portfolio.items()
        )
        return self.cash + holdings


# ============================================================
# Strategy Base Classes
# ============================================================

class IndicatorStrategy(ABC):
    """
    Vectorized strategy: compute signals on a DataFrame at once.
    
    Subclass and implement compute_signals() to add signal columns.
    """

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def compute_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add signal columns to the DataFrame.
        
        Convention: add a 'signal' column (1=buy, -1=sell, 0=hold)
        and optional 'signal_strength' (0.0-1.0).
        """
        ...

    def overlay_config(self) -> Dict[str, Any]:
        """Return chart overlay configuration (optional)."""
        return {}


class ScriptStrategy(ABC):
    """
    Event-driven strategy: respond to bar-by-bar events.
    
    Subclass and implement on_init() and on_bar().
    """

    @property
    def name(self) -> str:
        return self.__class__.__name__

    def on_init(self, ctx: StrategyContext) -> None:
        """Called once before backtest starts. Set parameters here."""
        pass

    def on_bar(self, ctx: StrategyContext, bar: Bar) -> None:
        """Called for each new bar. Place orders via ctx.buy()/ctx.sell()."""
        pass

    def on_order_filled(self, ctx: StrategyContext, trade: TradeRecord) -> None:
        """Called when an order is filled. Optional."""
        pass

    def on_finish(self, ctx: StrategyContext) -> None:
        """Called when backtest ends. Optional."""
        pass


# ============================================================
# Strategy Runner
# ============================================================

class StrategyRunner:
    """Execute strategies and produce backtest results."""

    def __init__(self, initial_capital: float = 100000.0, commission_rate: float = 0.001):
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate

    def run_indicator(
        self, strategy: IndicatorStrategy, data: pd.DataFrame
    ) -> BacktestResult:
        """Run a vectorized indicator strategy."""
        start_time = time.time()
        df = strategy.compute_signals(data.copy())

        if "signal" not in df.columns:
            df["signal"] = 0

        # Simple vectorized backtest
        equity = self.initial_capital
        position = 0.0
        equity_curve = [equity]
        trades: List[TradeRecord] = []
        wins = 0
        losses = 0

        for i, row in df.iterrows():
            price = row.get("close", 0)
            signal = row.get("signal", 0)

            if signal > 0 and position <= 0:
                # Buy
                qty = int(equity * 0.95 / price) if price > 0 else 0
                if qty > 0:
                    cost = qty * price * (1 + self.commission_rate)
                    equity -= cost
                    position += qty
                    trades.append(TradeRecord(
                        order=Order(symbol="asset", side="buy", quantity=qty, timestamp=str(i)),
                        fill_price=price, fill_quantity=qty, timestamp=str(i),
                        commission=qty * price * self.commission_rate,
                    ))

            elif signal < 0 and position > 0:
                # Sell
                revenue = position * price * (1 - self.commission_rate)
                pnl = revenue - (trades[-1].fill_price * position if trades else 0)
                if pnl > 0:
                    wins += 1
                else:
                    losses += 1
                equity += revenue
                trades.append(TradeRecord(
                    order=Order(symbol="asset", side="sell", quantity=position, timestamp=str(i)),
                    fill_price=price, fill_quantity=position, timestamp=str(i),
                    commission=position * price * self.commission_rate,
                ))
                position = 0.0

            equity_curve.append(equity + position * price)

        total_trades = len(trades)
        total_pnl = equity_curve[-1] - self.initial_capital
        max_dd = self._max_drawdown(equity_curve)
        sharpe = self._sharpe_ratio(equity_curve)

        return BacktestResult(
            strategy_name=strategy.name,
            total_trades=total_trades,
            winning_trades=wins,
            losing_trades=losses,
            total_pnl=total_pnl,
            max_drawdown=max_dd,
            sharpe_ratio=sharpe,
            win_rate=wins / max(1, wins + losses),
            equity_curve=equity_curve,
            trades=trades,
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    def run_script(
        self, strategy: ScriptStrategy, bars: List[Bar]
    ) -> BacktestResult:
        """Run an event-driven script strategy."""
        start_time = time.time()
        ctx = StrategyContext(initial_capital=self.initial_capital)
        strategy.on_init(ctx)

        equity_curve = [self.initial_capital]
        wins = 0
        losses = 0

        for bar in bars:
            ctx._bar_history.append(bar)
            ctx.indicators_cache.clear()
            strategy.on_bar(ctx, bar)

            # Process pending orders
            for order in ctx.orders:
                if order.status == "pending":
                    fill_price = bar.close
                    if order.side == "buy":
                        cost = order.quantity * fill_price * (1 + self.commission_rate)
                        if ctx.cash >= cost:
                            ctx.cash -= cost
                            ctx.portfolio[order.symbol] = ctx.portfolio.get(order.symbol, 0) + order.quantity
                            order.status = "filled"
                            trade = TradeRecord(
                                order=order, fill_price=fill_price,
                                fill_quantity=order.quantity, timestamp=bar.timestamp,
                                commission=order.quantity * fill_price * self.commission_rate,
                            )
                            ctx.trades.append(trade)
                            strategy.on_order_filled(ctx, trade)
                    elif order.side == "sell":
                        held = ctx.portfolio.get(order.symbol, 0)
                        if held >= order.quantity:
                            revenue = order.quantity * fill_price * (1 - self.commission_rate)
                            ctx.cash += revenue
                            ctx.portfolio[order.symbol] = held - order.quantity
                            order.status = "filled"
                            trade = TradeRecord(
                                order=order, fill_price=fill_price,
                                fill_quantity=order.quantity, timestamp=bar.timestamp,
                                commission=order.quantity * fill_price * self.commission_rate,
                            )
                            ctx.trades.append(trade)
                            strategy.on_order_filled(ctx, trade)

            # Track equity
            prices = {bar.symbol: bar.close}
            equity_curve.append(ctx.equity(prices))

        strategy.on_finish(ctx)

        # Count wins/losses
        buy_prices: Dict[str, float] = {}
        for t in ctx.trades:
            if t.order.side == "buy":
                buy_prices[t.order.order_id] = t.fill_price
            elif t.order.side == "sell":
                buy_p = buy_prices.get(t.order.order_id, t.fill_price)
                if t.fill_price > buy_p:
                    wins += 1
                else:
                    losses += 1

        total_trades = len(ctx.trades)
        total_pnl = equity_curve[-1] - self.initial_capital
        max_dd = self._max_drawdown(equity_curve)
        sharpe = self._sharpe_ratio(equity_curve)

        return BacktestResult(
            strategy_name=strategy.name,
            total_trades=total_trades,
            winning_trades=wins,
            losing_trades=losses,
            total_pnl=total_pnl,
            max_drawdown=max_dd,
            sharpe_ratio=sharpe,
            win_rate=wins / max(1, wins + losses),
            equity_curve=equity_curve,
            trades=ctx.trades,
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    @staticmethod
    def _max_drawdown(equity_curve: List[float]) -> float:
        if len(equity_curve) < 2:
            return 0.0
        peak = equity_curve[0]
        max_dd = 0.0
        for val in equity_curve:
            if val > peak:
                peak = val
            dd = (peak - val) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @staticmethod
    def _sharpe_ratio(equity_curve: List[float], risk_free: float = 0.0) -> float:
        if len(equity_curve) < 10:
            return 0.0
        returns = [
            (equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1]
            for i in range(1, len(equity_curve))
            if equity_curve[i-1] != 0
        ]
        if not returns:
            return 0.0
        mean_ret = sum(returns) / len(returns)
        std_ret = (sum((r - mean_ret) ** 2 for r in returns) / len(returns)) ** 0.5
        if std_ret == 0:
            return 0.0
        return (mean_ret - risk_free) / std_ret * (252 ** 0.5)
