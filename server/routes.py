"""REST API routes — character management + photo upload + AIGC generation."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, BackgroundTasks

from server.aigc_service import MockAIGCService, EMOTIONS

router = APIRouter()

def _characters_dir(request: Request) -> Path:
    return request.app.state.characters_dir

def _read_manifest(char_dir: Path) -> Optional[dict]:
    manifest = char_dir / "manifest.json"
    if not manifest.exists():
        return None
    return json.loads(manifest.read_text())

def _write_manifest(char_dir: Path, data: dict):
    (char_dir / "manifest.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))


@router.get("/status")
async def status():
    return {"status": "ok"}


@router.get("/characters")
async def list_characters(request: Request):
    chars_dir = _characters_dir(request)
    result = []
    for d in sorted(chars_dir.iterdir()):
        if not d.is_dir():
            continue
        manifest = _read_manifest(d)
        if manifest is None:
            continue
        emotions_ready = [e for e in EMOTIONS if (d / f"{e}.png").exists()]
        result.append({
            "name": d.name,
            "display_name": manifest.get("name", d.name),
            "emotions_ready": len(emotions_ready),
            "emotions_total": len(EMOTIONS),
            "status": manifest.get("status", "ready"),
        })
    return result


@router.get("/characters/{name}")
async def get_character(name: str, request: Request):
    char_dir = _characters_dir(request) / name
    if not char_dir.exists():
        raise HTTPException(404, f"Character '{name}' not found")
    manifest = _read_manifest(char_dir)
    if manifest is None:
        raise HTTPException(404, f"Character '{name}' has no manifest")
    emotions = {}
    for e in EMOTIONS:
        img_path = char_dir / f"{e}.png"
        emotions[e] = {"ready": img_path.exists(), "url": f"/characters/{name}/{e}.png" if img_path.exists() else None}
    return {"name": name, "display_name": manifest.get("name", name), "emotions": emotions, "status": manifest.get("status", "ready")}


@router.post("/characters", status_code=201)
async def create_character(
    request: Request,
    background_tasks: BackgroundTasks,
    name: str = Form(...),
    photo: UploadFile = File(...),
):
    chars_dir = _characters_dir(request)
    char_dir = chars_dir / name
    if char_dir.exists():
        raise HTTPException(409, f"Character '{name}' already exists")
    char_dir.mkdir(parents=True)

    source_path = char_dir / "source.jpg"
    content = await photo.read()
    source_path.write_bytes(content)

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

    background_tasks.add_task(_generate)

    return {"name": name, "status": "generating"}


@router.delete("/characters/{name}")
async def delete_character(name: str, request: Request):
    char_dir = _characters_dir(request) / name
    if not char_dir.exists():
        raise HTTPException(404, f"Character '{name}' not found")
    shutil.rmtree(char_dir)
    return {"deleted": name}
