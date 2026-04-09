"""Interaction count persistence — JSON file storage with write debouncing."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path


class InteractionStore:
    def __init__(self, path: Path):
        self._path = path
        self._counts: dict[str, int] = {}
        self.last_hit_ts: str | None = None
        self._dirty = False
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                self._counts = data.get("counts", {})
                self.last_hit_ts = data.get("last_hit_ts")
            except (json.JSONDecodeError, KeyError):
                pass  # Corrupt file — start fresh

    def increment(self, character: str) -> int:
        with self._lock:
            self._counts[character] = self._counts.get(character, 0) + 1
            self.last_hit_ts = datetime.now(timezone.utc).isoformat()
            self._dirty = True
            return self._counts[character]

    def get_count(self, character: str) -> int:
        return self._counts.get(character, 0)

    def get_total(self) -> int:
        with self._lock:
            return sum(self._counts.values())

    def get_rankings(self) -> list[dict]:
        with self._lock:
            snapshot = list(self._counts.items())
        sorted_items = sorted(
            snapshot,
            key=lambda x: (-x[1], x[0])
        )
        return [
            {"name": name, "count": count, "rank": i + 1}
            for i, (name, count) in enumerate(sorted_items)
        ]

    def flush(self):
        """Write to disk if dirty."""
        with self._lock:
            if not self._dirty:
                return
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps({
                "counts": self._counts,
                "last_hit_ts": self.last_hit_ts,
            }, indent=2, ensure_ascii=False))
            self._dirty = False
