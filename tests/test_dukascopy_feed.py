"""Tests for Dukascopy Bank Live Feed & Historical Warm-up."""
import time
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from entrystrategy.core.models import Candle, TickData, SignalStatus
from entrystrategy.data.dukascopy_feed import DukascopyFeed, DUKASCOPY_AVAILABLE
from entrystrategy.service import EntryStrategyService
from entrystrategy.config import AppConfig


def test_dukascopy_feed_init():
    feed = DukascopyFeed(
        symbol="XAUUSD",
        timeframe="M5",
        warmup_candles=50,
        poll_interval_s=1.0,
    )
    assert feed.symbol == "XAUUSD"
    assert feed.timeframe == "M5"
    assert feed.warmup_candles == 50
    assert feed.poll_interval_s == 1.0
    assert feed.is_connected is False


def test_dukascopy_feed_tick_callback_dispatch():
    received_ticks = []

    def on_tick_cb(tick: TickData, is_history: bool = False):
        received_ticks.append((tick, is_history))

    feed = DukascopyFeed(
        symbol="XAUUSD",
        timeframe="M5",
        on_tick=on_tick_cb,
    )

    now = datetime.now(timezone.utc)
    ts_ms = int(now.timestamp() * 1000)
    fake_tick = TickData(
        ts_ms=ts_ms,
        bid=3950.25,
        ask=3950.55,
        last=3950.40,
        volume=1.0,
        flags=6,
        symbol="XAUUSD"
    )

    if feed.on_tick:
        feed.on_tick(fake_tick, False)

    assert len(received_ticks) == 1
    t, is_hist = received_ticks[0]
    assert t.symbol == "XAUUSD"
    assert t.bid == 3950.25
    assert t.ask == 3950.55
    assert round(t.spread, 2) == 0.30
    assert is_hist is False


def test_dukascopy_feed_bar_completed_callback():
    received_bars = []

    def on_bar_cb(candle: Candle, is_history: bool = False):
        received_bars.append((candle, is_history))

    feed = DukascopyFeed(
        symbol="XAUUSD",
        timeframe="M5",
        on_bar_completed=on_bar_cb,
    )

    now = datetime.now(timezone.utc)
    bar = Candle(
        timestamp=now,
        open=3948.0,
        high=3955.0,
        low=3947.5,
        close=3953.2,
        tick_volume=120.0,
        symbol="XAUUSD",
        timeframe="M5",
        is_closed=True,
    )

    if feed.on_bar_completed:
        feed.on_bar_completed(bar, False)

    assert len(received_bars) == 1
    c, is_hist = received_bars[0]
    assert c.timeframe == "M5"
    assert c.close == 3953.2
    assert is_hist is False


def test_dukascopy_service_integration():
    """Verify service correctly uses Dukascopy feed and reports state."""
    config = AppConfig(
        symbol="XAUUSD",
        timeframe="M5",
        enable_ticks=False,
        enable_simulation=False,
    )
    svc = EntryStrategyService(config=config, start_servers=False)
    
    state = svc.get_matrix_state()
    assert "feed" in state
    assert state["feed"]["source"] == "DUKASCOPY_ECN"
    assert state["config"]["timeframe"] == "M5"
    assert state["config"]["enable_ticks"] is False

    # Simulate arrival of a completed M5 candle
    now = datetime.now(timezone.utc)
    c1 = Candle(
        timestamp=now - timedelta(minutes=5),
        open=3940.0,
        high=3950.0,
        low=3938.0,
        close=3948.0,
        tick_volume=150.0,
        symbol="XAUUSD",
        timeframe="M5",
        is_closed=True,
    )
    svc._on_bar_completed(c1, is_history=False)
    assert svc.buffer.total_candles == 1
    assert svc.latest_price == 3948.0


def test_dukascopy_live_timeframe_switch():
    """Verify switching timeframe updates both service and Dukascopy feed."""
    config = AppConfig(symbol="XAUUSD", timeframe="M5", enable_ticks=False, enable_simulation=False)
    svc = EntryStrategyService(config=config, start_servers=False)
    
    res = svc.set_timeframe("M1")
    assert res["success"] is True
    assert res["timeframe"] == "M1"
    assert svc.active_timeframe == "M1"
    assert svc.dukascopy_feed.timeframe == "M1"

    # Unsupported timeframe
    res_bad = svc.set_timeframe("H1")
    assert res_bad["success"] is False
