"""Safely strip non-runtime debug symbols from Linux ELF bundle files.

Build-time only. A temporary copy is stripped and atomically replaces the
original only if GNU strip succeeds and the resulting ELF is smaller.
Dynamic symbols are retained (--strip-debug, never --strip-all).
"""
from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path


def optimize(root: Path) -> tuple[int, int]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Expected an existing real bundle directory")
    stripper = shutil.which("strip")
    if stripper is None:
        raise RuntimeError("GNU strip is required to optimize Linux ELF bundles")
    optimized = 0
    saved = 0
    for path in root.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        meta = path.stat()
        if not stat.S_ISREG(meta.st_mode) or meta.st_size < 1024 * 1024:
            continue
        with path.open("rb") as handle:
            if handle.read(4) != bytes([0x7f, 0x45, 0x4c, 0x46]):
                continue
        fd, temporary = tempfile.mkstemp(prefix=".pb-strip-", dir=path.parent)
        os.close(fd)
        try:
            shutil.copy2(path, temporary)
            result = subprocess.run(
                [stripper, "--strip-debug", "--", temporary],
                capture_output=True, text=True, check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(f"strip failed for {path}: {result.stderr[:250]}")
            after = os.stat(temporary).st_size
            if 0 < after < meta.st_size:
                os.replace(temporary, path)
                optimized += 1
                saved += meta.st_size - after
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return optimized, saved


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    changed, saved = optimize(args.directory)
    print(f"Debug-symbol stripped ELF files: {changed}; saved {saved / 1048576:.1f} MiB")


if __name__ == "__main__":
    main()
