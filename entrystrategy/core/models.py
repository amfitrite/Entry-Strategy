"""Data models for Entry Strategy Engine."""
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NONE = "NONE"


@dataclass
class TickData:
    ts_ms: int
    bid: float
    ask: float
    last: float = 0.0
    volume: float = 1.0
    flags: int = 0
    symbol: str = "XAUUSD"

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0 if self.last <= 0 else self.last

    @property
    def spread(self) -> float:
        return max(0.0, self.ask - self.bid)


@dataclass
class Candle:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    tick_volume: float = 1.0
    real_volume: float = 0.0
    spread: float = 0.0
    symbol: str = "XAUUSD"
    timeframe: str = "M1"
    is_closed: bool = True

    @property
    def range(self) -> float:
        return max(0.0001, self.high - self.low)

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def upper_wick(self) -> float:
        return max(0.0, self.high - max(self.open, self.close))

    @property
    def lower_wick(self) -> float:
        return max(0.0, min(self.open, self.close) - self.low)

    @property
    def is_bullish(self) -> bool:
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        return self.close < self.open

    @property
    def is_doji(self) -> bool:
        return self.body <= (self.range * 0.1)


@dataclass
class EntrySignal:
    pattern_id: int
    family_name: str
    direction: SignalDirection
    price: float
    timestamp_ms: int
    reasons: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "family_name": self.family_name,
            "direction": self.direction.value,
            "price": round(self.price, 2),
            "timestamp_ms": self.timestamp_ms,
            "time_str": datetime.fromtimestamp(self.timestamp_ms / 1000.0).strftime("%H:%M:%S.%f")[:-3],
            "reasons": self.reasons,
            "metrics": self.metrics,
            "confidence": self.confidence,
        }
