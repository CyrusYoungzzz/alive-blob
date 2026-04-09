"""Blob Engine — WebSocket server + gait controller.

Features:
- /ws/eye endpoint: Eye App connects here
- /ws/mobile endpoint: Mobile clients connect here
- Mobile sends set_emotion → relays play_emotion to Eye App + updates gait
- Mobile sends switch_character → updates current character
- Periodic state_sync push to mobile clients
- GPIO gait controller: pump + valve control per emotion
"""

import asyncio
import json
import logging
from pathlib import Path

import websockets
from websockets.server import serve

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
log = logging.getLogger("engine")

# 延迟导入 gait controller，Mac 上也能运行
try:
    from gait_controller import GaitController
    _HAS_GAIT = True
except ImportError:
    _HAS_GAIT = False
    log.warning("GaitController not available (missing deps?) — gait disabled")

from interaction_store import InteractionStore
from touch_sensor import create_touch_sensor


BUILTIN_CHARS = {
    "cube": {"type": "3d", "name": "Cube", "avatar": None},
    "keji-shu": {
        "type": "image",
        "name": "科技薯",
        "avatar": "https://sns-avatar-qc.xhscdn.com/avatar/1040g2jo3154311m61e6g5pkcpsk0uc8t76cabeo?imageView2/2/w/540/format/webp",
    },
}


class BlobEngine:
    def __init__(self, port: int = 8000, characters_dir: str = "characters", enable_gait: bool = True):
        self.port = port
        self.characters_dir = Path(characters_dir)
        self.eye_clients: set = set()
        self.mobile_clients: set = set()
        self.current_emotion = "sleepy"
        self.current_character = None
        self._running = False
        self._intensity = 0.7
        self.gait = GaitController() if (_HAS_GAIT and enable_gait) else None
        self._store = InteractionStore(Path("data/interactions.json"))
        self._touch = create_touch_sensor(self._on_touch_hit)

    async def start(self):
        self._running = True
        if self.characters_dir.exists():
            for d in sorted(self.characters_dir.iterdir()):
                if (d / "manifest.json").exists():
                    self.current_character = d.name
                    break

        # 启动步态控制器
        if self.gait:
            await self.gait.start()

        self._loop = asyncio.get_running_loop()
        self._touch.start()

        async with serve(self._handler, "0.0.0.0", self.port):
            log.info(f"Engine WebSocket server on port {self.port}")
            sync_task = asyncio.create_task(self._state_sync_loop())
            flush_task = None
            flush_task = asyncio.create_task(self._flush_loop())
            try:
                await asyncio.Future()
            finally:
                sync_task.cancel()
                if flush_task:
                    flush_task.cancel()
                self._touch.stop()
                self._store.flush()
                if self.gait:
                    await self.gait.stop()

    async def _handler(self, websocket):
        path = websocket.request.path if hasattr(websocket, 'request') else websocket.path
        if path == "/ws/eye":
            await self._handle_eye(websocket)
        elif path == "/ws/mobile":
            await self._handle_mobile(websocket)
        else:
            await websocket.close(4004, "Unknown path")

    async def _handle_eye(self, ws):
        self.eye_clients.add(ws)
        log.info(f"Eye App connected ({len(self.eye_clients)} total)")
        await self._send_set_face(ws)
        await self._send_play_emotion(ws)
        try:
            async for msg in ws:
                pass
        finally:
            self.eye_clients.discard(ws)
            log.info(f"Eye App disconnected ({len(self.eye_clients)} total)")

    async def _handle_mobile(self, ws):
        self.mobile_clients.add(ws)
        log.info(f"Mobile connected ({len(self.mobile_clients)} total)")
        # Send interaction snapshot on connect
        init_msg = json.dumps({
            "type": "interaction_init",
            "rankings": self._store.get_rankings(),
            "total": self._store.get_total(),
            "last_hit_ts": self._store.last_hit_ts,
        })
        await ws.send(init_msg)
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
            if self.gait:
                self.gait.set_emotion(self.current_emotion)
            await self._send_play_emotion()
        elif msg_type == "set_intensity":
            self._intensity = max(0.0, min(1.0, data.get("value", 0.7)))
            if self.gait:
                self.gait.set_intensity(self._intensity)
        elif msg_type == "switch_character":
            self.current_character = data["name"]
            log.info(f"Character → {self.current_character}")
            await self._send_set_face()
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

    async def _send_set_face(self, target=None):
        """发送角色信息给 Eye App。target=None 广播给所有 eye clients。"""
        if self.current_character is None:
            return
        builtin = BUILTIN_CHARS.get(self.current_character)
        if builtin:
            msg = json.dumps({
                "type": "set_face",
                "character": self.current_character,
                "char_type": builtin["type"],
                "avatar": builtin["avatar"],
            })
        else:
            msg = json.dumps({
                "type": "set_face",
                "image_url": f"/characters/{self.current_character}/source.jpg",
                "character": self.current_character,
                "char_type": "custom",
            })
        targets = [target] if target else list(self.eye_clients)
        for ws in targets:
            try:
                await ws.send(msg)
            except Exception:
                self.eye_clients.discard(ws)

    async def _send_play_emotion(self, target=None):
        if self.current_character is None:
            return
        builtin = BUILTIN_CHARS.get(self.current_character)
        char_type = builtin["type"] if builtin else "custom"
        msg = json.dumps({
            "type": "play_emotion",
            "emotion": self.current_emotion,
            "char_type": char_type,
            "image_path": f"/characters/{self.current_character}/{self.current_emotion}.png",
            "transition": "crossfade",
            "transition_ms": 800,
        })
        targets = [target] if target else list(self.eye_clients)
        for ws in targets:
            try:
                await ws.send(msg)
            except Exception:
                self.eye_clients.discard(ws)

    async def _state_sync_loop(self):
        while True:
            await asyncio.sleep(0.5)
            legs = self.gait.leg_states if self.gait else [0.0, 0.0]
            state = json.dumps({
                "type": "state_sync",
                "emotion": self.current_emotion,
                "character": self.current_character,
                "intensity": self._intensity,
                "legs": legs,
                "pump_on": self.gait.is_pump_on if self.gait else False,
            })
            for ws in list(self.mobile_clients):
                try:
                    await ws.send(state)
                except Exception:
                    self.mobile_clients.discard(ws)

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

    async def _flush_loop(self):
        """Periodically flush interaction counts to disk (1s debounce)."""
        while True:
            await asyncio.sleep(1.0)
            self._store.flush()


if __name__ == "__main__":
    engine = BlobEngine()
    asyncio.run(engine.start())
