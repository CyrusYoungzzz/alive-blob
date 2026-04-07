"""AIGC emotion generation service — pluggable interface + Mock implementation.

Interface: generate_emotions(source_image, output_dir) → dict[emotion, path]
Mock: Uses Pillow to generate 480x480 placeholder images with emotion labels.
Replace with real API by implementing AIGCService protocol.
"""

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
        """Generate 7 emotion images from source photo. Returns {emotion: file_path}."""
        ...


class MockAIGCService:
    """Mock AIGC — generates colored placeholder images with Pillow."""

    async def generate_emotions(
        self, source_image: Path, output_dir: Path
    ) -> dict[str, str]:
        if not source_image.exists():
            raise FileNotFoundError(f"Source image not found: {source_image}")

        output_dir.mkdir(parents=True, exist_ok=True)
        results = {}

        from PIL import Image, ImageDraw, ImageFont

        try:
            base_img = Image.open(source_image).resize((480, 480))
        except Exception:
            base_img = Image.new("RGB", (480, 480), "#333333")

        for emotion in EMOTIONS:
            img = base_img.copy()
            overlay = Image.new("RGBA", (480, 480), EMOTION_COLORS[emotion] + "80")
            img = Image.alpha_composite(img.convert("RGBA"), overlay)
            draw = ImageDraw.Draw(img)
            label = EMOTION_LABELS[emotion]
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
            except OSError:
                font = ImageFont.load_default()
            bbox = draw.textbbox((0, 0), label, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(((480 - tw) / 2, (480 - th) / 2), label, fill="white", font=font)
            out_path = output_dir / f"{emotion}.png"
            img.convert("RGB").save(out_path)
            results[emotion] = str(out_path)

        return results
