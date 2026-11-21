"""Linux hardlink optimization preserves file paths, bytes, and modes."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "deduplicate_bundle.py"
SPEC = importlib.util.spec_from_file_location("bundle_dedup", MODULE)
assert SPEC and SPEC.loader
dedup = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dedup)


@pytest.mark.skipif(os.name == "nt", reason="Hardlinks are an optional Linux packaging optimization")
def test_identical_binary_paths_are_preserved(tmp_path: Path) -> None:
    a = tmp_path / "libQt6Gui.so.6"
    b = tmp_path / "PyQt6" / "libQt6Gui.so.6"
    b.parent.mkdir()
    payload = b"duplicate library bytes" * 512
    a.write_bytes(payload)
    b.write_bytes(payload)
    linked, saved = dedup.deduplicate(tmp_path, min_size=1)
    assert linked == 1 and saved == len(payload)
    assert a.read_bytes() == b.read_bytes() == payload
    assert a.stat().st_ino == b.stat().st_ino
    assert a.stat().st_nlink == 2
    assert dedup.deduplicate(tmp_path, min_size=1) == (0, 0)


@pytest.mark.skipif(os.name == "nt", reason="Hardlinks are an optional Linux packaging optimization")
def test_different_files_and_symlinks_are_not_modified(tmp_path: Path) -> None:
    a, b, c = (tmp_path / n for n in ("one.so", "two.so", "link.so"))
    a.write_bytes(b"AAAA")
    b.write_bytes(b"BBBB")
    c.symlink_to(a)
    assert dedup.deduplicate(tmp_path, min_size=1) == (0, 0)
    assert c.is_symlink() and a.stat().st_ino != b.stat().st_ino


def test_requires_real_folder(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        dedup.deduplicate(tmp_path / "missing")
