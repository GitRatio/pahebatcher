"""Deduplicate byte-identical Qt shared libraries in the Linux distribution.

Keep every original path and file mode. Only regular, identical ELF files
in the two known PyInstaller Qt library directories are eligible.
"""
from __future__ import annotations

import hashlib
import os
import stat
import sys
import tempfile
from pathlib import Path


def digest(path: Path) -> bytes:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").digest()


def optimize(root: Path) -> tuple[int, int]:
    base = root / "_internal"
    qt = base / "PyQt6" / "Qt6" / "lib"
    if not qt.is_dir() or qt.is_symlink():
        return 0, 0
    count = saved = 0
    for first in sorted(base.glob("lib*.so*")):
        second = qt / first.name
        if first.is_symlink() or second.is_symlink():
            continue
        if not first.is_file() or not second.is_file():
            continue
        a, b = first.stat(), second.stat()
        if a.st_dev != b.st_dev or a.st_ino == b.st_ino or b.st_nlink != 1:
            continue
        if a.st_size != b.st_size or stat.S_IMODE(a.st_mode) != stat.S_IMODE(b.st_mode):
            continue
        with first.open("rb") as stream:
            if stream.read(4) != b"\x7fELF":
                continue
        if digest(first) != digest(second):
            continue
        with tempfile.TemporaryDirectory(prefix=".pb-dedupe-", dir=second.parent) as temporary:
            link = Path(temporary) / "library"
            os.link(first, link)
            os.replace(link, second)
        count += 1
        saved += b.st_size
    return count, saved


if __name__ == "__main__":
    count, saved = optimize(Path(sys.argv[1]))
    print(f"Deduplicated libraries: {count}; saved {saved:,} bytes ({saved / 1048576:.2f} MiB)")
