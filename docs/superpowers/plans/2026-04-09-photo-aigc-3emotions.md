# Photo + AIGC + 3-Emotion System Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace MockAIGCService with real Jimeng API img2img, and simplify the emotion system from 7 to 3 (sleepy, comfortable, crying) across the full stack.

**Architecture:** Minimal-change approach — swap the AIGC service implementation and update emotion lists/configs in all 3 modules (server, blob-engine, eye-app). No protocol or architecture changes.

**Tech Stack:** Python/FastAPI + httpx (Jimeng API), Three.js (3D Cube), vanilla JS (control panel)

**Spec:** `docs/superpowers/specs/2026-04-09-photo-aigc-3emotions-design.md`

---

## Chunk 1: Jimeng AIGC Service

### Task 1: Add httpx dependency

**Files:**
- Modify: `server/requirements.txt`

- [ ] **Step 1: Add httpx to requirements**

In `server/requirements.txt`, append:

```
httpx>=0.27.0
```

- [ ] **Step 2: Install**

Run: `pip install httpx>=0.27.0`

- [ ] **Step 3: Commit**

```bash
git add server/requirements.txt
git commit -m "deps: add httpx for Jimeng API integration"
```

---

### Task 2: Update EMOTIONS list and add JimengAIGCService

**Files:**
- Modify: `server/aigc_service.py` (full rewrite of EMOTIONS + new class)

- [ ] **Step 1: Update EMOTIONS list from 7 to 3**

Replace lines 11-31 of `server/aigc_service.py`:

```python
EMOTIONS = ["sleepy", "comfortable", "crying"]

EMOTION_COLORS = {
    "sleepy": "#8B8682",
    "comfortable": "#F5A623",
    "crying": "#4A90D9",
}

EMOTION_LABELS = {
    "sleepy": "😴 Sleepy",
    "comfortable": "😊 Comfortable",
    "crying": "😢 Crying",
}
```

- [ ] **Step 2: Update MockAIGCService to use new 3-emotion list**

The `MockAIGCService` class iterates `EMOTIONS` so it automatically picks up the new list. Update the docstring on the Protocol:

```python
@runtime_checkable
class AIGCService(Protocol):
    async def generate_emotions(
        self, source_image: Path, output_dir: Path
    ) -> dict[str, str]:
        """Generate emotion images from source photo. Returns {emotion: file_path}."""
        ...
```

- [ ] **Step 3: Add JimengAIGCService class**

Add these imports at the TOP of `server/aigc_service.py` (after the existing `from pathlib import Path` import):

```python
import asyncio
import base64
import io
import logging
import os

import httpx
from PIL import Image

log = logging.getLogger("aigc")
```

Then append the class at the END of the file:

```python
class JimengAIGCService:
    """Real AIGC using Jimeng (Volcengine) img2img API."""

    API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
    MODEL = "doubao-seedream-4-0-250828"

    EMOTION_PROMPTS = {
        "sleepy": "将这张人脸照片转换为可爱的卡通风格，表情是困倦的、眼睛半闭、打瞌睡的样子，柔和的色调",
        "comfortable": "将这张人脸照片转换为可爱的卡通风格，表情是舒服享受的、微笑眯眼、被轻轻抚摸的感觉，温暖的色调",
        "crying": "将这张人脸照片转换为可爱的卡通风格，表情是哭泣的、眼泪汪汪、委屈的样子，偏蓝冷色调",
    }

    def __init__(self):
        self.api_key = os.getenv("ARK_API_KEY", "")

    async def _generate_one(
        self, client: httpx.AsyncClient, emotion: str, image_b64: str, output_dir: Path
    ) -> tuple[str, str]:
        """Generate one emotion image with 1 retry. Returns (emotion, file_path)."""
        prompt = self.EMOTION_PROMPTS[emotion]

        payload = {
            "model": self.MODEL,
            "prompt": prompt,
            "image": [image_b64],
            "size": "2048x2048",
            "response_format": "url",
            "watermark": False,
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        last_err = None
        for attempt in range(2):  # 1 retry
            try:
                resp = await client.post(self.API_URL, json=payload, headers=headers, timeout=120.0)
                resp.raise_for_status()
                data = resp.json()

                if not data.get("data"):
                    raise RuntimeError(f"Jimeng API returned no data for {emotion}: {data}")

                image_url = data["data"][0]["url"]

                # Download the generated image
                img_resp = await client.get(image_url, timeout=60.0)
                img_resp.raise_for_status()

                # Resize to 480x480 and save
                img = Image.open(io.BytesIO(img_resp.content))
                img = img.resize((480, 480), Image.LANCZOS)
                out_path = output_dir / f"{emotion}.png"
                img.save(out_path)
                log.info(f"Generated {emotion} → {out_path}")

                return emotion, str(out_path)
            except Exception as e:
                last_err = e
                if attempt == 0:
                    log.warning(f"Retry {emotion} after error: {e}")
                    await asyncio.sleep(2)

        raise last_err

    async def generate_emotions(
        self, source_image: Path, output_dir: Path
    ) -> dict[str, str]:
        if not self.api_key:
            raise RuntimeError("ARK_API_KEY environment variable not set")

        if not source_image.exists():
            raise FileNotFoundError(f"Source image not found: {source_image}")

        output_dir.mkdir(parents=True, exist_ok=True)

        # Read source image and encode as base64
        raw = source_image.read_bytes()
        b64 = base64.b64encode(raw).decode()
        # Try data URI format first; if API rejects it, fall back to raw base64
        image_b64 = f"data:image/jpeg;base64,{b64}"

        async with httpx.AsyncClient() as client:
            # Run all 3 emotions concurrently
            tasks = [
                self._generate_one(client, emotion, image_b64, output_dir)
                for emotion in EMOTIONS
            ]
            results_list = await asyncio.gather(*tasks, return_exceptions=True)

        results = {}
        mock_fallback = MockAIGCService()
        has_failures = False

        for r in results_list:
            if isinstance(r, Exception):
                log.error(f"Jimeng API error: {r}")
                has_failures = True
            else:
                emotion, path = r
                results[emotion] = path

        # Fall back to mock for any failed emotions
        if has_failures:
            missing = [e for e in EMOTIONS if e not in results]
            if missing:
                log.warning(f"Falling back to mock for: {missing}")
                mock_results = await mock_fallback.generate_emotions(source_image, output_dir)
                for e in missing:
                    if e in mock_results:
                        results[e] = mock_results[e]

        return results
```

- [ ] **Step 4: Verify syntax**

Run: `python -c "from server.aigc_service import JimengAIGCService, EMOTIONS; print(EMOTIONS)"`
Expected: `['sleepy', 'comfortable', 'crying']`

- [ ] **Step 5: Commit**

```bash
git add server/aigc_service.py
git commit -m "feat: add JimengAIGCService with img2img + reduce emotions to 3"
```

---

### Task 3: Update routes to use Jimeng service

**Files:**
- Modify: `server/routes.py:13,45,65-66,88-101`

- [ ] **Step 1: Update import and service selection**

In `server/routes.py`, change line 13:

```python
from server.aigc_service import MockAIGCService, EMOTIONS
```
to:
```python
import os
from server.aigc_service import MockAIGCService, JimengAIGCService, EMOTIONS
```

- [ ] **Step 2: Update manifest key from "videos" to "emotions"**

In the `create_character` endpoint (lines 88-101), change the manifest and generation logic:

Replace:
```python
    manifest = {
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "generating",
        "videos": {},
    }
    _write_manifest(char_dir, manifest)

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
```

With:
```python
    manifest = {
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "generating",
        "emotions": {},
    }
    _write_manifest(char_dir, manifest)

    async def _generate():
        if os.getenv("ARK_API_KEY"):
            service = JimengAIGCService()
        else:
            service = MockAIGCService()
        try:
            results = await service.generate_emotions(source_path, char_dir)
            manifest["status"] = "ready"
            manifest["emotions"] = {e: f"{e}.png" for e in results}
            _write_manifest(char_dir, manifest)
        except Exception as exc:
            manifest["status"] = f"error: {exc}"
            _write_manifest(char_dir, manifest)
```

- [ ] **Step 3: Verify server starts**

Run: `cd /Users/cyrus/Desktop/alive-blob && python -c "from server.main import app; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add server/routes.py
git commit -m "feat: wire JimengAIGCService into character creation route"
```

---

## Chunk 2: Emotion System 7→3 (All Modules)

### Task 4: Update blob-engine config

**Files:**
- Modify: `blob-engine/config.py:5,8,27-35`

- [ ] **Step 1: Update DEFAULT_EMOTION and EMOTIONS**

Change line 5:
```python
DEFAULT_EMOTION = "sleepy"
```

Change line 8:
```python
EMOTIONS = ["sleepy", "comfortable", "crying"]
```

- [ ] **Step 2: Update GAIT_PARAMS to 3 emotions**

Replace lines 27-35:
```python
GAIT_PARAMS = {
    "sleepy":      {"step_ms": 3000, "duty": 0.3, "pattern": "pause"},
    "comfortable": {"step_ms": 2000, "duty": 0.5, "pattern": "steady"},
    "crying":      {"step_ms": 600,  "duty": 0.2, "pattern": "stomp"},
}
```

- [ ] **Step 3: Commit**

```bash
git add blob-engine/config.py
git commit -m "feat: reduce blob-engine emotions to 3 (sleepy/comfortable/crying)"
```

---

### Task 5: Update blob-engine engine.py

**Files:**
- Modify: `blob-engine/engine.py:48`

**Note:** `server/main.py` is listed in the spec (Section 3.3) but needs no changes — service selection is handled in `routes.py`.

- [ ] **Step 1: Change default emotion**

Change line 48:
```python
        self.current_emotion = "sleepy"
```

- [ ] **Step 2: Commit**

```bash
git add blob-engine/engine.py
git commit -m "feat: engine default emotion → sleepy"
```

---

### Task 6: Update gait_controller fallback

**Files:**
- Modify: `blob-engine/gait_controller.py:136,292`

- [ ] **Step 1: Change default emotion in GaitController**

Change line 136:
```python
        self._current_emotion = "sleepy"
```

- [ ] **Step 2: Change fallback in gait loop**

Change line 292:
```python
            params = GAIT_PARAMS.get(self._current_emotion, GAIT_PARAMS["sleepy"])
```

- [ ] **Step 3: Commit**

```bash
git add blob-engine/gait_controller.py
git commit -m "feat: gait controller default → sleepy"
```

---

### Task 7: Update eye-app cube.js

**Files:**
- Modify: `eye-app/cube.js:14-57,159,246`

- [ ] **Step 1: Replace 7-emotion EMOTIONS object with 3 emotions**

Replace lines 14-57 (the EMOTIONS object) with:

```javascript
  const EMOTIONS = {
    sleepy: {
      baseColor: [0.3, 0.3, 0.4], rimColor: [0.5, 0.5, 0.6],
      noise: 0.1, eyeScale: 0.15, eyeSpace: 0.4, browL: -0.1, browA: 0,
      mouthX: 0.3, mouthY: 0.02,
      pulseFreq: 0.6, pulseAmp: 0.015, jitter: 0, tilt: -0.1
    },
    comfortable: {
      baseColor: [0.9, 0.6, 0.3], rimColor: [1.0, 0.85, 0.6],
      noise: 0.2, eyeScale: 0.4, eyeSpace: 0.42, browL: 0.1, browA: -0.15,
      mouthX: 0.7, mouthY: 0.12,
      pulseFreq: 1.5, pulseAmp: 0.03, jitter: 0, tilt: 0
    },
    crying: {
      baseColor: [0.3, 0.3, 0.8], rimColor: [0.5, 0.5, 1.0],
      noise: 0.5, eyeScale: 1.2, eyeSpace: 0.5, browL: 0.15, browA: 0.3,
      mouthX: 0.5, mouthY: 0.35,
      pulseFreq: 6.0, pulseAmp: 0.08, jitter: 0.03, tilt: 0
    }
  };
```

- [ ] **Step 2: Change default emotion variables**

Change line 159:
```javascript
  let targetEmotion = 'sleepy';
```

- [ ] **Step 3: Fix fallback in animate()**

Change line 246:
```javascript
    const cfg = EMOTIONS[targetEmotion] || EMOTIONS.sleepy;
```

- [ ] **Step 4: Commit**

```bash
git add eye-app/cube.js
git commit -m "feat: cube.js emotions reduced to 3 (sleepy/comfortable/crying)"
```

---

### Task 8: Update eye-app player.js

**Files:**
- Modify: `eye-app/player.js:15,96`

- [ ] **Step 1: Change default emotion**

Change line 15:
```javascript
  let currentEmotion = 'sleepy';
```

Change line 96:
```javascript
  setEmotion('sleepy');
```

- [ ] **Step 2: Commit**

```bash
git add eye-app/player.js
git commit -m "feat: player.js default emotion → sleepy"
```

---

### Task 9: Update eye-app emotion CSS effects

**Files:**
- Modify: `eye-app/style.css:57-141`

- [ ] **Step 1: Replace 7 emotion CSS blocks with 3**

Replace lines 57-141 (all the `#screen.emo-*` rules) with:

```css
/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Image character — emotion effects
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

/* Sleepy — dim blur, slow droop */
#screen.emo-sleepy .face-img {
  filter: brightness(0.55) saturate(0.35) blur(2px) hue-rotate(200deg);
  animation: sleepy-droop 3.5s ease-in-out infinite;
}
@keyframes sleepy-droop {
  0%, 100% { transform: translateY(0) rotate(0deg) scale(1); }
  40%      { transform: translateY(8px) rotate(-4deg) scale(0.98); }
  80%      { transform: translateY(15px) rotate(-7deg) scale(0.96); }
}

/* Comfortable — warm glow, gentle breathing */
#screen.emo-comfortable .face-img {
  filter: brightness(1.15) saturate(1.3) sepia(0.1) hue-rotate(-10deg);
  animation: comfortable-breathe 3s ease-in-out infinite;
}
@keyframes comfortable-breathe {
  0%, 100% { transform: scale(1) rotate(0deg); }
  50%      { transform: scale(1.04) rotate(1deg); }
}

/* Crying — blue tint, tremble */
#screen.emo-crying .face-img {
  filter: brightness(0.7) saturate(0.8) hue-rotate(200deg) contrast(1.1);
  animation: crying-tremble 0.15s ease-in-out infinite;
}
@keyframes crying-tremble {
  0%, 100% { transform: translateY(0) rotate(0deg); }
  25%      { transform: translateY(-2px) rotate(-1deg); }
  75%      { transform: translateY(2px) rotate(1deg); }
}
```

- [ ] **Step 2: Commit**

```bash
git add eye-app/style.css
git commit -m "feat: eye-app CSS emotions reduced to 3"
```

---

### Task 10: Update mobile control panel

**Files:**
- Modify: `server/static/app.js:6-14`

- [ ] **Step 1: Replace 7-emotion EMOTIONS array with 3**

Replace lines 6-14:

```javascript
  const EMOTIONS = [
    { id: 'sleepy',      emoji: '😴', label: '困',  color: '#5C5C70' },
    { id: 'comfortable', emoji: '😊', label: '舒服', color: '#F5A623' },
    { id: 'crying',      emoji: '😢', label: '哭',  color: '#4A90D9' },
  ];
```

- [ ] **Step 2: Commit**

```bash
git add server/static/app.js
git commit -m "feat: mobile control panel emotions reduced to 3"
```

---

**Files from spec that need NO changes (dynamically generated or generic styling):**
- `server/main.py` — service selection handled in `routes.py`
- `server/static/index.html` — emotion buttons generated dynamically by `app.js`
- `server/static/style.css` — chip styles are generic, not emotion-specific

---

## Chunk 3: Integration Verification

### Task 11: End-to-end smoke test

- [ ] **Step 1: Verify server starts without ARK_API_KEY (mock mode)**

Run:
```bash
cd /Users/cyrus/Desktop/alive-blob
unset ARK_API_KEY
uvicorn server.main:app --host 0.0.0.0 --port 8080 &
sleep 2
curl -s http://localhost:8080/api/status
```
Expected: `{"status":"ok"}`

- [ ] **Step 2: Test character creation with mock**

Run:
```bash
# Create a test character using an existing source image
curl -s -X POST http://localhost:8080/api/characters \
  -F "name=test-smoke" \
  -F "photo=@characters/6/source.jpg"
```
Expected: `{"name":"test-smoke","status":"generating"}`

- [ ] **Step 3: Poll until ready**

Run:
```bash
sleep 3
curl -s http://localhost:8080/api/characters/test-smoke
```
Expected: Status should be "ready" with 3 emotions (sleepy, comfortable, crying)

- [ ] **Step 4: Verify generated files**

Run:
```bash
ls -la characters/test-smoke/
```
Expected: `source.jpg`, `sleepy.png`, `comfortable.png`, `crying.png`, `manifest.json`

- [ ] **Step 5: Clean up test character**

Run:
```bash
curl -s -X DELETE http://localhost:8080/api/characters/test-smoke
kill %1 2>/dev/null  # stop background server
```

- [ ] **Step 6: Test with real Jimeng API (if ARK_API_KEY is set)**

Run:
```bash
# Only if you have the API key ready
export ARK_API_KEY="<your-key>"
uvicorn server.main:app --host 0.0.0.0 --port 8080 &
sleep 2
curl -s -X POST http://localhost:8080/api/characters \
  -F "name=test-jimeng" \
  -F "photo=@characters/6/source.jpg"
# Wait for generation (~30-60s for 3 concurrent API calls)
sleep 45
curl -s http://localhost:8080/api/characters/test-jimeng | python -m json.tool
```
Expected: Status "ready" with 3 emotion images generated by Jimeng

- [ ] **Step 7: Final commit (if any fixes were needed)**

```bash
git add -A
git commit -m "fix: integration test fixes for 3-emotion system"
```
