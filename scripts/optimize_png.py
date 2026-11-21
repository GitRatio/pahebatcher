"""Losslessly recompress static PNG assets for release packaging.

Preserves the exact filtered pixel stream, alpha, dimensions and image quality.
Only writes smaller files. Standard library only; no downloads or new runtime deps.
"""
from __future__ import annotations

import argparse
import struct
import zlib
from pathlib import Path

SIGNATURE = b"\x89PNG\r\n\x1a\n"
MAX_PNG_SIZE = 12 * 1024 * 1024


def optimize_png(path: Path) -> tuple[int, int]:
    original = path.read_bytes()
    if not original.startswith(SIGNATURE) or len(original) > MAX_PNG_SIZE:
        raise ValueError(f"Unsupported PNG: {path}")
    chunks: list[tuple[bytes, bytes]] = []
    cursor = len(SIGNATURE)
    while cursor + 12 <= len(original):
        size = struct.unpack_from(">I", original, cursor)[0]
        start = cursor + 8
        stop = start + size
        if stop + 4 > len(original):
            raise ValueError("Malformed PNG")
        kind = original[cursor + 4:cursor + 8]
        data = original[start:stop]
        crc = struct.unpack_from(">I", original, stop)[0]
        if zlib.crc32(kind + data) & 0xffffffff != crc:
            raise ValueError("Corrupt PNG checksum")
        chunks.append((kind, data))
        cursor = stop + 4
        if kind == b"IEND":
            break
    if not chunks or chunks[0][0] != b"IHDR" or chunks[-1][0] != b"IEND" or cursor != len(original):
        raise ValueError("Invalid PNG chunk sequence")
    kinds = [kind for kind, _ in chunks]
    indices = [index for index, kind in enumerate(kinds) if kind == b"IDAT"]
    # Animated PNGs and complex interleaved streams are unchanged.
    if (not indices or indices != list(range(indices[0], indices[-1] + 1))
            or any(kind in (b"acTL", b"fcTL", b"fdAT") for kind in kinds)):
        return len(original), len(original)
    compressed = b"".join(chunks[index][1] for index in indices)
    decoder = zlib.decompressobj()
    filtered = decoder.decompress(compressed, 64 * 1024 * 1024 + 1)
    if len(filtered) > 64 * 1024 * 1024 or decoder.unconsumed_tail or not decoder.eof:
        raise ValueError("Oversized PNG image data")
    filtered += decoder.flush()
    smaller = zlib.compress(filtered, level=9)
    if len(smaller) >= len(compressed):
        return len(original), len(original)
    output = bytearray(SIGNATURE)
    for index, (kind, payload) in enumerate(chunks):
        if index == indices[0]:
            payload = smaller
        elif index in indices:
            continue
        output += struct.pack(">I", len(payload)) + kind + payload
        output += struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)
    if len(output) < len(original):
        path.write_bytes(output)
        return len(original), len(output)
    return len(original), len(original)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args()
    for path in args.paths:
        before, after = optimize_png(path)
        print(f"{path}: {before:,} -> {after:,} bytes ({before-after:,} saved)")


if __name__ == "__main__":
    main()
