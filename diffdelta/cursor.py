"""Cursor persistence — automatically saves and loads polling state."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Optional


DEFAULT_CURSOR_DIR = os.path.join(Path.home(), ".diffdelta")
DEFAULT_CURSOR_FILE = "cursors.json"


class CursorStore:
    """Persists cursors to a local JSON file so bots survive restarts.

    By default, cursors are saved to ~/.diffdelta/cursors.json.
    Each feed URL gets its own cursor entry.
    """

    def __init__(self, path: Optional[str] = None) -> None:
        if path:
            self._path = path
        else:
            self._path = os.path.join(DEFAULT_CURSOR_DIR, DEFAULT_CURSOR_FILE)

        self._cursors: Dict[str, str] = {}
        self._load()

    def get(self, key: str) -> Optional[str]:
        """Get the stored cursor for a feed key."""
        return self._cursors.get(key)

    def set(self, key: str, cursor: str) -> None:
        """Save a cursor and persist to disk."""
        self._cursors[key] = cursor
        self._save()

    def clear(self, key: Optional[str] = None) -> None:
        """Clear cursor(s). If key is None, clears all cursors."""
        if key:
            self._cursors.pop(key, None)
        else:
            self._cursors.clear()
        self._save()

    def _load(self) -> None:
        """Load cursors from disk."""
        try:
            if os.path.exists(self._path):
                with open(self._path, "r") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._cursors = data
        except (json.JSONDecodeError, OSError):
            # Corrupted file — start fresh
            self._cursors = {}

    def _save(self) -> None:
        """Persist cursors to disk."""
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            with open(self._path, "w") as f:
                json.dump(self._cursors, f, indent=2)
        except OSError:
            # Can't write — silently continue (in-memory only)
            pass
