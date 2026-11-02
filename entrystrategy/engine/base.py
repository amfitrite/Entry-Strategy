"""Base Pattern Class for all Entry Strategies."""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from entrystrategy.core.models import EntrySignal, SignalDirection
from entrystrategy.core.buffer import MarketBuffer


class BasePattern(ABC):
    def __init__(
        self,
        pattern_id: int,
        name: str,
        category: str,
        description: str,
        cooldown_ms: int = 3000,
    ):
        self.pattern_id = pattern_id
        self.name = name
        self.category = category
        self.description = description
        self.cooldown_ms = cooldown_ms
        self.last_trigger_ms: int = 0
        self.last_direction: SignalDirection = SignalDirection.NONE
        self.last_signal: Optional[EntrySignal] = None

    def check(self, buffer: MarketBuffer) -> Optional[EntrySignal]:
        """Wrapper around evaluate that enforces cooldown and state tracking."""
        sig = self.evaluate(buffer)
        if sig and sig.direction != SignalDirection.NONE:
            now_ms = sig.timestamp_ms
            if (now_ms - self.last_trigger_ms) >= self.cooldown_ms or sig.direction != self.last_direction:
                self.last_trigger_ms = now_ms
                self.last_direction = sig.direction
                self.last_signal = sig
                return sig
        return None

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
            "last_direction": self.last_direction.value,
            "last_trigger_ms": self.last_trigger_ms,
            "last_signal": self.last_signal.to_dict() if self.last_signal else None,
        }
