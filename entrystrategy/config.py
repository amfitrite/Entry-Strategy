"""Configuration for Entry Strategy Pattern Engine."""
from dataclasses import dataclass


@dataclass
class AppConfig:
    # Dukascopy ECN Live Feed settings (Geneva, Swiss)
    symbol: str = "XAUUSD"
    timeframe: str = "M5"  # Default timeframe M5 (with M1 option)
    enable_ticks: bool = False  # Pure candle M5 evaluation default; ticks can be toggled
    dukascopy_warmup_candles: int = 100  # Initial historical bar sync (100 bars)
    dukascopy_poll_interval_s: float = 1.0  # Live tick polling interval
    
    # Tick & Candle buffers
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
