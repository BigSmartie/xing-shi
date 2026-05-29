from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonFileCache:
    """Small JSON cache that works locally and in simple serverless runtimes."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def get(self, namespace: str, key: str) -> dict[str, Any] | None:
        path = self._path(namespace, key)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def set(self, namespace: str, key: str, value: dict[str, Any]) -> None:
        path = self._path(namespace, key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _path(self, namespace: str, key: str) -> Path:
        safe_namespace = "".join(ch for ch in namespace if ch.isalnum() or ch in "-_")
        safe_key = "".join(ch for ch in key if ch.isalnum() or ch in "-_")
        return self.root / safe_namespace / f"{safe_key}.json"

