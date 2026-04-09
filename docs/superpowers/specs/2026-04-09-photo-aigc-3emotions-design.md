# Photo + AIGC + 3-Emotion System Design

**Date**: 2026-04-09
**Status**: Draft
**Scope**: 全链路改造 — 情绪系统 7→3 + 即梦 API 真实 AIGC 集成

---

## 1. 概述

将 Alive Blob 的情绪系统从 7 种简化为 3 种（困、舒服、哭），并用即梦（火山引擎）API 替换 MockAIGCService，实现拍照→AI 卡通风格化→情绪图生成→圆屏显示的���整链路。

### 1.1 目标

- 跑通拍照 → 即梦 img2img → 3 张情绪卡通图 → 圆屏显示的完整流程
- 全链路情绪系统从 7 种缩减为 3 种
- 保持现有架构不变，最小改动

### 1.2 新情绪系统

| 情绪 ID | 中文 | 触发条件 | 默认 |
|---------|------|---------|------|
| `sleepy` | 困 | 无交互（默认状态） | 是 |
| `comfortable` | 舒服 | 轻拍触摸 | 否 |
| `crying` | 哭 | 重拍触摸 | 否 |

### 1.3 状态机

```
启动 → sleepy
轻触 → comfortable → (衰减 ~5s) → sleepy
重触 → crying → (衰减 ~8s) → sleepy
```

---

## 2. AIGC 服务：即梦 API 集成

### 2.1 API 信息

- **Endpoint**: `https://ark.cn-beijing.volces.com/api/v3/images/generations`
- **Model**: `doubao-seedream-4-0-250828`
- **Auth**: Bearer Token (`ARK_API_KEY` 环境变量)
- **能力**: img2img（传 `image` 参数 + prompt）

### 2.2 生成流程

```
用户拍照 → POST /api/characters (FormData: name, photo)
  → 保存 source.jpg
  → 将 source.jpg 转为 base64 data URI
  → 并发 3 次即梦 img2img 调用（asyncio.gather）
    ├── prompt_sleepy   → sleepy.png
    ├── prompt_comfortable → comfortable.png
    └── prompt_crying   → crying.png
  → 下载生成图片 URL → 缩放到 480×480
  → 更新 manifest.json status: "ready"
```

### 2.3 Prompt 设计

```python
EMOTION_PROMPTS = {
    "sleepy": "将这张人脸照片转换为可爱的卡通风格，表情是困倦的、眼睛半闭、打瞌睡的样子，柔和的色调",
    "comfortable": "将这张人脸照片转换为可爱的卡通风格，表情是舒服享受的、微笑眯眼、被轻轻抚摸的感觉，温暖的色调",
    "crying": "将这张人脸照片转换为可爱的卡通风格，表情是哭泣的、眼泪汪汪、委屈的样子，偏蓝冷色调",
}
```

### 2.4 img2img 请求体

```json
{
    "model": "doubao-seedream-4-0-250828",
    "prompt": "<emotion_prompt>",
    "image": ["data:image/jpeg;base64,<base64_data>"],
    "size": "2048x2048",
    "response_format": "url",
    "watermark": false
}
```

### 2.5 错误处理

- API Key 缺失 → 回退到 MockAIGCService
- 单个情绪生成失败 → 重试 1 次，仍失败则用 Mock 占位
- 超时 → 120s timeout
- 生成的 URL 24h 过期 → 必须立即下载保存

### 2.6 图片后处理

- 即梦输出 2048×2048 → Pillow 缩放到 480×480
- 保存为 PNG（匹配现有格式）

---

## 3. 改动文件清单

### 3.1 server/aigc_service.py

- 新增 `JimengAIGCService` 类，实现 `AIGCService` Protocol
- 3 个情绪 prompt，并发 img2img 调用
- 图片下载 + 缩放到 480×480
- 保留 `MockAIGCService` 作为回退
- 新增依赖：`httpx`（异步 HTTP 客户端）

### 3.2 server/main.py

- 根据 `ARK_API_KEY` 环境变量选择 Jimeng 或 Mock 服务
- 情绪列表从 7 改为 3

### 3.3 blob-engine/config.py

- `EMOTIONS` 列表：`["sleepy", "comfortable", "crying"]`
- `DEFAULT_EMOTION`: `"sleepy"`
- 步态参数适配 3 情绪

### 3.4 blob-engine/engine.py

- 默认情绪 → `sleepy`
- 移除多余的 7 情绪处理逻辑
- state_sync 消息中的情绪值适配

### 3.5 blob-engine/gait_controller.py

- 步态映射：
  - `sleepy` → 慢步（低频率，低占空比）
  - `comfortable` → 稳步（中等节奏）
  - `crying` → 停步或颤抖（快速微动）

### 3.6 eye-app/cube.js

- 3D Cube 情绪参数从 7 组缩减为 3 组
- `sleepy`：深蓝色，低噪声，小眼睛，平嘴
- `comfortable`：暖橙色，柔和噪声，眯眼，微笑
- `crying`：蓝紫色，高噪声，大眼睛（泪），下弯嘴

### 3.7 eye-app/player.js

- 情绪处理逻辑适配 3 种
- 自定义角色显示 AIGC 生成的对应情绪 PNG

### 3.8 server/static/index.html

- 控制面板情绪按钮从 7 个改为 3 个大按钮
- 按钮标签：困 / 舒服 / 哭

### 3.9 server/static/style.css

- 按钮样式适配 3 个情绪

---

## 4. 角色包结构

```
characters/{name}/
├── manifest.json
├── source.jpg          # 原始上传照片
├── sleepy.png          # 480×480 卡通困倦图
├── comfortable.png     # 480×480 卡通舒服图
└── crying.png          # 480×480 卡通哭泣图
```

**manifest.json**:
```json
{
  "name": "角色名",
  "status": "ready",
  "emotions": {
    "sleepy": "sleepy.png",
    "comfortable": "comfortable.png",
    "crying": "crying.png"
  }
}
```

Status 流转：`"generating"` → `"ready"` | `"error: ..."`

---

## 5. 依赖变更

### Python (server/requirements.txt)

新增：
```
httpx>=0.27.0
```

### 环境变量

```bash
ARK_API_KEY=<即梦火山引擎 API Key>
```

---

## 6. 测试策略

- **单元测试**：Mock httpx 验证请求体格式、错误处理、重试逻辑
- **集成测试**：用真实 API Key 生成一组图片，验证完整流程
- **手动验证**：在圆屏上查看 3 种情绪图的显示效果

---

## 7. 不做的事

- 不重构 WebSocket 消息协议
- 不改角色系统架构
- 不加新的 UI 页面
- 不做 prompt 调优（先跑通，后迭代）
