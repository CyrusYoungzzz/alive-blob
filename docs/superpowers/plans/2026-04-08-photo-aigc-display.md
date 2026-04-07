# 手机拍照 → AIGC 生成表情 → 圆屏展示 实现计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用户在手机浏览器上传/拍照一张人脸照片，后端调用 AIGC API 生成 7 种情绪表情图片，组成角色包，在 2.1 寸圆屏上展示当前情绪对应的表情图片。

**Architecture:** 三个模块按设计规范搭建：FastAPI Server (port 8080) 处理 REST API 和静态文件；Blob Engine (port 8000) 运行 WebSocket 服务连接 Eye App 和手机；Eye App 全屏显示图片。AIGC 服务设计为可插拔接口，MVP 阶段用 mock 实现（生成带文字标注的占位图）。

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, websockets, Pillow (mock AIGC), HTML5/JS/CSS

---

## 文件结构

```
alive-blob/
├── blob-engine/
│   ├── engine.py              # 最小 WebSocket 服务器 + 主循环
│   ├── config.py              # 配置常量
│   └── requirements.txt
│
├── server/
│   ├── main.py                # FastAPI 入口
│   ├── routes.py              # REST API 路由（上传、角色管理）
│   ├── aigc_service.py        # AIGC 可插拔接口 + mock 实现
│   ├── requirements.txt
│   └── static/                # 手机控制面板
│       ├── index.html         # SPA 入口
│       ├── app.js             # 上传逻辑 + WebSocket + 角色管理
│       └── style.css          # 移动端样式
│
├── eye-app/
│   ├── index.html             # 全屏图片展示
│   ├── style.css              # 圆屏适配样式
│   ├── player.js              # 图片显示 + 情绪切换 + 过渡动效
│   └── ws.js                  # WebSocket 客户端
│
├── characters/                # 角色包存储（运行时生成）
│
├── scripts/
│   └── start.sh               # 启动所有模块
│
└── tests/
    ├── test_aigc_service.py    # AIGC 服务测试
    ├── test_routes.py          # API 路由测试
    └── test_engine.py          # Engine WebSocket 测试
```

---

## Chunk 1: 后端基础 — Server + AIGC 服务

### Task 1: 项目初始化 + Python 依赖

**Files:**
- Create: `server/requirements.txt`
- Create: `blob-engine/requirements.txt`

- [ ] **Step 1: 创建 server/requirements.txt**

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
python-multipart==0.0.9
Pillow==10.4.0
aiofiles==24.1.0
```

- [ ] **Step 2: 创建 blob-engine/requirements.txt**

```
websockets==12.0
```

- [ ] **Step 3: 安装依赖**

Run: `cd /Users/cyrus/Desktop/alive-blob && python3 -m venv .venv && source .venv/bin/activate && pip install -r server/requirements.txt -r blob-engine/requirements.txt`

- [ ] **Step 4: Commit**

```bash
git add server/requirements.txt blob-engine/requirements.txt
git commit -m "feat: add Python dependencies for server and engine"
```

---

### Task 2: AIGC 可插拔服务 + Mock 实现

**Files:**
- Create: `server/aigc_service.py`
- Create: `tests/test_aigc_service.py`

- [ ] **Step 1: 写失败测试**

`tests/test_aigc_service.py`:
```python
import pytest
import asyncio
from pathlib import Path
from server.aigc_service import MockAIGCService, EMOTIONS

def test_emotions_list():
    assert len(EMOTIONS) == 7
    assert "calm" in EMOTIONS
    assert "grumpy" in EMOTIONS

@pytest.mark.asyncio
async def test_mock_generates_all_emotions(tmp_path):
    service = MockAIGCService()
    # 创建一个假的输入图片
    from PIL import Image
    src = tmp_path / "face.jpg"
    Image.new("RGB", (200, 200), "white").save(src)

    results = await service.generate_emotions(src, tmp_path / "output")
    assert len(results) == 7
    for emotion in EMOTIONS:
        assert emotion in results
        assert Path(results[emotion]).exists()
        # 验证输出是 480x480 PNG
        img = Image.open(results[emotion])
        assert img.size == (480, 480)

@pytest.mark.asyncio
async def test_mock_handles_missing_source(tmp_path):
    service = MockAIGCService()
    with pytest.raises(FileNotFoundError):
        await service.generate_emotions(tmp_path / "nonexistent.jpg", tmp_path)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/cyrus/Desktop/alive-blob && python -m pytest tests/test_aigc_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'server.aigc_service'`

- [ ] **Step 3: 实现 AIGC 服务**

`server/aigc_service.py`:
```python
"""AIGC 表情生成服务 — 可插拔接口 + Mock 实现。

接口：generate_emotions(source_image, output_dir) → dict[emotion, path]
Mock 实现：用 Pillow 生成带情绪文字标注的 480x480 占位图。
替换为真实 API 时只需实现 AIGCService 协议。
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Protocol, runtime_checkable

EMOTIONS = ["calm", "happy", "excited", "curious", "sleepy", "shy", "grumpy"]

EMOTION_COLORS = {
    "calm": "#4A90D9",
    "happy": "#F5A623",
    "excited": "#D0021B",
    "curious": "#7B68EE",
    "sleepy": "#8B8682",
    "shy": "#FFB6C1",
    "grumpy": "#2F4F4F",
}

EMOTION_LABELS = {
    "calm": "😌 Calm",
    "happy": "😄 Happy",
    "excited": "🤩 Excited",
    "curious": "🤔 Curious",
    "sleepy": "😴 Sleepy",
    "shy": "😳 Shy",
    "grumpy": "😤 Grumpy",
}


@runtime_checkable
class AIGCService(Protocol):
    async def generate_emotions(
        self, source_image: Path, output_dir: Path
    ) -> dict[str, str]:
        """从源照片生成 7 种情绪图片，返回 {emotion: file_path}。"""
        ...


class MockAIGCService:
    """Mock AIGC — 用 Pillow 生成带文字的彩色占位图。"""

    async def generate_emotions(
        self, source_image: Path, output_dir: Path
    ) -> dict[str, str]:
        if not source_image.exists():
            raise FileNotFoundError(f"Source image not found: {source_image}")

        output_dir.mkdir(parents=True, exist_ok=True)
        results = {}

        from PIL import Image, ImageDraw, ImageFont

        # 尝试加载源图片作为底图
        try:
            base_img = Image.open(source_image).resize((480, 480))
        except Exception:
            base_img = Image.new("RGB", (480, 480), "#333333")

        for emotion in EMOTIONS:
            img = base_img.copy()
            draw = ImageDraw.Draw(img)
            # 半透明色块覆盖
            overlay = Image.new("RGBA", (480, 480), EMOTION_COLORS[emotion] + "80")
            img = Image.alpha_composite(img.convert("RGBA"), overlay)
            draw = ImageDraw.Draw(img)
            # 情绪文字
            label = EMOTION_LABELS[emotion]
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
            except OSError:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), label, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(((480 - tw) / 2, (480 - th) / 2), label, fill="white", font=font)
            # 保存为 PNG
            out_path = output_dir / f"{emotion}.png"
            img.convert("RGB").save(out_path)
            results[emotion] = str(out_path)

        return results
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/cyrus/Desktop/alive-blob && python -m pytest tests/test_aigc_service.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/aigc_service.py tests/test_aigc_service.py
git commit -m "feat: add pluggable AIGC service with mock implementation"
```

---

### Task 3: FastAPI 服务器 + REST API

**Files:**
- Create: `server/__init__.py`（空文件）
- Create: `server/main.py`
- Create: `server/routes.py`
- Create: `tests/test_routes.py`
- Create: `tests/__init__.py`（空文件）

- [ ] **Step 1: 创建 __init__.py 文件**

创建空的 `server/__init__.py` 和 `tests/__init__.py`。

- [ ] **Step 2: 写 API 路由测试**

`tests/test_routes.py`:
```python
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from server.main import create_app

@pytest.fixture
def client(tmp_path):
    app = create_app(characters_dir=tmp_path / "characters")
    return TestClient(app)

def test_list_characters_empty(client):
    resp = client.get("/api/characters")
    assert resp.status_code == 200
    assert resp.json() == []

def test_create_character_with_photo(client, tmp_path):
    # 创建一个测试图片
    from PIL import Image
    import io
    img = Image.new("RGB", (200, 200), "red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    resp = client.post(
        "/api/characters",
        data={"name": "test-boss"},
        files={"photo": ("face.jpg", buf, "image/jpeg")},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-boss"
    assert data["status"] == "generating"

def test_list_characters_after_create(client, tmp_path):
    from PIL import Image
    import io
    img = Image.new("RGB", (200, 200), "red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    client.post(
        "/api/characters",
        data={"name": "boss"},
        files={"photo": ("face.jpg", buf, "image/jpeg")},
    )
    resp = client.get("/api/characters")
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert "boss" in names

def test_get_character_detail(client, tmp_path):
    from PIL import Image
    import io
    img = Image.new("RGB", (200, 200), "red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    client.post(
        "/api/characters",
        data={"name": "detail-test"},
        files={"photo": ("face.jpg", buf, "image/jpeg")},
    )
    resp = client.get("/api/characters/detail-test")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "detail-test"
    assert "emotions" in data

def test_delete_character(client, tmp_path):
    from PIL import Image
    import io
    img = Image.new("RGB", (200, 200), "red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    buf.seek(0)

    client.post(
        "/api/characters",
        data={"name": "to-delete"},
        files={"photo": ("face.jpg", buf, "image/jpeg")},
    )
    resp = client.delete("/api/characters/to-delete")
    assert resp.status_code == 200

    resp = client.get("/api/characters/to-delete")
    assert resp.status_code == 404

def test_status_endpoint(client):
    resp = client.get("/api/status")
    assert resp.status_code == 200
    assert "ok" in resp.json()["status"]
```

- [ ] **Step 3: 运行测试确认失败**

Run: `python -m pytest tests/test_routes.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: 实现 server/main.py**

```python
"""FastAPI 应用入口。"""

from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

def create_app(characters_dir: Path | None = None) -> FastAPI:
    if characters_dir is None:
        characters_dir = Path(__file__).parent.parent / "characters"
    characters_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="Alive Blob Server")
    app.state.characters_dir = characters_dir

    from server.routes import router
    app.include_router(router, prefix="/api")

    # 角色包图片静态服务
    app.mount("/characters", StaticFiles(directory=str(characters_dir)), name="characters")

    # 手机控制面板静态文件
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app

app = create_app()
```

- [ ] **Step 5: 实现 server/routes.py**

```python
"""REST API 路由 — 角色管理 + 照片上传 + AIGC 生成。"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, BackgroundTasks

from server.aigc_service import MockAIGCService, EMOTIONS

router = APIRouter()

def _characters_dir(request: Request) -> Path:
    return request.app.state.characters_dir

def _read_manifest(char_dir: Path) -> dict | None:
    manifest = char_dir / "manifest.json"
    if not manifest.exists():
        return None
    return json.loads(manifest.read_text())

def _write_manifest(char_dir: Path, data: dict):
    (char_dir / "manifest.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))


@router.get("/status")
async def status():
    return {"status": "ok"}


@router.get("/characters")
async def list_characters(request: Request):
    chars_dir = _characters_dir(request)
    result = []
    for d in sorted(chars_dir.iterdir()):
        if not d.is_dir():
            continue
        manifest = _read_manifest(d)
        if manifest is None:
            continue
        emotions_ready = [e for e in EMOTIONS if (d / f"{e}.png").exists()]
        result.append({
            "name": d.name,
            "display_name": manifest.get("name", d.name),
            "emotions_ready": len(emotions_ready),
            "emotions_total": len(EMOTIONS),
            "status": manifest.get("status", "ready"),
        })
    return result


@router.get("/characters/{name}")
async def get_character(name: str, request: Request):
    char_dir = _characters_dir(request) / name
    if not char_dir.exists():
        raise HTTPException(404, f"Character '{name}' not found")
    manifest = _read_manifest(char_dir)
    if manifest is None:
        raise HTTPException(404, f"Character '{name}' has no manifest")
    emotions = {}
    for e in EMOTIONS:
        img_path = char_dir / f"{e}.png"
        emotions[e] = {"ready": img_path.exists(), "url": f"/characters/{name}/{e}.png" if img_path.exists() else None}
    return {"name": name, "display_name": manifest.get("name", name), "emotions": emotions, "status": manifest.get("status", "ready")}


@router.post("/characters", status_code=201)
async def create_character(
    request: Request,
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    photo: UploadFile = File(...),
):
    chars_dir = _characters_dir(request)
    char_dir = chars_dir / name
    if char_dir.exists():
        raise HTTPException(409, f"Character '{name}' already exists")
    char_dir.mkdir(parents=True)

    # 保存上传的原始照片
    source_path = char_dir / "source.jpg"
    content = await photo.read()
    source_path.write_bytes(content)

    # 创建 manifest
    manifest = {
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "generating",
        "videos": {},
    }
    _write_manifest(char_dir, manifest)

    # 后台生成 AIGC 图片
    async def _generate():
        service = MockAIGCService()
        try:
            results = await service.generate_emotions(source_path, char_dir)
            manifest["status"] = "ready"
            manifest["videos"] = {e: f"{e}.png" for e in results}
            _write_manifest(char_dir, manifest)
        except Exception as exc:
            manifest["status"] = f"error: {exc}"
            _write_manifest(char_dir, manifest)

    background_tasks.add_task(_generate)

    return {"name": name, "status": "generating"}


@router.delete("/characters/{name}")
async def delete_character(name: str, request: Request):
    char_dir = _characters_dir(request) / name
    if not char_dir.exists():
        raise HTTPException(404, f"Character '{name}' not found")
    shutil.rmtree(char_dir)
    return {"deleted": name}
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_routes.py -v`
Expected: 6 tests PASS

- [ ] **Step 7: Commit**

```bash
git add server/ tests/
git commit -m "feat: add FastAPI server with character upload and AIGC generation"
```

---

## Chunk 2: Eye App + Engine + 手机控制面板

### Task 4: Blob Engine — 最小 WebSocket 服务

**Files:**
- Create: `blob-engine/config.py`
- Create: `blob-engine/engine.py`
- Create: `tests/test_engine.py`

- [ ] **Step 1: 写 Engine 测试**

`tests/test_engine.py`:
```python
import pytest
import asyncio
import json
import websockets

# Engine 配置
WS_PORT = 18765  # 测试用端口，避免冲突

@pytest.mark.asyncio
async def test_engine_echo_emotion():
    """测试: 手机发 set_emotion → Engine 转发 play_emotion 给 Eye App"""
    from blob_engine.engine import BlobEngine

    engine = BlobEngine(port=WS_PORT, characters_dir="/tmp/test-chars")
    task = asyncio.create_task(engine.start())

    try:
        await asyncio.sleep(0.3)  # 等 engine 启动

        # Eye App 连接
        eye_ws = await websockets.connect(f"ws://localhost:{WS_PORT}/ws/eye")
        # 手机连接
        mobile_ws = await websockets.connect(f"ws://localhost:{WS_PORT}/ws/mobile")

        # 手机发送情绪指令
        await mobile_ws.send(json.dumps({"type": "set_emotion", "emotion": "happy"}))

        # Eye App 应收到 play_emotion
        msg = await asyncio.wait_for(eye_ws.recv(), timeout=2)
        data = json.loads(msg)
        assert data["type"] == "play_emotion"
        assert "happy" in data["image_path"]

        await eye_ws.close()
        await mobile_ws.close()
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/test_engine.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 blob-engine/config.py**

```python
"""Blob Engine 配置常量。"""

WS_PORT = 8000
DEFAULT_CHARACTER = "default"
DEFAULT_EMOTION = "calm"
STATE_SYNC_INTERVAL_MS = 500

EMOTIONS = ["calm", "happy", "excited", "curious", "sleepy", "shy", "grumpy"]
```

- [ ] **Step 4: 实现 blob-engine/engine.py**

```python
"""Blob Engine — 最小 WebSocket 服务器。

MVP 功能：
- /ws/eye 端点: Eye App 连接
- /ws/mobile 端点: 手机客户端连接
- 手机发 set_emotion → 转发 play_emotion 给 Eye App
- 手机发 switch_character → 更新当前角色
- 定时推送 state_sync 给手机
"""

import asyncio
import json
import logging
from pathlib import Path

import websockets
from websockets.server import serve

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("engine")

class BlobEngine:
    def __init__(self, port: int = 8000, characters_dir: str = "characters"):
        self.port = port
        self.characters_dir = Path(characters_dir)
        self.eye_ws = None
        self.mobile_clients: set = set()
        self.current_emotion = "calm"
        self.current_character = None
        self._running = False

    async def start(self):
        self._running = True
        # 自动检测第一个可用角色
        if self.characters_dir.exists():
            for d in sorted(self.characters_dir.iterdir()):
                if (d / "manifest.json").exists():
                    self.current_character = d.name
                    break

        async with serve(self._handler, "0.0.0.0", self.port):
            log.info(f"Engine WebSocket server on port {self.port}")
            sync_task = asyncio.create_task(self._state_sync_loop())
            try:
                await asyncio.Future()  # 永远运行
            finally:
                sync_task.cancel()

    async def _handler(self, websocket):
        path = websocket.request.path if hasattr(websocket, 'request') else websocket.path
        if path == "/ws/eye":
            await self._handle_eye(websocket)
        elif path == "/ws/mobile":
            await self._handle_mobile(websocket)
        else:
            await websocket.close(4004, "Unknown path")

    async def _handle_eye(self, ws):
        self.eye_ws = ws
        log.info("Eye App connected")
        # 立即发送当前状态
        await self._send_play_emotion()
        try:
            async for msg in ws:
                pass  # Eye App 目前不发消息给 Engine
        finally:
            self.eye_ws = None
            log.info("Eye App disconnected")

    async def _handle_mobile(self, ws):
        self.mobile_clients.add(ws)
        log.info(f"Mobile connected ({len(self.mobile_clients)} total)")
        try:
            async for msg in ws:
                await self._handle_mobile_message(json.loads(msg))
        finally:
            self.mobile_clients.discard(ws)
            log.info(f"Mobile disconnected ({len(self.mobile_clients)} total)")

    async def _handle_mobile_message(self, data: dict):
        msg_type = data.get("type")
        if msg_type == "set_emotion":
            self.current_emotion = data["emotion"]
            log.info(f"Emotion → {self.current_emotion}")
            await self._send_play_emotion()
        elif msg_type == "switch_character":
            self.current_character = data["name"]
            log.info(f"Character → {self.current_character}")
            await self._send_play_emotion()
        elif msg_type == "list_characters":
            chars = []
            if self.characters_dir.exists():
                for d in sorted(self.characters_dir.iterdir()):
                    if (d / "manifest.json").exists():
                        chars.append(d.name)
            for ws in list(self.mobile_clients):
                try:
                    await ws.send(json.dumps({"type": "characters_list", "characters": chars}))
                except Exception:
                    pass

    async def _send_play_emotion(self):
        if self.eye_ws is None or self.current_character is None:
            return
        image_path = f"/characters/{self.current_character}/{self.current_emotion}.png"
        msg = json.dumps({
            "type": "play_emotion",
            "image_path": image_path,
            "emotion": self.current_emotion,
            "transition": "crossfade",
            "transition_ms": 800,
        })
        try:
            await self.eye_ws.send(msg)
        except Exception:
            log.warning("Failed to send to Eye App")

    async def _state_sync_loop(self):
        while True:
            await asyncio.sleep(0.5)
            state = json.dumps({
                "type": "state_sync",
                "emotion": self.current_emotion,
                "character": self.current_character,
                "intensity": 0.7,
            })
            for ws in list(self.mobile_clients):
                try:
                    await ws.send(state)
                except Exception:
                    self.mobile_clients.discard(ws)


if __name__ == "__main__":
    engine = BlobEngine()
    asyncio.run(engine.start())
```

- [ ] **Step 5: 添加 blob_engine/__init__.py**

创建空文件 `blob-engine/__init__.py`。

注意：测试中用 `blob_engine` 导入，需要确保 Python 路径正确。在项目根目录创建 `pyproject.toml` 或用 `PYTHONPATH`。

- [ ] **Step 6: 运行测试确认通过**

Run: `cd /Users/cyrus/Desktop/alive-blob && PYTHONPATH=blob-engine:. python -m pytest tests/test_engine.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add blob-engine/ tests/test_engine.py
git commit -m "feat: add minimal Blob Engine WebSocket server"
```

---

### Task 5: Eye App — 圆屏图片展示

**Files:**
- Create: `eye-app/index.html`
- Create: `eye-app/style.css`
- Create: `eye-app/player.js`
- Create: `eye-app/ws.js`

- [ ] **Step 1: 创建 eye-app/index.html**

```html
<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=480, initial-scale=1.0, user-scalable=no">
  <title>Alive Blob Eye</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <div id="screen">
    <img id="layer-a" class="emotion-img active" src="" alt="">
    <img id="layer-b" class="emotion-img" src="" alt="">
    <div id="status-dot"></div>
  </div>
  <script src="ws.js"></script>
  <script src="player.js"></script>
</body>
</html>
```

- [ ] **Step 2: 创建 eye-app/style.css**

```css
* { margin: 0; padding: 0; box-sizing: border-box; }

html, body {
  width: 480px;
  height: 480px;
  overflow: hidden;
  background: #000;
}

#screen {
  position: relative;
  width: 480px;
  height: 480px;
  border-radius: 50%;
  overflow: hidden;
  background: #111;
}

.emotion-img {
  position: absolute;
  top: 0; left: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  opacity: 0;
  transition: opacity 0.8s ease-in-out;
}

.emotion-img.active {
  opacity: 1;
}

#status-dot {
  position: absolute;
  bottom: 20px;
  right: 20px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #f00;
}

#status-dot.connected {
  background: #0f0;
}

/* 情绪切换时的背景色 */
#screen.emotion-happy { background: #FFF8E1; }
#screen.emotion-excited { background: #FFEBEE; }
#screen.emotion-curious { background: #E8EAF6; }
#screen.emotion-sleepy { background: #ECEFF1; }
#screen.emotion-shy { background: #FCE4EC; }
#screen.emotion-grumpy { background: #263238; }
#screen.emotion-calm { background: #E3F2FD; }
```

- [ ] **Step 3: 创建 eye-app/ws.js**

```javascript
/** WebSocket 客户端 — 连接 Blob Engine */
const EyeWS = (() => {
  const ENGINE_URL = `ws://${location.hostname}:8000/ws/eye`;
  let ws = null;
  let onMessage = null;

  function connect() {
    ws = new WebSocket(ENGINE_URL);
    ws.onopen = () => {
      console.log('[WS] Connected to Engine');
      document.getElementById('status-dot').classList.add('connected');
    };
    ws.onclose = () => {
      console.log('[WS] Disconnected, reconnecting in 2s...');
      document.getElementById('status-dot').classList.remove('connected');
      setTimeout(connect, 2000);
    };
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (onMessage) onMessage(data);
    };
    ws.onerror = () => ws.close();
  }

  return {
    connect,
    set onMessage(fn) { onMessage = fn; },
  };
})();
```

- [ ] **Step 4: 创建 eye-app/player.js**

```javascript
/** 图片播放器 — 双层交叉淡入淡出 */
(() => {
  const layerA = document.getElementById('layer-a');
  const layerB = document.getElementById('layer-b');
  const screen = document.getElementById('screen');
  let currentLayer = layerA;

  // 获取服务器基础 URL（图片从 FastAPI 的 /characters/ 静态路由获取）
  const SERVER_BASE = `http://${location.hostname}:8080`;

  function showEmotion(imagePath, emotion) {
    const nextLayer = currentLayer === layerA ? layerB : layerA;
    const fullUrl = SERVER_BASE + imagePath;

    nextLayer.onload = () => {
      // 切换 active
      currentLayer.classList.remove('active');
      nextLayer.classList.add('active');
      currentLayer = nextLayer;

      // 更新背景色
      screen.className = '';
      screen.classList.add(`emotion-${emotion}`);
    };
    nextLayer.src = fullUrl;
  }

  // 监听 Engine 消息
  EyeWS.onMessage = (data) => {
    if (data.type === 'play_emotion') {
      showEmotion(data.image_path, data.emotion);
    }
  };

  // 启动连接
  EyeWS.connect();
})();
```

- [ ] **Step 5: Commit**

```bash
git add eye-app/
git commit -m "feat: add Eye App with image display and WebSocket connection"
```

---

### Task 6: 手机控制面板 — 拍照上传 + 情绪控制

**Files:**
- Create: `server/static/index.html`
- Create: `server/static/app.js`
- Create: `server/static/style.css`

- [ ] **Step 1: 创建 server/static/index.html**

```html
<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Alive Blob 控制面板</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <!-- 底部标签栏 -->
  <nav id="tabs">
    <button class="tab active" data-tab="home">🏠</button>
    <button class="tab" data-tab="emotion">😊</button>
    <button class="tab" data-tab="upload">📷</button>
  </nav>

  <!-- Home 标签页 -->
  <section id="page-home" class="page active">
    <h2>Alive Blob</h2>
    <div id="current-status">
      <div class="status-row">
        <span>角色</span>
        <span id="s-character">--</span>
      </div>
      <div class="status-row">
        <span>情绪</span>
        <span id="s-emotion">--</span>
      </div>
      <div id="preview-img-container">
        <img id="preview-img" src="" alt="当前表情">
      </div>
    </div>
  </section>

  <!-- Emotion 标签页 -->
  <section id="page-emotion" class="page">
    <h2>情绪控制</h2>
    <div id="emotion-grid"></div>
  </section>

  <!-- Upload 标签页 -->
  <section id="page-upload" class="page">
    <h2>角色管理</h2>
    <div id="upload-form">
      <input type="text" id="char-name" placeholder="角色名称（英文）">
      <label id="photo-label" for="photo-input">
        📷 选择照片或拍照
        <input type="file" id="photo-input" accept="image/*" capture="environment">
      </label>
      <div id="photo-preview-container" style="display:none">
        <img id="photo-preview" src="" alt="预览">
      </div>
      <button id="btn-create" disabled>🚀 生成表情包</button>
      <div id="upload-status"></div>
    </div>
    <h3>已有角色</h3>
    <div id="character-list"></div>
  </section>

  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 2: 创建 server/static/style.css**

```css
* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #0a0a0a;
  color: #e0e0e0;
  min-height: 100vh;
  padding-bottom: 70px;
}

/* 标签栏 */
#tabs {
  position: fixed;
  bottom: 0;
  left: 0; right: 0;
  display: flex;
  background: #1a1a1a;
  border-top: 1px solid #333;
  z-index: 100;
}

.tab {
  flex: 1;
  padding: 14px;
  font-size: 24px;
  background: none;
  border: none;
  cursor: pointer;
  opacity: 0.5;
}

.tab.active { opacity: 1; }

/* 页面 */
.page { display: none; padding: 20px; }
.page.active { display: block; }
.page h2 { margin-bottom: 16px; font-size: 20px; }
.page h3 { margin: 20px 0 10px; font-size: 16px; color: #888; }

/* 状态 */
.status-row {
  display: flex;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid #222;
  font-size: 16px;
}

#preview-img-container {
  margin-top: 16px;
  text-align: center;
}

#preview-img {
  max-width: 200px;
  border-radius: 50%;
  border: 3px solid #333;
}

/* 情绪按钮网格 */
#emotion-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.emotion-btn {
  padding: 20px;
  font-size: 18px;
  border: 2px solid #333;
  border-radius: 12px;
  background: #1a1a1a;
  color: #e0e0e0;
  cursor: pointer;
  text-align: center;
}

.emotion-btn.active {
  border-color: #4A90D9;
  background: #1a2a3a;
}

/* 上传表单 */
#upload-form input[type="text"] {
  width: 100%;
  padding: 12px;
  font-size: 16px;
  background: #1a1a1a;
  border: 1px solid #333;
  border-radius: 8px;
  color: #e0e0e0;
  margin-bottom: 12px;
}

#photo-label {
  display: block;
  padding: 16px;
  text-align: center;
  background: #1a1a1a;
  border: 2px dashed #444;
  border-radius: 12px;
  cursor: pointer;
  font-size: 16px;
  margin-bottom: 12px;
}

#photo-label input { display: none; }

#photo-preview {
  max-width: 100%;
  max-height: 200px;
  border-radius: 8px;
  margin: 8px 0;
}

#btn-create {
  width: 100%;
  padding: 14px;
  font-size: 18px;
  background: #4A90D9;
  color: white;
  border: none;
  border-radius: 12px;
  cursor: pointer;
}

#btn-create:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

#upload-status {
  margin-top: 12px;
  padding: 8px;
  text-align: center;
  font-size: 14px;
  color: #888;
}

/* 角色列表 */
.char-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  background: #1a1a1a;
  border-radius: 8px;
  margin-bottom: 8px;
}

.char-card .name { font-weight: bold; }
.char-card .status { font-size: 12px; color: #888; }

.char-card button {
  padding: 6px 12px;
  border-radius: 6px;
  border: 1px solid #333;
  background: #222;
  color: #e0e0e0;
  cursor: pointer;
  font-size: 13px;
}

.char-card button.use-btn { border-color: #4A90D9; }
.char-card button.del-btn { border-color: #D0021B; color: #D0021B; }
```

- [ ] **Step 3: 创建 server/static/app.js**

```javascript
/** 手机控制面板 — 上传照片、情绪控制、角色管理 */
(() => {
  const API = '';  // 同源，FastAPI 服务
  const ENGINE_WS = `ws://${location.hostname}:8000/ws/mobile`;
  let ws = null;
  let currentCharacter = null;
  let currentEmotion = 'calm';

  // ─── Tab 切换 ───
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById(`page-${tab.dataset.tab}`).classList.add('active');
      if (tab.dataset.tab === 'upload') refreshCharacterList();
    });
  });

  // ─── WebSocket 连接 Engine ───
  function connectWS() {
    ws = new WebSocket(ENGINE_WS);
    ws.onopen = () => console.log('[Mobile WS] Connected');
    ws.onclose = () => {
      console.log('[Mobile WS] Disconnected, reconnecting...');
      setTimeout(connectWS, 2000);
    };
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.type === 'state_sync') {
        currentEmotion = data.emotion;
        currentCharacter = data.character;
        updateHomeStatus(data);
        updateEmotionGrid();
      }
    };
    ws.onerror = () => ws.close();
  }

  function sendWS(msg) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(msg));
    }
  }

  // ─── Home 状态更新 ───
  function updateHomeStatus(state) {
    document.getElementById('s-character').textContent = state.character || '--';
    document.getElementById('s-emotion').textContent = state.emotion || '--';
    const img = document.getElementById('preview-img');
    if (state.character && state.emotion) {
      img.src = `${API}/characters/${state.character}/${state.emotion}.png`;
      img.style.display = 'block';
    } else {
      img.style.display = 'none';
    }
  }

  // ─── 情绪控制 ───
  const EMOTIONS = [
    { id: 'calm', label: '😌 平静' },
    { id: 'happy', label: '😄 开心' },
    { id: 'excited', label: '🤩 兴奋' },
    { id: 'curious', label: '🤔 好奇' },
    { id: 'sleepy', label: '😴 困倦' },
    { id: 'shy', label: '😳 害羞' },
    { id: 'grumpy', label: '😤 不爽' },
  ];

  const emotionGrid = document.getElementById('emotion-grid');
  EMOTIONS.forEach(em => {
    const btn = document.createElement('button');
    btn.className = 'emotion-btn';
    btn.dataset.emotion = em.id;
    btn.textContent = em.label;
    btn.addEventListener('click', () => {
      sendWS({ type: 'set_emotion', emotion: em.id });
    });
    emotionGrid.appendChild(btn);
  });

  function updateEmotionGrid() {
    document.querySelectorAll('.emotion-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.emotion === currentEmotion);
    });
  }

  // ─── 照片上传 ───
  const photoInput = document.getElementById('photo-input');
  const photoPreview = document.getElementById('photo-preview');
  const previewContainer = document.getElementById('photo-preview-container');
  const charNameInput = document.getElementById('char-name');
  const btnCreate = document.getElementById('btn-create');
  const uploadStatus = document.getElementById('upload-status');

  photoInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      photoPreview.src = ev.target.result;
      previewContainer.style.display = 'block';
      checkCreateReady();
    };
    reader.readAsDataURL(file);
  });

  charNameInput.addEventListener('input', checkCreateReady);

  function checkCreateReady() {
    btnCreate.disabled = !(charNameInput.value.trim() && photoInput.files.length);
  }

  btnCreate.addEventListener('click', async () => {
    const name = charNameInput.value.trim();
    const file = photoInput.files[0];
    if (!name || !file) return;

    btnCreate.disabled = true;
    uploadStatus.textContent = '⏳ 上传中...';

    const formData = new FormData();
    formData.append('name', name);
    formData.append('photo', file);

    try {
      const resp = await fetch(`${API}/api/characters`, { method: 'POST', body: formData });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || resp.statusText);
      }
      uploadStatus.textContent = '🎨 AI 正在生成表情包...';

      // 轮询等待生成完成
      await pollCharacterReady(name);

      uploadStatus.textContent = '✅ 生成完成！';
      // 自动切换到新角色
      sendWS({ type: 'switch_character', name });
      refreshCharacterList();

      // 重置表单
      charNameInput.value = '';
      photoInput.value = '';
      previewContainer.style.display = 'none';
    } catch (err) {
      uploadStatus.textContent = `❌ ${err.message}`;
    }
    btnCreate.disabled = false;
  });

  async function pollCharacterReady(name, maxWait = 60000) {
    const start = Date.now();
    while (Date.now() - start < maxWait) {
      await new Promise(r => setTimeout(r, 1000));
      const resp = await fetch(`${API}/api/characters/${name}`);
      if (!resp.ok) continue;
      const data = await resp.json();
      if (data.status === 'ready') return;
      if (data.status.startsWith('error')) throw new Error(data.status);
    }
    throw new Error('生成超时');
  }

  // ─── 角色列表 ───
  const characterList = document.getElementById('character-list');

  async function refreshCharacterList() {
    try {
      const resp = await fetch(`${API}/api/characters`);
      const chars = await resp.json();
      characterList.innerHTML = '';
      chars.forEach(c => {
        const card = document.createElement('div');
        card.className = 'char-card';
        card.innerHTML = `
          <div>
            <div class="name">${c.display_name || c.name}</div>
            <div class="status">${c.emotions_ready}/${c.emotions_total} 表情 · ${c.status}</div>
          </div>
          <div>
            <button class="use-btn" data-name="${c.name}">使用</button>
            <button class="del-btn" data-name="${c.name}">删除</button>
          </div>
        `;
        card.querySelector('.use-btn').addEventListener('click', () => {
          sendWS({ type: 'switch_character', name: c.name });
        });
        card.querySelector('.del-btn').addEventListener('click', async () => {
          if (!confirm(`确定删除 ${c.name}？`)) return;
          await fetch(`${API}/api/characters/${c.name}`, { method: 'DELETE' });
          refreshCharacterList();
        });
        characterList.appendChild(card);
      });
    } catch (err) {
      characterList.innerHTML = `<p style="color:#888">加载失败</p>`;
    }
  }

  // ─── 初始化 ───
  connectWS();
  refreshCharacterList();
})();
```

- [ ] **Step 4: Commit**

```bash
git add server/static/
git commit -m "feat: add mobile control panel with photo upload and emotion control"
```

---

### Task 7: 启动脚本 + 端到端测试

**Files:**
- Create: `scripts/start.sh`

- [ ] **Step 1: 创建 scripts/start.sh**

```bash
#!/usr/bin/env bash
# Alive Blob — 启动所有模块
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

# 激活虚拟环境
if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi

# 创建 characters 目录
mkdir -p characters

echo "🚀 Starting Alive Blob..."

# 1. FastAPI Server (port 8080)
echo "[1/3] Starting FastAPI server on :8080..."
uvicorn server.main:app --host 0.0.0.0 --port 8080 --reload &
SERVER_PID=$!

# 等待 server 启动
for i in $(seq 1 10); do
  if curl -s http://localhost:8080/api/status > /dev/null 2>&1; then
    echo "  ✅ Server ready"
    break
  fi
  sleep 1
done

# 2. Blob Engine (port 8000)
echo "[2/3] Starting Blob Engine on :8000..."
python -m blob_engine.engine &
ENGINE_PID=$!
sleep 1
echo "  ✅ Engine ready"

# 3. Eye App (仅在 Pi 上启动 kiosk 模式)
if command -v chromium-browser &> /dev/null; then
  echo "[3/3] Starting Eye App in kiosk mode..."
  chromium-browser --kiosk --disable-infobars --noerrdialogs \
    --enable-features=VaapiVideoDecoder --use-gl=egl \
    "http://localhost:8080/eye-app/" &
  EYE_PID=$!
else
  echo "[3/3] Chromium not found — open Eye App manually:"
  echo "  → http://localhost:8080/eye-app/"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Alive Blob is running!"
echo "  📱 手机控制面板: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):8080"
echo "  👁  Eye App:     http://localhost:8080/eye-app/"
echo "  ⚙  API:         http://localhost:8080/api/status"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Press Ctrl+C to stop all services"

# 等待中断
trap "echo '🛑 Shutting down...'; kill $SERVER_PID $ENGINE_PID ${EYE_PID:-} 2>/dev/null; exit 0" INT TERM
wait
```

- [ ] **Step 2: 添加 Eye App 静态文件路由**

在 `server/main.py` 中添加 eye-app 静态文件挂载，使 `/eye-app/` 路径可以从 FastAPI 访问 Eye App 文件：

```python
# 在 create_app 中添加（characters mount 之后，static mount 之前）
eye_app_dir = Path(__file__).parent.parent / "eye-app"
if eye_app_dir.exists():
    app.mount("/eye-app", StaticFiles(directory=str(eye_app_dir), html=True), name="eye-app")
```

- [ ] **Step 3: 端到端手动测试**

Run: `bash scripts/start.sh`

测试流程：
1. 打开手机浏览器访问 `http://<Pi-IP>:8080`
2. 切到「📷」标签页，输入角色名，选择照片
3. 点击「🚀 生成表情包」，等待生成完成
4. 切到「😊」标签页，点击情绪按钮
5. Eye App (`http://localhost:8080/eye-app/`) 应显示对应情绪图片

- [ ] **Step 4: Commit**

```bash
git add scripts/start.sh
git commit -m "feat: add start script for launching all modules"
```

---

## 验证方式

1. **单元测试**: `python -m pytest tests/ -v` — AIGC 服务和 API 路由测试全通过
2. **端到端**: 运行 `bash scripts/start.sh` → 手机上传照片 → 7 张情绪图片生成 → 切换情绪 → Eye App 显示对应图片
3. **关键检查点**:
   - `POST /api/characters` 上传照片后，`characters/<name>/` 下出现 7 个 `.png` + `manifest.json`
   - WebSocket 连接 `/ws/mobile` 发 `set_emotion` → `/ws/eye` 收到 `play_emotion`
   - Eye App 图片交叉淡入淡出切换
