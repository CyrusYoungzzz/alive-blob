"""MPR121 capacitive touch sensor — hit detection with callback.

Extracted from scripts/whip-test.py. Runs in a background thread,
calls on_hit(intensity_label, level) when a strike is detected.

On non-Pi platforms, provides MockTouchSensor that logs only.
"""

import logging
import threading
import time
from typing import Callable, Optional

from config import (
    TOUCH_CHANNEL, TOUCH_POLL_INTERVAL, TOUCH_BASELINE_ALPHA,
    TOUCH_HIT_THRESHOLD, TOUCH_HIT_COOLDOWN,
    TOUCH_MEDIUM_HIT, TOUCH_HEAVY_HIT,
)

log = logging.getLogger("touch")

HitCallback = Callable[[str, int], None]  # (label, level)


def classify_hit(delta: int) -> tuple:
    """Classify hit intensity by capacitance delta. Requires delta >= TOUCH_HIT_THRESHOLD."""
    if delta >= TOUCH_HEAVY_HIT:
        return "重击", 3
    if delta >= TOUCH_MEDIUM_HIT:
        return "中等", 2
    return "轻触", 1


class TouchSensor:
    """MPR121 capacitive sensor reader — runs in background thread."""

    def __init__(self, on_hit: HitCallback):
        self._on_hit = on_hit
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        log.info("TouchSensor started (MPR121 channel %d)", TOUCH_CHANNEL)

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None
        log.info("TouchSensor stopped")

    def _loop(self):
        try:
            import board
            import busio
            import adafruit_mpr121

            i2c = busio.I2C(board.SCL, board.SDA)
            mpr = adafruit_mpr121.MPR121(i2c)
            baseline = mpr[TOUCH_CHANNEL].raw_value
        except Exception:
            log.exception("TouchSensor: I2C init failed, thread exiting")
            self._running = False
            return

        last_hit_time = 0.0

        while self._running:
            try:
                raw = mpr[TOUCH_CHANNEL].raw_value
                delta = raw - baseline

                # Update baseline when no hit
                if abs(delta) < TOUCH_HIT_THRESHOLD:
                    baseline = baseline * (1 - TOUCH_BASELINE_ALPHA) + raw * TOUCH_BASELINE_ALPHA

                # Detect hit
                now = time.time()
                if delta >= TOUCH_HIT_THRESHOLD and (now - last_hit_time > TOUCH_HIT_COOLDOWN):
                    label, level = classify_hit(delta)
                    last_hit_time = now
                    log.info("Hit detected: %s (delta=%+d)", label, delta)
                    try:
                        self._on_hit(label, level)
                    except Exception:
                        log.exception("on_hit callback error")
            except Exception:
                log.exception("TouchSensor: read error")
                time.sleep(0.5)

            time.sleep(TOUCH_POLL_INTERVAL)


class MockTouchSensor:
    """Stub for non-Pi environments — does nothing."""

    def __init__(self, on_hit: HitCallback):
        log.info("MockTouchSensor (no real sensor)")

    def start(self):
        pass

    def stop(self):
        pass


def create_touch_sensor(on_hit: HitCallback):
    """Factory: returns real sensor on Pi, mock otherwise."""
    try:
        import board  # noqa: F401
        return TouchSensor(on_hit)
    except ImportError:
        return MockTouchSensor(on_hit)
