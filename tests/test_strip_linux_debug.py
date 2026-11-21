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
    # Build a larger library with genuine debug symbols to test the pipeline.
    large_source = tmp_path / "large_fixture.c"
    large_source.write_text(
        "int exported_answer(void) { return 42; }\n" +
        "\n".join(f"static int placeholder_{i}(void) {{ return {i}; }}" for i in range(25000)),
        encoding="utf-8",
    )
    large_lib = tmp_path / "large_fixture.so"
    subprocess.run(["gcc", "-g", "-O0", "-shared", "-fPIC", str(large_source),
                    "-o", str(large_lib)], check=True)
    if large_lib.stat().st_size < 1024 * 1024:
        pytest.skip("Compiler emitted a smaller fixture than expected")
    before = large_lib.stat().st_size
    changed, saved = strip_debug.optimize(tmp_path)
    assert changed >= 1 and saved > 0 and large_lib.stat().st_size < before
    import ctypes
    library = ctypes.CDLL(str(large_lib))
    assert library.exported_answer() == 42


def test_directory_validation(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        strip_debug.optimize(tmp_path / "missing")
