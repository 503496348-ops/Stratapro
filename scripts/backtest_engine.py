"""
Stratapro Backtest Engine
=========================
Inspired by QuantDinger (8.1K⭐) declarative strategy pattern.

Key patterns adopted:
- Declarative strategy with @param and @strategy annotations
- Four-way signal model: open_long, open_short, close_long, close_short
- Edge detection: trigger-on-true-only-once
- Engine-managed risk: stopLoss/takeProfit by engine, not strategy
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable
import datetime


@dataclass
class StrategyParams:
    """Declarative strategy parameters (parsed from @param annotations)."""
    name: str = ""
    description: str = ""
    params: dict = field(default_factory=dict)
    strategy_config: dict = field(default_factory=dict)


@dataclass
class TradeSignal:
    """Four-way trade signal."""
    timestamp: str
    action: str  # open_long, open_short, close_long, close_short
    price: float
    reason: str = ""
    confidence: float = 0.0


@dataclass
class BacktestResult:
    """Backtest execution result."""
    strategy_name: str
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return: float  # percentage
    max_drawdown: float  # percentage
    win_rate: float  # percentage
    total_trades: int
    winning_trades: int
    losing_trades: int
    sharpe_ratio: float
    trades: list[TradeSignal] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"策略: {self.strategy_name}\n"
            f"回测区间: {self.start_date} → {self.end_date}\n"
            f"初始资金: ¥{self.initial_capital:,.0f}\n"
            f"最终资金: ¥{self.final_capital:,.0f}\n"
            f"总收益: {self.total_return:+.2f}%\n"
            f"最大回撤: {self.max_drawdown:.2f}%\n"
            f"胜率: {self.win_rate:.1f}%\n"
            f"总交易: {self.total_trades} (赢{self.winning_trades}/亏{self.losing_trades})\n"
            f"夏普比率: {self.sharpe_ratio:.2f}"
        )


def edge(series) -> list[bool]:
    """Edge detection: True only on the first occurrence of a True value.
    
    Same as QuantDinger's edge() function:
    s = s.fillna(False).astype(bool)
    return s & ~s.shift(1).fillna(False)
    """
    result = []
    prev = False
    for val in series:
        current = bool(val)
        result.append(current and not prev)
        prev = current
    return result


def backtest(
    prices: list[float],
    signals: list[dict],
    initial_capital: float = 100000.0,
    stop_loss_pct: float = 0.02,
    take_profit_pct: float = 0.05,
    position_size_pct: float = 0.25,
    strategy_name: str = "unnamed",
    start_date: str = "",
    end_date: str = "",
) -> BacktestResult:
    """Execute a backtest with engine-managed risk control.
    
    Args:
        prices: Close prices series
        signals: List of {"index": int, "action": str, "reason": str}
        initial_capital: Starting capital in CNY
        stop_loss_pct: Engine-managed stop loss (e.g., 0.02 = 2%)
        take_profit_pct: Engine-managed take profit (e.g., 0.05 = 5%)
        position_size_pct: Position size as fraction of capital
        strategy_name: Name for reporting
        start_date/end_date: Date range string
    
    Returns:
        BacktestResult with full metrics
    """
    capital = initial_capital
    position = 0.0
    entry_price = 0.0
    equity_curve = [capital]
    trades = []
    winning = 0
    losing = 0
    signal_map = {s["index"]: s for s in signals}

    for i, price in enumerate(prices):
        # Check stop loss / take profit if in position
        if position > 0 and entry_price > 0:
            pnl_pct = (price - entry_price) / entry_price
            if pnl_pct <= -stop_loss_pct:
                # Stop loss triggered
                capital += position * price
                profit = position * (price - entry_price)
                losing += 1
                trades.append(TradeSignal(
                    timestamp=f"day_{i}",
                    action="close_long",
                    price=price,
                    reason=f"止损 {pnl_pct:.1%}",
                    confidence=1.0,
                ))
                position = 0.0
                entry_price = 0.0
            elif pnl_pct >= take_profit_pct:
                # Take profit triggered
                capital += position * price
                profit = position * (price - entry_price)
                winning += 1
                trades.append(TradeSignal(
                    timestamp=f"day_{i}",
                    action="close_long",
                    price=price,
                    reason=f"止盈 {pnl_pct:.1%}",
                    confidence=1.0,
                ))
                position = 0.0
                entry_price = 0.0

        # Process strategy signals
        if i in signal_map:
            sig = signal_map[i]
            action = sig.get("action", "")
            if action == "open_long" and position == 0:
                invest = capital * position_size_pct
                shares = invest / price
                position = shares
                capital -= invest
                entry_price = price
                trades.append(TradeSignal(
                    timestamp=f"day_{i}", action="open_long",
                    price=price, reason=sig.get("reason", ""),
                ))
            elif action == "close_long" and position > 0:
                capital += position * price
                profit = position * (price - entry_price)
                if profit > 0:
                    winning += 1
                else:
                    losing += 1
                trades.append(TradeSignal(
                    timestamp=f"day_{i}", action="close_long",
                    price=price, reason=sig.get("reason", ""),
                ))
                position = 0.0
                entry_price = 0.0

        # Mark-to-market
        total_value = capital + position * price
        equity_curve.append(total_value)

    # Final metrics
    final_value = capital + position * prices[-1] if prices else capital
    total_return = (final_value - initial_capital) / initial_capital * 100
    max_dd = 0.0
    peak = equity_curve[0]
    for v in equity_curve:
        if v > peak:
            peak = v
        dd = (peak - v) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

    total_trades = winning + losing
    win_rate = winning / total_trades * 100 if total_trades > 0 else 0

    # Sharpe ratio (simplified)
    if len(equity_curve) > 1:
        returns = [(equity_curve[i] - equity_curve[i-1]) / equity_curve[i-1]
                   for i in range(1, len(equity_curve)) if equity_curve[i-1] > 0]
        if returns:
            avg_ret = sum(returns) / len(returns)
            std_ret = (sum((r - avg_ret)**2 for r in returns) / len(returns)) ** 0.5
            sharpe = (avg_ret / std_ret * (252 ** 0.5)) if std_ret > 0 else 0
        else:
            sharpe = 0.0
    else:
        sharpe = 0.0

    return BacktestResult(
        strategy_name=strategy_name,
        start_date=start_date or "N/A",
        end_date=end_date or "N/A",
        initial_capital=initial_capital,
        final_capital=round(final_value, 2),
        total_return=round(total_return, 2),
        max_drawdown=round(max_dd, 2),
        win_rate=round(win_rate, 1),
        total_trades=total_trades,
        winning_trades=winning,
        losing_trades=losing,
        sharpe_ratio=round(sharpe, 2),
        trades=trades,
        equity_curve=equity_curve,
    )


if __name__ == "__main__":
    # Self-test: simple dual MA crossover
    import random
    random.seed(42)
    prices = [100.0]
    for _ in range(251):
        prices.append(prices[-1] * (1 + random.uniform(-0.03, 0.03)))

    # Generate crossover signals
    short_ma = [sum(prices[max(0,i-4):i+1])/(min(i+1, 5)) for i in range(len(prices))]
    long_ma = [sum(prices[max(0,i-19):i+1])/(min(i+1, 20)) for i in range(len(prices))]
    golden = edge(short_ma[i] > long_ma[i] for i in range(len(prices)))
    death = edge(short_ma[i] < long_ma[i] for i in range(len(prices)))

    signals = []
    for i in range(len(prices)):
        if golden[i]:
            signals.append({"index": i, "action": "open_long", "reason": "金叉"})
        elif death[i]:
            signals.append({"index": i, "action": "close_long", "reason": "死叉"})

    result = backtest(prices, signals, strategy_name="双均线交叉", start_date="2025-01-01", end_date="2025-12-31")
    print(result.summary())
