"""Contract checks for the webview-based native Bunny Takeover UI."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from pahebatcher.config import VERSION
from pahebatcher.gui import webui


ASSETS = Path(webui.__file__).parent / "assets"


def test_desktop_ui_has_correct_screen_contract() -> None:
    html = (ASSETS / "desktop.html").read_text(encoding="utf-8")
    javascript = (ASSETS / "desktop.js").read_text(encoding="utf-8")
    assert "frame" in html and "hero" in html and "rail-art" in html
    assert "grid-template-columns:225px minmax(0,1fr)" in html
    for page in ("home", "episodes", "downloads", "player", "library", "settings", "about"):
        assert f'id="page-{page}"' in html
    for key in ("download-selected", "download-progress", "search-results", "series-title"):
        assert f'id="{key}"' in html
    for method in ("bootstrap", "search", "scan", "save_settings", "download", "status", "library", "play"):
        assert f"'{method}'" in javascript
    assert f"v{VERSION}" in html
    assert "Solo Leveling" not in html  # no fake sample data pretending to be actual results
    assert "__BUNNY__" not in html
    assert 'id="about-version"' in html
    assert 'class="about-details"' in html
    assert "ready.version" in javascript
    assert "takeover_bunny.b64" not in html


def test_default_python_module_launches_native_gui() -> None:
    launcher = (ASSETS.parent / "__main__.py").read_text(encoding="utf-8")
    assert "pahebatcher.gui.webui import main" in launcher
    assert "pahebatcher.gui.app import main" not in launcher


def test_bundled_mascot_and_icons_are_valid_images() -> None:
    png = (ASSETS / "bunny.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert int.from_bytes(png[16:20], "big") >= 500
    assert (ASSETS / "icon.png").read_bytes()[:8] == png[:8]
    assert (ASSETS / "icon.ico").read_bytes()[:4] == b"\x00\x00\x01\x00"


class FakeConfig:
    def __init__(self) -> None:
        self.data = {"quality": 720, "audio_lang": "jpn", "max_parallel": 2}

    def get(self, key: str) -> object:
        return self.data[key]

    def set(self, key: str, value: object) -> None:
        self.data[key] = value


def test_native_settings_bridge_validates_mutations(monkeypatch: pytest.MonkeyPatch) -> None:
    api = webui.TakeoverApi.__new__(webui.TakeoverApi)
    api.cfg = FakeConfig()  # type: ignore[assignment]
    api._lock = threading.RLock()
    monkeypatch.setattr(webui, "save_settings", lambda cfg: None)
    assert api.save_settings({"quality": 1080, "audio_lang": "eng", "max_parallel": 4}) == {"ok": True}
    assert api.cfg.get("quality") == 1080
    with pytest.raises(ValueError):
        api.save_settings({"max_parallel": 99})
    with pytest.raises(ValueError):
        api.save_settings({"unsafe": "true"})
    with pytest.raises(ValueError):
        api.save_settings({"quality": "1080"})
    # Reject the whole payload, not only the invalid final setting.
    before = dict(api.cfg.data)
    with pytest.raises(ValueError):
        api.save_settings({"quality": 360, "max_parallel": 99})
    assert api.cfg.data == before
    with pytest.raises(ValueError):
        api.save_settings(None)  # type: ignore[arg-type]


def test_external_link_restricted_to_gitratio_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(webui.webbrowser, "open", lambda url: True)
    assert webui.TakeoverApi.open_external(
        "https://github.com/GitRatio/pahebatcher/releases/tag/preview"
    ) == {"ok": True}
    assert webui.TakeoverApi.open_external(
        "https://github.com/abdullahkhfb/pahebatcher"
    ) == {"ok": True}
    for url in ("https://evil.example/", "http://github.com/GitRatio/pahebatcher",
                "https://github.com/GitRatio/pahebatcher.evil/", "javascript:alert(1)"):
        with pytest.raises(ValueError):
            webui.TakeoverApi.open_external(url)

def test_multiseries_queue_runs_serially_and_preserves_selected_series(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import concurrent.futures
    from types import SimpleNamespace

    from pahebatcher import ffmpeg_setup

    monkeypatch.setattr(ffmpeg_setup, "find_ffmpeg", lambda: "/usr/bin/ffmpeg")
    api = webui.TakeoverApi.__new__(webui.TakeoverApi)
    api._lock = threading.RLock()
    api._ready = lambda: None  # type: ignore[method-assign]
    api._pending = []
    api._queue_limit = 20
    api._job = None
    api._job_error = ""
    api._job_result = ""
    api._job_count = 0
    api._job_title = ""
    api._job_total_done = 0
    ep_a, ep_b = SimpleNamespace(ep_str="1"), SimpleNamespace(ep_str="2")
    anime_a = SimpleNamespace(title="Series A", episodes=[ep_a])
    anime_b = SimpleNamespace(title="Series B", episodes=[ep_b])
    api._anime = anime_a
    submitted: list[concurrent.futures.Future] = []

    class FakeBackend:
        current_dash = None

        async def download(self, anime: object, episodes: list[object]) -> dict:
            return {}

    api.backend = FakeBackend()  # type: ignore[assignment]

    def submit(coro: object) -> concurrent.futures.Future:
        coro.close()  # type: ignore[attr-defined]
        future: concurrent.futures.Future = concurrent.futures.Future()
        submitted.append(future)
        return future

    api._submit = submit  # type: ignore[method-assign]
    assert api.download([0])["started"]
    api._anime = anime_b
    assert api.download([0])["started"]
    assert len(submitted) == 1
    assert api.status()["queued"] == [{"title": "Series B", "episodes": 1}]
    submitted[0].set_result({"1": Path("a.mp4")})
    assert len(submitted) == 2
    assert api._job_title == "Series B"
    assert not api._pending
    submitted[1].set_result({"2": None})
    result = api.status()
    assert not result["active"]
    assert result["completed_episodes"] == 1
    assert result["fraction"] < 1
    assert "Partial download" in result["message"]


def test_multiseries_queue_rejects_invalid_selection_without_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = webui.TakeoverApi.__new__(webui.TakeoverApi)
    api._lock = threading.RLock()
    api._ready = lambda: None  # type: ignore[method-assign]
    api._pending = []
    api._queue_limit = 20
    api._anime = None
    for indices in ([0, 0], [-1], ["0"], list(range(501)), []):
        with pytest.raises(ValueError):
            api.download(indices)  # type: ignore[arg-type]
    assert api._pending == []


def test_network_status_is_local_and_redacted(monkeypatch: pytest.MonkeyPatch) -> None:
    import shutil
    import sys
    import urllib.request

    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/warp-cli")
    monkeypatch.setattr(urllib.request, "getproxies", lambda: {"https": "http://user:secret@example.org:8080"})
    assert webui.TakeoverApi.network_status() == {
        "warp_detected": True,
        "system_proxy_configured": True,
        "routing_verified": False,
    }


def test_convert_media_bridge_preserves_original(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from pahebatcher import media_convert

    api = webui.TakeoverApi.__new__(webui.TakeoverApi)
    api.cfg = FakeConfig()  # type: ignore[assignment]
    api.cfg.set("output_dir", str(tmp_path))
    api._lock = threading.RLock()
    api._conversion_lock = threading.Lock()
    source = tmp_path / "episode.mp4"
    source.write_bytes(b"original")
    api._library_paths = {"0": source}

    def fake_remux(src: Path, dst: Path) -> Path:
        assert src == source.resolve()
        dst.write_bytes(b"converted")
        return dst

    monkeypatch.setattr(media_convert, "remux", fake_remux)
    assert api.convert_media("0", "mkv") == {"ok": True, "name": "episode.converted.mkv"}
    assert source.read_bytes() == b"original"
    with pytest.raises(ValueError):
        api.convert_media("0", "../mp4")
    with pytest.raises(ValueError):
        api.convert_media("99", "mp4")
    assert not api._conversion_lock.locked()
