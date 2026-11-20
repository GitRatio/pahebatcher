"""Read-only loopback media player for downloaded MP4/WebM episodes.

The HTML player is intentionally browser-backed: Tk cannot decode video on
its own, while the system browser already provides hardware-accelerated HTML5
playback on Windows, macOS and Linux. No internet-facing service is started.
"""

from __future__ import annotations

import json
import re
import secrets
import threading
import webbrowser
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

from pahebatcher.config import VERSION

SUPPORTED_EXTENSIONS = frozenset({".mp4", ".webm", ".m4v", ".mov"})
MIME_TYPES = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
}
_RANGE = re.compile(r"bytes=(\d*)-(\d*)\Z")
_EPISODE = re.compile(r"^Ep(?:isode)?[\s._-]*(\d+(?:\.\d+)?)\s*[-._ ]*\s*(.*)$", re.I)


@dataclass(frozen=True)
class PlaybackItem:
    path: Path
    series: str
    episode: str
    title: str
    audio: str = ""
    description: str = ""

    @classmethod
    def from_file(cls, path: Path) -> PlaybackItem:
        """Infer metadata from a standalone downloaded file without network calls."""
        match = _EPISODE.match(path.stem)
        episode = match.group(1) if match else "—"
        title = (match.group(2).strip() if match else path.stem) or f"Episode {episode}"
        return cls(path=path, series=path.parent.name, episode=episode, title=title)


class _PlayerHTTPServer(ThreadingHTTPServer):
    session: PlayerSession


class PlayerSession:
    """One private playback page; the only accessible media are explicitly supplied files."""

    def __init__(self, items: list[PlaybackItem]) -> None:
        if not items:
            raise ValueError("Select at least one downloaded video to play.")
        if len(items) > 500:
            raise ValueError("A playlist may contain at most 500 videos.")
        self.items: list[PlaybackItem] = []
        for item in items:
            path = item.path.expanduser().resolve(strict=True)
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                raise ValueError(f"Unsupported video file: {item.path}")
            self.items.append(
                PlaybackItem(path, item.series, item.episode, item.title,
                             item.audio, item.description)
            )
        self.token = secrets.token_urlsafe(32)
        self.nonce = secrets.token_urlsafe(24)
        self._closed = False

        self.server = _PlayerHTTPServer(("127.0.0.1", 0), _PlayerHandler)
        self.server.session = self
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.url = f"http://127.0.0.1:{self.port}/watch/{self.token}/"
        self._thread = threading.Thread(
            target=self.server.serve_forever, name="pahebatcher-player", daemon=True
        )
        self._thread.start()

    def open(self) -> bool:
        return bool(webbrowser.open(self.url, new=1))

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self.server.shutdown()
            self.server.server_close()
            self._thread.join(timeout=2)


class _PlayerHandler(BaseHTTPRequestHandler):
    server_version = "PaheBatcherPlayer"
    sys_version = ""

    @property
    def session(self) -> PlayerSession:
        return cast(_PlayerHTTPServer, self.server).session

    def log_message(self, _format: str, *args: object) -> None:
        return  # Never disclose signed local playback URLs in logs.

    def do_HEAD(self) -> None:
        self._serve(head_only=True)

    def do_GET(self) -> None:
        self._serve(head_only=False)

    def _headers(self, content_type: str, length: int, status: int = 200,
                 extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; "
            f"script-src 'nonce-{self.session.nonce}'; "
            f"style-src 'nonce-{self.session.nonce}'; "
            "media-src 'self'; img-src 'self' data:; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        )
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def _error(self, status: int) -> None:
        self._headers("text/plain; charset=utf-8", 0, status=status)

    def _serve(self, head_only: bool) -> None:
        origin = f"http://127.0.0.1:{self.session.port}"
        if self.headers.get("Host") != f"127.0.0.1:{self.session.port}":
            self._error(403)
            return
        if self.headers.get("Origin") not in (None, origin):
            self._error(403)
            return

        uri = urlsplit(self.path)
        if uri.query or uri.fragment:
            self._error(404)
            return
        if uri.path == f"/watch/{self.session.token}/":
            template = (Path(__file__).parent / "assets" / "player.html").read_text(
                encoding="utf-8"
            )
            playlist = [
                {
                    "series": item.series,
                    "episode": item.episode,
                    "title": item.title,
                    "audio": item.audio,
                    "description": item.description,
                    "kind": "Episode" if item.episode not in {"", "—"} else "Standalone video",
                    "format": item.path.suffix.lower().lstrip(".").upper(),
                    "src": f"/media/{self.session.token}/{index}",
                }
                for index, item in enumerate(self.session.items)
            ]
            safe_json = json.dumps(playlist, ensure_ascii=True).replace("<", "\\u003c").replace(
                ">", "\\u003e"
            ).replace("&", "\\u0026")
            html = template.replace("__PLAYER_DATA__", safe_json).replace(
                "__PLAYER_NONCE__", self.session.nonce
            ).replace("__APP_VERSION__", VERSION)
            data = html.encode("utf-8")
            self._headers("text/html; charset=utf-8", len(data))
            if not head_only:
                self.wfile.write(data)
            return

        prefix = f"/media/{self.session.token}/"
        if not uri.path.startswith(prefix):
            self._error(404)
            return
        index_str = uri.path[len(prefix):]
        if not index_str.isascii() or not index_str.isdecimal():
            self._error(404)
            return
        index = int(index_str)
        if index >= len(self.session.items):
            self._error(404)
            return

        media = self.session.items[index].path
        try:
            with media.open("rb") as handle:
                size = media.stat().st_size
                start, end = 0, size - 1
                partial = False
                if rng := self.headers.get("Range"):
                    match = _RANGE.fullmatch(rng.strip())
                    if not match or not size or not any(match.groups()):
                        self._headers("text/plain", 0, status=416,
                                      extra={"Content-Range": f"bytes */{size}"})
                        return
                    first, last = match.groups()
                    if first:
                        start = int(first)
                        end = min(int(last), size - 1) if last else size - 1
                    else:
                        start = max(size - int(last), 0)
                        end = size - 1
                    if start >= size or start > end:
                        self._headers("text/plain", 0, status=416,
                                      extra={"Content-Range": f"bytes */{size}"})
                        return
                    partial = True
                length = max(0, end - start + 1)
                extra = {"Accept-Ranges": "bytes"}
                if partial:
                    extra["Content-Range"] = f"bytes {start}-{end}/{size}"
                self._headers(MIME_TYPES[media.suffix.lower()], length,
                              status=206 if partial else 200, extra=extra)
                if not head_only:
                    handle.seek(start)
                    remaining = length
                    while remaining:
                        block = handle.read(min(256 * 1024, remaining))
                        if not block:
                            break
                        self.wfile.write(block)
                        remaining -= len(block)
        except (FileNotFoundError, PermissionError, IsADirectoryError):
            self._error(404)
        except (BrokenPipeError, ConnectionResetError):
            return  # The viewer skipped or closed the episode.
