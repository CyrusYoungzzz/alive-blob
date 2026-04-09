# CLAUDE.md

## What is this

Alive Blob — 48 小时黑客松项目。气动软体机器人，硅胶双腿行走，触摸感应，2.1" 圆形 HDMI 屏显示 AI 表情。运行在 Raspberry Pi 4B 上。

## Quick start

```bash
scripts/setup-pi.sh   # 首次：安装系统依赖
scripts/start.sh      # 启动所有模块
```

Pi 4B 可直接 USB 启动，无需 SD 卡。

## Conventions

- 文档主要用中文，技术术语保留英文
- Commit message: imperative mood, concise scope

## Architecture

三个模块通过 WebSocket (JSON) 通信：

| 模块 | 路径 | 技术栈 | 端口 | 职责 |
|------|------|--------|------|------|
| Blob Engine | `blob-engine/` | Python, websockets | 8000 | 核心大脑：情绪状态机、步态控制、触摸输入 |
| Eye App | `eye-app/` | HTML/JS/CSS | — | 圆屏 480×480 kiosk 模式，播放情绪视频 + 触摸涟漪 |
| Web Server | `server/` | FastAPI | 8080 | REST API + WebSocket 中继，手机控制面板 |

情绪状态：Calm, Happy, Curious, Sleepy, Excited, Shy, Grumpy（7 种）

角色资源在 `characters/{name}/`，每个角色含 `manifest.json` + 7 个情绪 `.mp4`。

启动脚本在 `scripts/`：`setup-pi.sh`（系统依赖）、`start.sh`（启动全部）、`kiosk.sh`（Chromium kiosk）。

## Hardware (修改 GPIO/步态相关代码时参考)

**GPIO 引脚分配：**

| GPIO | 继电器通道 | 控制对象 | 安全限制 |
|------|-----------|---------|---------|
| 18 | CH1 | 12V 气泵 | 连续运行 ≤30s，冷却 ≥2s |
| 23 | CH2 | 左腿电磁阀 | — |
| 24 | CH3 | 右腿电磁阀 | — |

- **I2C (GPIO2/3)** → MPR121 电容触摸传感器，地址 0x5A
- 继电器模块**高电平触发**（GPIO HIGH = 继电器 ON）
- 电源：12V 适配器 → LM2596 降压 → 5V 供 Pi 和屏幕
- **安全规则**：启动气泵前必须先泄压（打开两个阀门）；退出时通过 `atexit` + signal handler 清理 GPIO

## Reference (按需查阅)

- 设计规格：`docs/superpowers/specs/2026-04-01-alive-blob-design.md`
- 接线手册：`docs/wiring-manual.md`
- 硬件清单：`docs/hardware-shopping-list.md`（BOM ~¥350-550）
- 硬件测试记录：`docs/hardware-test-log.md`
