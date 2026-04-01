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
   │Sensor  │ │(x3)    │ │(12V)   │   │(Control)  │
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
| 12V normally-closed solenoid valve | 3 | 15-25 CNY each | 6mm tubing |
| IRF520 MOSFET module | 4 | 3-5 CNY each | Or 4-ch relay module |
| 12V to 5V buck converter | 1 | 5-10 CNY | 3A+ for Pi |
| 12V power adapter | 1 | 15-25 CNY | 3A+ |
| 6mm silicone tubing | 2m | 5-10 CNY | |
| Dupont wires + breadboard | misc | 15-20 CNY | |
| **Total** | | **400-650 CNY** | Silicone materials handled by structural engineer |

### GPIO Pin Assignment

```
GPIO18 = Air pump on/off (HIGH = on)
GPIO23 = Valve 1 - Body breathing (HIGH = open)
GPIO24 = Valve 2 - Left tentacle (HIGH = open)
GPIO25 = Valve 3 - Right/rear tentacle (HIGH = open)
I2C SDA (GPIO2) = MPR121 touch sensor
I2C SCL (GPIO3) = MPR121 touch sensor
MPR121 I2C address = 0x5A
```

### Pneumatic Topology

```
Air pump → Main tube ─┬─→ Valve 1 → Body cavity (breathing)
                      ├─→ Valve 2 → Left tentacle cavity
                      └─→ Valve 3 → Right/rear tentacle cavity
```

### Physical Form

The blob is an abstract creature — not a specific animal:
- Central round body (houses the display screen)
- 3-4 irregular soft tentacles extending from the body
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

| Pattern | Detection Rule | Triggers |
|---------|---------------|----------|
| Gentle tap | Single point, < 500ms | Happy |
| Sustained press | Same point, > 2s | Shy |
| Rapid taps | 3+ taps within 1s | Excited |
| Slap | Multi-point + high frequency | Grumpy |
| New location | Distance from last touch > threshold | Curious |
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
  "x": 0.6, "y": 0.3,
  "gesture": "tap",
  "effect": "ripple"
}
```

### Engine → Mobile (state sync, every 500ms)

```json
{
  "type": "state_sync",
  "emotion": "excited",
  "intensity": 0.85,
  "breathing_bpm": 24,
  "tentacles": [0.9, 0.7, 0.8],
  "touch_active": true,
  "character": "trump"
}
```

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
POST /api/characters/{name}/upload
Content-Type: multipart/form-data
Body: emotion=happy, file=happy.mp4
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

### Integration Interfaces

Only two interfaces need to be agreed upon before independent development:

**Interface 1: A ↔ B (GPIO hardware protocol)**
```
GPIO18 = pump (HIGH=on), GPIO23 = valve1-body, GPIO24 = valve2-tentL, GPIO25 = valve3-tentR
I2C = MPR121 touch (0x5A)
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
