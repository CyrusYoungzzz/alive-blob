"""Blob Engine configuration constants."""

WS_PORT = 8000
DEFAULT_CHARACTER = "default"
DEFAULT_EMOTION = "calm"
STATE_SYNC_INTERVAL_MS = 500

EMOTIONS = ["calm", "happy", "excited", "curious", "sleepy", "shy", "grumpy"]

# ─── GPIO 引脚 ───
GPIO_PUMP = 18       # 继电器 IN1 → 气泵
GPIO_VALVE_LEFT = 23  # 继电器 IN2 → 左腿电磁阀
GPIO_VALVE_RIGHT = 24 # 继电器 IN3 → 右腿电磁阀

# 继电器触发方式: True = 高电平触发 (HIGH = 吸合)
RELAY_ACTIVE_HIGH = True

# ─── 气泵安全 ───
PUMP_MAX_RUN_SECONDS = 30   # 最长连续运行
PUMP_COOLDOWN_SECONDS = 2   # 冷却时间
PUMP_BLEED_MS = 100         # 启泵前泄压等待时间

# ─── 步态参数 ───
# step_ms: 一步时间（左→右为一步）
# duty: 充气占空比（0.8=猛烈, 0.3=轻柔）
# pattern: 步态模式
GAIT_PARAMS = {
    "calm":    {"step_ms": 2000, "duty": 0.5, "pattern": "steady"},
    "happy":   {"step_ms": 500,  "duty": 0.5, "pattern": "steady"},
    "excited": {"step_ms": 200,  "duty": 0.5, "pattern": "steady"},
    "sleepy":  {"step_ms": 3000, "duty": 0.3, "pattern": "pause"},
    "curious": {"step_ms": 800,  "duty": 0.6, "pattern": "asymmetric"},
    "shy":     {"step_ms": 1500, "duty": 0.3, "pattern": "steady"},
    "grumpy":  {"step_ms": 600,  "duty": 0.8, "pattern": "stomp"},
}
