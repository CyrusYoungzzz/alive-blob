# Alive Blob - Design Spec

An abstract soft robot companion that breathes, responds to touch, and displays AIGC-generated facial expressions. Built for a 48-hour hackathon.

## Project Goal

Create a physical companion that feels alive — not a device, but a living blob. Users can upload anyone's face photo, generate emotion videos with AIGC tools, and the blob will display those expressions while its silicone body breathes and tentacles move in response to touch.

## Team

- 3 people: 1 structural engineer (pneumatic silicone expert) + 2 software engineers
- Physical demo required for hackathon judges

## System Architecture

```
┌────────────────────────────────��────────────────────┐
│                  Raspberry Pi 4B                    │
│                                                      │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │ Eye App  │  │  Blob Engine │  │  Web Server   │  │
│  │ (Browser │  │  (Python)    │  │  (FastAPI)    │  │
│  │  fullscr)│  │              │  │              │  │
│  │  Video   │  │ - Emotion SM │  │ - REST API   │  │
│  │  Player  │  │ - Breath Ctrl│  │ - WebSocket  │  │
│  └────▲─────┘  │ - Touch Proc │  └──────▲───────┘  │
│       │        │ - Pump Ctrl  │         │           │
│   WebSocket    └──────┬───────┘    WiFi/LAN        │
│       │               │               │             │
│       └───────────��───┤               │             │
│                       │               │             │
│              GPIO / I2C               │             │
│                  │                    │             │
└──────────────────┼────────────────────┼─────────────┘
                   │                    │
        ┌──────────┼──────────┐         │
        │          │          │         │
   ┌────▼───┐ ┌───▼────┐ ┌───▼────┐   ┌▼──────────┐
   │MPR121  │ │Solenoid│ │Air     │   │Mobile     │
   │Touch   │ │Valves  │ │Pump    │   │Browser    │
   │Sensor  │ │(x6)    │ │(12V)   │   │(Control)  │
   └────────┘ └────────┘ └────────┘   └───────────┘
        │          │          │
   ┌────▼──────────▼──────────▼───────┐
   │      Blob Silicone Body          │
   │  Body    ← 1 channel: breathing  │
   │  Tent-L  ← 2 channel: left      │
   │  Tent-R  ← 3 channel: right     │
   └───────────────────────────────────┘
```

Three software modules:

1. **Eye App** — fullscreen Chromium on Pi renders AIGC emotion videos with touch overlay effects
2. **Blob Engine** — Python core process managing emotion state machine, breathing rhythm, touch response, and pump control
3. **Web Server** — FastAPI providing REST API + WebSocket for mobile control panel

## Hardware

### Bill of Materials

| Item | Qty | Est. Cost | Notes |
|------|-----|-----------|-------|
| Raspberry Pi 4B 2GB | 1 | 200-300 CNY | 4GB also works |
| 3.5-5" HDMI LCD | 1 | 80-150 CNY | Square or round IPS preferred |
| MPR121 capacitive touch module | 1 | 15-25 CNY | 12 channels |
| 12V micro air pump | 1 | 20-40 CNY | Quiet model preferred |
| 12V normally-closed solenoid valve | 3 | 15-25 CNY each | 6mm tubing, intake |
| 12V normally-open solenoid valve | 3 | 15-25 CNY each | 6mm tubing, exhaust |
| IRF520 MOSFET module | 7 | 3-5 CNY each | Or use 8-ch relay module |
| 12V to 5V buck converter | 1 | 5-10 CNY | 3A+ for Pi |
| 12V power adapter | 1 | 15-25 CNY | 3A+ |
| 6mm silicone tubing | 2m | 5-10 CNY | |
| Dupont wires + breadboard | misc | 15-20 CNY | |
| **Total** | | **~500-800 CNY** | Silicone materials handled by structural engineer |

### GPIO Pin Assignment

```
GPIO18 = Air pump on/off (HIGH = on)
GPIO23 = Intake Valve 1 - Body (HIGH = open, NC)
GPIO24 = Intake Valve 2 - Left tentacle (HIGH = open, NC)
GPIO25 = Intake Valve 3 - Right tentacle (HIGH = open, NC)
GPIO12 = Exhaust Valve 1 - Body (HIGH = close, NO)
GPIO16 = Exhaust Valve 2 - Left tentacle (HIGH = close, NO)
GPIO20 = Exhaust Valve 3 - Right tentacle (HIGH = close, NO)
I2C SDA (GPIO2) = MPR121 touch sensor
I2C SCL (GPIO3) = MPR121 touch sensor
MPR121 I2C address = 0x5A
```

### Pneumatic Topology

```
                     ┌─→ Valve 1 (NC) → Body cavity ──→ Exhaust Valve 1 (NO) → vent
Air pump → Main tube ┼─→ Valve 2 (NC) → Left tentacle → Exhaust Valve 2 (NO) → vent
                     └─→ Valve 3 (NC) → Right tentacle → Exhaust Valve 3 (NO) → vent

NC = normally-closed (default: air blocked, open to inflate)
NO = normally-open  (default: air vents out, close to hold pressure)
```

**Inflate cycle:** Open intake valve (NC→open) + close exhaust valve (NO→closed) + pump ON.
**Deflate cycle:** Close intake valve (NC→closed) + open exhaust valve (NO→open) + pump OFF. Air escapes passively through the exhaust.
**Hold:** Close both intake and exhaust valves.

**Pump safety watchdog:**
- Maximum continuous pump runtime: 10 seconds. Engine auto-kills pump after 10s and requires 2s cooldown.
- Maximum valve-closed (hold pressure) duration: 30 seconds. After 30s, exhaust valve auto-opens to release pressure.
- On Engine process exit or crash: all GPIO pins reset to LOW (all NC valves close, all NO valves open → safe deflation). Implemented via `atexit` handler and `signal` handler for SIGTERM/SIGINT.

### Additional Hardware for Exhaust Path

The exhaust/deflation path requires 3 additional normally-open solenoid valves (already included in BOM above).

### Physical Form

The blob is an abstract creature — not a specific animal:
- Central round body (houses the display screen)
- 2 independently controlled tentacles (left + right) + optional passive tentacles (no pneumatics, just floppy silicone for aesthetics)
- No defined front/back — it's a blob of living matter
- Semi-translucent or fluorescent silicone for an alien aesthetic
- Capacitive touch sensors embedded under the silicone surface

## Emotion System

### 7 Emotions

The blob has 7 emotion states. Each emotion simultaneously affects three outputs: the face video, breathing rhythm, and tentacle movement. The design tone is exaggerated and comedic — the blob is a drama queen.

| Emotion | Eye/Face (AIGC Video) | Breathing | Tentacles |
|---------|----------------------|-----------|-----------|
| **Calm** | Relaxed face, slow blinks, gentle nodding | Slow & deep (4s in + 4s out) | Gentle sway |
| **Happy** | Huge grin, exaggerated laughing, eyebrows up | Quick & light (2s cycle) | Slap the ground like clapping |
| **Curious** | Head tilt, raised eyebrow, eyes darting around | Slightly faster, irregular | One tentacle reaches toward touch point |
| **Sleepy** | Yawning, drooping eyes, head slowly tilting down | Very slow & deep (6s cycle) | All droop limp like noodles |
| **Excited** | Jaw drop, eyes wide, head shaking rapidly | Rapid shallow breathing | All tentacles spring up then fall |
| **Shy** | Head down, blushing, peeking up timidly | Slightly faster | Tentacles curl inward (covering face) |
| **Grumpy** | Crying, furrowed brows, pouting mouth | Short huffs | Tentacles cross (arms crossed) or shake stiffly |

### State Machine

```
                    ┌──────────────┐
          timeout   │              │ any touch
        ┌──────────►│    Sleepy    ├──────────┐
        │  (>60s)   │              │          │
        │           └──────────────┘          ▼
        │                                ┌─────────┐
   ┌────┴─────┐                          │  Calm   │◄── initial state
   │          │◄─────────────────────────│         │
   │  Calm    │     gentle tap           └────┬────┘
   │          │──── gentle tap ──► Happy       │
   └────┬─────┘                               │
        │         rapid repeated taps          │
        ├─────────────────────►  Excited       │
        │                                      │
        │         new touch location           │
        ├─────────────────────►  Curious       │
        │                                      │
        │         sustained press (>2s)        │
        ├─────────────────────►  Shy           │
        │                                      │
        │         slap (high freq + large area)│
        └─────────────────────►  Grumpy        │
                                               │
         all non-Calm emotions ── decay ──────►┘
                              (10-30s timeout)
```

Key design decisions:
- **Natural decay**: All emotions gradually return to Calm after 10-30 seconds of no interaction
- **Touch pattern recognition**: Engine analyzes touch frequency, duration, and area to classify gestures
- **Smooth transitions**: Emotion changes crossfade over 0.8-1.2 seconds (both video and tentacle position)
- **Mobile override**: The mobile control panel can force any emotion, overriding the automatic state machine

### Touch Pattern Recognition

The MPR121 provides 12 discrete touch channels (0-11), not continuous XY coordinates. Channels are mapped to physical zones on the blob:

```
MPR121 Channel Mapping:
  Channels 0-3:  Body top (around screen)
  Channels 4-5:  Body sides
  Channels 6-8:  Left tentacle (base → tip)
  Channels 9-11: Right tentacle (base → tip)
```

Person A places sensors according to this zone map. Person B reads channel numbers and classifies by zone.

| Pattern | Detection Rule | Triggers |
|---------|---------------|----------|
| Gentle tap | Single channel, < 500ms | Happy |
| Sustained press | Same channel held > 2s | Shy |
| Rapid taps | 3+ activations within 1s on any channels | Excited |
| Slap | 3+ channels activate simultaneously | Grumpy |
| New zone | Channel in different zone from last touch | Curious |
| No touch | > 60s silence | Sleepy |

## AIGC Face System

### Overview

Instead of abstract eye animations, the blob displays AI-generated facial expression videos. Users generate emotion videos externally using any AIGC tool (Kling, Runway, ComfyUI, CapCut, etc.) and upload them as "character packs."

### Video Specifications

- Resolution: 480x480 or 720x720 (match screen)
- Duration: 3-5 seconds, seamless loop
- Format: MP4 (H.264), Pi hardware-decodes natively
- Per character: 7 videos (one per emotion), ~20-40MB total
- Multiple character packs supported (e.g., "Trump pack", "Musk pack", "My Boss pack")

### Character Pack Structure

```
characters/
├── trump/
│   ├── calm.mp4
│   ├── happy.mp4
│   ├── excited.mp4
│   ├── curious.mp4
│   ├── sleepy.mp4
│   ├── shy.mp4
│   └── grumpy.mp4
├── musk/
│   └── ...
└── boss/
    └── ...
```

### AIGC Video Generation Guide (for content creators)

For each emotion, generate a 3-5 second looping video from the target face photo:

| Emotion | Prompt Direction |
|---------|-----------------|
| Calm | Relaxed expression, slow blinks, gentle nodding |
| Happy | Big laugh, exaggerated grin, bouncing eyebrows |
| Excited | Jaw drop, eyes popping wide, head shaking wildly |
| Curious | Head tilting, one eyebrow raised, eyes darting |
| Sleepy | Big yawn, drooping eyes, head slowly falling |
| Shy | Looking down, blushing, peeking up shyly |
| Grumpy | Crying face, furrowed brows, pouting lips |

## Software Modules

### 1. Blob Engine (Python — the brain)

Core process running on the Pi, coordinating all modules.

```
blob-engine/
├── engine.py          # Main loop, module coordination
├── emotion_sm.py      # Emotion state machine
├── touch_handler.py   # Touch pattern recognition
├── pump_controller.py # GPIO pump + valve PWM control
├── config.py          # All tunable parameters
└── requirements.txt
```

**Main loop (~50ms per tick):**
```
Read touch → Classify gesture → State machine decision → Update emotion →
  ├→ Pump commands (GPIO)
  ├→ Face video switch (WebSocket → Eye App)
  └→ State sync (WebSocket → Mobile)
```

### 2. Eye App (Frontend — the face)

Fullscreen Chromium page on the Pi display, video-based.

```
eye-app/
├── index.html
├── style.css
├── player.js          # Dual-layer video switch engine
├── overlay.js         # Canvas touch feedback layer
├── transitions.js     # Crossfade between emotion videos
└── ws.js              # WebSocket client
```

**Video playback design:**
- Two `<video>` elements stacked (Layer A / Layer B)
- Current emotion video loops on Layer A
- On emotion change: Layer B loads new video → crossfade (0.8s) → swap roles
- Videos set to `loop` + `muted`, fullscreen fill
- Background color shifts with emotion (e.g., red glow for Grumpy)

**Touch feedback overlay (Canvas layer on top of video):**
- Tap → ripple / heart particle at touch position
- Slap → CSS shake effect on entire screen
- Sustained press → expanding ripple from press point
- Provides instant "it felt that" feedback without waiting for video switch

### 3. Web Server (FastAPI — communication hub)

```
server/
├── main.py            # FastAPI application entry
├── routes.py          # REST API routes (upload, character management)
├── ws_manager.py      # WebSocket connection management
└── static/            # Mobile control panel frontend
    ├── index.html
    ├── app.js
    └── style.css
```

## Communication Protocol

All communication uses WebSocket with JSON messages. Every message has a `type` field for routing.

### WebSocket Architecture

```
                  ┌───────── ws://localhost:8000/ws/eye ──────────┐
                  │                                                │
             ┌────▼─────┐                                   ┌─────┴──────┐
             │ Eye App  │                                   │   Blob     │
             │ (browser)│                                   │  Engine    │
             └──────────┘                                   │  (Python)  │
                                                            └─────┬──────┘
             ┌──────────┐                                         │
             │ Mobile   │── ws://192.168.x.x:8000/ws/mobile ─────┘
             │ (phone)  │
             └──────────┘
```

The **Blob Engine runs its own WebSocket server** (via `websockets` library) on port 8000 with two endpoints:
- `/ws/eye` — Eye App connects here. Only one connection expected.
- `/ws/mobile` — Mobile clients connect here. Multiple connections allowed (all receive same state_sync).

The **FastAPI server** runs on port 8080 and handles REST API only (file uploads, character CRUD, health check). It does NOT proxy WebSocket traffic — the Engine handles WebSocket directly to minimize latency for touch feedback.

Mobile clients connect to the Engine's WebSocket for real-time control, and to the FastAPI server for REST operations (file upload, character listing).

### Engine → Eye App (video control)

```json
{
  "type": "play_emotion",
  "video_path": "/characters/trump/happy.mp4",
  "transition": "crossfade",
  "transition_ms": 800
}
```

```json
{
  "type": "touch_feedback",
  "zone": "body_top",
  "channel": 2,
  "gesture": "tap",
  "effect": "ripple"
}
```

The Eye App maps zones to screen regions for overlay effects:
- `body_top` → center of screen
- `body_sides` → left/right edge
- `left_tentacle` → bottom-left
- `right_tentacle` → bottom-right

### Engine → Mobile (state sync, every 500ms)

```json
{
  "type": "state_sync",
  "emotion": "excited",
  "intensity": 0.85,
  "breathing_bpm": 24,
  "tentacles": [0.9, 0.7],
  "touch_active": true,
  "character": "trump"
}
```

**Field definitions:**
- `intensity` (0.0 - 1.0): Global performance intensity. Scales three things simultaneously: (1) pump duty cycle / inflation depth, (2) breathing amplitude, (3) tentacle movement range. At 0.0 the blob barely moves; at 1.0 it's maximum drama. Default: 0.7.
- `tentacles` array: Current inflation ratio per channel. Index 0 = left tentacle, index 1 = right tentacle. 0.0 = fully deflated, 1.0 = maximum inflation. Read-only for mobile display.
- `breathing_bpm`: Current breaths per minute.
- `touch_active`: Whether any touch channel is currently activated.

### Mobile → Engine (user commands)

```json
{ "type": "set_emotion", "emotion": "happy" }
{ "type": "set_intensity", "value": 0.6 }
{ "type": "set_breathing", "bpm": 12 }
{ "type": "switch_character", "name": "trump" }
{ "type": "list_characters" }
```

### Mobile → Server (file upload via REST)

```
POST   /api/characters                       # Create new character pack (body: { name })
GET    /api/characters                       # List all packs with completeness status
GET    /api/characters/{name}                # Get one pack's detail (which emotions have videos)
DELETE /api/characters/{name}                # Delete a pack
POST   /api/characters/{name}/videos         # Upload video (multipart: emotion=happy, file=happy.mp4)
GET    /api/characters/{name}/videos/{emotion} # Stream a video file (for preview thumbnail)
GET    /api/status                           # System health: engine running, screen connected, touch active
```

## Mobile Control Panel

Four-tab SPA served by FastAPI, accessed via same-LAN mobile browser.

### Tab 1: Home (Status Overview)

- Current character name and face preview thumbnail
- Current emotion with icon
- Intensity bar (0-1)
- Breathing BPM
- Tentacle inflation levels (per-channel bar)
- Touch activity indicator

### Tab 2: Emotion (Core Interaction)

- 7 emotion buttons in a grid, tap to force-switch
- Intensity slider (quiet ↔ dramatic), affects animation amplitude + tentacle range + breathing depth
- Breathing speed slider (BPM)
- Auto/Manual toggle: auto = touch-driven state machine, manual = phone overrides

### Tab 3: Upload (Character Management)

- List of installed character packs with status (X/7 videos ready)
- Active character indicator, tap to switch
- "New character" flow: name → upload 7 emotion videos one by one
- Delete character pack

### Tab 4: Settings

- WiFi connection status
- Screen brightness
- Touch sensitivity adjustment
- Pump force ceiling (safety limit)
- System restart

## Startup, Shutdown, and Error Handling

### Startup Sequence

`scripts/start.sh` launches all processes in order via a simple shell script (no systemd needed for hackathon):

1. **FastAPI server** starts first (port 8080) — serves mobile panel static files and REST API.
2. **Blob Engine** starts second (port 8000) — opens WebSocket server, initializes GPIO, starts main loop.
3. **Eye App** starts last — `chromium-browser --kiosk --disable-infobars --enable-features=VaapiVideoDecoder http://localhost:8000/ws/eye` (fullscreen mode, hardware video decode enabled).

Health check: `start.sh` waits for each process to bind its port before starting the next one. If any process fails to start within 10 seconds, the script prints an error and exits.

### Shutdown Sequence

`scripts/stop.sh` or Ctrl+C on `start.sh`:

1. Send SIGTERM to Blob Engine → `atexit` handler sets all GPIO LOW (safe deflation) → process exits.
2. Send SIGTERM to FastAPI server → process exits.
3. Kill Chromium process.

**Critical: GPIO cleanup on crash.** The Engine registers both `atexit` and `signal.signal(SIGTERM/SIGINT)` handlers that call `GPIO.cleanup()`. This ensures all NC valves close and all NO valves open (= safe deflation) even on unexpected termination.

### Error Handling and Fallbacks

| Failure | Behavior |
|---------|----------|
| Eye App WebSocket disconnects | Engine continues running. Eye App auto-reconnects every 2 seconds. Face freezes on last frame during disconnect. |
| Mobile WebSocket disconnects | Engine continues in auto mode (touch-driven). Mobile panel shows "Reconnecting..." and auto-retries. |
| MPR121 touch sensor not detected on I2C | Engine starts in "no-touch" mode. Logs warning. Mobile-only control works. Emotion stays on Calm unless mobile overrides. |
| Incomplete character pack (< 7 videos) | System allows switching to it. Missing emotions fall back to a static placeholder image (a "?" face). Mobile shows which emotions are missing. |
| Pump runs > 10s continuously | Watchdog auto-kills pump. 2s cooldown before next activation. |
| Valve held closed > 30s | Exhaust valve auto-opens to release pressure. |
| Engine process crashes | GPIO cleanup handler fires. start.sh can be re-run manually. |

### Demo Mode

For situations where hardware partially fails during the demo:

Activated via mobile Settings tab or by starting Engine with `--demo` flag.

- **No touch sensor?** → Mobile panel becomes the sole input. Emotion buttons work as normal.
- **No pneumatics?** → Face videos still switch on the screen. The experience degrades gracefully to "interactive face display."
- **No screen?** → Tentacles still respond to touch. The experience degrades to "touch-responsive soft sculpture."

The core loop (touch → emotion → outputs) is designed so each output channel (face, body, mobile) operates independently. Any combination can fail without crashing the Engine.

## Character Pack Format

Each character pack is a directory under `characters/` with a `manifest.json`:

```json
{
  "name": "Trump",
  "created_at": "2026-04-01T12:00:00Z",
  "videos": {
    "calm": "calm.mp4",
    "happy": "happy.mp4",
    "excited": "excited.mp4",
    "curious": "curious.mp4",
    "sleepy": "sleepy.mp4",
    "shy": "shy.mp4",
    "grumpy": "grumpy.mp4"
  }
}
```

`manifest.json` is auto-generated by the server when videos are uploaded. The `videos` map only includes emotions that have been uploaded — missing keys indicate incomplete pack. The mobile Upload tab reads this to show completion status.

## Project File Structure

```
alive-blob/
├── blob-engine/
│   ├── engine.py
│   ├── emotion_sm.py
│   ├── touch_handler.py
│   ├── pump_controller.py
│   ├── config.py
│   └── requirements.txt
│
├── eye-app/
│   ├── index.html
│   ├── style.css
│   ├── player.js
│   ├── overlay.js
│   ├── transitions.js
│   └── ws.js
│
├── server/
│   ├── main.py
│   ├── routes.py
│   ├── ws_manager.py
│   └── static/
│       ├── index.html
│       ├── app.js
│       └── style.css
│
├── characters/
│   └── trump/
│       ├── calm.mp4
│       ├── happy.mp4
│       ├── excited.mp4
│       ├── curious.mp4
│       ├── sleepy.mp4
│       ├── shy.mp4
│       └── grumpy.mp4
│
├── scripts/
│   ├── setup-pi.sh
│   ├── start.sh
│   └── kiosk.sh
│
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-04-01-alive-blob-design.md
│
└── README.md
```

## Team Division (3 People, End-to-End Ownership)

### Person A — "The Body" (Structural Engineer)

Owns everything physical:
- Silicone mold design and casting
- Air pump + solenoid valve assembly
- Tubing and pneumatic topology
- Touch sensor placement under silicone
- All GPIO wiring to Raspberry Pi
- Physical assembly of the complete blob

**Deliverable:** A physical body that can inflate/deflate each channel independently and sense touch.

### Person B — "The Brain + Face" (Software)

Owns the core experience loop:
- Blob Engine: emotion state machine, touch pattern recognition, pump GPIO control
- Eye App: video player, crossfade transitions, touch overlay effects
- Complete pipeline: touch input → emotion decision → video playback + GPIO output

**Deliverable:** Touch it → face changes → tentacles move. The complete experience loop.

### Person C — "The Phone + Infrastructure" (Software)

Owns remote control and system infrastructure:
- FastAPI server + WebSocket manager
- Mobile control panel (all 4 tabs)
- File upload and character pack management
- Pi system setup, networking, auto-start scripts

**Deliverable:** Open phone browser → control everything + upload character videos.

**Side task for Person C (hours 0-8):** Generate the first character pack (7 AIGC emotion videos) using any tool while setting up the Pi environment. This ensures there is demo content ready before integration begins.

### Integration Interfaces

Only two interfaces need to be agreed upon before independent development:

**Interface 1: A ↔ B (GPIO hardware protocol)**
```
GPIO18 = pump, GPIO23-25 = intake valves (NC), GPIO12/16/20 = exhaust valves (NO)
I2C = MPR121 touch (0x5A), channels 0-5 = body, 6-8 = left tentacle, 9-11 = right tentacle
```

**Interface 2: B ↔ C (WebSocket message protocol)**
As defined in the Communication Protocol section above.

### 48h Timeline

```
       0h        8h        16h       24h       32h       40h       48h
        │─────────│─────────│─────────│─────────│─────────│─────────│

A Body  │ Mold +  │ Curing  │ Pneum.  │ Sensor+ │ Integ.  │  Demo  │
        │ casting │ (help   │ assembly│ wiring  │ tuning  │  prep  │
        │ design  │  B/C)   │ pump+   │ final   │         │        │
        │         │         │ valves  │ assembly│         │        │

B Brain │ Engine  │ Eye App │ GPIO    │ ← Integration → │  Demo  │
  +Face │ state   │ video   │ control │ end-to-end test  │  prep  │
        │ machine │ player  │ touch   │ polish + bugfix  │        │
        │ mock    │ effects │ hw link │                  │        │

C Phone │ FastAPI │ Control │ Upload  │ ← Integration → │  Demo  │
  +Infra│ WSocket │ panel   │ char    │ Pi deploy        │  prep  │
        │ Pi env  │ emotion │ mgmt    │ auto-start       │        │
        │ setup   │ sliders │ settings│                  │        │

        ▼         ▼          ▼          ▼          ▼          ▼
      Align     Modules    Modules    HW+SW      Full       Demo
      interfaces run solo  complete   integrate  pipeline    day
```

**Day 1 goal:** Each module runs and tests independently. B uses keyboard to simulate touch. C uses fake data for panel.

**Day 2 goal:** Integrate software + hardware. End-to-end: touch → emotion → face → tentacles. Polish and bugfix.

**Last 8h:** Feature freeze. Bug fixes and demo preparation only.

### Risk Mitigation

- **Silicone curing failure:** If the first silicone pour has defects (bubbles, leaks), there is no time for a full redo. Fallback: use inflatable balloons inside a fabric sleeve for the body, with touch sensors taped to the outside. Ugly but functional.
- **Video performance on Pi:** If dual-video crossfade is choppy, fall back to hard-cut transitions (no crossfade). Use 480x480 resolution as the safe baseline. Launch Chromium with `--enable-features=VaapiVideoDecoder --use-gl=egl` for hardware acceleration.
- **Partial hardware failure at demo:** Demo mode allows the system to function with any subset of hardware working. See Error Handling section.
