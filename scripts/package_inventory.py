"""Report actual bundle footprint without following duplicate file links."""

from __future__ import annotations

import sys
from pathlib import Path


def inventory(root: Path) -> tuple[int, int, int]:
    apparent = unique = links = 0
    seen: set[tuple[int, int]] = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            links += 1
            continue
        if not path.is_file():
            continue
        stat = path.stat()
        apparent += stat.st_size
        key = (stat.st_dev, stat.st_ino)
        if key not in seen or not stat.st_ino:
            unique += stat.st_size
            seen.add(key)
    return apparent, unique, links


if __name__ == "__main__":
    apparent, unique, links = inventory(Path(sys.argv[1]))
    print(f"Regular file bytes: {apparent:,}")
    print(f"Unique file bytes: {unique:,} ({unique / 1048576:.2f} MiB)")
    print(f"Symbolic links: {links}")
