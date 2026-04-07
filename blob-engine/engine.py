"""Blob Engine — minimal WebSocket server.

MVP features:
- /ws/eye endpoint: Eye App connects here
- /ws/mobile endpoint: Mobile clients connect here
- Mobile sends set_emotion → relays play_emotion to Eye App
- Mobile sends switch_character → updates current character
- Periodic state_sync push to mobile clients
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
        if self.characters_dir.exists():
            for d in sorted(self.characters_dir.iterdir()):
                if (d / "manifest.json").exists():
                    self.current_character = d.name
                    break

        async with serve(self._handler, "0.0.0.0", self.port):
            log.info(f"Engine WebSocket server on port {self.port}")
            sync_task = asyncio.create_task(self._state_sync_loop())
            try:
                await asyncio.Future()
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
        await self._send_play_emotion()
        try:
            async for msg in ws:
                pass
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
