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


def test_external_link_restricted_to_gitratio_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(webui.webbrowser, "open", lambda url: True)
    assert webui.TakeoverApi.open_external(
        "https://github.com/GitRatio/pahebatcher/releases/tag/preview"
    ) == {"ok": True}
    for url in ("https://evil.example/", "http://github.com/GitRatio/pahebatcher",
                "https://github.com/GitRatio/pahebatcher.evil/", "javascript:alert(1)"):
        with pytest.raises(ValueError):
            webui.TakeoverApi.open_external(url)