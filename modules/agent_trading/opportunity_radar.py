# -*- coding: utf-8 -*-
"""
深度方略-Stratapro · Opportunity Radar
AtomCollide-智械工坊 · 2026

Cross-venue opportunity scanner that monitors multiple markets
(crypto, stocks, forex) for trading signals and anomalies.

Inspired by QuantDinger's multi-venue execution and opportunity detection.

Features:
  - Cross-venue price discrepancy detection (arbitrage signals)
  - Volume anomaly detection (unusual volume spikes)
  - Momentum scanning (strong trend identification)
  - Multi-timeframe analysis
  - Structured opportunity scoring (0-100)

Usage:
    from modules.opportunity_radar import OpportunityRadar

    radar = OpportunityRadar()
    radar.add_feed("binance", binance_data)
    radar.add_feed("okx", okx_data)
    opportunities = radar.scan()
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


class OpportunityType(Enum):
    ARBITRAGE = "arbitrage"         # Price discrepancy across venues
    VOLUME_SPIKE = "volume_spike"   # Unusual volume increase
    MOMENTUM = "momentum"           # Strong directional move
    MEAN_REVERSION = "mean_reversion"  # Oversold/overbought
    BREAKOUT = "breakout"           # Price breaking key levels


class SignalStrength(Enum):
    STRONG = "strong"    # Score 80-100
    MODERATE = "moderate"  # Score 50-79
    WEAK = "weak"        # Score 20-49
    NOISE = "noise"      # Score < 20


@dataclass
class Opportunity:
    """A detected trading opportunity."""
    opp_type: str
    symbol: str
    venue: str
    score: int               # 0-100
    strength: str            # strong/moderate/weak/noise
    direction: str           # long/short/neutral
    entry_price: float
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    risk_reward_ratio: float = 0.0
    confidence: float = 0.0
    timestamp: str = ""
    details: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> str:
        emoji = {"strong": "🟢", "moderate": "🟡", "weak": "🟠", "noise": "⚪"}.get(self.strength, "⚪")
        return (
            f"{emoji} [{self.score}] {self.opp_type.upper()} {self.symbol} @ {self.venue} "
            f"| {self.direction} | entry: {self.entry_price} | {self.details}"
        )


@dataclass
class VenueFeed:
    """Market data from a single venue."""
    venue: str
    data: pd.DataFrame
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)


class OpportunityRadar:
    """
    Cross-venue opportunity scanner.

    Accepts market data feeds from multiple venues and scans for:
    - Arbitrage opportunities (price discrepancies)
    - Volume anomalies
    - Momentum signals
    - Mean reversion setups
    - Breakout patterns
    """

    def __init__(
        self,
        min_score: int = 30,
        arbitrage_threshold: float = 0.005,
        volume_spike_multiplier: float = 2.5,
        momentum_lookback: int = 20,
    ):
        self.min_score = min_score
        self.arbitrage_threshold = arbitrage_threshold
        self.volume_spike_multiplier = volume_spike_multiplier
        self.momentum_lookback = momentum_lookback
        self._feeds: Dict[str, VenueFeed] = {}

    def add_feed(
        self,
        venue: str,
        data: pd.DataFrame,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        Add a market data feed from a venue.

        DataFrame should have columns: timestamp, symbol, open, high, low, close, volume
        """
        self._feeds[venue] = VenueFeed(
            venue=venue,
            data=data,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )

    def scan(self, symbol: Optional[str] = None) -> List[Opportunity]:
        """
        Scan all feeds for opportunities.

        Args:
            symbol: Filter for specific symbol. None = scan all.

        Returns:
            List of Opportunity objects, sorted by score descending.
        """
        opportunities: List[Opportunity] = []

        # 1. Cross-venue arbitrage
        opportunities.extend(self._scan_arbitrage(symbol))

        # 2. Per-venue scans
        for venue, feed in self._feeds.items():
            df = feed.data
            if symbol:
                df = df[df.get("symbol", df.index) == symbol] if "symbol" in df.columns else df

            opportunities.extend(self._scan_volume_spike(df, venue))
            opportunities.extend(self._scan_momentum(df, venue))
            opportunities.extend(self._scan_mean_reversion(df, venue))
            opportunities.extend(self._scan_breakout(df, venue))

        # Filter by minimum score and sort
        opportunities = [o for o in opportunities if o.score >= self.min_score]
        opportunities.sort(key=lambda o: o.score, reverse=True)
        return opportunities

    def _scan_arbitrage(self, symbol: Optional[str] = None) -> List[Opportunity]:
        """Detect price discrepancies across venues."""
        opps: List[Opportunity] = []
        venues = list(self._feeds.keys())
        if len(venues) < 2:
            return opps

        # Get latest prices from each venue
        prices: Dict[str, Dict[str, float]] = {}
        for venue, feed in self._feeds.items():
            df = feed.data
            if df.empty:
                continue
            if "symbol" in df.columns and "close" in df.columns:
                latest = df.groupby("symbol")["close"].last()
                prices[venue] = latest.to_dict()

        # Compare prices across venue pairs
        for i in range(len(venues)):
            for j in range(i + 1, len(venues)):
                v1, v2 = venues[i], venues[j]
                p1, p2 = prices.get(v1, {}), prices.get(v2, {})
                common_symbols = set(p1.keys()) & set(p2.keys())

                for sym in common_symbols:
                    price1, price2 = p1[sym], p2[sym]
                    if price1 == 0:
                        continue
                    diff_pct = abs(price1 - price2) / min(price1, price2)

                    if diff_pct >= self.arbitrage_threshold:
                        buy_venue = v1 if price1 < price2 else v2
                        sell_venue = v2 if price1 < price2 else v1
                        buy_price = min(price1, price2)
                        sell_price = max(price1, price2)
                        score = min(100, int(diff_pct * 5000))  # 0.5% → 25, 2% → 100

                        opps.append(Opportunity(
                            opp_type=OpportunityType.ARBITRAGE.value,
                            symbol=sym,
                            venue=f"{buy_venue}→{sell_venue}",
                            score=score,
                            strength=self._score_to_strength(score),
                            direction="long",
                            entry_price=buy_price,
                            target_price=sell_price,
                            risk_reward_ratio=diff_pct / 0.001 if diff_pct > 0 else 0,
                            confidence=min(1.0, diff_pct * 10),
                            timestamp=datetime.now(timezone.utc).isoformat(),
                            details=f"Spread: {diff_pct:.2%} ({buy_venue} @ {buy_price} → {sell_venue} @ {sell_price})",
                            metadata={"buy_venue": buy_venue, "sell_venue": sell_venue, "spread_pct": diff_pct},
                        ))

        return opps

    def _scan_volume_spike(self, df: pd.DataFrame, venue: str) -> List[Opportunity]:
        """Detect unusual volume spikes."""
        opps: List[Opportunity] = []
        if df.empty or "volume" not in df.columns:
            return opps

        try:
            vol = df["volume"]
            if len(vol) < 20:
                return opps

            avg_vol = vol.rolling(20).mean()
            current_vol = vol.iloc[-1]
            avg_val = avg_vol.iloc[-1]

            if avg_val > 0 and current_vol > avg_val * self.volume_spike_multiplier:
                ratio = current_vol / avg_val
                score = min(100, int(ratio * 20))
                direction = "long" if df["close"].iloc[-1] > df["close"].iloc[-2] else "short"

                opps.append(Opportunity(
                    opp_type=OpportunityType.VOLUME_SPIKE.value,
                    symbol=str(df.get("symbol", "unknown").iloc[-1]) if "symbol" in df.columns else "unknown",
                    venue=venue,
                    score=score,
                    strength=self._score_to_strength(score),
                    direction=direction,
                    entry_price=float(df["close"].iloc[-1]),
                    confidence=min(1.0, ratio / 5),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    details=f"Volume {ratio:.1f}x average ({current_vol:.0f} vs avg {avg_val:.0f})",
                    metadata={"volume_ratio": ratio},
                ))
        except Exception:
            pass

        return opps

    def _scan_momentum(self, df: pd.DataFrame, venue: str) -> List[Opportunity]:
        """Detect strong momentum moves."""
        opps: List[Opportunity] = []
        if df.empty or "close" not in df.columns:
            return opps

        try:
            close = df["close"]
            if len(close) < self.momentum_lookback:
                return opps

            # Calculate returns over lookback period
            ret = (close.iloc[-1] / close.iloc[-self.momentum_lookback] - 1) * 100
            direction = "long" if ret > 0 else "short"
            abs_ret = abs(ret)

            # Score based on magnitude of move
            score = min(100, int(abs_ret * 10))  # 5% → 50, 10% → 100

            if score >= self.min_score:
                opps.append(Opportunity(
                    opp_type=OpportunityType.MOMENTUM.value,
                    symbol=str(df.get("symbol", "unknown").iloc[-1]) if "symbol" in df.columns else "unknown",
                    venue=venue,
                    score=score,
                    strength=self._score_to_strength(score),
                    direction=direction,
                    entry_price=float(close.iloc[-1]),
                    confidence=min(1.0, abs_ret / 15),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    details=f"{abs_ret:.1f}% move over {self.momentum_lookback} periods",
                    metadata={"return_pct": ret, "lookback": self.momentum_lookback},
                ))
        except Exception:
            pass

        return opps

    def _scan_mean_reversion(self, df: pd.DataFrame, venue: str) -> List[Opportunity]:
        """Detect oversold/overbought conditions (mean reversion setups)."""
        opps: List[Opportunity] = []
        if df.empty or "close" not in df.columns:
            return opps

        try:
            close = df["close"]
            if len(close) < 20:
                return opps

            # Simple RSI-like calculation
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss.replace(0, 1e-10)
            rsi = 100 - (100 / (1 + rs))
            current_rsi = rsi.iloc[-1]

            if current_rsi < 30:
                score = min(100, int((30 - current_rsi) * 3))
                opps.append(Opportunity(
                    opp_type=OpportunityType.MEAN_REVERSION.value,
                    symbol=str(df.get("symbol", "unknown").iloc[-1]) if "symbol" in df.columns else "unknown",
                    venue=venue, score=score, strength=self._score_to_strength(score),
                    direction="long", entry_price=float(close.iloc[-1]),
                    confidence=min(1.0, (30 - current_rsi) / 30),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    details=f"RSI={current_rsi:.1f} (oversold)", metadata={"rsi": current_rsi},
                ))
            elif current_rsi > 70:
                score = min(100, int((current_rsi - 70) * 3))
                opps.append(Opportunity(
                    opp_type=OpportunityType.MEAN_REVERSION.value,
                    symbol=str(df.get("symbol", "unknown").iloc[-1]) if "symbol" in df.columns else "unknown",
                    venue=venue, score=score, strength=self._score_to_strength(score),
                    direction="short", entry_price=float(close.iloc[-1]),
                    confidence=min(1.0, (current_rsi - 70) / 30),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    details=f"RSI={current_rsi:.1f} (overbought)", metadata={"rsi": current_rsi},
                ))
        except Exception:
            pass

        return opps

    def _scan_breakout(self, df: pd.DataFrame, venue: str) -> List[Opportunity]:
        """Detect price breaking key levels (20-period high/low)."""
        opps: List[Opportunity] = []
        if df.empty or "close" not in df.columns or "high" not in df.columns:
            return opps

        try:
            if len(df) < 20:
                return opps

            high_20 = df["high"].rolling(20).max().iloc[-2]  # Previous bar's 20-period high
            low_20 = df["low"].rolling(20).min().iloc[-2]
            current = df["close"].iloc[-1]

            if current > high_20:
                breakout_pct = (current - high_20) / high_20 * 100
                score = min(100, int(breakout_pct * 20 + 40))
                opps.append(Opportunity(
                    opp_type=OpportunityType.BREAKOUT.value,
                    symbol=str(df.get("symbol", "unknown").iloc[-1]) if "symbol" in df.columns else "unknown",
                    venue=venue, score=score, strength=self._score_to_strength(score),
                    direction="long", entry_price=float(current),
                    target_price=float(current * 1.02),
                    stop_loss=float(high_20),
                    risk_reward_ratio=2.0,
                    confidence=min(1.0, breakout_pct / 3),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    details=f"Broke above 20-period high ({high_20:.2f}) by {breakout_pct:.1f}%",
                    metadata={"level": high_20, "breakout_pct": breakout_pct},
                ))
            elif current < low_20:
                breakout_pct = (low_20 - current) / low_20 * 100
                score = min(100, int(breakout_pct * 20 + 40))
                opps.append(Opportunity(
                    opp_type=OpportunityType.BREAKOUT.value,
                    symbol=str(df.get("symbol", "unknown").iloc[-1]) if "symbol" in df.columns else "unknown",
                    venue=venue, score=score, strength=self._score_to_strength(score),
                    direction="short", entry_price=float(current),
                    target_price=float(current * 0.98),
                    stop_loss=float(low_20),
                    risk_reward_ratio=2.0,
                    confidence=min(1.0, breakout_pct / 3),
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    details=f"Broke below 20-period low ({low_20:.2f}) by {breakout_pct:.1f}%",
                    metadata={"level": low_20, "breakout_pct": breakout_pct},
                ))
        except Exception:
            pass

        return opps

    @staticmethod
    def _score_to_strength(score: int) -> str:
        if score >= 80:
            return SignalStrength.STRONG.value
        elif score >= 50:
            return SignalStrength.MODERATE.value
        elif score >= 20:
            return SignalStrength.WEAK.value
        return SignalStrength.NOISE.value

    def get_summary(self, opportunities: List[Opportunity]) -> str:
        """Generate a human-readable summary of opportunities."""
        if not opportunities:
            return "No opportunities detected."

        by_type: Dict[str, int] = defaultdict(int)
        by_strength: Dict[str, int] = defaultdict(int)
        for o in opportunities:
            by_type[o.opp_type] += 1
            by_strength[o.strength] += 1

        lines = [
            f"🔍 Opportunity Radar: {len(opportunities)} opportunities found",
            f"   Venues: {len(self._feeds)} ({', '.join(self._feeds.keys())})",
            "",
            "By Type:",
        ]
        for t, c in sorted(by_type.items(), key=lambda x: -x[1]):
            lines.append(f"  {t}: {c}")
        lines.append("")
        lines.append("By Strength:")
        for s in ["strong", "moderate", "weak"]:
            if s in by_strength:
                emoji = {"strong": "🟢", "moderate": "🟡", "weak": "🟠"}[s]
                lines.append(f"  {emoji} {s}: {by_strength[s]}")
        lines.append("")
        lines.append("Top 5:")
        for o in opportunities[:5]:
            lines.append(f"  {o.summary()}")

        return "\n".join(lines)
