"""Local filesystem source resolution."""

from __future__ import annotations

import json
from pathlib import Path


def resolve_local(source: str) -> Path:
    """Resolve a local directory path to an absolute module root."""
    path = Path(source).expanduser()
    if not path.is_dir():
        msg = f"Source is not a directory: {source}"
        raise ValueError(msg)
    return path.resolve()


def read_module_id(root: Path) -> str:
    """Read module id from companion/manifest.json."""
    manifest_path = root / "companion" / "manifest.json"
    if not manifest_path.is_file():
        msg = f"Missing companion/manifest.json under {root}"
        raise ValueError(msg)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    module_id = data.get("id")
    if not isinstance(module_id, str) or not module_id:
        msg = f"manifest.json missing string 'id' field: {manifest_path}"
        raise ValueError(msg)
    return module_id
