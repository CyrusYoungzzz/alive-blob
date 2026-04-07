"""步态控制器 — GPIO 控制气泵和电磁阀。

在 Pi 上使用 RPi.GPIO，在 Mac/非 Pi 环境自动切换为 Mock GPIO（仅打日志）。

安全机制：
- 气泵最长连续运行 30 秒，超时自动切断
- 启泵前必须先泄压（开阀门等 100ms）
- 进程退出时 GPIO 全部复位（atexit + signal）

步态模式：
- steady: 左右交替，均匀节奏
- pause:  走两步停一下（sleepy）
- asymmetric: 快-慢-快（curious）
- stomp:  重踏步，高占空比（grumpy）
"""

import asyncio
import atexit
import logging
import signal
import time

from config import (
    GAIT_PARAMS,
    GPIO_PUMP,
    GPIO_VALVE_LEFT,
    GPIO_VALVE_RIGHT,
    PUMP_BLEED_MS,
    PUMP_COOLDOWN_SECONDS,
    PUMP_MAX_RUN_SECONDS,
    RELAY_ACTIVE_HIGH,
)

log = logging.getLogger("gait")

# ─── GPIO 抽象层 ───
# Pi 上用 RPi.GPIO，其他平台用 Mock

try:
    import RPi.GPIO as _GPIO
    _GPIO.setmode(_GPIO.BCM)
    _GPIO.setwarnings(False)
    _ON_PI = True
    log.info("Running on Raspberry Pi — real GPIO enabled")
except (ImportError, RuntimeError):
    _ON_PI = False
    log.info("Not on Pi — using mock GPIO (log only)")


class _MockGPIO:
    """Mock GPIO for development on non-Pi machines."""
    BCM = 11
    OUT = 0
    HIGH = 1
    LOW = 0

    @staticmethod
    def setmode(mode): pass

    @staticmethod
    def setwarnings(flag): pass

    @staticmethod
    def setup(pin, mode): pass

    @staticmethod
    def output(pin, value):
        state = "ON" if value else "OFF"
        log.debug(f"[MockGPIO] pin {pin} → {state}")

    @staticmethod
    def cleanup():
        log.info("[MockGPIO] cleanup")


GPIO = _GPIO if _ON_PI else _MockGPIO()


class GaitController:
    """控制气泵和电磁阀，根据情绪驱动步态。"""

    def __init__(self):
        self._pump_on = False
        self._pump_start_time = 0.0
        self._pump_cooldown_until = 0.0
        self._left_open = False
        self._right_open = False
        self._current_emotion = "calm"
        self._intensity = 0.7
        self._running = False
        self._gait_task = None

        # 初始化 GPIO 引脚
        if _ON_PI:
            GPIO.setup(GPIO_PUMP, GPIO.OUT)
            GPIO.setup(GPIO_VALVE_LEFT, GPIO.OUT)
            GPIO.setup(GPIO_VALVE_RIGHT, GPIO.OUT)

        # 确保初始状态：全部关闭
        self._all_off()

        # 注册清理
        atexit.register(self.cleanup)
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, self._signal_handler)

    def _signal_handler(self, signum, frame):
        log.info(f"Received signal {signum}, cleaning up GPIO")
        self.cleanup()
        raise SystemExit(0)

    # ─── 底层 GPIO 操作 ───

    def _pin_on(self, pin):
        val = GPIO.HIGH if RELAY_ACTIVE_HIGH else GPIO.LOW
        GPIO.output(pin, val)

    def _pin_off(self, pin):
        val = GPIO.LOW if RELAY_ACTIVE_HIGH else GPIO.HIGH
        GPIO.output(pin, val)

    def _all_off(self):
        """关闭气泵和所有阀门。"""
        self._pin_off(GPIO_PUMP)
        self._pin_off(GPIO_VALVE_LEFT)
        self._pin_off(GPIO_VALVE_RIGHT)
        self._pump_on = False
        self._left_open = False
        self._right_open = False

    def cleanup(self):
        """安全关闭所有输出并释放 GPIO。"""
        log.info("GPIO cleanup: shutting down pump and valves")
        self._all_off()
        if _ON_PI:
            GPIO.cleanup()

    # ─── 气泵控制（带安全看门狗）───

    async def _start_pump(self):
        """启泵序列：先泄压 → 等待 → 再通电气泵。"""
        now = time.monotonic()

        # 冷却期检查
        if now < self._pump_cooldown_until:
            remaining = self._pump_cooldown_until - now
            log.warning(f"Pump in cooldown, {remaining:.1f}s remaining")
            return

        if self._pump_on:
            return

        # 泄压：先开至少一个阀门
        self._pin_on(GPIO_VALVE_LEFT)
        self._left_open = True
        await asyncio.sleep(PUMP_BLEED_MS / 1000.0)

        # 启动气泵
        self._pin_on(GPIO_PUMP)
        self._pump_on = True
        self._pump_start_time = time.monotonic()
        log.info("Pump ON")

    def _stop_pump(self):
        """停止气泵并进入冷却。"""
        if not self._pump_on:
            return
        self._pin_off(GPIO_PUMP)
        self._pump_on = False
        self._pump_cooldown_until = time.monotonic() + PUMP_COOLDOWN_SECONDS
        log.info("Pump OFF (cooldown)")

    def _check_pump_watchdog(self):
        """看门狗：超过最大运行时间自动切断。"""
        if self._pump_on:
            elapsed = time.monotonic() - self._pump_start_time
            if elapsed >= PUMP_MAX_RUN_SECONDS:
                log.warning(f"Pump watchdog: {elapsed:.0f}s exceeded limit, forcing OFF")
                self._stop_pump()

    # ─── 阀门控制 ───

    def _set_valves(self, left: bool, right: bool):
        """设置左右阀门状态。"""
        if left and not self._left_open:
            self._pin_on(GPIO_VALVE_LEFT)
            self._left_open = True
        elif not left and self._left_open:
            self._pin_off(GPIO_VALVE_LEFT)
            self._left_open = False

        if right and not self._right_open:
            self._pin_on(GPIO_VALVE_RIGHT)
            self._right_open = True
        elif not right and self._right_open:
            self._pin_off(GPIO_VALVE_RIGHT)
            self._right_open = False

    # ─── 步态循环 ───

    def set_emotion(self, emotion: str):
        """切换情绪，步态会在下一个周期自动更新。"""
        if emotion in GAIT_PARAMS:
            self._current_emotion = emotion
            log.info(f"Gait emotion → {emotion}")

    def set_intensity(self, value: float):
        """设置表演强度 (0.0-1.0)。"""
        self._intensity = max(0.0, min(1.0, value))

    @property
    def leg_states(self):
        """返回 [左腿充气比, 右腿充气比]，供 state_sync 使用。"""
        return [1.0 if self._left_open else 0.0, 1.0 if self._right_open else 0.0]

    @property
    def is_pump_on(self):
        return self._pump_on

    async def start(self):
        """启动步态循环。"""
        self._running = True
        self._gait_task = asyncio.create_task(self._gait_loop())
        log.info("Gait controller started")

    async def stop(self):
        """停止步态循环，关闭所有输出。"""
        self._running = False
        if self._gait_task:
            self._gait_task.cancel()
            try:
                await self._gait_task
            except asyncio.CancelledError:
                pass
        self._stop_pump()
        self._all_off()
        log.info("Gait controller stopped")

    async def _gait_loop(self):
        """主步态循环 — 根据当前情绪交替控制阀门。"""
        step_count = 0

        while self._running:
            params = GAIT_PARAMS.get(self._current_emotion, GAIT_PARAMS["calm"])
            step_ms = params["step_ms"]
            duty = params["duty"] * self._intensity
            pattern = params["pattern"]

            # 看门狗检查
            self._check_pump_watchdog()

            # 确保气泵运行
            if not self._pump_on and self._intensity > 0.05:
                await self._start_pump()

            # 如果强度极低，停泵
            if self._intensity <= 0.05:
                self._stop_pump()
                self._set_valves(False, False)
                await asyncio.sleep(0.5)
                continue

            # 根据 pattern 执行步态
            if pattern == "pause" and step_count % 3 == 2:
                # sleepy: 走两步停一下
                self._set_valves(False, False)
                await asyncio.sleep(step_ms / 1000.0 * 1.5)
            elif pattern == "asymmetric":
                # curious: 快-慢-快 不对称节奏
                if step_count % 2 == 0:
                    # 左腿充气（快）
                    self._set_valves(True, False)
                    await asyncio.sleep(step_ms / 1000.0 * duty * 0.6)
                    self._set_valves(False, False)
                    await asyncio.sleep(step_ms / 1000.0 * (1 - duty))
                else:
                    # 右腿充气（慢）
                    self._set_valves(False, True)
                    await asyncio.sleep(step_ms / 1000.0 * duty * 1.4)
                    self._set_valves(False, False)
                    await asyncio.sleep(step_ms / 1000.0 * (1 - duty))
            elif pattern == "stomp":
                # grumpy: 重踏步，高占空比
                self._set_valves(step_count % 2 == 0, step_count % 2 != 0)
                await asyncio.sleep(step_ms / 1000.0 * duty)
                self._set_valves(False, False)
                await asyncio.sleep(step_ms / 1000.0 * (1 - duty) * 0.3)
            else:
                # steady: 标准交替
                is_left = step_count % 2 == 0
                self._set_valves(is_left, not is_left)
                await asyncio.sleep(step_ms / 1000.0 * duty)
                # 短暂双关（让空气流动）
                self._set_valves(False, False)
                await asyncio.sleep(step_ms / 1000.0 * (1 - duty))

            step_count += 1
