import pytest
import asyncio
import json
import websockets

WS_PORT = 18765  # test port to avoid conflicts

@pytest.mark.asyncio
async def test_engine_echo_emotion():
    """Test: mobile sends set_emotion → Engine relays play_emotion to Eye App"""
    from blob_engine.engine import BlobEngine

    engine = BlobEngine(port=WS_PORT, characters_dir="/tmp/test-chars")
    # Set current_character directly so _send_play_emotion will fire
    engine.current_character = "test"
    task = asyncio.create_task(engine.start())

    try:
        await asyncio.sleep(0.3)

        eye_ws = await websockets.connect(f"ws://localhost:{WS_PORT}/ws/eye")
        mobile_ws = await websockets.connect(f"ws://localhost:{WS_PORT}/ws/mobile")

        # Drain initial messages sent on Eye App connect (set_face + play_emotion)
        for _ in range(3):
            try:
                initial = await asyncio.wait_for(eye_ws.recv(), timeout=1)
            except asyncio.TimeoutError:
                break

        await mobile_ws.send(json.dumps({"type": "set_emotion", "emotion": "happy"}))

        msg = await asyncio.wait_for(eye_ws.recv(), timeout=2)
        data = json.loads(msg)
        assert data["type"] == "play_emotion"
        assert data["emotion"] == "happy"
        assert "happy" in data["image_path"]

        await eye_ws.close()
        await mobile_ws.close()
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
