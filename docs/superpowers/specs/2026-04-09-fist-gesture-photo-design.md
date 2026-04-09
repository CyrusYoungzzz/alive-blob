# 捏拳手势拍照功能设计

## 概述

在手机控制面板 Page 2（添加角色页）的摄像头画面上，新增 MediaPipe Hands 手势检测。用户张开手掌后握拳，即可触发拍照，替代手动点击快门按钮。拍照后复用现有的人脸检测 → 预览确认 → AIGC 生成流程。

## 交互流程

```
进入 Page 2 → 打开摄像头 + 加载 face-api + 加载 MediaPipe Hands
                    ↓
           实时检测手部 landmarks (21 关键点)
                    ↓
      检测到"张开手掌" → 提示 "保持... 握拳拍照！"
                    ↓
        检测到"握拳" → 触发 captureAndDetect()
                    ↓
   face-api 检测人脸 → 预览选择 → 命名 → 上传 AIGC
```

现有的快门按钮 + Space 快捷键保持不变，手势是新增的触发方式。

## 手势��定逻辑

使用 MediaPipe Hands JS SDK 检测 21 个手部关键点。

### 张开手掌判定

4 根手指（食指到小指）都伸直：每根手指的���尖（tip）y 坐标 < 指间关节（PIP）y 坐标。

```
手指     指尖 landmark    PIP landmark
食指     8               6
中指     12              10
无名指   16              14
小指     20              18
```

判定为"张开"：4 根手指的 tip.y < pip.y（屏幕坐标系，y 向下）。

### 握拳判定

4 根手指都弯曲：每根手指的 tip.y > pip.y。

### 状态机

```
IDLE → (检测到张开 ≥300ms) → OPEN → (检测到握拳 ≥300ms) → TRIGGER → (拍照) → COOLDOWN(2s) → IDLE
```

- **IDLE**：等待张开手掌
- **OPEN**：手掌已张开，等待握拳
- **TRIGGER**：握拳确认，调用 `captureAndDetect()`
- **COOLDOWN**：2 秒冷却期，防止重复触发

300ms 的持续时间要求避免误触发。

## UI 变更

### 手势提示条

在摄像头画面底部叠加半透明提示条 `#gesture-hint`：

| 状态 | 提示文字 | 样式 |
|------|---------|------|
| 无手 / IDLE | "伸开手掌，握拳拍照" | 灰色半透明 |
| OPEN（手掌张开） | "保持... 握拳拍照！" | 绿色，脉冲动画 |
| TRIGGER | "拍摄中..." | 白色闪烁 |
| COOLDOWN | 隐藏 | — |

### 手部 landmarks 可视化

在 canvas overlay 上绘制手部关键点连线（半透明绿色），与现有的人脸检测绿框共存。

## 技术选型

### MediaPipe Hands JS

使用 `@mediapipe/hands` + `@mediapipe/camera_utils` CDN：
- 浏览器端运行，无需服务器计算
- 支持单手检测（`maxNumHands: 1`，够用且性能更好）
- 模型轻量，手机端可实时运行

CDN 加载：
```html
<script src="https://cdn.jsdelivr.net/npm/@mediapipe/hands/hands.js" crossorigin="anonymous"></script>
```

注意：MediaPipe Hands 有自己的摄像头输入循环，需要与现有的 `getUserMedia` + face-api 检测循环协调。方案是共用同一个 `<video>` 元素，将 video 帧同时送给 face-api 和 MediaPipe Hands。

## 改动范围

| 文件 | 改动内容 | 估算行数 |
|------|---------|---------|
| `server/static/index.html` | 加载 MediaPipe Hands CDN；新增 `#gesture-hint` DOM | ~5 行 |
| `server/static/app.js` | 手势检测模块：初始化 Hands、手势分类、状态机、与 captureAndDetect 对接 | ~80 行 |
| `server/static/style.css` | `#gesture-hint` 提示条样式 + 动画 | ~15 行 |

**不改后端**。拍照后的流程完全复用现有的 `captureAndDetect()` → face-api → upload API。

## 兼容性

- MediaPipe Hands JS 需要 WebGL 支持（现代手机浏览器均支持）
- 若 MediaPipe 加载失败，静默降级：只有快门按钮和 Space 可用，不影响现有功能
- face-api.js 和 MediaPipe Hands 共用同一 video 元素，互不干扰

## 测试策略

1. 手机 Chrome/Safari 打开 Page 2，验证摄像头 + 手势检测正常启动
2. 张开手掌 → 握拳 → 验证自动拍照触发
3. 连续握拳 → 验证 2 秒冷却期生效
4. 只用快门按钮 → 验证原有流程不受影响
5. MediaPipe 加载失败场景 → 验证降级到手动模式
