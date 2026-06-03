"""Run the vendored OpenAVC driver validator against a single driver file."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import yaml  # type: ignore[import-untyped]

CATEGORY_TO_DIR: dict[str, str] = {
    "projector": "projectors",
    "display": "displays",
    "switcher": "switchers",
    "audio": "audio",
    "camera": "cameras",
    "video": "video",
    "streaming": "streaming",
    "lighting": "lighting",
    "power": "power",
    "utility": "utility",
}

_C2O_ROOT = Path(__file__).resolve().parents[1]
_VENDORED_ROOT = _C2O_ROOT / "vendored" / "openavc_drivers"
_BUILD_INDEX = _VENDORED_ROOT / "scripts" / "build_index.py"
_MANUFACTURERS = _VENDORED_ROOT / "manufacturers.json"
_POINTER_LOC_RE = re.compile(r"^[A-Za-z0-9_<>\[\].]+$")


@dataclass(frozen=True)
class UpstreamValidationResult:
    """Captured result from the vendored OpenAVC validation script."""

    passed: bool
    exit_code: int
    stdout: str
    stderr: str
    errors: list[str]
    pointers: list[str]


def _read_driver_category(driver_path: Path) -> str:
    """Return the driver category when it can be read, else a collectable default."""
    try:
        data = yaml.safe_load(driver_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return "utility"
    if not isinstance(data, dict):
        return "utility"
    category = data.get("category")
    if not isinstance(category, str):
        return "utility"
    return category if category in CATEGORY_TO_DIR else "utility"


@contextmanager
def _stage_driver_island(driver_path: Path) -> Iterator[Path]:
    """Create a temporary upstream-style repo root containing one driver."""
    category_dir = CATEGORY_TO_DIR[_read_driver_category(driver_path)]
    with tempfile.TemporaryDirectory(prefix="c2o-validate-") as tmp:
        root = Path(tmp)
        shutil.copy2(_MANUFACTURERS, root / "manufacturers.json")
        driver_dir = root / category_dir
        driver_dir.mkdir()
        shutil.copy2(driver_path, driver_dir / driver_path.name)
        yield root


def _run_build_index_check(repo_root: Path) -> subprocess.CompletedProcess[str]:
    """Invoke the vendored build_index.py in check-only mode."""
    return subprocess.run(
        [sys.executable, str(_BUILD_INDEX), "--check", "--root", str(repo_root)],
        capture_output=True,
        text=True,
        check=False,
    )


def _parse_upstream_errors(stderr: str) -> list[str]:
    """Extract upstream validation error bodies from stderr."""
    errors: list[str] = []
    for line in stderr.splitlines():
        if line.startswith("  - "):
            errors.append(line[4:])
    return errors


def _errors_to_pointers(errors: list[str]) -> list[str]:
    """Best-effort conversion from upstream ``path: loc: msg`` lines to pointers."""
    pointers: list[str] = []
    for error in errors:
        parts = error.split(": ", 2)
        if len(parts) < 3:
            continue
        loc = parts[1].strip()
        if loc == "<root>":
            pointers.append("/")
            continue
        if not loc or not _POINTER_LOC_RE.fullmatch(loc):
            continue
        pointers.append("/" + loc.replace(".", "/"))
    return pointers


def validate_upstream(driver_path: Path) -> UpstreamValidationResult:
    """Validate a single .avcdriver by staging it for the upstream validator."""
    resolved = driver_path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(str(resolved))
    if resolved.suffix != ".avcdriver":
        raise ValueError(f"{resolved}: expected a .avcdriver file")

    with _stage_driver_island(resolved) as repo_root:
        proc = _run_build_index_check(repo_root)

    errors = _parse_upstream_errors(proc.stderr)
    return UpstreamValidationResult(
        passed=proc.returncode == 0,
        exit_code=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        errors=errors,
        pointers=_errors_to_pointers(errors),
    )
