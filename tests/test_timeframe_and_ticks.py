"""Unit tests for Multi-Timeframe (M1/M5) and Tick Mode Toggle functionality."""
import time
from datetime import datetime, timezone
import pytest
from entrystrategy.config import AppConfig
from entrystrategy.core.buffer import MarketBuffer
from entrystrategy.core.models import Candle, TickData
from entrystrategy.data.mt5_bridge import TickToBarAggregator
from entrystrategy.service import EntryStrategyService
from entrystrategy.gui.app import MatrixWindowAPI


def test_default_config_is_m5_and_ticks_enabled():
    """Verify system defaults are M5 and ticks mode enabled."""
    config = AppConfig()
    assert config.timeframe == "M5"
    assert config.enable_ticks is True

    buf = MarketBuffer()
    assert buf.active_timeframe == "M5"
    assert buf.enable_ticks is True


def test_market_buffer_timeframe_isolation():
    """Verify M1 and M5 candles are kept isolated and query reflects active timeframe."""
    buf = MarketBuffer()
    assert buf.active_timeframe == "M5"

    now = datetime.now(timezone.utc)
    c_m1_1 = Candle(timestamp=now, open=2000.0, high=2002.0, low=1999.0, close=2001.0, timeframe="M1")
    c_m1_2 = Candle(timestamp=now, open=2001.0, high=2005.0, low=2000.0, close=2004.0, timeframe="M1")
    c_m5_1 = Candle(timestamp=now, open=1995.0, high=2005.0, low=1994.0, close=2003.0, timeframe="M5")

    buf.add_completed_candle(c_m1_1)
    buf.add_completed_candle(c_m1_2)
    buf.add_completed_candle(c_m5_1)

    # When active timeframe is M5
    assert buf.total_candles == 1
    candles_m5 = buf.get_recent_candles(5)
    assert len(candles_m5) == 1
    assert candles_m5[0].close == 2003.0

    # Switch to M1
    buf.set_active_timeframe("M1")
    assert buf.active_timeframe == "M1"
    assert buf.total_candles == 2
    candles_m1 = buf.get_recent_candles(5)
    assert len(candles_m1) == 2
    # Index 0 is the newest candle (c_m1_2: 2004.0), index 1 is previous (c_m1_1: 2001.0)
    assert candles_m1[0].close == 2004.0
    assert candles_m1[1].close == 2001.0

    # Switch back to M5
    buf.set_active_timeframe("M5")
    assert buf.active_timeframe == "M5"
    assert buf.total_candles == 1


def test_market_buffer_tick_toggle():
    """Verify disabling ticks hides tick slices while preserving latest price/spread."""
    buf = MarketBuffer()
    now_ms = int(time.time() * 1000)

    t1 = TickData(ts_ms=now_ms - 200, bid=2740.0, ask=2740.5, last=2740.25, volume=1.0)
    t2 = TickData(ts_ms=now_ms, bid=2741.0, ask=2741.5, last=2741.25, volume=1.0)

    buf.add_tick(t1)
    buf.add_tick(t2)

    assert len(buf.get_recent_ticks(5)) == 2
    assert buf.latest_tick is not None
    assert buf.latest_tick.last == 2741.25

    # Disable ticks
    buf.set_enable_ticks(False)
    assert buf.enable_ticks is False
    # Tick slice returns empty so tick patterns don't trigger
    assert len(buf.get_recent_ticks(5)) == 0
    # Latest tick readout for header still remains valid
    assert buf.latest_tick is not None
    assert buf.latest_tick.last == 2741.25

    # Re-enable ticks
    buf.set_enable_ticks(True)
    assert len(buf.get_recent_ticks(5)) == 2


def test_tick_to_bar_aggregator_m1_and_m5():
    """Verify aggregator produces both M1 and M5 completed bars via callback."""
    completed_bars = []
    agg = TickToBarAggregator(on_bar_completed=lambda b: completed_bars.append(b))

    # Base epoch aligned to 300s (M5) boundary
    base_epoch = 1700000000.0
    t1 = TickData(ts_ms=int(base_epoch * 1000), bid=2700.0, ask=2701.0, last=2700.5, volume=10.0)
    # 65 seconds later -> triggers M1 bar close
    t2 = TickData(ts_ms=int((base_epoch + 65) * 1000), bid=2705.0, ask=2706.0, last=2705.5, volume=15.0)

    agg.process_tick(t1)
    agg.process_tick(t2)

    assert len(completed_bars) == 1
    assert completed_bars[0].timeframe == "M1"
    assert completed_bars[0].open == 2700.5

    # 305 seconds later -> triggers M5 bar close
    t3 = TickData(ts_ms=int((base_epoch + 305) * 1000), bid=2710.0, ask=2711.0, last=2710.5, volume=20.0)
    agg.process_tick(t3)

    m5_bars = [b for b in completed_bars if b.timeframe == "M5"]
    assert len(m5_bars) == 1
    assert m5_bars[0].open == 2700.5


def test_service_timeframe_and_tick_toggle():
    """Verify EntryStrategyService handles set_timeframe and toggle_ticks_mode cleanly."""
    config = AppConfig(enable_simulation=False, bridge_port=5579)
    service = EntryStrategyService(config, start_servers=False)

    # Initial state check
    state = service.get_matrix_state()
    assert state["config"]["timeframe"] == "M5"
    assert state["config"]["enable_ticks"] is True

    # Switch timeframe to M1
    res_tf = service.set_timeframe("M1")
    assert res_tf["success"] is True
    assert res_tf["timeframe"] == "M1"

    state = service.get_matrix_state()
    assert state["config"]["timeframe"] == "M1"

    # Disable ticks
    res_ticks = service.toggle_ticks_mode(False)
    assert res_ticks["success"] is True
    assert res_ticks["enable_ticks"] is False

    state = service.get_matrix_state()
    assert state["config"]["enable_ticks"] is False

    # Check that Tick category patterns are labeled DISABLED
    tick_cards = [p for p in state["patterns"] if p["category"] == "Tick"]
    assert len(tick_cards) > 0
    for card in tick_cards:
        assert card["status"] == "DISABLED"
        assert "dinonaktifkan" in card["status_reason"]
        assert card["time_ago"] == "TICKS OFF"

    # Re-enable ticks
    res_ticks_on = service.toggle_ticks_mode(True)
    assert res_ticks_on["success"] is True
    assert res_ticks_on["enable_ticks"] is True

    state = service.get_matrix_state()
    assert state["config"]["enable_ticks"] is True


def test_matrix_window_api_timeframe_and_ticks():
    """Verify MatrixWindowAPI exposes JSON endpoints for set_timeframe and toggle_ticks_mode."""
    config = AppConfig(enable_simulation=False, bridge_port=5580)
    service = EntryStrategyService(config, start_servers=False)
    api = MatrixWindowAPI(service)

    # Test set_timeframe
    res = api.set_timeframe("M1")
    assert '"timeframe": "M1"' in res

    # Test toggle_ticks_mode
    res_off = api.toggle_ticks_mode(False)
    assert '"enable_ticks": false' in res_off

    res_on = api.toggle_ticks_mode()
    assert '"enable_ticks": true' in res_on
