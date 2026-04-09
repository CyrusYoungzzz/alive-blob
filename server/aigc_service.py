"""AIGC emotion generation service — pluggable interface + Mock + Jimeng implementation.

Interface: generate_emotions(source_image, output_dir) → dict[emotion, path]
Mock: Uses Pillow to generate 480x480 placeholder images with emotion labels.
Jimeng: Uses Volcengine Ark SDK (doubao-seedream) for real img2img generation.
"""

import asyncio
import base64
import io
import logging
import os
from pathlib import Path
from typing import Protocol, runtime_checkable

import httpx
from PIL import Image

log = logging.getLogger("aigc")

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


@runtime_checkable
class AIGCService(Protocol):
    async def generate_emotions(
        self, source_image: Path, output_dir: Path
    ) -> dict[str, str]:
        """Generate emotion images from source photo. Returns {emotion: file_path}."""
        ...


class MockAIGCService:
    """Mock AIGC — generates colored placeholder images with Pillow."""

    async def generate_emotions(
        self, source_image: Path, output_dir: Path, on_progress=None
    ) -> dict[str, str]:
        if not source_image.exists():
            raise FileNotFoundError(f"Source image not found: {source_image}")

        output_dir.mkdir(parents=True, exist_ok=True)
        results = {}

        from PIL import ImageDraw, ImageFont

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


class JimengAIGCService:
    """Real AIGC using Volcengine Ark SDK with AK/SK authentication."""

    MODEL = "doubao-seedream-5-0-260128"

    EMOTION_PROMPTS = {
        "sleepy": (
            "参考附件中人物，保留人物的主要五官、发型等面部特征，"
            "生成一个 Emoji 风格 iOS 系统图标质感样式的人物头像，"
            "人物表情为半闭眼睛、微微嘟嘴、慵懒犯困的样子，眼皮沉重，"
            "圆形图标，正方形 1:1 构图，人物面部居中占画面 80%，"
            "图标底色为淡淡的薰衣草紫和浅灰蓝的渐变色，"
            "图标带有柔和的阴影过渡，纯白色背景，"
            "人物头顶头发微微超出圆形边界，突出立体感，"
            "整体线条圆润，色彩鲜明，具有简洁可爱的现代视觉风格，"
            "iOS 系统风格，极简主义，简约高级"
        ),
        "comfortable": (
            "参考附件中人物，保留人物的主要五官、发型等面部特征，"
            "生成一个 Emoji 风格 iOS 系统图标质感样式的人物头像，"
            "人物表情为被奖励感到舒爽愉悦的样子，眼睛微闭上翻、"
            "嘴角不自觉上扬露出享受的笑意、脸颊泛红，略带陶醉感，"
            "圆形图标，正方形 1:1 构图，人物面部居中占画面 80%，"
            "图标底色为淡淡的薄荷绿和蜜桃粉的渐变色，"
            "图标带有柔和的阴影过渡，纯白色背景，"
            "人物头顶头发微微超出圆形边界，突出立体感，"
            "整体线条圆润，色彩鲜明，具有简洁可爱的现代视觉风格，"
            "iOS 系统风格，极简主义，简约高级"
        ),
        "crying": (
            "参考附件中人物，保留人物的主要五官、发型等面部特征，"
            "生成一个 Emoji 风格 iOS 系统图标质感样式的人物头像，"
            "人物表情为大哭的样子，眼睛紧闭挤出泪水，嘴巴大张，眉毛上扬皱起，"
            "圆形图标，正方形 1:1 构图，人物面部居中占画面 80%，"
            "图标底色为淡淡的浅蓝和雾灰蓝的渐变色，"
            "图标带有柔和的阴影过渡，纯白色背景，"
            "人物头顶头发微微超出圆形边界，突出立体感，"
            "整体线条圆润，色彩鲜明，具有简洁可爱的现代视觉风格，"
            "iOS 系统风格，极简主义，简约高级"
        ),
    }

    def __init__(self):
        self.api_key = os.getenv("ARK_API_KEY", "")
        self.ak = os.getenv("VOLC_ACCESSKEY", "")
        self.sk = os.getenv("VOLC_SECRETKEY", "")

    def _create_client(self):
        from volcenginesdkarkruntime import Ark
        # Prefer API Key (Bearer token); fall back to AK/SK
        if self.api_key:
            return Ark(api_key=self.api_key)
        return Ark(ak=self.ak, sk=self.sk)

    def _generate_one_sync(
        self, client, emotion: str, image_b64: str, output_dir: Path
    ) -> tuple[str, str]:
        """Generate one emotion image (sync, called from thread). Returns (emotion, file_path)."""
        prompt = self.EMOTION_PROMPTS[emotion]

        last_err = None
        for attempt in range(2):  # 1 retry
            try:
                resp = client.images.generate(
                    model=self.MODEL,
                    prompt=prompt,
                    image=[image_b64],
                    size="2048x2048",
                    response_format="url",
                    watermark=False,
                )

                if not resp.data:
                    raise RuntimeError(f"Jimeng API returned no data for {emotion}")

                image_url = resp.data[0].url

                # Download the generated image
                img_resp = httpx.get(image_url, timeout=60.0)
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
                    import time
                    time.sleep(2)

        raise last_err

    async def generate_emotions(
        self, source_image: Path, output_dir: Path, on_progress=None
    ) -> dict[str, str]:
        if not self.api_key and not (self.ak and self.sk):
            raise RuntimeError("ARK_API_KEY or VOLC_ACCESSKEY/VOLC_SECRETKEY not set")

        if not source_image.exists():
            raise FileNotFoundError(f"Source image not found: {source_image}")

        output_dir.mkdir(parents=True, exist_ok=True)

        # Read source image and encode as base64 data URI
        raw = source_image.read_bytes()
        b64 = base64.b64encode(raw).decode()
        image_b64 = f"data:image/jpeg;base64,{b64}"

        client = self._create_client()
        loop = asyncio.get_event_loop()

        results = {}
        for i, emotion in enumerate(EMOTIONS):
            if on_progress:
                on_progress(i, len(EMOTIONS), emotion)
            try:
                emotion_name, path = await loop.run_in_executor(
                    None, self._generate_one_sync, client, emotion, image_b64, output_dir
                )
                results[emotion_name] = path
            except Exception as e:
                log.error(f"Jimeng API error for {emotion}: {e}")
                # Fall back to mock for this emotion
                log.warning(f"Falling back to mock for: {emotion}")
                mock_results = await MockAIGCService().generate_emotions(source_image, output_dir)
                if emotion in mock_results:
                    results[emotion] = mock_results[emotion]

        return results
