"""GitRatio Bunny Takeover native desktop UI.

HTML/CSS is rendered by pywebview; source resolution and downloads continue to
use the existing Python backend. The HTML is bundled and never loaded from a
remote origin. Keep the classic Tk UI available as an explicit legacy option.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
import webbrowser
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pahebatcher.config import VERSION
from pahebatcher.gui.app import GuiDashboard
from pahebatcher.gui.bridge import Backend, load_settings, save_settings
from pahebatcher.gui.player import SUPPORTED_EXTENSIONS, PlaybackItem, PlayerSession


class TakeoverApi:
    """Narrow, validated Python bridge for a bundled, trusted HTML page."""

    def __init__(self) -> None:
        self.cfg = load_settings()
        self.backend = Backend(self.cfg)
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True, name="takeover-asyncio")
        self.thread.start()
        self._boot_future: concurrent.futures.Future[None] = self._submit(self.backend.start())
        self._anime: Any = None
        self._job: concurrent.futures.Future[dict[str, Path | None]] | None = None
        self._job_error = ""
        self._job_result = ""
        self._job_title = ""
        self._job_count = 0
        self._players: list[PlayerSession] = []
        self._library_paths: dict[str, Path] = {}
        self._lock = threading.RLock()

    def _submit(self, coro: Any) -> concurrent.futures.Future[Any]:
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def _ready(self) -> None:
        self._boot_future.result(timeout=90)

    def bootstrap(self) -> dict[str, Any]:
        self._ready()
        return {
            "version": VERSION,
            "solver_ok": self._submit(self.backend.ping()).result(timeout=25),
            "settings": self._settings(),
        }

    def _settings(self) -> dict[str, Any]:
        return {
            "quality": int(self.cfg.get("quality")),
            "audio_lang": str(self.cfg.get("audio_lang")),
            "max_parallel": int(self.cfg.get("max_parallel")),
            "output_dir": str(self.cfg.get("output_dir")),
        }

    def search(self, query: str) -> list[dict[str, Any]]:
        if not 1 <= len(query.strip()) <= 160:
            raise ValueError("Enter a search term of 1-160 characters.")
        self._ready()
        results = self._submit(self.backend.search(query.strip())).result(timeout=100)
        allowed = ("title", "session", "type", "year", "episodes")
        return [{k: row.get(k) for k in allowed} for row in results[:100]]

    def scan(self, session: str) -> dict[str, Any]:
        if not 1 <= len(session) <= 140:
            raise ValueError("Invalid series identifier.")
        self._ready()
        anime = self._submit(self.backend.scan(session)).result(timeout=100)
        with self._lock:
            self._anime = anime
        return {
            "title": anime.title,
            "description": anime.description,
            "episodes": [{"title": ep.title, "session": ep.session, "number": ep.number,
                          "ep_str": ep.ep_str, "audio": ep.audio} for ep in anime.episodes],
        }

    def save_settings(self, updates: object) -> dict[str, bool]:
        if not isinstance(updates, dict) or set(updates) - {"quality", "audio_lang", "max_parallel"}:
            raise ValueError("Unsupported setting.")
        # Validate the entire payload before changing any saved preference.
        # A partially invalid request must never leave a half-updated config.
        for key, value in updates.items():
            valid_quality = key == "quality" and type(value) is int and value in (360, 720, 1080)
            valid_audio = key == "audio_lang" and value in ("jpn", "eng")
            valid_parallel = key == "max_parallel" and type(value) is int and 1 <= value <= 4
            if not (valid_quality or valid_audio or valid_parallel):
                raise ValueError("Invalid setting value.")
        with self._lock:
            for key, value in updates.items():
                self.cfg.set(key, value)
            save_settings(self.cfg)
        return {"ok": True}

    def choose_folder(self) -> str:
        import webview  # type: ignore[import-not-found]
        window = webview.windows[0]
        try:
            result = window.create_file_dialog(webview.FOLDER_DIALOG)
        except Exception as exc:
            raise RuntimeError("The system could not open a folder chooser.") from exc
        if not result:
            return ""
        selected = Path(result[0]).expanduser()
        if not selected.is_dir():
            raise ValueError("Please choose an existing directory.")
        with self._lock:
            self.cfg.set("output_dir", str(selected))
            save_settings(self.cfg)
        return str(selected)

    def download(self, indices: list[int]) -> dict[str, Any]:
        if not indices or len(indices) > 500:
            raise ValueError("Select between 1 and 500 episodes.")
        if any(type(index) is not int or index < 0 for index in indices):
            raise ValueError("Invalid episode selection.")
        if len(indices) != len(set(indices)):
            raise ValueError("Duplicate episode selection.")
        self._ready()
        from pahebatcher import ffmpeg_setup

        if ffmpeg_setup.find_ffmpeg() is None:
            return {"started": False,
                    "error": "FFmpeg is required to combine episodes. Install FFmpeg first."}
        with self._lock:
            anime = self._anime
            if anime is None or any(index >= len(anime.episodes) for index in indices):
                raise ValueError("Please open a series and select its episodes first.")
            if self._job is not None and not self._job.done():
                return {"started": False, "error": "A download is already running."}
            self._job_error = ""
            self._job_result = ""
            self._job_title = anime.title
            self._job_count = len(indices)
            self.backend.current_dash = None
            selected = [anime.episodes[index] for index in indices]

            import pahebatcher.downloader as dl

            def dashboard_factory(total_eps: int, console: Any = None,
                                  title: str = "") -> GuiDashboard:
                dash = GuiDashboard(total_eps, title=title)
                self.backend.current_dash = dash
                return dash

            dl.Dashboard = dashboard_factory  # type: ignore[assignment,misc,attr-defined,unused-ignore]
            self._job = self._submit(self.backend.download(anime, selected))
            self._job.add_done_callback(self._download_done)
        return {"started": True}

    def _download_done(self, future: concurrent.futures.Future[Any]) -> None:
        with self._lock:
            try:
                results = future.result()
                done = sum(1 for path in results.values() if path is not None)
                self._job_result = f"Finished: {done} of {self._job_count} episodes downloaded."
            except (Exception, concurrent.futures.CancelledError) as exc:
                self._job_error = "Download cancelled." if future.cancelled() else str(exc)[:500]

    def status(self) -> dict[str, Any]:
        with self._lock:
            job = self._job
            active = bool(job and not job.done())
            dash = self.backend.current_dash
            items: list[dict[str, Any]] = []
            fraction = 0.0
            if dash is not None:
                import time
                now = time.monotonic()
                try:
                    fraction = float(dash._overall(now)[0])
                    items = [{"episode": str(key), "state": str(ep.state),
                              "fraction": float(ep.fraction)}
                             for key, ep in list(dash._eps.items())[:150]]
                except (AttributeError, RuntimeError, ValueError):
                    pass
            if not active and job and not self._job_error and self._job_result:
                fraction = 1.0
            msg = self._job_error or self._job_result or (
                f"Downloading {self._job_count} episode(s)…" if active else "No active download"
            )
            return {"title": self._job_title, "active": active, "fraction": fraction,
                    "items": items, "message": msg}

    def cancel(self) -> dict[str, bool]:
        with self._lock:
            if self._job is not None and not self._job.done():
                self._job.cancel()
        return {"ok": True}

    def library(self) -> list[dict[str, Any]]:
        directory = Path(str(self.cfg.get("output_dir"))).expanduser().resolve()
        if not directory.is_dir():
            return []
        files: list[Path] = []
        for candidate in directory.rglob("*"):
            if len(files) >= 200:
                break
            if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
                path = candidate.resolve()
                if path.is_relative_to(directory):
                    files.append(path)
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        with self._lock:
            self._library_paths = {str(index): path for index, path in enumerate(files)}
        return [{"id": str(index), "name": path.name, "size": path.stat().st_size,
                 "series": path.parent.name} for index, path in enumerate(files)]

    def play(self, id_: str) -> dict[str, bool]:
        if not id_.isascii() or not id_.isdecimal():
            raise ValueError("Choose a saved video from Library.")
        with self._lock:
            path = self._library_paths.get(id_)
        root = Path(str(self.cfg.get("output_dir"))).expanduser().resolve()
        if path is None or not path.is_file() or not path.resolve().is_relative_to(root):
            raise ValueError("Video is no longer available in your downloads folder.")
        session = PlayerSession([PlaybackItem.from_file(path)])
        try:
            import webview

            webview.windows[0].load_url(session.url)
        except (ImportError, AttributeError, IndexError, RuntimeError):
            if not session.open():
                session.close()
                raise RuntimeError("No native webview or browser is available for playback.")
        self._players.append(session)
        return {"ok": True}

    def back_to_app(self) -> dict[str, bool]:
        """Return from the local-video player to the existing native application."""
        import webview

        page = Path(__file__).resolve().parent / "assets" / "desktop.html"
        webview.windows[0].load_url(str(page))
        return {"ok": True}

    @staticmethod
    def open_external(url: str) -> dict[str, bool]:
        if not isinstance(url, str):
            raise ValueError("External link must be a URL.")
        parsed = urlsplit(url)
        permitted = (
            parsed.path == "/GitRatio/pahebatcher"
            or parsed.path.startswith("/GitRatio/pahebatcher/")
            or parsed.path == "/abdullahkhfb/pahebatcher"
        )
        if (parsed.scheme != "https" or parsed.hostname != "github.com" or
                parsed.username or parsed.password or parsed.port or not permitted):
            raise ValueError("This external link is not permitted.")
        return {"ok": bool(webbrowser.open(url))}

    def shutdown(self) -> None:
        try:
            if self._job is not None and not self._job.done():
                self._job.cancel()
            self._submit(self.backend.close()).result(timeout=8)
        except Exception:
            pass
        for session in self._players:
            session.close()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(timeout=2)


def main() -> None:
    """Launch the real HTML-powered desktop UI, not the previous Tk facsimile."""
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError(
            'The new desktop UI needs pywebview. Install using: pip install "pahebatcher[gui,browser]"'
        ) from exc

    api = TakeoverApi()
    assets = Path(__file__).resolve().parent / "assets"
    page = assets / "desktop.html"
    if not page.is_file():
        raise RuntimeError("Bundled desktop.html is missing. Reinstall the application.")
    try:
        webview.create_window(
            f"GitRatio Bunny Takeover · v{VERSION}", str(page), js_api=api,
            width=1450, height=920, min_size=(1040, 700),
            background_color="#0d101b", text_select=False,
        )
        webview.start(debug=False)
    finally:
        api.shutdown()


if __name__ == "__main__":
    main()
