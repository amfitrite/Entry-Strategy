"""Base Pattern Class for all Entry Strategies with Event Deduplication."""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from datetime import datetime
from entrystrategy.core.models import EntrySignal, SignalDirection, PatternRole
from entrystrategy.core.buffer import MarketBuffer


class BasePattern(ABC):
    def __init__(
        self,
        pattern_id: int,
        name: str,
        category: str,
        description: str,
        role: PatternRole = PatternRole.ENTRY,
        phenomenon: str = "",
        cooldown_ms: int = 3000,
    ):
        self.pattern_id = pattern_id
        self.name = name
        self.category = category
        self.description = description
        self.role = role
        self.phenomenon = phenomenon
        self.cooldown_ms = cooldown_ms
        
        # State tracking and event deduplication
        self.last_trigger_ms: int = 0
        self.last_direction: SignalDirection = SignalDirection.NONE
        self.last_signal: Optional[EntrySignal] = None
        self.last_event_id: Optional[str] = None
        self.last_candle_ts: Optional[datetime] = None

    def reset(self):
        """Resets pattern state for clean session or testing."""
        self.last_trigger_ms = 0
        self.last_direction = SignalDirection.NONE
        self.last_signal = None
        self.last_event_id = None
        self.last_candle_ts = None

    def _is_event_deduplicated(self, event_id: str) -> bool:
        """Helper to test if this exact event ID has already triggered."""
        return bool(event_id and self.last_event_id == event_id)

    def _is_candle_deduplicated(self, candle_ts: datetime, direction: SignalDirection) -> bool:
        """Helper to test if a candle pattern already triggered on this bar and direction."""
        return bool(self.last_candle_ts == candle_ts and self.last_direction == direction)

    def check(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        """Wrapper around evaluate that enforces event-based deduplication, detection timestamp freshness, and execution price."""
        sig = self.evaluate(buffer)
        if not sig or sig.direction == SignalDirection.NONE:
            return None

        # P0 Fix: Ensure timestamp_ms represents detection time, not candle open time
        now_wall_ms = buffer.current_time_ms
        if sig.timestamp_ms < (now_wall_ms - 10_000):
            sig.timestamp_ms = now_wall_ms

        # P0 Fix: Ensure execution_price accounts for Bid/Ask spread
        sig.execution_price = buffer.get_execution_price(sig.direction, sig.trigger_price)

        now_ms = sig.timestamp_ms

        # Deduplication Rule 1: Candle patterns evaluate per bar
        # A candle pattern may trigger ONLY ONCE per candle bar and direction!
        if self.category == "Candle":
            recent_candles = buffer.get_recent_candles(1)
            if recent_candles:
                current_c0_ts = recent_candles[0].timestamp
                if self.last_candle_ts == current_c0_ts and self.last_direction == sig.direction:
                    return None
                self.last_candle_ts = current_c0_ts

        # Deduplication Rule 2: Explicit Event ID matching
        if sig.event_id and sig.event_id == self.last_event_id:
            return None

        # Deduplication Rule 3: Micro Tick / Hybrid cooldown for same direction
        if sig.direction == self.last_direction:
            if (now_ms - self.last_trigger_ms) < self.cooldown_ms:
                return None

        # New valid event accepted!
        self.last_trigger_ms = now_ms
        self.last_direction = sig.direction
        self.last_event_id = sig.event_id
        self.last_signal = sig
        return sig

    def register_signal(self, sig: EntrySignal):
        """Manually registers an executed signal for deduplication tracking."""
        self.last_trigger_ms = sig.timestamp_ms
        self.last_direction = sig.direction
        self.last_event_id = sig.event_id
        self.last_signal = sig

    @abstractmethod
    def evaluate(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        """Core deterministic predicate function. Must return EntrySignal or None."""
        pass

    def get_info(self) -> Dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "role": self.role.value,
            "phenomenon": self.phenomenon,
            "last_direction": self.last_direction.value,
            "last_trigger_ms": self.last_trigger_ms,
            "last_signal": self.last_signal.to_dict() if self.last_signal else None,
        }
