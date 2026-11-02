"""Configuration for Entry Strategy Pattern Engine."""
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppConfig:
    # MT5 Bridge settings
    bridge_host: str = "127.0.0.1"
    bridge_port: int = 5558  # Port 5558 as requested
    symbol: str = "XAUUSD"
    timeframe: str = "M5"  # Default timeframe M5 (supports M1 and M5)
    enable_ticks: bool = True  # Toggle for tick-based analysis mode
    
    # Tick & Candle buffers
    tick_buffer_size: int = 2000
    candle_buffer_size: int = 300
    
    # GUI settings
    window_title: str = "Entry Strategy Matrix"
    window_width: int = 1380
    window_height: int = 860
    frameless: bool = True
    
    # Simulation settings (when MT5 is offline)
    enable_simulation: bool = True
    sim_tick_interval_ms: int = 250
    sim_base_price: float = 2745.0
