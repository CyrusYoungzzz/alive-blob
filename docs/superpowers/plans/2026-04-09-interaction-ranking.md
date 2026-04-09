# Interaction Ranking System — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real-time interaction ranking system that counts physical sensor hits per character and displays a leaderboard on a PC-optimized left-right layout.

**Architecture:** New `touch_sensor.py` module reads MPR121 capacitive sensor (extracted from `whip-test.py`). `engine.py` gains an interaction counter with JSON file persistence and event-driven WebSocket broadcast. Mobile/PC frontend gets a left-right split layout: animation left, leaderboard right.

**Tech Stack:** Python 3.9 + websockets + asyncio (backend), vanilla JS/CSS (frontend), JSON file storage

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `blob-engine/touch_sensor.py` | Create | MPR121 sensor reading thread, hit detection, callback to engine |
| `blob-engine/interaction_store.py` | Create | JSON file persistence for interaction counts |
| `blob-engine/engine.py` | Modify | Integrate touch sensor + interaction counting + WS broadcast |
| `blob-engine/config.py` | Modify | Add touch sensor constants |
| `server/static/index.html` | Modify | Left-right split layout for Page 1 |
| `server/static/style.css` | Modify | Styles for ranking panel + left-right layout |
| `server/static/app.js` | Modify | Ranking UI rendering + `interaction_update`/`interaction_init` handling |
| `blob-engine/tests/test_interaction_store.py` | Create | Tests for interaction count persistence |
| `blob-engine/tests/test_touch_sensor.py` | Create | Tests for hit classification logic |

---

## Chunk 1: Backend — Interaction Store + Touch Sensor

### Task 1: Interaction Store (JSON persistence)

**Files:**
- Create: `blob-engine/interaction_store.py`
- Create: `blob-engine/tests/__init__.py`
- Create: `blob-engine/tests/test_interaction_store.py`

- [ ] **Step 1: Write failing tests for InteractionStore**

```python
# blob-engine/tests/test_interaction_store.py
import json
import tempfile
from pathlib import Path

from interaction_store import InteractionStore


def test_increment_new_character():
    with tempfile.TemporaryDirectory() as d:
        store = InteractionStore(Path(d) / "interactions.json")
        store.increment("cube")
        assert store.get_count("cube") == 1


def test_increment_existing_character():
    with tempfile.TemporaryDirectory() as d:
        store = InteractionStore(Path(d) / "interactions.json")
        store.increment("cube")
        store.increment("cube")
        store.increment("cube")
        assert store.get_count("cube") == 3


def test_rankings_sorted_by_count_desc():
    with tempfile.TemporaryDirectory() as d:
        store = InteractionStore(Path(d) / "interactions.json")
        for _ in range(5):
            store.increment("a")
        for _ in range(10):
            store.increment("b")
        for _ in range(3):
            store.increment("c")
        rankings = store.get_rankings()
        assert rankings[0]["name"] == "b"
        assert rankings[0]["rank"] == 1
        assert rankings[1]["name"] == "a"
        assert rankings[2]["name"] == "c"


def test_persistence_across_instances():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "interactions.json"
        store1 = InteractionStore(path)
        store1.increment("cube")
        store1.increment("cube")
        store1.flush()

        store2 = InteractionStore(path)
        assert store2.get_count("cube") == 2


def test_total_count():
    with tempfile.TemporaryDirectory() as d:
        store = InteractionStore(Path(d) / "interactions.json")
        store.increment("a")
        store.increment("b")
        store.increment("b")
        assert store.get_total() == 3


def test_last_hit_timestamp():
    with tempfile.TemporaryDirectory() as d:
        store = InteractionStore(Path(d) / "interactions.json")
        store.increment("cube")
        assert store.last_hit_ts is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/cyrus/Desktop/alive-blob/blob-engine && python -m pytest tests/test_interaction_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'interaction_store'`

- [ ] **Step 3: Implement InteractionStore**

```python
# blob-engine/interaction_store.py
"""Interaction count persistence — JSON file storage with write debouncing."""

import json
import time
import threading
from datetime import datetime, timezone
from pathlib import Path


class InteractionStore:
    def __init__(self, path: Path):
        self._path = path
        self._counts: dict[str, int] = {}
        self.last_hit_ts: str | None = None
        self._dirty = False
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if self._path.exists():
            data = json.loads(self._path.read_text())
            self._counts = data.get("counts", {})
            self.last_hit_ts = data.get("last_hit_ts")

    def increment(self, character: str) -> int:
        with self._lock:
            self._counts[character] = self._counts.get(character, 0) + 1
            self.last_hit_ts = datetime.now(timezone.utc).isoformat()
            self._dirty = True
            return self._counts[character]

    def get_count(self, character: str) -> int:
        return self._counts.get(character, 0)

    def get_total(self) -> int:
        return sum(self._counts.values())

    def get_rankings(self) -> list[dict]:
        sorted_items = sorted(
            self._counts.items(),
            key=lambda x: (-x[1], x[0])
        )
        return [
            {"name": name, "count": count, "rank": i + 1}
            for i, (name, count) in enumerate(sorted_items)
        ]

    def flush(self):
        """Write to disk if dirty."""
        with self._lock:
            if not self._dirty:
                return
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps({
                "counts": self._counts,
                "last_hit_ts": self.last_hit_ts,
            }, indent=2, ensure_ascii=False))
            self._dirty = False
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/cyrus/Desktop/alive-blob/blob-engine && python -m pytest tests/test_interaction_store.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add blob-engine/interaction_store.py blob-engine/tests/
git commit -m "feat: add InteractionStore with JSON persistence"
```

---

### Task 2: Touch Sensor Module

**Files:**
- Create: `blob-engine/touch_sensor.py`
- Create: `blob-engine/tests/test_touch_sensor.py`
- Modify: `blob-engine/config.py`

- [ ] **Step 1: Add touch sensor constants to config.py**

Append to `blob-engine/config.py`:

```python
# ─── 触摸传感器 ───
TOUCH_CHANNEL = 0            # MPR121 通道
TOUCH_POLL_INTERVAL = 0.02   # 20ms 轮询
TOUCH_BASELINE_ALPHA = 0.05  # 基线更新速率
TOUCH_HIT_THRESHOLD = 40     # 打击阈值
TOUCH_HIT_COOLDOWN = 0.15    # 防抖间隔（秒）
TOUCH_LIGHT_HIT = 40
TOUCH_MEDIUM_HIT = 100
TOUCH_HEAVY_HIT = 200
```

- [ ] **Step 2: Write failing tests for hit classification**

```python
# blob-engine/tests/test_touch_sensor.py
from touch_sensor import classify_hit


def test_light_hit():
    label, level = classify_hit(50)
    assert level == 1
    assert "轻" in label


def test_medium_hit():
    label, level = classify_hit(150)
    assert level == 2
    assert "中" in label


def test_heavy_hit():
    label, level = classify_hit(250)
    assert level == 3
    assert "重" in label


def test_boundary_medium():
    label, level = classify_hit(100)
    assert level == 2


def test_boundary_heavy():
    label, level = classify_hit(200)
    assert level == 3
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd /Users/cyrus/Desktop/alive-blob/blob-engine && python -m pytest tests/test_touch_sensor.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'touch_sensor'`

- [ ] **Step 4: Implement touch_sensor.py**

```python
# blob-engine/touch_sensor.py
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
    TOUCH_LIGHT_HIT, TOUCH_MEDIUM_HIT, TOUCH_HEAVY_HIT,
)

log = logging.getLogger("touch")

HitCallback = Callable[[str, int], None]  # (label, level)


def classify_hit(delta: int) -> tuple[str, int]:
    """Classify hit intensity by capacitance delta."""
    if delta >= TOUCH_HEAVY_HIT:
        return "重击", 3
    elif delta >= TOUCH_MEDIUM_HIT:
        return "中等", 2
    else:
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
        import board
        import busio
        import adafruit_mpr121

        i2c = busio.I2C(board.SCL, board.SDA)
        mpr = adafruit_mpr121.MPR121(i2c)
        baseline = mpr[TOUCH_CHANNEL].raw_value
        last_hit_time = 0.0

        while self._running:
            raw = mpr[TOUCH_CHANNEL].raw_value
            delta = raw - baseline

            # Update baseline when no hit
            if abs(delta) < TOUCH_HIT_THRESHOLD:
                baseline = baseline * (1 - TOUCH_BASELINE_ALPHA) + raw * TOUCH_BASELINE_ALPHA

            # Detect hit
            now = time.time()
            if delta > TOUCH_HIT_THRESHOLD and (now - last_hit_time > TOUCH_HIT_COOLDOWN):
                label, level = classify_hit(delta)
                last_hit_time = now
                log.info("Hit detected: %s (delta=%+d)", label, delta)
                try:
                    self._on_hit(label, level)
                except Exception:
                    log.exception("on_hit callback error")

            time.sleep(TOUCH_POLL_INTERVAL)


class MockTouchSensor:
    """Stub for non-Pi environments — does nothing."""

    def __init__(self, on_hit: HitCallback):
        log.info("MockTouchSensor (no real sensor)")

    def start(self):
        pass

    def stop(self):
        pass


def create_touch_sensor(on_hit: HitCallback) -> TouchSensor | MockTouchSensor:
    """Factory: returns real sensor on Pi, mock otherwise."""
    try:
        import board  # noqa: F401
        return TouchSensor(on_hit)
    except ImportError:
        return MockTouchSensor(on_hit)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/cyrus/Desktop/alive-blob/blob-engine && python -m pytest tests/test_touch_sensor.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add blob-engine/touch_sensor.py blob-engine/tests/test_touch_sensor.py blob-engine/config.py
git commit -m "feat: add TouchSensor module with MPR121 hit detection"
```

---

### Task 3: Engine Integration

**Files:**
- Modify: `blob-engine/engine.py`

Changes to `BlobEngine`:
1. Init: create `InteractionStore` + `TouchSensor`
2. `on_hit` callback: increment count → broadcast `interaction_update`
3. `_handle_mobile`: send `interaction_init` on connect
4. Periodic flush (every 1s) for dirty writes

- [ ] **Step 1: Add imports and init changes to engine.py**

After the gait controller import block (line 29), add:

```python
from interaction_store import InteractionStore
from touch_sensor import create_touch_sensor
```

In `__init__` (after line 52 `self.gait = ...`), add:

```python
        self._store = InteractionStore(Path("data/interactions.json"))
        self._touch = create_touch_sensor(self._on_touch_hit)
```

- [ ] **Step 2: Add the on_touch_hit callback and broadcast method**

Add these methods to `BlobEngine` class (after `__init__`):

```python
    def _on_touch_hit(self, label: str, level: int):
        """Called from touch sensor thread when a hit is detected."""
        char = self.current_character
        if not char:
            return
        count = self._store.increment(char)
        log.info("Interaction: %s on '%s' → %d total", label, char, count)
        # Schedule async broadcast from sync thread (use captured loop reference)
        self._loop.call_soon_threadsafe(
            asyncio.ensure_future, self._broadcast_interaction(char, count)
        )

    async def _broadcast_interaction(self, character: str, count: int):
        """Push interaction_update to all mobile clients."""
        msg = json.dumps({
            "type": "interaction_update",
            "character": character,
            "count": count,
            "rankings": self._store.get_rankings(),
            "total": self._store.get_total(),
            "last_hit_ts": self._store.last_hit_ts,
        })
        for ws in list(self.mobile_clients):
            try:
                await ws.send(msg)
            except Exception:
                self.mobile_clients.discard(ws)
```

- [ ] **Step 3: Send interaction_init on mobile connect**

In `_handle_mobile` method (after line 99 `log.info(...)`, before `try:`), add:

```python
        # Send interaction snapshot on connect
        init_msg = json.dumps({
            "type": "interaction_init",
            "rankings": self._store.get_rankings(),
            "total": self._store.get_total(),
            "last_hit_ts": self._store.last_hit_ts,
        })
        await ws.send(init_msg)
```

- [ ] **Step 4: Start touch sensor and add periodic flush**

In `start()` method, after `await self.gait.start()` (line 64), add:

```python
        self._loop = asyncio.get_running_loop()
        self._touch.start()
```

After `sync_task = asyncio.create_task(...)` (line 68), add:

```python
            flush_task = asyncio.create_task(self._flush_loop())
```

In the `finally:` block (line 71-74), add before `if self.gait:`:

```python
                if flush_task:
                    flush_task.cancel()
                self._touch.stop()
                self._store.flush()
```

After `sync_task = asyncio.create_task(...)` (line 68), add:

```python
            flush_task = None
            flush_task = asyncio.create_task(self._flush_loop())
```

Add the flush loop method:

```python
    async def _flush_loop(self):
        """Periodically flush interaction counts to disk (1s debounce)."""
        while True:
            await asyncio.sleep(1.0)
            self._store.flush()
```

- [ ] **Step 5: Verify engine starts without errors on Mac**

Run: `cd /Users/cyrus/Desktop/alive-blob/blob-engine && timeout 3 python engine.py; true`
Expected: Engine starts, logs "MockTouchSensor" and "Engine WebSocket server on port 8000", then exits on timeout. No errors.

- [ ] **Step 6: Commit**

```bash
git add blob-engine/engine.py
git commit -m "feat: integrate touch sensor + interaction counting into engine"
```

---

## Chunk 2: Frontend — Left-Right Layout + Ranking UI

### Task 4: HTML Layout Restructure

**Files:**
- Modify: `server/static/index.html`

Replace the Page 1 slide content (lines 17-43) with a left-right split layout.

- [ ] **Step 1: Restructure Page 1 HTML**

Replace the `<!-- Page 1: 角色展示 -->` section (the entire `<div class="slide" id="slide-char">` block, lines 17-43) with:

```html
      <!-- Page 1: 角色展示 + 排行榜 -->
      <div class="slide" id="slide-char">
        <div class="slide-inner">

          <div class="top-bar">
            <div>
              <div class="title" id="char-name-display">Cube</div>
              <div class="subtitle" id="char-desc">Alive Blob</div>
            </div>
            <div id="conn-dot"></div>
          </div>

          <div class="main-split">
            <!-- Left: Animation + Emotion Controls -->
            <div class="split-left">
              <div class="avatar-wrap">
                <div class="avatar-glow" id="avatar-glow"></div>
                <iframe id="eye-preview" src="/eye-app/" frameborder="0" scrolling="no" allowtransparency="true"></iframe>
              </div>

              <div class="emotion-name" id="emotion-name">calm</div>

              <div class="chips-wrap">
                <div class="chips" id="chips"></div>
              </div>
            </div>

            <!-- Right: Ranking Leaderboard -->
            <div class="split-right">
              <div class="rank-panel">
                <div class="rank-header">
                  <span class="rank-title">排行榜</span>
                  <span class="rank-total" id="rank-total">0 次互动</span>
                </div>
                <div class="rank-list" id="rank-list">
                  <!-- Populated by JS -->
                </div>
                <div class="rank-footer">
                  <span class="rank-chars" id="rank-chars">角色总数: 0</span>
                  <span class="rank-last-hit" id="rank-last-hit"></span>
                </div>
              </div>
            </div>
          </div>

          <div class="dots">
            <span class="dot on"></span><span class="dot"></span>
          </div>
        </div>
      </div>
```

- [ ] **Step 2: Verify page loads without JS errors**

Open `http://localhost:8080` in browser — page should load (ranking panel empty but no console errors).

- [ ] **Step 3: Commit**

```bash
git add server/static/index.html
git commit -m "feat: restructure Page 1 to left-right split layout"
```

---

### Task 5: CSS for Split Layout + Ranking Panel

**Files:**
- Modify: `server/static/style.css`

- [ ] **Step 1: Add split layout styles**

Append to `server/static/style.css` (after the existing Page 1 styles, around line 62):

```css
/* ── Split layout (Page 1) ── */
.main-split{display:flex;gap:24px;flex:1;min-height:0;margin-top:8px}
.split-left{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;min-width:0}
.split-right{width:320px;flex-shrink:0;display:flex;flex-direction:column;min-height:0}

@media(max-width:900px){
  .main-split{flex-direction:column;gap:12px}
  .split-right{width:100%;max-height:200px;overflow-y:auto}
}

/* ── Ranking panel ── */
.rank-panel{flex:1;display:flex;flex-direction:column;
  background:var(--card);border:1px solid var(--border);border-radius:14px;
  padding:16px;overflow:hidden}
.rank-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}
.rank-title{font-size:16px;font-weight:700;letter-spacing:0.5px}
.rank-total{font-size:12px;color:var(--t2)}

.rank-list{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:6px;
  scrollbar-width:thin;scrollbar-color:rgba(255,255,255,0.1) transparent}
.rank-list::-webkit-scrollbar{width:4px}
.rank-list::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.1);border-radius:2px}

.rank-item{display:flex;align-items:center;gap:10px;padding:10px 12px;
  border-radius:10px;background:rgba(255,255,255,0.03);
  border:1px solid transparent;transition:all .3s}
.rank-item.active{border-color:var(--accent);background:rgba(108,123,255,0.08)}
.rank-item.flash{animation:rank-flash .6s ease-out}
@keyframes rank-flash{0%{background:rgba(108,123,255,0.25)}100%{background:rgba(255,255,255,0.03)}}

.rank-pos{width:28px;height:28px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-size:13px;font-weight:700;flex-shrink:0}
.rank-pos.gold{background:linear-gradient(135deg,#FFD700,#FFA500);color:#000}
.rank-pos.silver{background:linear-gradient(135deg,#C0C0C0,#A0A0A0);color:#000}
.rank-pos.bronze{background:linear-gradient(135deg,#CD7F32,#A0522D);color:#fff}
.rank-pos.other{background:rgba(255,255,255,0.08);color:var(--t2)}

.rank-name{flex:1;font-size:14px;font-weight:500;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.rank-bar-wrap{flex:2;height:6px;background:rgba(255,255,255,0.06);border-radius:3px;overflow:hidden}
.rank-bar{height:100%;border-radius:3px;background:var(--accent);transition:width .4s ease-out}
.rank-count{font-size:13px;color:var(--t2);min-width:40px;text-align:right}

.rank-footer{display:flex;justify-content:space-between;align-items:center;
  margin-top:12px;padding-top:10px;border-top:1px solid var(--border)}
.rank-chars{font-size:11px;color:var(--t2)}
.rank-last-hit{font-size:11px;color:var(--t2)}
```

- [ ] **Step 2: Verify layout renders correctly**

Open `http://localhost:8080` — left side shows animation + chips, right side shows empty ranking panel. Both columns visible side by side on desktop.

- [ ] **Step 3: Commit**

```bash
git add server/static/style.css
git commit -m "feat: add CSS for split layout and ranking panel"
```

---

### Task 6: JavaScript — Ranking Logic + WebSocket Handling

**Files:**
- Modify: `server/static/app.js`

- [ ] **Step 1: Add ranking state variables**

After the existing state variables (line 23 `let ws = null, currentCharId = 'cube', currentEmotion = 'calm';`), add:

```javascript
  let rankings = [], totalInteractions = 0, lastHitTs = null;
```

- [ ] **Step 2: Add interaction message handling to WebSocket onmessage**

In the `ws.onmessage` handler (inside `connectWS()`, around line 66-71), add cases for the new message types. Replace the existing `ws.onmessage` with:

```javascript
    ws.onmessage = e => {
      const d = JSON.parse(e.data);
      if (d.type === 'state_sync') {
        if (d.character) currentCharId = d.character;
        if (d.emotion && d.emotion !== currentEmotion) { currentEmotion = d.emotion; syncUI(); }
      } else if (d.type === 'interaction_init') {
        rankings = d.rankings || [];
        totalInteractions = d.total || 0;
        lastHitTs = d.last_hit_ts || null;
        renderRanking();
      } else if (d.type === 'interaction_update') {
        rankings = d.rankings || [];
        totalInteractions = d.total || 0;
        lastHitTs = d.last_hit_ts || null;
        renderRanking(d.character);
      }
    };
```

- [ ] **Step 3: Add the renderRanking function**

Add before the `/* ── Init ── */` section (before line 373):

```javascript
  /* ── Ranking ── */
  function renderRanking(flashCharId) {
    const list = document.getElementById('rank-list');
    const maxCount = rankings.length ? rankings[0].count : 1;

    list.innerHTML = '';
    rankings.forEach(r => {
      const item = document.createElement('div');
      item.className = 'rank-item' + (r.name === currentCharId ? ' active' : '');
      if (r.name === flashCharId) item.classList.add('flash');

      const posClass = r.rank === 1 ? 'gold' : r.rank === 2 ? 'silver' : r.rank === 3 ? 'bronze' : 'other';
      const barPct = maxCount > 0 ? (r.count / maxCount * 100) : 0;

      item.innerHTML = `
        <div class="rank-pos ${posClass}">${r.rank}</div>
        <div class="rank-name">${r.name}</div>
        <div class="rank-bar-wrap"><div class="rank-bar" style="width:${barPct}%"></div></div>
        <div class="rank-count">${r.count}次</div>
      `;
      list.appendChild(item);
    });

    document.getElementById('rank-total').textContent = `${totalInteractions} 次互动`;
    document.getElementById('rank-chars').textContent = `角色总数: ${rankings.length}`;

    const lastHitEl = document.getElementById('rank-last-hit');
    if (lastHitTs) {
      const ago = Math.round((Date.now() - new Date(lastHitTs).getTime()) / 1000);
      lastHitEl.textContent = ago < 60 ? `${ago}s ago` : `${Math.round(ago / 60)}m ago`;
    } else {
      lastHitEl.textContent = '';
    }
  }
```

- [ ] **Step 4: Call renderRanking in init**

After `refreshList();` (line 376), add:

```javascript
  renderRanking();
```

- [ ] **Step 5: Verify full flow works end-to-end**

1. Start engine: `cd /Users/cyrus/Desktop/alive-blob/blob-engine && python engine.py`
2. Start server: `cd /Users/cyrus/Desktop/alive-blob && python -m server.main`
3. Open `http://localhost:8080` — left-right layout visible, ranking panel shows empty state
4. Verify WebSocket connects (green dot)
5. Verify emotion chips still work

- [ ] **Step 6: Commit**

```bash
git add server/static/app.js
git commit -m "feat: add ranking UI with real-time interaction updates"
```

---

### Task 7: Final Integration Test

- [ ] **Step 1: Run all Python tests**

Run: `cd /Users/cyrus/Desktop/alive-blob/blob-engine && python -m pytest tests/ -v`
Expected: All tests pass

- [ ] **Step 2: Manual end-to-end verification**

On Pi (or Mac with mock):
1. Start all: `scripts/start.sh`
2. Open PC browser → `http://<pi-ip>:8080`
3. Verify: left-right layout, animation playing, ranking panel visible
4. On Pi: tap capacitive sensor → interaction count increments, ranking updates in real time
5. Switch character → new hits count for the new character
6. Restart engine → verify counts persist

- [ ] **Step 3: Commit all remaining changes**

```bash
git add -A
git commit -m "feat: complete interaction ranking system"
```
