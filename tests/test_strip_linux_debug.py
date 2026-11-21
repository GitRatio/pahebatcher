"""Verify Linux debug stripping preserves a runnable native shared library."""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/strip_linux_debug.py"
SPEC = importlib.util.spec_from_file_location("strip_linux_debug", SOURCE)
assert SPEC is not None and SPEC.loader is not None
strip_debug = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(strip_debug)


@pytest.mark.skipif(os.name == "nt", reason="Linux-only release optimization")
def test_debug_strip_preserves_runtime_symbols(tmp_path: Path) -> None:
    if not shutil.which("gcc") or not shutil.which("strip"):
        pytest.skip("Linux native build tools unavailable")
    source = tmp_path / "fixture.c"
    source.write_text("int exported_answer(void) { return 42; }\n", encoding="utf-8")
    output = tmp_path / "fixture.so"
    subprocess.run(["gcc", "-g", "-shared", "-fPIC", str(source), "-o", str(output)], check=True)
    before = output.stat().st_size
    changed, saved = strip_debug.optimize(tmp_path)
    assert changed == 0  # small fixture is intentionally skipped by 1 MiB limit
    assert saved == 0
    if not shutil.which("objcopy"):
        pytest.skip("objcopy is unavailable")
    # Use a synthetic debug section instead of compiling 25,000 functions.
    large_lib = tmp_path / "large_fixture.so"
    shutil.copy2(output, large_lib)
    debug_section = tmp_path / "extra_debug.bin"
    debug_section.write_bytes(bytes([42]) * (2 * 1024 * 1024))
    subprocess.run(
        ["objcopy", "--add-section", f".debug_extra={debug_section}", str(large_lib)],
        check=True,
    )
    before = large_lib.stat().st_size
    changed, saved = strip_debug.optimize(tmp_path)
    assert changed >= 1 and saved > 0 and large_lib.stat().st_size < before
    import ctypes
    library = ctypes.CDLL(str(large_lib))
    assert library.exported_answer() == 42


def test_directory_validation(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        strip_debug.optimize(tmp_path / "missing")
