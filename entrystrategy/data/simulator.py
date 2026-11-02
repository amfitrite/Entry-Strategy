"""Synthetic Tick and Candle Generator for instant preview and verification."""
import threading
import time
import random
from datetime import datetime, timezone, timedelta
from typing import Callable, Optional
from entrystrategy.core.models import TickData, Candle


class MarketSimulator:
    """Generates realistic XAUUSD ticks and bars for testing the 40 entry patterns."""
    def __init__(
        self,
        base_price: float = 2745.0,
        interval_ms: int = 250,
        on_tick: Optional[Callable[[TickData], None]] = None,
        on_bar: Optional[Callable[[Candle], None]] = None,
    ):
        self.base_price = base_price
        self.interval_ms = interval_ms
        self.on_tick = on_tick
        self.on_bar = on_bar
        
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.current_px = base_price
        self.bar_start_px = base_price
        self.bar_high = base_price
        self.bar_low = base_price
        self.bar_ticks = 0
        self.current_bar_min = datetime.now(timezone.utc).minute

    def start(self):
        if self.running:
            return
        self.running = True
        self._seed_initial_bars()
        self.thread = threading.Thread(target=self._loop, daemon=True, name="SimulatorThread")
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)

    def _seed_initial_bars(self):
        """Pre-populate historical bars for both M1 and M5 so candle patterns have context immediately."""
        now = datetime.now(timezone.utc)
        
        # 1. Seed M1 bars
        px = self.base_price - 3.0
        for i in range(25, 0, -1):
            dt = now - timedelta(minutes=i)
            o = px
            rng = random.uniform(0.6, 2.2)
            direction = random.choice([1, -1, 1])
            c = o + (direction * random.uniform(0.2, rng))
            h = max(o, c) + random.uniform(0.05, 0.4)
            l = min(o, c) - random.uniform(0.05, 0.4)
            candle_m1 = Candle(
                timestamp=dt,
                open=round(o, 2),
                high=round(h, 2),
                low=round(l, 2),
                close=round(c, 2),
                tick_volume=random.randint(60, 240),
                spread=1.4,
                symbol="XAUUSD",
                timeframe="M1",
                is_closed=True,
            )
            if self.on_bar:
                self.on_bar(candle_m1)
            px = c

        # 2. Seed M5 bars (Default Timeframe)
        px_m5 = self.base_price - 6.0
        for i in range(25, 0, -1):
            dt_m5 = now - timedelta(minutes=i * 5)
            o = px_m5
            rng = random.uniform(1.2, 4.0)
            direction = random.choice([1, -1, 1])
            c = o + (direction * random.uniform(0.4, rng))
            h = max(o, c) + random.uniform(0.1, 0.8)
            l = min(o, c) - random.uniform(0.1, 0.8)
            candle_m5 = Candle(
                timestamp=dt_m5,
                open=round(o, 2),
                high=round(h, 2),
                low=round(l, 2),
                close=round(c, 2),
                tick_volume=random.randint(250, 1000),
                spread=1.4,
                symbol="XAUUSD",
                timeframe="M5",
                is_closed=True,
            )
            if self.on_bar:
                self.on_bar(candle_m5)
            px_m5 = c

        self.current_px = px
        self.bar_start_px = px
        self.bar_high = px
        self.bar_low = px

    def _loop(self):
        while self.running:
            # Generate micro drift
            # 80% micro noise, 20% burst move
            if random.random() < 0.15:
                delta = random.choice([0.25, -0.25, 0.4, -0.4, 0.6, -0.6])
            else:
                delta = random.uniform(-0.08, 0.08)

            self.current_px = round(self.current_px + delta, 2)
            self.bar_high = max(self.bar_high, self.current_px)
            self.bar_low = min(self.bar_low, self.current_px)
            self.bar_ticks += 1

            now_dt = datetime.now(timezone.utc)
            spread = random.choice([1.2, 1.4, 1.5, 1.6])
            half_spread = spread / 20.0  # 1.5 pips = 0.15 pts

            tick = TickData(
                ts_ms=int(time.time() * 1000),
                bid=round(self.current_px - half_spread, 2),
                ask=round(self.current_px + half_spread, 2),
                last=self.current_px,
                volume=random.choice([1.0, 2.0, 5.0]),
                symbol="XAUUSD",
            )
            if self.on_tick:
                self.on_tick(tick)

            # Check minute roll
            if now_dt.minute != self.current_bar_min:
                completed_m1 = Candle(
                    timestamp=now_dt.replace(second=0, microsecond=0) - timedelta(minutes=1),
                    open=round(self.bar_start_px, 2),
                    high=round(self.bar_high, 2),
                    low=round(self.bar_low, 2),
                    close=round(self.current_px, 2),
                    tick_volume=self.bar_ticks,
                    spread=1.4,
                    symbol="XAUUSD",
                    timeframe="M1",
                    is_closed=True,
                )
                if self.on_bar:
                    self.on_bar(completed_m1)

                # Check 5-minute roll
                if now_dt.minute % 5 == 0:
                    completed_m5 = Candle(
                        timestamp=now_dt.replace(second=0, microsecond=0) - timedelta(minutes=5),
                        open=round(self.bar_start_px, 2),
                        high=round(self.bar_high, 2),
                        low=round(self.bar_low, 2),
                        close=round(self.current_px, 2),
                        tick_volume=self.bar_ticks * 5,
                        spread=1.4,
                        symbol="XAUUSD",
                        timeframe="M5",
                        is_closed=True,
                    )
                    if self.on_bar:
                        self.on_bar(completed_m5)
                
                self.current_bar_min = now_dt.minute
                self.bar_start_px = self.current_px
                self.bar_high = self.current_px
                self.bar_low = self.current_px
                self.bar_ticks = 0

            time.sleep(self.interval_ms / 1000.0)
