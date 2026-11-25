from pathlib import Path
from types import SimpleNamespace

import pytest

from pahebatcher import media_convert


def test_remux_preserves_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "input.mp4"
    source.write_bytes(b"original")
    destination = tmp_path / "output.mkv"
    monkeypatch.setattr(media_convert, "find_ffmpeg", lambda: "ffmpeg")

    def run(args, **kwargs):
        assert "-protocol_whitelist" in args
        assert "copy" in args
        Path(args[-1]).write_bytes(b"converted")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(media_convert.subprocess, "run", run)
    assert media_convert.remux(source, destination) == destination
    assert source.read_bytes() == b"original"
    assert destination.read_bytes() == b"converted"
    with pytest.raises(FileExistsError):
        media_convert.remux(source, destination)


def test_remux_failure_removes_partial_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "input.mp4"
    source.write_bytes(b"original")
    destination = tmp_path / "output.webm"
    monkeypatch.setattr(media_convert, "find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(media_convert.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1))
    with pytest.raises(RuntimeError):
        media_convert.remux(source, destination)
    assert list(tmp_path.iterdir()) == [source]
