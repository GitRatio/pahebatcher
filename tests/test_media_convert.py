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


@pytest.mark.parametrize(
    ("extension", "video", "audio"),
    [("mp4", "libx264", "aac"), ("mkv", "libx264", "aac"), ("webm", "libvpx-vp9", "libopus")],
)
def test_transcode_profiles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                            extension: str, video: str, audio: str) -> None:
    source = tmp_path / "input.mp4"
    source.write_bytes(b"original")
    destination = tmp_path / ("output." + extension)
    monkeypatch.setattr(media_convert, "find_ffmpeg", lambda: "ffmpeg")

    def run(args, **kwargs):
        assert args[args.index("-c:v") + 1] == video
        assert args[args.index("-c:a") + 1] == audio
        assert args[args.index("-threads:v") + 1] == "2"
        assert args[args.index("-threads:a") + 1] == "1"
        assert args[args.index("-map") + 1] == "0"
        Path(args[-1]).write_bytes(b"converted")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(media_convert.subprocess, "run", run)
    assert media_convert.convert(source, destination, transcode=True) == destination
    assert source.read_bytes() == b"original"
