"""Deduplicate identical Linux bundle binaries without removing required paths.

Linux tar preserves hard links, so identical copies can share on-disk blocks
and an archive entry. Only regular files with equal sizes, permissions and
SHA-256 hashes are eligible. Windows/macOS bundles are deliberately untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import stat
import tempfile
from pathlib import Path

MIN_SIZE = 1024 * 1024


def digest(path: Path) -> bytes:
    hash_ = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hash_.update(chunk)
    return hash_.digest()


def deduplicate(root: Path, min_size: int = MIN_SIZE) -> tuple[int, int]:
    """Return (linked file count, estimated bytes of unique disk space saved)."""
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Expected an existing real directory")
    candidates: dict[tuple[int, int], list[Path]] = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            continue
        metadata = path.stat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size < min_size:
            continue
        key = (metadata.st_size, stat.S_IMODE(metadata.st_mode))
        candidates.setdefault(key, []).append(path)

    linked = 0
    bytes_saved = 0
    for (size, _mode), paths in candidates.items():
        if len(paths) < 2:
            continue
        seen: dict[bytes, Path] = {}
        for path in paths:
            key = digest(path)
            first = seen.get(key)
            if first is None:
                seen[key] = path
                continue
            before = path.stat()
            first_stat = first.stat()
            if (before.st_dev != first_stat.st_dev or
                    (before.st_dev, before.st_ino) == (first_stat.st_dev, first_stat.st_ino)):
                continue
            fd, name = tempfile.mkstemp(prefix=".pb-dedup-", dir=path.parent)
            os.close(fd)
            os.unlink(name)
            try:
                os.link(first, name)
                os.replace(name, path)
            finally:
                if os.path.exists(name):
                    os.unlink(name)
            linked += 1
            bytes_saved += size
    return linked, bytes_saved


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    linked, saved = deduplicate(args.bundle)
    print(f"Deduplicated {linked} identical files; saved ~{saved / 1048576:.1f} MiB unpacked")


if __name__ == "__main__":
    main()
