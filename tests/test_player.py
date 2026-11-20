"""Regression tests for the cross-platform read-only video player."""

from __future__ import annotations

import http.client
from pathlib import Path

import pytest

from pahebatcher.gui.player import PlaybackItem, PlayerSession


@pytest.fixture
def player(tmp_path: Path):
    video = tmp_path / "Ep 003 - Test.mp4"
    video.write_bytes(b"0123456789")
    session = PlayerSession([
        PlaybackItem(video, "Sample Series", "3", "A Test Episode", "jpn"),
    ])
    try:
        yield session
    finally:
        session.close()


def request(session: PlayerSession, suffix: str, headers: dict[str, str] | None = None,
            method: str = "GET") -> tuple[int, dict[str, str], bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", session.port, timeout=4)
    try:
        conn.request(method, suffix, headers=headers or {})
        response = conn.getresponse()
        data = response.read()
        return response.status, dict(response.getheaders()), data
    finally:
        conn.close()


def test_player_metadata_and_csp(player: PlayerSession) -> None:
    status, headers, data = request(player, f"/watch/{player.token}/")
    assert status == 200
    assert headers["Content-Type"].startswith("text/html")
    assert "default-src 'none'" in headers["Content-Security-Policy"]
    assert "Sample Series" in data.decode("utf-8")
    assert "A Test Episode" in data.decode("utf-8")
    assert "video" in data.decode("utf-8")
    assert "@videojs/cdn@10.5.0/video-neutral.js" in data.decode("utf-8")
    assert "https://cdn.jsdelivr.net" in headers["Content-Security-Policy"]
    assert "connect-src 'self'" in headers["Content-Security-Policy"]
    assert "video-neutral-skin" in data.decode("utf-8")
    from pahebatcher.config import VERSION
    assert f"v{VERSION}" in data.decode("utf-8")


def test_range_and_seek(player: PlayerSession) -> None:
    route = f"/media/{player.token}/0"
    status, headers, data = request(player, route, {"Range": "bytes=3-5"})
    assert (status, data) == (206, b"345")
    assert headers["Content-Range"] == "bytes 3-5/10"
    assert headers["Accept-Ranges"] == "bytes"
    status, headers, data = request(player, route, {"Range": "bytes=-3"})
    assert (status, data) == (206, b"789")
    status, headers, data = request(player, route, {"Range": "bytes=10-"})
    assert status == 416
    assert headers["Content-Range"] == "bytes */10"
    assert data == b""


def test_head_and_full_file(player: PlayerSession) -> None:
    route = f"/media/{player.token}/0"
    status, headers, data = request(player, route, method="HEAD")
    assert (status, data) == (200, b"")
    assert headers["Content-Length"] == "10"
    status, headers, data = request(player, route)
    assert (status, data) == (200, b"0123456789")


def test_deny_unknown_urls_and_cross_site(player: PlayerSession) -> None:
    assert request(player, "/media/bad/0")[0] == 404
    assert request(player, f"/media/{player.token}/../0")[0] == 404
    assert request(player, f"/media/{player.token}/1234")[0] == 404
    assert request(player, f"/watch/{player.token}/", {"Host": "evil.example"})[0] == 403
    assert request(player, f"/watch/{player.token}/",
                   {"Origin": "https://evil.example"})[0] == 403


def test_xss_metadata_is_escaped(tmp_path: Path) -> None:
    file = tmp_path / "movie.webm"
    file.write_bytes(b"123")
    injection = '</script><img src="http://attacker">'
    session = PlayerSession([PlaybackItem(file, injection, "1", injection)])
    try:
        _, _, data = request(session, f"/watch/{session.token}/")
        assert injection.encode() not in data
        assert b"\\u003c/script\\u003e" in data
    finally:
        session.close()


def test_unknown_format_and_missing_file(tmp_path: Path) -> None:
    unknown = tmp_path / "not-video.txt"
    unknown.write_text("bad")
    with pytest.raises(ValueError, match="Unsupported"):
        PlayerSession([PlaybackItem.from_file(unknown)])
    with pytest.raises(FileNotFoundError):
        PlayerSession([PlaybackItem.from_file(tmp_path / "missing.mp4")])
    with pytest.raises(ValueError, match="at least one"):
        PlayerSession([])


def test_filename_metadata(tmp_path: Path) -> None:
    item = PlaybackItem.from_file(tmp_path / "My Series" / "Ep 012 - Finale.mp4")
    assert (item.series, item.episode, item.title) == ("My Series", "012", "Finale")


def test_no_external_browser_dependency(player: PlayerSession, monkeypatch: pytest.MonkeyPatch) -> None:
    urls: list[str] = []
    monkeypatch.setattr("pahebatcher.gui.player.webbrowser.open", lambda url, new: urls.append(url) or True)
    assert player.open()
    assert urls == [player.url]


def test_series_synopsis_from_download(tmp_path: Path) -> None:
    video = tmp_path / "Ep 001.mp4"
    video.write_bytes(b"movie")
    session = PlayerSession([
        PlaybackItem(video, "Test Anime", "1", "Pilot", "jpn", "A story about heroes."),
    ])
    try:
        status, _headers, html = request(session, f"/watch/{session.token}/")
        text = html.decode("utf-8")
        assert status == 200
        assert "A story about heroes." in text
        assert "About this anime" in text
    finally:
        session.close()


def test_synopsis_extraction() -> None:
    from pahebatcher.extract.scanner import AnimePaheScanner

    doc = (
        '<meta property="og:description" content="A short preview">'
        '<div class="anime-synopsis"><p>A hero &amp; friend</p> faces danger.</div>'
    )
    assert AnimePaheScanner._extract_description(doc) == "A hero & friend faces danger."
    assert AnimePaheScanner._extract_description(
        '<meta name="description" content="A standalone movie">'
    ) == "A standalone movie"
    assert AnimePaheScanner._extract_description("<html><body></body></html>") == ""


def test_player_csp_avoids_unrestricted_remote_requests(player: PlayerSession) -> None:
    status, headers, _ = request(player, f"/watch/{player.token}/")
    assert status == 200
    csp = headers["Content-Security-Policy"]
    assert "connect-src 'self'" in csp
    assert "media-src 'self'" in csp
    assert "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net" in csp


def test_responsive_player_styles_are_consolidated(player: PlayerSession) -> None:
    status, _headers, page = request(player, f"/watch/{player.token}/")
    html = page.decode("utf-8")
    assert status == 200
    assert html.count('<style nonce=') == 1
    assert "grid-template-columns: minmax(0, 1fr)" in html
    assert "@media (max-width: 1050px)" in html
    assert "@media (max-width: 390px)" in html
    assert "video-player:fullscreen" in html
    assert "video-neutral-skin { aspect-ratio: 16 / 9" in html
    assert "min-height:180px" not in html


def test_takeover_branding_download_link_and_local_filename(player: PlayerSession) -> None:
    status, headers, data = request(player, f"/watch/{player.token}/")
    html = data.decode("utf-8")
    assert status == 200
    assert '<div class="desktop-window">' in html
    assert 'class="rail-bunny"' in html
    assert 'class="graffiti-banner"' in html
    assert 'id="download-video"' in html
    assert "Ep 003 - Test.mp4" in html
    assert "__PLAYER_TOKEN__" not in html
    assert f'/mascot/{player.token}/bunny.png' in html
    assert "data:image/png;base64" not in html
    assert "img-src 'self';" in headers["Content-Security-Policy"]


def test_full_resolution_mascot_is_served_locally(player: PlayerSession) -> None:
    from struct import unpack

    image_url = f"/mascot/{player.token}/bunny.png"
    status, headers, png = request(player, image_url)
    assert status == 200
    assert headers["Content-Type"] == "image/png"
    assert png.startswith(b"\\x89PNG\\r\\n\\x1a\\n")
    assert unpack(">II", png[16:24]) == (650, 650)
    assert request(player, "/mascot/invalid/bunny.png")[0] == 404
    assert request(player, image_url, {"Origin": "https://evil.example"})[0] == 403
