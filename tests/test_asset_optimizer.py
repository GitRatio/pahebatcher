"""Ensure optional build-time PNG recompression is pixel-perfect and safe."""
from __future__ import annotations

import importlib.util
import struct
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("asset_optimizer", ROOT / "scripts/optimize_png.py")
assert SPEC is not None and SPEC.loader is not None
optimizer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(optimizer)


def chunk(kind: bytes, body: bytes) -> bytes:
    return (struct.pack(">I", len(body)) + kind + body +
            struct.pack(">I", zlib.crc32(kind + body) & 0xffffffff))


def test_png_is_lossless_and_no_larger(tmp_path: Path) -> None:
    # Repeated true-color pixels, intentionally stored with little compression.
    width, height = 64, 64
    raw = (bytes([0]) + bytes([0x45, 0x78, 0xAB]) * width) * height
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    original = (optimizer.SIGNATURE + chunk(b"IHDR", ihdr) +
                chunk(b"IDAT", zlib.compress(raw, 0)) + chunk(b"IEND", b""))
    file = tmp_path / "art.png"
    file.write_bytes(original)
    before, after = optimizer.optimize_png(file)
    assert before == len(original)
    assert after < before
    output = file.read_bytes()
    assert output.startswith(optimizer.SIGNATURE)
    cursor = 8
    while cursor < len(output):
        size = int.from_bytes(output[cursor:cursor+4], "big")
        kind = output[cursor+4:cursor+8]
        payload = output[cursor+8:cursor+8+size]
        if kind == b"IDAT":
            assert zlib.decompress(payload) == raw
        cursor += 12 + size


def test_invalid_png_refused_without_modification(tmp_path: Path) -> None:
    file = tmp_path / "invalid.png"
    file.write_bytes(b"not a png")
    try:
        optimizer.optimize_png(file)
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid PNG should be rejected")
    assert file.read_bytes() == b"not a png"


def test_mascot_png_dimensions_are_not_reduced() -> None:
    # Asset dimensions matter more than raw file size: do not reduce sharpness.
    from pahebatcher.gui.webui import __file__ as module_file

    source = Path(module_file).parent / "assets" / "bunny.png"
    png = source.read_bytes()
    assert png.startswith(optimizer.SIGNATURE)
    width, height = struct.unpack_from(">II", png, 16)
    assert width >= 500 and height >= 500
