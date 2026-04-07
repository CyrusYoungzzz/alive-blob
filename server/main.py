"""FastAPI application entry point."""

from __future__ import annotations

from pathlib import Path
from typing import Optional
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

def create_app(characters_dir: Optional[Path] = None) -> FastAPI:
    if characters_dir is None:
        characters_dir = Path(__file__).parent.parent / "characters"
    characters_dir.mkdir(parents=True, exist_ok=True)

    app = FastAPI(title="Alive Blob Server")
    app.state.characters_dir = characters_dir

    from server.routes import router
    app.include_router(router, prefix="/api")

    # Character images static serving
    app.mount("/characters", StaticFiles(directory=str(characters_dir)), name="characters")

    # Eye App static files (added later in Task 7)
    eye_app_dir = Path(__file__).parent.parent / "eye-app"
    if eye_app_dir.exists():
        app.mount("/eye-app", StaticFiles(directory=str(eye_app_dir), html=True), name="eye-app")

    # Mobile control panel static files
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app

app = create_app()
