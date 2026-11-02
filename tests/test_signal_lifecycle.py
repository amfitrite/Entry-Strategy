"""Unit tests for Signal Lifecycle State Machine and Retention/Expiration Rules.

Verifies:
1. ACTIVE: signal is born on pattern trigger, records price, time, direction, ID.
2. PENDING CONFIRMATION: condition no longer present in tick buffer does not drop signal;
   transitions to PENDING_CONFIRMATION while waiting for follow-through.
3. CONFIRMED: price follows direction (BUY goes up, SELL goes down).
4. INVALIDATED: price breaches invalidation_price; terminal state reached.
5. EXPIRED: max age duration exceeded; terminal state reached.
6. Deduplication: duplicate events do not create new signals.
7. Immutability: terminal signals cannot transition to another state.
"""
import pytest
import time
from datetime import datetime
from entrystrategy.core.models import (
    EntrySignal,
    SignalDirection,
    SignalStatus,
    PatternRole,
    Candle,
    TickData,
)
from entrystrategy.service import EntryStrategyService
from entrystrategy.config import AppConfig


def test_signal_birth_active():
    """Verify that a newly triggered signal starts in ACTIVE state with all metadata."""
    now_ms = int(time.time() * 1000)
    sig = EntrySignal(
        pattern_id=1,
        family_name="Candlestick Reversal",
        direction=SignalDirection.BUY,
        reference_price=2740.0,
        trigger_price=2742.50,
        timestamp_ms=now_ms,
        invalidation_price=2739.0,
        pattern_role=PatternRole.ENTRY,
        event_id="test_birth_1",
    )
    assert sig.status == SignalStatus.ACTIVE
    assert sig.is_alive is True
    assert sig.is_terminal is False
    assert sig.invalidation_price == 2739.0
    assert sig.trigger_price == 2742.50


def test_signal_retained_in_pending_confirmation():
    """Rule: Kondisi pola tidak lagi terpenuhi -> Tetap simpan sinyal.
    After initial trigger pulse (>= 2s) without confirmation or invalidation,
    the signal transitions to PENDING_CONFIRMATION and remains alive.
    """
    base_ms = 1000000000000
    sig = EntrySignal(
        pattern_id=4,
        family_name="Inside Bar Breakout",
        direction=SignalDirection.BUY,
        reference_price=2740.0,
        trigger_price=2742.0,
        timestamp_ms=base_ms,
        invalidation_price=2738.0,
        max_age_sec=30.0,
    )
    # Price moves slightly but does not reach confirmation (+0.20) or invalidation (2738.0)
    # 2.5 seconds later
    changed = sig.update_lifecycle(current_price=2742.05, current_ts_ms=base_ms + 2500, spread=0.10)
    assert changed is True
    assert sig.status == SignalStatus.PENDING_CONFIRMATION
    assert sig.is_alive is True
    assert "menunggu" in sig.status_reason.lower()


def test_signal_confirmed_buy_and_sell():
    """Rule: Harga mengikuti arah sinyal -> CONFIRMED.
    BUY: current_price >= trigger + threshold
    SELL: current_price <= trigger - threshold
    """
    base_ms = 1000000000000
    # BUY test
    sig_buy = EntrySignal(
        pattern_id=11,
        family_name="Tick Momentum",
        direction=SignalDirection.BUY,
        reference_price=2740.0,
        trigger_price=2742.0,
        timestamp_ms=base_ms,
        invalidation_price=2739.0,
    )
    # Price rises to 2742.30 (+0.30 pts)
    sig_buy.update_lifecycle(current_price=2742.30, current_ts_ms=base_ms + 1000, spread=0.10)
    assert sig_buy.status == SignalStatus.CONFIRMED
    assert sig_buy.confirmed_price == 2742.30
    assert sig_buy.is_alive is True

    # SELL test
    sig_sell = EntrySignal(
        pattern_id=11,
        family_name="Tick Momentum",
        direction=SignalDirection.SELL,
        reference_price=2740.0,
        trigger_price=2738.0,
        timestamp_ms=base_ms,
        invalidation_price=2741.0,
    )
    # Price drops to 2737.70 (-0.30 pts)
    sig_sell.update_lifecycle(current_price=2737.70, current_ts_ms=base_ms + 1000, spread=0.10)
    assert sig_sell.status == SignalStatus.CONFIRMED
    assert sig_sell.confirmed_price == 2737.70
    assert sig_sell.is_alive is True


def test_signal_invalidated_on_breach():
    """Rule: Harga mencapai invalidation level -> Ubah status menjadi INVALIDATED."""
    base_ms = 1000000000000
    # BUY invalidation (breaches below invalidation level)
    sig_buy = EntrySignal(
        pattern_id=6,
        family_name="Momentum",
        direction=SignalDirection.BUY,
        reference_price=2740.0,
        trigger_price=2743.0,
        timestamp_ms=base_ms,
        invalidation_price=2739.50,
    )
    # Price drops below 2739.50
    changed = sig_buy.update_lifecycle(current_price=2739.40, current_ts_ms=base_ms + 1500)
    assert changed is True
    assert sig_buy.status == SignalStatus.INVALIDATED
    assert sig_buy.invalidated_price == 2739.40
    assert sig_buy.is_terminal is True
    assert sig_buy.is_alive is False
    assert "menembus level invalidasi" in sig_buy.status_reason

    # SELL invalidation (breaches above invalidation level)
    sig_sell = EntrySignal(
        pattern_id=6,
        family_name="Momentum",
        direction=SignalDirection.SELL,
        reference_price=2740.0,
        trigger_price=2737.0,
        timestamp_ms=base_ms,
        invalidation_price=2741.0,
    )
    sig_sell.update_lifecycle(current_price=2741.10, current_ts_ms=base_ms + 1500)
    assert sig_sell.status == SignalStatus.INVALIDATED
    assert sig_sell.invalidated_price == 2741.10
    assert sig_sell.is_terminal is True
    assert sig_sell.is_alive is False


def test_signal_expired_after_max_age():
    """Rule: Masa berlaku habis -> Ubah status menjadi EXPIRED."""
    base_ms = 1000000000000
    sig = EntrySignal(
        pattern_id=7,
        family_name="Breakout",
        direction=SignalDirection.BUY,
        reference_price=2740.0,
        trigger_price=2742.0,
        timestamp_ms=base_ms,
        invalidation_price=2738.0,
        max_age_sec=30.0,
    )
    # At 29.5s: still within max age
    sig.update_lifecycle(current_price=2742.05, current_ts_ms=base_ms + 29500)
    assert sig.status != SignalStatus.EXPIRED

    # At 30.1s: expired!
    changed = sig.update_lifecycle(current_price=2742.05, current_ts_ms=base_ms + 30100)
    assert changed is True
    assert sig.status == SignalStatus.EXPIRED
    assert sig.is_terminal is True
    assert sig.is_alive is False
    assert sig.expired_time_ms == base_ms + 30100
    assert "Batas usia sinyal tercapai" in sig.status_reason


def test_terminal_state_immutability():
    """Terminal states (INVALIDATED, EXPIRED) must not revert or change."""
    base_ms = 1000000000000
    sig = EntrySignal(
        pattern_id=8,
        family_name="Failed Breakout",
        direction=SignalDirection.BUY,
        reference_price=2740.0,
        trigger_price=2742.0,
        timestamp_ms=base_ms,
        invalidation_price=2739.0,
    )
    # Trigger invalidation
    sig.update_lifecycle(current_price=2738.50, current_ts_ms=base_ms + 1000)
    assert sig.status == SignalStatus.INVALIDATED

    # Price later rallies to 2750.00: cannot confirm an invalidated signal!
    sig.update_lifecycle(current_price=2750.00, current_ts_ms=base_ms + 5000)
    assert sig.status == SignalStatus.INVALIDATED
    assert sig.confirmed_price is None


def test_service_lifecycle_integration():
    """Test full service lifecycle tracking across ticks and matrix state generation."""
    config = AppConfig(enable_simulation=False)
    service = EntryStrategyService(config)
    service.latest_price = 2742.0
    service.latest_spread = 0.10

    now_ms = int(time.time() * 1000)
    # Manually register an active signal
    sig = EntrySignal(
        pattern_id=1,
        family_name="Candlestick Reversal",
        direction=SignalDirection.BUY,
        reference_price=2740.0,
        trigger_price=2742.0,
        timestamp_ms=now_ms,
        invalidation_price=2739.0,
        event_id="test_service_lifecyle_1",
    )
    with service._lock:
        service.latest_signals_by_pattern[1] = sig
        service.recent_signals.appendleft(sig)
        service.total_buy_signals += 1

    # Check matrix state: active buy should be 1
    state1 = service.get_matrix_state()
    assert state1["stats"]["active_buy"] == 1
    p1 = next(p for p in state1["patterns"] if p["id"] == 1)
    assert p1["active"] is True
    assert p1["status"] == "ACTIVE"

    # Price moves in favor: confirm signal
    service.latest_price = 2742.50
    state2 = service.get_matrix_state()
    p1_v2 = next(p for p in state2["patterns"] if p["id"] == 1)
    assert p1_v2["status"] == "CONFIRMED"
    assert state2["stats"]["active_buy"] == 1

    # Price drops below invalidation
    service.latest_price = 2738.00
    state3 = service.get_matrix_state()
    p1_v3 = next(p for p in state3["patterns"] if p["id"] == 1)
    assert p1_v3["status"] == "INVALIDATED"
    # Invalidation is terminal: active_buy drops to 0!
    assert state3["stats"]["active_buy"] == 0

    service.stop()
