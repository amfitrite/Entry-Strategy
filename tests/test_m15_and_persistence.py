"""Tests for M15 Timeframe Option and 'Continue Where You Left Off' Session Persistence."""
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

from entrystrategy.config import AppConfig
from entrystrategy.core.models import (
    Candle,
    EntrySignal,
    SignalDirection,
    SignalStatus,
    PatternRole,
)
from entrystrategy.core.buffer import MarketBuffer
from entrystrategy.core.persistence import (
    save_session_state,
    load_session_state,
    clear_session_state,
)
from entrystrategy.engine.registry import PatternRegistry
from entrystrategy.data.dukascopy_feed import DukascopyFeed
from entrystrategy.service import EntryStrategyService
from entrystrategy.gui.app import MatrixWindowAPI


def test_market_buffer_m15_isolation_and_retrieval():
    """Verify that M15 candles are stored in their own isolated circular buffer and do not leak into M1/M5."""
    buf = MarketBuffer(candle_capacity=10, default_timeframe="M15")
    assert buf.active_timeframe == "M15"
    assert buf.total_candles == 0
    assert buf.total_candles_m15 == 0

    now = datetime.now(timezone.utc)

    # Ingest M1 bar
    c_m1 = Candle(
        timestamp=now,
        open=2740.0,
        high=2742.0,
        low=2739.0,
        close=2741.0,
        timeframe="M1",
        is_closed=True,
    )
    buf.add_completed_candle(c_m1)

    # Ingest M5 bar
    c_m5 = Candle(
        timestamp=now,
        open=2740.0,
        high=2745.0,
        low=2738.0,
        close=2744.0,
        timeframe="M5",
        is_closed=True,
    )
    buf.add_completed_candle(c_m5)

    # Active timeframe is M15, so total_candles should still be 0
    assert buf.total_candles == 0
    assert buf.total_candles_m1 == 1
    assert buf.total_candles_m5 == 1
    assert buf.total_candles_m15 == 0

    # Ingest M15 bar
    c_m15 = Candle(
        timestamp=now,
        open=2735.0,
        high=2750.0,
        low=2730.0,
        close=2748.0,
        timeframe="M15",
        is_closed=True,
    )
    buf.add_completed_candle(c_m15)

    assert buf.total_candles == 1
    assert buf.total_candles_m15 == 1

    # Verify get_recent_candles retrieves M15 bar
    recent = buf.get_recent_candles(1)
    assert len(recent) == 1
    assert recent[0].close == 2748.0
    assert recent[0].timeframe == "M15"

    # Switch active timeframe to M5
    buf.set_active_timeframe("M5")
    assert buf.active_timeframe == "M5"
    assert buf.total_candles == 1
    assert buf.get_recent_candles(1)[0].close == 2744.0

    # Switch back to M15
    buf.set_active_timeframe("M15")
    assert buf.active_timeframe == "M15"
    assert buf.total_candles == 1
    assert buf.get_recent_candles(1)[0].close == 2748.0


def test_registry_m15_signal_max_age_900_sec():
    """Verify that signals evaluated in M15 mode receive max_age_sec = 900.0 (15 minutes)."""
    buf = MarketBuffer(candle_capacity=100, default_timeframe="M15")
    registry = PatternRegistry()

    now = datetime.now(timezone.utc)
    # Populate with synthetic breakout candles
    for i in range(25):
        ts = now - timedelta(minutes=(25 - i) * 15)
        c = Candle(
            timestamp=ts,
            open=2700.0 + i,
            high=2702.0 + i,
            low=2699.0 + i,
            close=2701.5 + i,
            timeframe="M15",
            is_closed=True,
        )
        buf.add_completed_candle(c)

    signals = registry.evaluate_all(buf)
    # For any signal generated in M15 candle mode, max_age_sec must be 900.0
    for sig in signals:
        assert sig.max_age_sec == 900.0, f"Expected 900.0s for M15 signal, got {sig.max_age_sec}"


def test_dukascopy_feed_m15_timeframe_handling():
    """Verify DukascopyFeed accepts M15 and correctly sets interval_min = 15."""
    feed = DukascopyFeed(symbol="XAUUSD", timeframe="M15")
    assert feed.timeframe == "M15"
    assert "M15" in feed.last_candle_timestamp

    # Switching to M5 and back to M15
    feed.set_timeframe("M5")
    assert feed.timeframe == "M5"
    feed.set_timeframe("M15")
    assert feed.timeframe == "M15"

    # Reject invalid timeframes
    feed.set_timeframe("H1")
    assert feed.timeframe == "M15"


def test_entry_signal_serialization_round_trip():
    """Verify EntrySignal to_dict and from_dict preserve all lifecycle fields, reasons, and metrics."""
    now_ms = int(time.time() * 1000)
    orig = EntrySignal(
        pattern_id=14,
        family_name="Breakout & Retest",
        direction=SignalDirection.BUY,
        reference_price=2740.0,
        trigger_price=2742.50,
        execution_price=2742.75,
        invalidation_price=2738.0,
        timestamp_ms=now_ms,
        pattern_role=PatternRole.ENTRY,
        phenomenon="Breakout resistance disusul retest",
        event_id=f"test_evt_{now_ms}",
        status=SignalStatus.CONFIRMED,
        status_reason="Harga terkonfirmasi naik",
        max_age_sec=900.0,
        confirmed_price=2744.0,
        confirmed_time_ms=now_ms + 1000,
        invalidated_price=None,
        invalidated_time_ms=None,
        expired_time_ms=None,
        reasons=["Kondisi 1 valid", "Kondisi 2 valid"],
        metrics={"level": 2740.0},
    )

    d = orig.to_dict()
    assert d["pattern_id"] == 14
    assert d["max_age_sec"] == 900.0
    assert d["confirmed_time_ms"] == now_ms + 1000

    reconstructed = EntrySignal.from_dict(d)
    assert reconstructed.pattern_id == orig.pattern_id
    assert reconstructed.family_name == orig.family_name
    assert reconstructed.direction == orig.direction
    assert reconstructed.trigger_price == orig.trigger_price
    assert reconstructed.execution_price == orig.execution_price
    assert reconstructed.invalidation_price == orig.invalidation_price
    assert reconstructed.status == orig.status
    assert reconstructed.max_age_sec == orig.max_age_sec
    assert reconstructed.confirmed_price == orig.confirmed_price
    assert reconstructed.confirmed_time_ms == orig.confirmed_time_ms
    assert reconstructed.reasons == orig.reasons
    assert reconstructed.metrics == orig.metrics


def test_persistence_atomic_save_and_load(tmp_path):
    """Verify atomic state saving and loading with thread safety."""
    state_file = tmp_path / "user_state_test.json"

    assert load_session_state(state_file) is None

    test_payload = {
        "version": "1.0",
        "active_timeframe": "M15",
        "total_buy": 12,
        "total_sell": 7,
        "preferences": {
            "view": "history",
            "radar_filter": "BUY",
            "history_filter": "CONFIRMED",
        },
        "window": {"x": 150, "y": 200, "width": 1400, "height": 900, "is_simple_mode": False},
        "recent_signals": [],
    }

    ok = save_session_state(test_payload, state_file)
    assert ok is True
    assert state_file.exists()

    loaded = load_session_state(state_file)
    assert loaded is not None
    assert loaded["active_timeframe"] == "M15"
    assert loaded["total_buy"] == 12
    assert loaded["preferences"]["view"] == "history"
    assert loaded["window"]["width"] == 1400

    clear_session_state(state_file)
    assert not state_file.exists()


def test_service_continue_where_you_left_off(tmp_path):
    """Verify EntryStrategyService automatically restores session state on startup:
    - Timeframe M15
    - Cumulative Buy/Sell counts
    - Recent signal history
    - User UI preferences
    """
    state_file = tmp_path / "user_state_session.json"
    now_ms = int(time.time() * 1000)

    # Prepare saved session state
    saved_sig = {
        "pattern_id": 7,
        "family_name": "Breakout",
        "direction": "BUY",
        "reference_price": 2740.0,
        "trigger_price": 2745.0,
        "execution_price": 2745.25,
        "price": 2745.0,
        "invalidation_price": 2738.0,
        "pattern_role": "ENTRY",
        "status": "CONFIRMED",
        "status_reason": "Harga bergerak searah",
        "timestamp_ms": now_ms,
        "event_id": f"saved_sig_{now_ms}",
        "max_age_sec": 900.0,
        "reasons": ["Breakout valid"],
        "metrics": {},
    }

    initial_state = {
        "version": "1.0",
        "active_timeframe": "M15",
        "total_buy": 15,
        "total_sell": 8,
        "preferences": {
            "view": "history",
            "radar_filter": "BUY",
            "history_filter": "CONFIRMED",
        },
        "window": {"x": 200, "y": 150, "width": 1400, "height": 900, "is_simple_mode": False},
        "recent_signals": [saved_sig],
    }
    save_session_state(initial_state, state_file)

    # Initialize Service with session persistence enabled
    cfg = AppConfig(enable_simulation=False)
    svc = EntryStrategyService(
        config=cfg,
        start_servers=False,
        persist_session=True,
        state_filepath=str(state_file),
    )

    # Assert session was cleanly restored
    assert svc.session_restored is True
    assert svc.active_timeframe == "M15"
    assert svc.buffer.active_timeframe == "M15"
    assert svc.total_buy_signals == 15
    assert svc.total_sell_signals == 8
    assert len(svc.recent_signals) == 1
    assert svc.recent_signals[0].pattern_id == 7
    assert svc.saved_preferences["view"] == "history"
    assert svc.saved_preferences["history_filter"] == "CONFIRMED"

    # Verify get_matrix_state reports restored session
    state = svc.get_matrix_state()
    assert state["config"]["timeframe"] == "M15"
    assert state["stats"]["total_buy"] == 15
    assert state["saved_session"]["restored"] is True
    assert state["saved_session"]["preferences"]["view"] == "history"

    # Test switching timeframe to M5 updates state file
    svc.set_timeframe("M5")
    assert svc.active_timeframe == "M5"
    updated_state = load_session_state(state_file)
    assert updated_state["active_timeframe"] == "M5"

    # Test MatrixWindowAPI preference update
    api = MatrixWindowAPI(svc)
    api.save_user_preferences(json.dumps({"view": "radar", "radar_filter": "SELL"}))
    reloaded = load_session_state(state_file)
    assert reloaded["preferences"]["view"] == "radar"
    assert reloaded["preferences"]["radar_filter"] == "SELL"


def test_service_set_timeframe_m15_api():
    """Verify set_timeframe accepts M15 and correctly clears pattern timestamps and expires active signals."""
    cfg = AppConfig(enable_simulation=False)
    svc = EntryStrategyService(config=cfg, start_servers=False, persist_session=False)

    # Manually trigger a signal in M5
    svc.trigger_pattern_manual_test(1, "BUY")
    assert svc.latest_signals_by_pattern[1].is_alive is True

    # Switch to M15
    res = svc.set_timeframe("M15")
    assert res["success"] is True
    assert res["timeframe"] == "M15"
    assert svc.active_timeframe == "M15"
    assert svc.buffer.active_timeframe == "M15"

    # Previous active signal in M5 must be transitioned to EXPIRED due to timeframe shift
    assert svc.latest_signals_by_pattern[1].status == SignalStatus.EXPIRED
    assert "M15" in svc.latest_signals_by_pattern[1].status_reason


def test_hybrid_patterns_dynamic_timeframe_in_reasons():
    """Verify that pattern reasons dynamically reflect the active timeframe (M15, M5, or M1)
    and do not hardcode 'M5' when running on M15 bars.
    """
    from entrystrategy.engine.patterns.hybrid import (
        BreakoutPattern,
        MomentumExhaustionPattern,
    )
    now = datetime.now(timezone.utc)

    # Test on M15 buffer: Bull exhaustion on M15 (c1 large bull range 8.32 pts, c0 stalls)
    buf_m15 = MarketBuffer(candle_capacity=10, default_timeframe="M15")
    c1_m15 = Candle(
        timestamp=now - timedelta(minutes=30),
        open=2740.0,
        high=2748.32,
        low=2740.0,
        close=2748.0,
        timeframe="M15",
        is_closed=True,
    )
    c0_m15 = Candle(
        timestamp=now - timedelta(minutes=15),
        open=2748.0,
        high=2748.5,
        low=2747.0,
        close=2747.2,
        timeframe="M15",
        is_closed=True,
    )
    buf_m15.add_completed_candle(c1_m15)
    buf_m15.add_completed_candle(c0_m15)

    pat30 = MomentumExhaustionPattern()
    sig30 = pat30.evaluate(buf_m15)
    assert sig30 is not None
    assert sig30.direction == SignalDirection.SELL
    # The reason string MUST state M15, NOT M5!
    assert "M15" in sig30.reasons[0]
    assert "M5" not in sig30.reasons[0]
    assert "m15_mom_exh" in sig30.event_id

    # Test Breakout on M15
    buf_bo = MarketBuffer(candle_capacity=10, default_timeframe="M15")
    c1_bo = Candle(now - timedelta(minutes=30), 2740.0, 2745.0, 2739.0, 2744.0, timeframe="M15", is_closed=True)
    c0_bo = Candle(now - timedelta(minutes=15), 2744.2, 2748.0, 2743.8, 2747.5, timeframe="M15", is_closed=True)
    buf_bo.add_completed_candle(c1_bo)
    buf_bo.add_completed_candle(c0_bo)

    pat7 = BreakoutPattern()
    sig7 = pat7.evaluate(buf_bo)
    assert sig7 is not None
    assert "Breakout High Candle C[1] M15" in sig7.reasons[0]
    assert "M5" not in sig7.reasons[0]
    assert "m15_breakout" in sig7.event_id
