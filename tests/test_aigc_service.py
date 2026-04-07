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
    from PIL import Image
    src = tmp_path / "face.jpg"
    Image.new("RGB", (200, 200), "white").save(src)

    results = await service.generate_emotions(src, tmp_path / "output")
    assert len(results) == 7
    for emotion in EMOTIONS:
        assert emotion in results
        assert Path(results[emotion]).exists()
        img = Image.open(results[emotion])
        assert img.size == (480, 480)

@pytest.mark.asyncio
async def test_mock_handles_missing_source(tmp_path):
    service = MockAIGCService()
    with pytest.raises(FileNotFoundError):
        await service.generate_emotions(tmp_path / "nonexistent.jpg", tmp_path)
