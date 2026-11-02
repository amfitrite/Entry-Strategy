"""Domain Models for Entry Strategy Engine."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NONE = "NONE"


class PatternRole(str, Enum):
    ENTRY = "ENTRY"                   # Memiliki pemicu arah BUY/SELL langsung
    SETUP_TRIGGER = "SETUP_TRIGGER"   # Mendeteksi kondisi yang membutuhkan pemicu lanjutan
    CONFIRMATION = "CONFIRMATION"     # Mengonfirmasi fenomena mikro yang terjadi
    STRUCTURE = "STRUCTURE"           # Mengonfirmasi struktur harga (swing, staircase, dsb)


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
        if self.last > 0:
            return self.last
        return (self.bid + self.ask) / 2.0

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
    tick_volume: float = 0.0
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
    reference_price: float              # Level referensi/anchor pola (misal: Mother Bar High, Level Reversal)
    trigger_price: float                # Harga aktual saat trigger tereksekusi (Bid/Ask)
    timestamp_ms: int                   # Timestamp milidetik saat trigger terjadi
    invalidation_price: Optional[float] = None # Level di mana premis pola ini batal
    pattern_role: PatternRole = PatternRole.ENTRY
    phenomenon: str = ""                # Deskripsi fenomena pergerakan harga yang diukur
    reasons: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    event_id: str = ""                  # Kunci unik event untuk deduplikasi sinyal
    confidence: float = 1.0
    price: Optional[float] = None       # Backwards-compatible field

    def __post_init__(self):
        if self.price is None:
            self.price = self.trigger_price
        elif self.trigger_price == 0.0 and self.price > 0.0:
            self.trigger_price = self.price

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "family_name": self.family_name,
            "direction": self.direction.value,
            "reference_price": round(self.reference_price, 2),
            "trigger_price": round(self.trigger_price, 2),
            "price": round(self.trigger_price, 2),
            "invalidation_price": round(self.invalidation_price, 2) if self.invalidation_price is not None else None,
            "pattern_role": self.pattern_role.value,
            "phenomenon": self.phenomenon,
            "timestamp_ms": self.timestamp_ms,
            "time_str": datetime.fromtimestamp(self.timestamp_ms / 1000.0).strftime("%H:%M:%S.%f")[:-3],
            "event_id": self.event_id,
            "reasons": self.reasons,
            "metrics": self.metrics,
            "confidence": self.confidence,
        }
