"""Unit tests for M5 Candle-Based Strategy Engine with Ticks Disabled."""
import time
from datetime import datetime, timezone, timedelta
import pytest
from entrystrategy.config import AppConfig
from entrystrategy.core.buffer import MarketBuffer
from entrystrategy.core.models import Candle, TickData, SignalDirection
from entrystrategy.data.mt5_bridge import TickToBarAggregator, MT5BridgeServer
from entrystrategy.service import EntryStrategyService
from entrystrategy.gui.app import MatrixWindowAPI
from entrystrategy.engine.registry import PatternRegistry


def test_default_config_is_m5_and_ticks_disabled():
    """Verify system defaults are strictly M5 timeframe and ticks disabled."""
    config = AppConfig()
    assert config.timeframe == "M5"
    assert config.enable_ticks is False

    buf = MarketBuffer()
    assert buf.active_timeframe == "M5"


def test_all_40_patterns_active_in_matrix_state_with_ticks_disabled():
    """Verify none of the 40 patterns are marked DISABLED when ticks are disabled."""
    config = AppConfig(enable_simulation=False, enable_ticks=False, bridge_port=5579)
    service = EntryStrategyService(config, start_servers=False)

    state = service.get_matrix_state()
    assert state["config"]["timeframe"] == "M5"
    assert state["config"]["enable_ticks"] is False

    # Check all 40 pattern cards: none should be marked DISABLED
    patterns = state["patterns"]
    assert len(patterns) == 40
    for p in patterns:
        assert p["status"] != "DISABLED"
        assert p["time_ago"] != "TICKS OFF"


def test_patterns_evaluate_on_m5_candles_without_ticks():
    """Verify patterns 11-17, 22, 23, 24, 40 evaluate and fire signals purely using M5 candles."""
    registry = PatternRegistry()
    buf = MarketBuffer()
    buf.set_enable_ticks(False)  # Ticks disabled
    assert len(buf.get_recent_ticks()) == 0

    now = datetime.now(timezone.utc)

    # 1. Test Pola 11: Momentum on M5 candles
    p11 = registry.get_pattern(11)
    c_prev = Candle(timestamp=now - timedelta(minutes=10), open=2740.0, high=2742.0, low=2739.0, close=2741.0, timeframe="M5")
    c_mom = Candle(timestamp=now - timedelta(minutes=5), open=2741.0, high=2744.5, low=2740.5, close=2744.0, timeframe="M5")
    buf.add_completed_candle(c_prev)
    buf.add_completed_candle(c_mom)

    sig11 = p11.evaluate(buf)
    assert sig11 is not None
    assert sig11.direction == SignalDirection.BUY
    assert "Momentum Candle M5" in sig11.reasons[0]

    # 2. Test Pola 14: Volume Burst on M5 candles
    buf_vol = MarketBuffer()
    buf_vol.set_enable_ticks(False)
    p14 = registry.get_pattern(14)
    for i in range(4, 0, -1):
        c = Candle(timestamp=now - timedelta(minutes=i * 5), open=2740.0, high=2742.0, low=2739.0, close=2741.0, tick_volume=100.0, timeframe="M5")
        buf_vol.add_completed_candle(c)
    # Burst candle: volume 350 vs avg 100
    c_burst = Candle(timestamp=now, open=2741.0, high=2745.0, low=2740.5, close=2744.5, tick_volume=350.0, timeframe="M5")
    buf_vol.add_completed_candle(c_burst)

    sig14 = p14.evaluate(buf_vol)
    assert sig14 is not None
    assert sig14.direction == SignalDirection.BUY
    assert "Ledakan Volume M5" in sig14.reasons[0]

    # 3. Test Pola 22: Consecutive Movement on M5 candles
    buf_consec = MarketBuffer()
    buf_consec.set_enable_ticks(False)
    p22 = registry.get_pattern(22)
    c_c1 = Candle(timestamp=now - timedelta(minutes=15), open=2738.0, high=2740.0, low=2737.5, close=2739.5, timeframe="M5")
    c_c2 = Candle(timestamp=now - timedelta(minutes=10), open=2739.5, high=2742.0, low=2739.0, close=2741.8, timeframe="M5")
    c_c3 = Candle(timestamp=now - timedelta(minutes=5), open=2741.8, high=2744.5, low=2741.5, close=2744.0, timeframe="M5")
    buf_consec.add_completed_candle(c_c1)
    buf_consec.add_completed_candle(c_c2)
    buf_consec.add_completed_candle(c_c3)

    sig22 = p22.evaluate(buf_consec)
    assert sig22 is not None
    assert sig22.direction == SignalDirection.BUY
    assert "3 Candle M5 Berturut-turut Bullish" in sig22.reasons[0]

    # 4. Test Pola 40: Hybrid M5 Candle Pin Bar & Follow-through
    buf_hyb = MarketBuffer()
    buf_hyb.set_enable_ticks(False)
    p40 = registry.get_pattern(40)
    # Pin bar with long lower wick (low 2735.0, close 2740.0, range 5.0, lower wick 4.0 >= 45%)
    c_pin = Candle(timestamp=now - timedelta(minutes=10), open=2739.0, high=2740.0, low=2735.0, close=2739.5, timeframe="M5")
    c_follow = Candle(timestamp=now - timedelta(minutes=5), open=2739.5, high=2743.0, low=2739.0, close=2742.5, timeframe="M5")
    buf_hyb.add_completed_candle(c_pin)
    buf_hyb.add_completed_candle(c_follow)

    sig40 = p40.evaluate(buf_hyb)
    assert sig40 is not None
    assert sig40.direction == SignalDirection.BUY
    assert "Sinergi M5: Pin bar" in sig40.reasons[0]


def test_bridge_server_parses_m5_bar_command():
    """Verify MT5BridgeServer parses #BAR:M5 lines sent by EA on M5 bar close."""
    completed_bars = []
    server = MT5BridgeServer(on_bar_completed=lambda c: completed_bars.append(c))

    now_epoch = 1700000000
    bar_line = f"#BAR:M5,{now_epoch},2740.00,2745.50,2739.00,2744.50,520,120,1.4\n"
    server._parse_line(bar_line)

    assert len(completed_bars) == 1
    candle = completed_bars[0]
    assert candle.timeframe == "M5"
    assert candle.open == 2740.00
    assert candle.high == 2745.50
    assert candle.low == 2739.00
    assert candle.close == 2744.50
    assert candle.tick_volume == 520.0
    assert candle.spread == 1.4
