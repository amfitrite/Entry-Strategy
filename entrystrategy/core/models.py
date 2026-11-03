"""Domain Models for Entry Strategy Engine."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional


class SignalDirection(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NONE = "NONE"


class SignalStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    CONFIRMED = "CONFIRMED"
    INVALIDATED = "INVALIDATED"
    EXPIRED = "EXPIRED"


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
    timeframe: str = "M5"
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
    trigger_price: float                # Level harga pemicu teknis pola (Bid candle close / breakout point)
    timestamp_ms: int                   # Timestamp milidetik saat trigger terjadi
    invalidation_price: Optional[float] = None # Level di mana premis pola ini batal
    execution_price: Optional[float] = None   # Perkiraan harga eksekusi riil (Ask untuk BUY, Bid untuk SELL)
    pattern_role: PatternRole = PatternRole.ENTRY
    phenomenon: str = ""                # Deskripsi fenomena pergerakan harga yang diukur
    reasons: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    event_id: str = ""                  # Kunci unik event untuk deduplikasi sinyal
    confidence: float = 1.0
    price: Optional[float] = None       # Backwards-compatible field
    
    # --- Lifecycle State Machine Fields ---
    status: SignalStatus = SignalStatus.ACTIVE
    status_reason: str = "Kondisi entry pola terpenuhi"
    max_age_sec: float = 30.0           # Batas usia sinyal (detik)
    confirmed_price: Optional[float] = None
    confirmed_time_ms: Optional[int] = None
    invalidated_price: Optional[float] = None
    invalidated_time_ms: Optional[int] = None
    expired_time_ms: Optional[int] = None

    def __post_init__(self):
        if self.execution_price is None:
            self.execution_price = self.trigger_price
        if self.price is None:
            self.price = self.execution_price
        elif self.trigger_price == 0.0 and self.price > 0.0:
            self.trigger_price = self.price

    @property
    def is_alive(self) -> bool:
        """Returns True if the signal is actively in play."""
        return self.status in (
            SignalStatus.ACTIVE,
            SignalStatus.PENDING_CONFIRMATION,
            SignalStatus.CONFIRMED,
        )

    @property
    def is_terminal(self) -> bool:
        """Returns True if the signal reached a terminal state (invalidated or expired)."""
        return self.status in (SignalStatus.INVALIDATED, SignalStatus.EXPIRED)

    def update_lifecycle(
        self,
        current_price: float,
        current_ts_ms: int,
        spread: float = 0.0,
        confirmation_threshold: float = 0.20,
    ) -> bool:
        """Evaluates price evolution against signal invalidation, confirmation, and expiry rules.
        Returns True if status changed.
        """
        # Terminal states are immutable
        if self.is_terminal:
            return False

        old_status = self.status
        elapsed_sec = max(0.0, (current_ts_ms - self.timestamp_ms) / 1000.0)

        # 1. Invalidation Check: Level invalidasi tercapai
        if self.invalidation_price is not None:
            if self.direction == SignalDirection.BUY and current_price <= self.invalidation_price:
                self.status = SignalStatus.INVALIDATED
                self.invalidated_price = current_price
                self.invalidated_time_ms = current_ts_ms
                self.status_reason = (
                    f"Harga ({current_price:.2f}) menembus level invalidasi ({self.invalidation_price:.2f})"
                )
                return True
            elif self.direction == SignalDirection.SELL and current_price >= self.invalidation_price:
                self.status = SignalStatus.INVALIDATED
                self.invalidated_price = current_price
                self.invalidated_time_ms = current_ts_ms
                self.status_reason = (
                    f"Harga ({current_price:.2f}) menembus level invalidasi ({self.invalidation_price:.2f})"
                )
                return True

        # 2. Expiration Check: Batas usia sinyal tercapai
        if elapsed_sec >= self.max_age_sec:
            self.status = SignalStatus.EXPIRED
            self.expired_time_ms = current_ts_ms
            if old_status == SignalStatus.CONFIRMED:
                self.status_reason = f"Siklus sinyal selesai (terkonfirmasi, batas {self.max_age_sec:.0f} detik tercapai)"
            else:
                self.status_reason = f"Batas usia sinyal tercapai ({self.max_age_sec:.0f} detik)"
            return True

        # 3. Confirmation Check: Harga mengikuti arah sinyal
        threshold = max(confirmation_threshold, spread)
        if self.status != SignalStatus.CONFIRMED:
            if self.direction == SignalDirection.BUY and current_price >= (self.trigger_price + threshold):
                self.status = SignalStatus.CONFIRMED
                self.confirmed_price = current_price
                self.confirmed_time_ms = current_ts_ms
                self.status_reason = (
                    f"Harga terkonfirmasi bergerak searah BUY (+{current_price - self.trigger_price:.2f} pts)"
                )
                return True
            elif self.direction == SignalDirection.SELL and current_price <= (self.trigger_price - threshold):
                self.status = SignalStatus.CONFIRMED
                self.confirmed_price = current_price
                self.confirmed_time_ms = current_ts_ms
                self.status_reason = (
                    f"Harga terkonfirmasi bergerak searah SELL (-{self.trigger_price - current_price:.2f} pts)"
                )
                return True

        # 4. Active -> Pending Confirmation Transition
        # Kondisi pemicu awal yang tidak lagi terpenuhi bukan alasan menghapus sinyal.
        if self.status == SignalStatus.ACTIVE and elapsed_sec >= 2.0:
            self.status = SignalStatus.PENDING_CONFIRMATION
            self.status_reason = "Harga bergerak, sinyal tersimpan menunggu kelanjutan/konfirmasi"
            return True

        return self.status != old_status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "family_name": self.family_name,
            "direction": self.direction.value,
            "reference_price": round(self.reference_price, 2),
            "trigger_price": round(self.trigger_price, 2),
            "execution_price": round(self.execution_price, 2) if self.execution_price is not None else round(self.trigger_price, 2),
            "price": round(self.trigger_price, 2),
            "invalidation_price": round(self.invalidation_price, 2) if self.invalidation_price is not None else None,
            "pattern_role": self.pattern_role.value,
            "status": self.status.value,
            "status_reason": self.status_reason,
            "is_alive": self.is_alive,
            "is_terminal": self.is_terminal,
            "phenomenon": self.phenomenon,
            "timestamp_ms": self.timestamp_ms,
            "time_str": datetime.fromtimestamp(self.timestamp_ms / 1000.0).strftime("%H:%M:%S.%f")[:-3],
            "event_id": self.event_id,
            "reasons": self.reasons,
            "metrics": self.metrics,
            "confidence": self.confidence,
            "max_age_sec": self.max_age_sec,
            "confirmed_price": round(self.confirmed_price, 2) if self.confirmed_price is not None else None,
            "confirmed_time_ms": self.confirmed_time_ms,
            "invalidated_price": round(self.invalidated_price, 2) if self.invalidated_price is not None else None,
            "invalidated_time_ms": self.invalidated_time_ms,
            "expired_time_ms": self.expired_time_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EntrySignal":
        """Reconstructs an EntrySignal instance safely from serialized dictionary."""
        dir_val = data.get("direction", "NONE")
        try:
            direction = SignalDirection(dir_val)
        except Exception:
            direction = SignalDirection.NONE

        status_val = data.get("status", "ACTIVE")
        try:
            status = SignalStatus(status_val)
        except Exception:
            status = SignalStatus.ACTIVE

        role_val = data.get("pattern_role", "ENTRY")
        try:
            role = PatternRole(role_val)
        except Exception:
            role = PatternRole.ENTRY

        return cls(
            pattern_id=int(data.get("pattern_id", 0)),
            family_name=str(data.get("family_name", "")),
            direction=direction,
            reference_price=float(data.get("reference_price", 0.0)),
            trigger_price=float(data.get("trigger_price", 0.0)),
            timestamp_ms=int(data.get("timestamp_ms", 0)),
            invalidation_price=float(data["invalidation_price"]) if data.get("invalidation_price") is not None else None,
            execution_price=float(data["execution_price"]) if data.get("execution_price") is not None else None,
            pattern_role=role,
            phenomenon=str(data.get("phenomenon", "")),
            reasons=list(data.get("reasons", [])),
            metrics=dict(data.get("metrics", {})),
            event_id=str(data.get("event_id", "")),
            confidence=float(data.get("confidence", 1.0)),
            price=float(data["price"]) if data.get("price") is not None else None,
            status=status,
            status_reason=str(data.get("status_reason", "")),
            max_age_sec=float(data.get("max_age_sec", 30.0)),
            confirmed_price=float(data["confirmed_price"]) if data.get("confirmed_price") is not None else None,
            confirmed_time_ms=data.get("confirmed_time_ms"),
            invalidated_price=float(data["invalidated_price"]) if data.get("invalidated_price") is not None else None,
            invalidated_time_ms=data.get("invalidated_time_ms"),
            expired_time_ms=data.get("expired_time_ms"),
        )
