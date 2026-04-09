"""赛博皮鞭 × 电容传感器 → 情绪触发测试。

用法：
    python3 whip-test.py              # 双通道模式：识别触摸模式 → 触发情绪 + 步态
    python3 whip-test.py --monitor    # 监控模式：看 ch0 + ch11 原始数据

接线：MPR121 通道 0 和通道 11 各接一片电极（铜箔/铝箔），皮鞭横跨接触。

交互模式：
- 持续双通道接触（ch0 + ch11 同时下降）→ comfortable（舒服）
- 间断单通道接触（快速抽打 3 次）      → crying（哭）
"""

import argparse
import base64
import json
import os
import socket
import struct
import time
import sys

# ─── MPR121 初始化 ───

try:
    import board
    import busio
    import adafruit_mpr121
    i2c = busio.I2C(board.SCL, board.SDA)
    mpr121 = adafruit_mpr121.MPR121(i2c)
    print("MPR121 初始化成功 (I2C 0x5A)")
except Exception as e:
    print(f"MPR121 初始化失败: {e}")
    print("请确认：")
    print("  1. I2C 已启用: sudo raspi-config nonint do_i2c 0")
    print("  2. 驱动已安装: pip3 install adafruit-circuitpython-mpr121")
    print("  3. 接线正确: VCC→3.3V, SDA→GPIO2, SCL→GPIO3")
    sys.exit(1)

# ─── GPIO 初始化（步态联动用）───

try:
    from gpiozero import LED
    pump = LED(18)
    valve_left = LED(23)
    valve_right = LED(24)
    HAS_GPIO = True
    print("GPIO 初始化成功 (pump=18, L=23, R=24)")
except Exception:
    HAS_GPIO = False
    print("GPIO 不可用，仅监控模式")

# ─── 检测参数 ───

CH_LEFT = 0              # 左侧电极通道
CH_RIGHT = 11            # 右侧电极通道
POLL_INTERVAL = 0.02     # 50Hz 采样
BASELINE_ALPHA = 0.05    # 基线更新速率
TOUCH_THRESHOLD = 40     # 电容下降超过此值 = 触摸中

# 模式识别参数
COMFORTABLE_HOLD_TIME = 1.0   # 双通道持续接触 ≥1s → comfortable
WHIP_WINDOW = 3.0             # 间断接触的时间窗口（秒）
WHIP_COUNT = 3                # 窗口内接触 ≥3 次 → crying
WHIP_GAP_MIN = 0.1            # 两次抽打最小间隔（防抖）


# ─── WebSocket 发送情绪到 Eye App ───

ENGINE_HOST = "localhost"
ENGINE_PORT = 8000
ENGINE_PATH = "/ws/mobile"

def send_emotion(emotion):
    """通过原始 WebSocket 发送情绪到 Blob Engine → Eye App 显示屏。无第三方依赖。"""
    try:
        sock = socket.create_connection((ENGINE_HOST, ENGINE_PORT), timeout=2)
        # WebSocket 握手
        key = base64.b64encode(os.urandom(16)).decode()
        req = (
            f"GET {ENGINE_PATH} HTTP/1.1\r\n"
            f"Host: {ENGINE_HOST}:{ENGINE_PORT}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        sock.sendall(req.encode())
        resp = sock.recv(1024)
        if b"101" not in resp:
            sock.close()
            print(f"  [WS] 握手失败")
            return
        # 发送 frame（masked, text）
        payload = json.dumps({"type": "set_emotion", "emotion": emotion}).encode()
        mask_key = os.urandom(4)
        frame = bytearray()
        frame.append(0x81)  # FIN + text opcode
        length = len(payload)
        if length < 126:
            frame.append(0x80 | length)  # masked
        elif length < 65536:
            frame.append(0x80 | 126)
            frame.extend(struct.pack(">H", length))
        frame.extend(mask_key)
        frame.extend(bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload)))
        sock.sendall(frame)
        # 关闭
        close_frame = bytearray([0x88, 0x80]) + os.urandom(4)
        sock.sendall(close_frame)
        sock.close()
        print(f"  [WS] 已发送情绪: {emotion}")
    except Exception as e:
        print(f"  [WS] 发送失败: {e}（Blob Engine 没在运行？）")


class DualChannelDetector:
    """双通道触摸模式检测器。"""

    def __init__(self):
        # 基线
        self.base_l = mpr121[CH_LEFT].raw_value
        self.base_r = mpr121[CH_RIGHT].raw_value
        # 触摸状态
        self.touching_l = False
        self.touching_r = False
        # comfortable 检测
        self.dual_touch_start = 0.0
        # crying 检测：记录单通道触摸事件时间戳
        self.whip_times = []
        # 上次触摸结束时间（用于检测间断）
        self.last_touch_end = 0.0
        self.was_touching = False
        # 当前情绪
        self.emotion = None
        self.emotion_time = 0.0

    def update(self):
        """读取传感器，更新状态，返回 (raw_l, raw_r, delta_l, delta_r, event)。"""
        now = time.time()
        raw_l = mpr121[CH_LEFT].raw_value
        raw_r = mpr121[CH_RIGHT].raw_value
        delta_l = self.base_l - raw_l  # 正值 = 触摸中
        delta_r = self.base_r - raw_r

        # 更新基线（仅在未触摸时）
        if delta_l < TOUCH_THRESHOLD:
            self.base_l = self.base_l * (1 - BASELINE_ALPHA) + raw_l * BASELINE_ALPHA
        if delta_r < TOUCH_THRESHOLD:
            self.base_r = self.base_r * (1 - BASELINE_ALPHA) + raw_r * BASELINE_ALPHA

        # 判断触摸状态
        touch_l = delta_l >= TOUCH_THRESHOLD
        touch_r = delta_r >= TOUCH_THRESHOLD
        any_touch = touch_l or touch_r
        both_touch = touch_l and touch_r

        event = None

        # ─── comfortable 检测：双通道持续接触 ───
        if both_touch:
            if self.dual_touch_start == 0:
                self.dual_touch_start = now
            elif now - self.dual_touch_start >= COMFORTABLE_HOLD_TIME:
                if self.emotion != "comfortable":
                    self.emotion = "comfortable"
                    self.emotion_time = now
                    event = "comfortable"
        else:
            self.dual_touch_start = 0.0

        # ─── crying 检测：间断单通道接触 ───
        # 检测触摸→释放的边沿（一次完整的"抽打"）
        if self.was_touching and not any_touch:
            # 刚松开 — 记录一次抽打
            if now - self.last_touch_end > WHIP_GAP_MIN:
                self.whip_times.append(now)
                self.last_touch_end = now

        # 清理超出时间窗口的记录
        self.whip_times = [t for t in self.whip_times if now - t <= WHIP_WINDOW]

        # 判定
        if len(self.whip_times) >= WHIP_COUNT and self.emotion != "crying":
            self.emotion = "crying"
            self.emotion_time = now
            self.whip_times.clear()
            event = "crying"

        # 更新前一帧状态
        self.was_touching = any_touch
        self.touching_l = touch_l
        self.touching_r = touch_r

        # 情绪超时重置（5 秒无操作回到 None）
        if self.emotion and now - self.emotion_time > 5.0 and not any_touch:
            self.emotion = None

        return raw_l, raw_r, delta_l, delta_r, event


MAX_ROUNDS = 6  # 每次触发只走 6 轮


def gait_crying():
    """哭泣步态 — 快速交替，0.5s 节奏，6 轮。"""
    send_emotion("crying")
    print("  [crying] 快速交替步态 x6")
    pump.on()
    r = valve_right
    l = valve_left
    r.on()
    l.on()
    try:
        for i in range(MAX_ROUNDS):
            time.sleep(0.5)
            r.off()
            time.sleep(0.5)
            r.on()
            time.sleep(0.5)
            l.off()
            time.sleep(0.5)
            l.on()
            print(f"    轮次 {i+1}/{MAX_ROUNDS}")
    finally:
        l.off()
        r.off()
        pump.off()
    print("  [crying] 步态结束")
    send_emotion("sleepy")


def gait_comfortable():
    """舒服步态 — 双腿同时充气1秒，放气1秒，循环3次。"""
    send_emotion("comfortable")
    print("  [comfortable] 双腿同步呼吸 x3")
    pump.on()
    l = valve_left
    r = valve_right
    try:
        for i in range(3):
            l.on()
            r.on()
            time.sleep(1.0)
            l.off()
            r.off()
            time.sleep(1.0)
            print(f"    轮次 {i+1}/3")
    finally:
        l.off()
        r.off()
        pump.off()
    print("  [comfortable] 步态结束")
    send_emotion("sleepy")


def react_mode():
    """双通道模式 — 识别触摸模式，触发情绪 → 执行对应步态。"""
    print("\n=== 赛博皮鞭 · 情绪触发模式 ===")
    print(f"  ch{CH_LEFT}（左电极） + ch{CH_RIGHT}（右电极）")
    print(f"  持续双触 ≥{COMFORTABLE_HOLD_TIME}s → comfortable（舒服慢走 x{MAX_ROUNDS}）")
    print(f"  间断抽打 ×{WHIP_COUNT} → crying（快速交替 x{MAX_ROUNDS}）")
    print("  Ctrl+C 退出\n")

    det = DualChannelDetector()

    try:
        while True:
            raw_l, raw_r, dl, dr, event = det.update()

            # 触摸指示
            tl = "▓" if det.touching_l else "░"
            tr = "▓" if det.touching_r else "░"
            whip_n = len(det.whip_times)
            emo = det.emotion or "—"

            status = f"  ch0={raw_l:4d}(Δ{dl:+4.0f}){tl}  ch11={raw_r:4d}(Δ{dr:+4.0f}){tr}  抽打:{whip_n}/{WHIP_COUNT}  情绪:{emo}"
            print(f"\r{status:<80}", end="", flush=True)

            if event and HAS_GPIO:
                print(f"\n  >>> 触发: {event.upper()} <<<")
                if event == "crying":
                    gait_crying()
                elif event == "comfortable":
                    gait_comfortable()
                # 步态结束后重置检测器，等待下一次交互
                det = DualChannelDetector()
                print("  等待下一次交互...\n")
            elif event:
                print(f"\n  >>> 触发: {event.upper()} <<<（GPIO 不可用，跳过步态）")

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n\n停止")


def monitor_mode():
    """监控模式 — 同时看 ch0 和 ch11 原始数据。"""
    print("\n=== 双通道监控模式 ===")
    print(f"通道 {CH_LEFT}（左） + 通道 {CH_RIGHT}（右）")
    print("Ctrl+C 退出\n")
    print(f"{'时间':>8}  {'ch0':>6}  {'base0':>6}  {'Δ0':>5}  {'ch11':>6}  {'base11':>6}  {'Δ11':>5}  状态")
    print("-" * 75)

    base_l = mpr121[CH_LEFT].raw_value
    base_r = mpr121[CH_RIGHT].raw_value

    try:
        while True:
            raw_l = mpr121[CH_LEFT].raw_value
            raw_r = mpr121[CH_RIGHT].raw_value
            dl = base_l - raw_l
            dr = base_r - raw_r

            if dl < TOUCH_THRESHOLD:
                base_l = base_l * (1 - BASELINE_ALPHA) + raw_l * BASELINE_ALPHA
            if dr < TOUCH_THRESHOLD:
                base_r = base_r * (1 - BASELINE_ALPHA) + raw_r * BASELINE_ALPHA

            status = ""
            if dl >= TOUCH_THRESHOLD and dr >= TOUCH_THRESHOLD:
                status = "双触摸"
            elif dl >= TOUCH_THRESHOLD:
                status = "左触摸"
            elif dr >= TOUCH_THRESHOLD:
                status = "右触摸"

            t = time.strftime("%H:%M:%S")
            print(f"\r{t}  {raw_l:6d}  {base_l:6.0f}  {dl:+5.0f}  {raw_r:6d}  {base_r:6.0f}  {dr:+5.0f}  {status:<10}", end="", flush=True)
            if status:
                print()

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print("\n\n停止监控")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="赛博皮鞭 × 电容传感器 → 情绪触发")
    parser.add_argument("--monitor", action="store_true", help="双通道监控模式")
    parser.add_argument("--threshold", type=int, default=40, help="触摸阈值 (默认 40)")
    args = parser.parse_args()

    TOUCH_THRESHOLD = args.threshold

    if args.monitor:
        monitor_mode()
    else:
        react_mode()
