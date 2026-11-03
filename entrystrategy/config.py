"""Configuration for Entry Strategy Pattern Engine."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class AppConfig:
    # Dukascopy ECN Live Feed settings (Geneva, Swiss)
    symbol: str = "XAUUSD"
    timeframe: str = "M5"  # Supported timeframes: "M1", "M5", "M15"
    enable_ticks: bool = False  # Deprecated compatibility flag; entry strategies are candle-only
    dukascopy_warmup_candles: int = 100  # Initial historical bar sync (100 bars)
    dukascopy_poll_interval_s: float = 1.0  # Live tick polling interval
    
    # Quote telemetry & candle buffers
    tick_buffer_size: int = 2000
    candle_buffer_size: int = 300
    
    # GUI settings
    window_title: str = "Entry Strategy Matrix Studio (Dukascopy Live)"
    window_width: int = 1380
    window_height: int = 860
    frameless: bool = True
    
    # Simulation settings (Fallback when offline or no internet)
    enable_simulation: bool = False
    sim_tick_interval_ms: int = 250
    sim_base_price: float = 3950.0
    
    # Session state persistence ("Continue where you left off")
    persist_session: bool = True
    state_filepath: Optional[str] = None

    # Volume and Order Flow Strategy Families (Patterns 41 - 56)
    enable_volume_strategies: bool = False
