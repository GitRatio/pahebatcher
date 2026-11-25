"""Optional local media remuxing using the existing FFmpeg installation."""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

from pahebatcher.ffmpeg_setup import NO_WINDOW, find_ffmpeg

FORMATS = frozenset({"mp4", "mkv", "webm"})
INPUTS = frozenset({".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi", ".ts"})


def remux(source: Path, destination: Path) -> Path:
    """Copy streams without quality loss; fail safely on incompatible codecs."""
    source = source.resolve(strict=True)
    destination = destination.resolve()
    if not source.is_file() or source.suffix.lower() not in INPUTS:
        raise ValueError("Choose a supported local video file.")
    if destination.suffix.lower().lstrip(".") not in FORMATS:
        raise ValueError("Unsupported output format.")
    if source == destination or destination.exists():
        raise FileExistsError("Output already exists; choose a new filename.")
    executable = find_ffmpeg()
    if executable is None:
        raise RuntimeError("Install FFmpeg before converting media.")
    fd, name = tempfile.mkstemp(prefix=".pahebatcher-", suffix=destination.suffix, dir=destination.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        result = subprocess.run(
            [executable, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
             "-protocol_whitelist", "file", "-i", str(source), "-map", "0",
             "-c", "copy", str(temporary)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=1800, creationflags=NO_WINDOW, check=False,
        )
        if result.returncode or temporary.stat().st_size == 0:
            raise RuntimeError("Remux failed; the target container may not support all source tracks.")
        # Hard-link publication is atomic and refuses to overwrite an existing file.
        os.link(temporary, destination)
        return destination
    finally:
        temporary.unlink(missing_ok=True)
