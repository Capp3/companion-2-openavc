"""Resolve local, URL, or bare-ID sources to module roots."""

from __future__ import annotations

import shutil
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from c2o.source.classify import SourceKind, classify_source
from c2o.source.local import resolve_local
from c2o.source.remote import git_clone


@dataclass(frozen=True, slots=True)
class ResolvedSource:
    """Resolved module root plus lifecycle metadata."""

    root: Path
    kind: SourceKind
    clone_url: str | None = None
    tempdir: Path | None = None


@contextmanager
def resolve_source(raw: str, *, keep_temp: bool = False) -> Iterator[ResolvedSource]:
    """Resolve a source argument and clean up cloned tempdirs on exit."""
    kind, clone_url = classify_source(raw)
    tempdir: Path | None = None

    try:
        if kind is SourceKind.LOCAL:
            yield ResolvedSource(root=resolve_local(raw.strip()), kind=kind)
            return

        if clone_url is None:
            msg = f"Remote source missing clone URL for {raw!r}"
            raise AssertionError(msg)

        tempdir = Path(tempfile.mkdtemp(prefix="c2o-clone-"))
        git_clone(clone_url, tempdir, depth=1)
        yield ResolvedSource(root=tempdir, kind=kind, clone_url=clone_url, tempdir=tempdir)
    finally:
        if tempdir is not None:
            if keep_temp:
                print(f"Preserved clone at: {tempdir}", file=sys.stderr)
            else:
                shutil.rmtree(tempdir)
