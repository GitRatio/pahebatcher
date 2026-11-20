"""pahebatcher desktop app (Tkinter). Search → pick episodes → watch downloads finish."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any

from pahebatcher import ffmpeg_setup
from pahebatcher.config import VERSION
from pahebatcher.gui.bridge import Backend, Bridge, load_settings, save_settings
from pahebatcher.gui.player import PlaybackItem, PlayerSession
from pahebatcher.gui.widgets import (
    BG,
    ERR,
    LINE,
    MUTED,
    OK,
    PANEL,
    PINK,
    STYLE_COLORS,
    TEXT,
    WARN,
    Button,
    Fonts,
    Link,
    Segmented,
    SlimScrollbar,
    ThinBar,
    make_entry,
    make_listbox,
)
from pahebatcher.models import AnimeInfo, EpisodeInfo
from pahebatcher.ui.dashboard import _STATES, Dashboard, _fmt_eta
from pahebatcher.utils import fmt_bytes

PIP_CMD = 'pip install "pahebatcher[browser]"'
EST_MB = {360: 50, 720: 90, 1080: 150}
MAX_CONTENT = 1280  # content stays readable on wide / full-screen windows


class GuiDashboard(Dashboard):
    """The terminal dashboard's state machine without the terminal: the GUI polls it."""

    def start(self) -> None:  # no Rich Live
        return

    def stop(self) -> None:
        return


def clean_title(title: str) -> str:
    return re.sub(r"\s+(?:DUB|SUB)\s*$", "", title or "", flags=re.I).strip() or "—"


# ── download rows ────────────────────────────────────────────────────────────
class EpRow(tk.Frame):
    def __init__(self, master: tk.Misc, key: str, fonts: Fonts) -> None:
        super().__init__(master, bg=BG)
        self.columnconfigure(2, weight=1)
        self.name = tk.Label(self, text=f"EP {key}", font=fonts.mono, fg=MUTED, bg=BG, width=7, anchor="w")
        self.state = tk.Label(self, font=fonts.mono, bg=BG, width=15, anchor="w")
        self.bar = ThinBar(self, height=3)
        self.detail = tk.Label(self, font=fonts.mono, fg=MUTED, bg=BG, width=24, anchor="e")
        self.name.grid(row=0, column=0, pady=5)
        self.state.grid(row=0, column=1, padx=(8, 12), pady=5)
        self.bar.grid(row=0, column=2, sticky="ew", pady=5)
        self.detail.grid(row=0, column=3, padx=(12, 0), pady=5)

    def update_from(self, ep: Any, now: float) -> None:
        glyph, style = _STATES.get(ep.state, (ep.state, "muted"))
        self.state.configure(text=ep.note or glyph, fg=STYLE_COLORS.get(style, MUTED))
        self.bar.set(ep.fraction)
        self.detail.configure(text=Dashboard._detail(ep, now).plain)


class DownloadView(tk.Frame):
    def __init__(self, app: App) -> None:
        super().__init__(app.body, bg=BG)
        f = app.fonts
        self.app = app
        self.title = tk.Label(self, font=f.title, fg=TEXT, bg=BG, anchor="w")
        self.title.pack(fill="x")
        self.sub = tk.Label(self, font=f.small, fg=MUTED, bg=BG, anchor="w")
        self.sub.pack(fill="x", pady=(2, 14))
        bar_row = tk.Frame(self, bg=BG)
        bar_row.pack(fill="x", pady=(0, 18))
        self.overall = ThinBar(bar_row, height=5)
        self.overall.pack(side="left", fill="x", expand=True)
        self.pct = tk.Label(bar_row, font=f.bold, fg=PINK, bg=BG, width=5, anchor="e")
        self.pct.pack(side="left")

        holder = tk.Frame(self, bg=BG)
        holder.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(holder, bg=BG, highlightthickness=0, bd=0)
        sb = SlimScrollbar(holder, self.canvas.yview, side="right", fill="y")
        self.inner = tk.Frame(self.canvas, bg=BG)
        win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self._sb = sb
        self.inner.bind("<Configure>", lambda _e: self._sync_scroll())
        self.canvas.bind("<Configure>", lambda e: self._resize(win, e.width))
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb._pack_kw["before"] = self.canvas
        self.canvas.bind_all("<MouseWheel>", self._wheel)

        foot = tk.Frame(self, bg=BG)
        foot.pack(fill="x", pady=(14, 0))
        self.status = tk.Label(foot, font=f.small, fg=MUTED, bg=BG, anchor="w")
        self.status.pack(side="left")
        self.btn_back = Button(foot, "Back to search", app.show_search, f)
        self.btn_open = Button(foot, "Open folder", self.open_folder, f)
        self.btn_watch = Button(foot, "Watch videos", self.watch_videos, f, primary=True)
        self.btn_cancel = Button(foot, "Cancel", self.cancel, f)
        self.rows: dict[str, EpRow] = {}
        self._dash_id = 0
        self.active = False
        self.future: Any = None
        self.out_dir = ""
        self._total = 0
        self._series = ""
        self._description = ""
        self._episode_map: dict[str, EpisodeInfo] = {}
        self._playlist: list[PlaybackItem] = []

    def _resize(self, win: int, width: int) -> None:
        self.canvas.itemconfigure(win, width=width)
        self._sync_scroll()

    def _sync_scroll(self) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.canvas.yview_moveto(self.canvas.yview()[0])  # re-emit so the bar shows/hides itself
        if self.inner.winfo_reqheight() <= self.canvas.winfo_height():
            self.canvas.yview_moveto(0)

    def _wheel(self, e: tk.Event[Any]) -> None:
        if self.winfo_ismapped() and self._sb.winfo_ismapped():
            self.canvas.yview_scroll(-1 if e.delta > 0 else 1, "units")

    def begin(self, title: str, total: int, out_dir: str, episodes: list[EpisodeInfo],
              description: str = "") -> None:
        self._series = title
        self._description = description
        self._episode_map = {ep.session: ep for ep in episodes}
        self._playlist = []
        self.title.configure(text=title)
        self.sub.configure(text=f"0 of {total} · starting")
        self.status.configure(text="")
        self.overall.set(0)
        self.pct.configure(text="0%")
        for w in self.inner.winfo_children():
            w.destroy()
        self.rows.clear()
        self._dash_id, self._total, self.out_dir, self.active = 0, total, out_dir, True
        for b in (self.btn_back, self.btn_open, self.btn_watch, self.btn_cancel):
            b.pack_forget()
        self.btn_cancel.pack(side="right")

    def refresh(self) -> None:
        dash = self.app.backend.current_dash
        if dash is None:
            return
        if id(dash) != self._dash_id:  # a retry pass starts a fresh dashboard
            self._dash_id = id(dash)
            for w in self.inner.winfo_children():
                w.destroy()
            self.rows.clear()
        now = time.monotonic()
        items = list(dash._eps.items())
        for key, ep in items:
            row = self.rows.get(key)
            if row is None:
                row = EpRow(self.inner, key, self.app.fonts)
                row.pack(fill="x")
                self.rows[key] = row
            row.update_from(ep, now)
        frac, speed, eta = dash._overall(now)
        self.overall.set(frac)
        self.pct.configure(text=f"{frac * 100:.0f}%")
        text = f"{dash._done_eps} of {self._total}"
        if speed > 0:
            text += f" · {fmt_bytes(int(speed))}/s · eta {_fmt_eta(eta)}"
        self.sub.configure(text=text)

    def finished(self, results: dict[str, Path | None]) -> None:
        self._playlist = []
        for session, path in results.items():
            if path is None or not path.is_file():
                continue
            ep = self._episode_map.get(session)
            self._playlist.append(PlaybackItem(
                path=path, series=self._series,
                episode=ep.ep_str if ep else "—",
                title=clean_title(ep.title) if ep else path.stem,
                audio=ep.audio if ep else "",
                description=self._description,
            ))
        self.refresh()
        self.active = False
        ok = sum(1 for v in results.values() if v is not None)
        fail = len(results) - ok
        self.overall.set(1.0 if not fail else self.overall._frac)
        self.sub.configure(text=f"{ok} of {self._total} completed" + (f" · {fail} failed" if fail else ""))
        done_text, done_color = ("✓ Finished", OK) if not fail else ("Finished with errors", WARN)
        self.status.configure(text=done_text, fg=done_color)
        self._end_buttons(show_open=ok > 0)

    def failed(self, exc: BaseException) -> None:
        self.active = False
        self.status.configure(text=f"✗ {exc}", fg=ERR)
        self._end_buttons(show_open=False)

    def cancel(self) -> None:
        if self.future is not None:
            self.future.cancel()
        self.active = False
        self.status.configure(text="Cancelled. Progress is kept; start again to resume.", fg=WARN)
        self._end_buttons(show_open=False)

    def _end_buttons(self, show_open: bool) -> None:
        self.btn_cancel.pack_forget()
        self.btn_back.pack(side="right")
        self.btn_watch.pack_forget()
        if show_open:
            self.btn_open.pack(side="right", padx=(0, 10))
            if self._playlist:
                self.btn_watch.pack(side="right", padx=(0, 10))

    def watch_videos(self) -> None:
        if self._playlist:
            self.app.play_items(self._playlist)

    def open_folder(self) -> None:
        path = self.out_dir
        if not path or not Path(path).exists():
            return
        if sys.platform == "win32":
            getattr(os, "startfile")(path)  # noqa: B009 - Windows-only API
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])


# ── episode picker ───────────────────────────────────────────────────────────
class EpisodesView(tk.Frame):
    def __init__(self, app: App) -> None:
        super().__init__(app.body, bg=BG)
        f = app.fonts
        self.app = app
        self.anime: AnimeInfo | None = None
        self.eps: list[EpisodeInfo] = []
        self.sel: set[float] = set()
        Link(self, "← search", app.show_search, f).pack(anchor="w")
        self.title = tk.Label(self, font=f.title, fg=TEXT, bg=BG, anchor="w")
        self.title.pack(fill="x", pady=(8, 0))
        self.sub = tk.Label(self, font=f.small, fg=MUTED, bg=BG, anchor="w")
        self.sub.pack(fill="x", pady=(2, 12))
        self.description = tk.Label(
            self, font=f.small, fg=MUTED, bg=BG, justify="left",
            anchor="w", wraplength=820,
        )
        self.description.pack(fill="x", pady=(0, 16))
        self.description.bind(
            "<Configure>",
            lambda e: self.description.configure(wraplength=max(240, e.width - 12)),
        )

        ctl = tk.Frame(self, bg=BG)
        ctl.pack(fill="x", pady=(0, 10))
        Button(ctl, "All", self.select_all, f).pack(side="left")
        Button(ctl, "None", self.select_none, f).pack(side="left", padx=8)
        self.range = make_entry(ctl, f, width=18)
        self.range.pack(side="left", padx=(12, 8))
        self.range.bind("<Return>", lambda _e: self.select_range())
        Button(ctl, "Select range", self.select_range, f).pack(side="left")
        tk.Label(
            self, text="Examples: 1-12 · 1,4,7 · 5-",
            font=f.small, fg=MUTED, bg=BG, anchor="w",
        ).pack(fill="x", pady=(0, 12))

        frame, self.lb = make_listbox(self, f)
        frame.pack(fill="both", expand=True)
        self.lb.bind("<ButtonRelease-1>", self._click)
        self.lb.bind("<space>", lambda _e: self._toggle(self.lb.index("active")))

        foot = tk.Frame(self, bg=BG)
        foot.pack(fill="x", pady=(14, 0))
        self.summary = tk.Label(foot, font=f.ui, fg=MUTED, bg=BG)
        self.summary.pack(side="left")
        self.go = Button(foot, "Download", self.start, f, primary=True)
        self.go.pack(side="right")

    def load(self, anime: AnimeInfo) -> None:
        self.anime = anime
        by_num = {ep.number: ep for ep in anime.episodes}
        self.eps = [by_num[n] for n in sorted(by_num)]
        self.sel = set()
        self.title.configure(text=anime.title)
        synopsis = anime.description.strip()
        if len(synopsis) > 350:
            synopsis = synopsis[:347].rsplit(" ", 1)[0] + "…"
        self.description.configure(text=synopsis or "Synopsis unavailable for this title.")
        first, last = (self.eps[0].ep_str, self.eps[-1].ep_str) if self.eps else ("-", "-")
        self.sub.configure(text=f"{len(self.eps)} episodes · {first} to {last}")
        self.lb.delete(0, "end")
        for ep in self.eps:
            self.lb.insert("end", self._line(ep, False))
            self.lb.itemconfig("end", fg=MUTED)
        self._summary()

    @staticmethod
    def _line(ep: EpisodeInfo, on: bool) -> str:
        return f" {'[x]' if on else '[ ]'}  Episode {ep.ep_str:<6} {clean_title(ep.title)}"

    def _paint(self, i: int) -> None:
        on = self.eps[i].number in self.sel
        self.lb.delete(i)
        self.lb.insert(i, self._line(self.eps[i], on))
        self.lb.itemconfig(i, fg=PINK if on else MUTED)
        self.lb.selection_clear(0, "end")

    def _toggle(self, i: int) -> None:
        if not 0 <= i < len(self.eps):
            return
        n = self.eps[i].number
        self.sel.symmetric_difference_update({n})
        self._paint(i)
        self._summary()

    def _click(self, e: tk.Event[Any]) -> None:
        self._toggle(int(self.lb.nearest(e.y)))  # type: ignore[no-untyped-call]

    def _set_all(self, numbers: set[float]) -> None:
        self.sel = set(numbers)
        for i in range(len(self.eps)):
            self._paint(i)
        self._summary()

    def select_all(self) -> None:
        self._set_all({e.number for e in self.eps})

    def select_none(self) -> None:
        self._set_all(set())

    def select_range(self) -> None:
        from pahebatcher.ui.prompts import _parse_ep_range

        raw = self.range.get().strip()
        if raw:
            self._set_all(set(_parse_ep_range(raw, self.eps)))

    def _summary(self) -> None:
        n = len(self.sel)
        mb = n * EST_MB.get(int(self.app.cfg.get("quality")), 120)
        self.summary.configure(text=f"{n} selected · ≈ {mb} MB" if n else "nothing selected")
        self.go.configure(text=f"Download {n} episode{'s' if n != 1 else ''}" if n else "Download")
        self.go.enable(n > 0)

    def start(self) -> None:
        if self.anime is None or not self.sel:
            return
        chosen = [e for e in self.eps if e.number in self.sel]
        anime = self.anime
        self.app.ensure_ffmpeg(lambda: self.app.start_download(anime, chosen))


# ── search ───────────────────────────────────────────────────────────────────
class SearchView(tk.Frame):
    def __init__(self, app: App) -> None:
        super().__init__(app.body, bg=BG)
        f = app.fonts
        self.app = app
        self.results: list[dict[str, Any]] = []
        self._token = 0
        row = tk.Frame(self, bg=BG)
        row.pack(fill="x")
        self.entry = make_entry(row, f)
        self.entry.pack(side="left", fill="x", expand=True, ipady=4)
        self.entry.bind("<Return>", lambda _e: self.search())
        self.btn = Button(row, "Search", self.search, f, primary=True)
        self.btn.pack(side="left", padx=(10, 0))
        self.status = tk.Label(self, text="Search for an anime, then double-click a result.", font=f.small,
                               fg=MUTED, bg=BG, anchor="w")
        self.status.pack(fill="x", pady=(10, 8))
        frame, self.lb = make_listbox(self, f)
        frame.pack(fill="both", expand=True)
        self.lb.bind("<Double-Button-1>", lambda _e: self.open())
        self.lb.bind("<Return>", lambda _e: self.open())

        settings = tk.Frame(self, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        settings.pack(fill="x", pady=(18, 0))
        options = tk.Frame(settings, bg=PANEL)
        options.pack(fill="x", padx=16, pady=(15, 12))
        cfg = app.cfg

        def setter(key: str) -> Callable[[Any], None]:
            def _set(v: Any) -> None:
                cfg.set(key, v)
                save_settings(cfg)
            return _set

        def group(label: str, widget_factory: Callable[[tk.Frame], tk.Widget]) -> None:
            section = tk.Frame(options, bg=PANEL)
            section.pack(side="left", padx=(0, 23))
            tk.Label(section, text=label.upper(), font=f.label, fg=MUTED, bg=PANEL,
                     anchor="w").pack(fill="x", pady=(0, 8))
            widget_factory(section).pack(anchor="w")

        group("Quality", lambda p: Segmented(
            p, [("360p", 360), ("720p", 720), ("1080p", 1080)],
            int(cfg.get("quality")), setter("quality"), f,
        ))
        group("Audio", lambda p: Segmented(
            p, [("SUB", "jpn"), ("DUB", "eng")],
            str(cfg.get("audio_lang")), setter("audio_lang"), f,
        ))
        group("Parallel", lambda p: Segmented(
            p, [(str(n), n) for n in (1, 2, 3, 4)],
            int(cfg.get("max_parallel")), setter("max_parallel"), f,
        ))

        folder_row = tk.Frame(settings, bg=PANEL)
        folder_row.pack(fill="x", padx=16, pady=(0, 14))
        tk.Label(folder_row, text="SAVE TO", font=f.label, fg=MUTED, bg=PANEL).pack(side="left")
        Link(folder_row, "Change folder", self.pick_folder, f, bg=PANEL).pack(side="right")
        self.folder = tk.Label(folder_row, font=f.small, fg=TEXT, bg=PANEL, anchor="w")
        self.folder.pack(side="left", padx=(14, 12), fill="x", expand=True)
        self._show_folder()

    def _show_folder(self) -> None:
        p = str(self.app.cfg.get("output_dir"))
        self.folder.configure(text=("…" + p[-65:]) if len(p) > 67 else p)

    def pick_folder(self) -> None:
        d = filedialog.askdirectory(initialdir=str(self.app.cfg.get("output_dir")), title="Download folder")
        if d:
            self.app.cfg.set("output_dir", d)
            save_settings(self.app.cfg)
            self._show_folder()

    def search(self) -> None:
        q = self.entry.get().strip()
        if not q:
            return
        if not self.app.solver_ok:
            self.status.configure(text="No Cloudflare solver yet — see the notice above.", fg=WARN)
            return
        self._token += 1
        token = self._token
        self.status.configure(text=f"Searching “{q}”…", fg=MUTED)
        self.app.bridge.run(
            self.app.backend.search(q),
            ok=lambda r: self._results(token, q, r),
            err=lambda e: self._fail(e),
        )

    def _results(self, token: int, q: str, results: list[dict[str, Any]]) -> None:
        if token != self._token:
            return
        self.results = results
        self.lb.delete(0, "end")
        if not results:
            self.status.configure(text=f"No results for “{q}”.", fg=WARN)
            return
        for r in results:
            title = str(r.get("title", "Unknown"))
            title = title if len(title) <= 46 else title[:45] + "…"
            kind, year, n = (str(r.get(k, "-")) for k in ("type", "year", "episodes"))
            self.lb.insert("end", f" {title:<46}  {kind:<7}{year:<6}{n:>4} eps")
        self.lb.selection_set(0)
        self.status.configure(text=f"{len(results)} results — double-click to open", fg=MUTED)

    def open(self) -> None:
        sel = self.lb.curselection()  # type: ignore[no-untyped-call]
        if not sel:
            return
        session = self.results[sel[0]].get("session")
        if not session:
            return
        self.status.configure(text="Loading episodes…", fg=MUTED)
        self.app.bridge.run(
            self.app.backend.scan(str(session)),
            ok=self._opened,
            err=lambda e: self._fail(e),
        )

    def _fail(self, exc: BaseException) -> None:
        self.status.configure(text=f"✗ {exc}", fg=ERR)

    def _opened(self, anime: AnimeInfo) -> None:
        self.status.configure(text="", fg=MUTED)
        self.app.show_episodes(anime)


# ── main window ──────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"PaheBatcher · GitRatio Edition v{VERSION}")
        self.geometry("1120x780")
        self.minsize(760, 620)
        self.configure(bg=BG)
        self._set_icon()
        self.fonts = Fonts(self)
        self.bridge = Bridge()
        self.cfg = load_settings()
        self.backend = Backend(self.cfg)
        self.solver_ok = False
        self._ff_busy = False
        self._ff_cancel: threading.Event | None = None
        self._after_ff: list[Callable[[], None]] = []
        self._pinging = False
        self._players: list[PlayerSession] = []

        import pahebatcher.downloader as dl

        def factory(total_eps: int, console: Any = None, title: str = "") -> GuiDashboard:
            d = GuiDashboard(total_eps, title=title)
            self.backend.current_dash = d
            return d

        dl.Dashboard = factory  # type: ignore[assignment,misc,attr-defined,unused-ignore]

        self._fullscreen = False
        self._pad = 24
        self._build_header()
        self.notices = tk.Frame(self, bg=BG)
        self.notices.pack(fill="x", padx=24)
        self._build_ffmpeg_notice()
        self._build_solver_notice()
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill="both", expand=True, padx=24, pady=(20, 28))
        self.v_search, self.v_eps, self.v_dl = SearchView(self), EpisodesView(self), DownloadView(self)
        self.show_search()

        self.refresh_ffmpeg_status()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind("<F11>", self.toggle_fullscreen)
        self.bind("<Alt-Return>", self.toggle_fullscreen)
        self.bind("<Escape>", self._exit_fullscreen)
        self.bind("<Configure>", self._on_resize)
        self.after(60, self._pump)
        self.bridge.run(self._boot(), ok=self._set_solver, err=lambda _e: self._set_solver(False))

    def _set_icon(self) -> None:
        assets = Path(__file__).parent / "assets"  # also correct inside a PyInstaller bundle
        try:
            self._icon = tk.PhotoImage(file=str(assets / "icon.png"))  # keep a reference or Tk drops it
            self.iconphoto(True, self._icon)
        except Exception:
            pass  # a missing icon must never stop the app
        if sys.platform == "win32":
            self.update_idletasks()
            _win_set_icon(self, assets / "icon.ico")


    # header + status ------------------------------------------------------
    def _build_header(self) -> None:
        """Two-tier header avoids collisions between the logo, status and actions."""
        f = self.fonts
        hdr = self.hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill="x", padx=24, pady=(22, 0))
        top = tk.Frame(hdr, bg=BG)
        top.pack(fill="x")
        try:
            self._logo = tk.PhotoImage(file=str(Path(__file__).parent / "assets" / "header_logo.png"))
            tk.Label(top, image=self._logo, bg=BG, bd=0).pack(side="left")
        except Exception:
            tk.Label(top, text="PaheBatcher", font=f.logo, fg=PINK, bg=BG).pack(side="left")
        status = tk.Frame(top, bg=BG)
        status.pack(side="right")
        tk.Label(status, text=f"v{VERSION}", font=f.small, fg=MUTED, bg=BG).pack(
            side="right", padx=(12, 0),
        )
        self.dot_solver = tk.Label(status, text="● Solver", font=f.small, fg=MUTED, bg=BG)
        self.dot_solver.pack(side="right", padx=(12, 0))
        self.dot_ffmpeg = tk.Label(status, text="● FFmpeg", font=f.small, fg=MUTED, bg=BG)
        self.dot_ffmpeg.pack(side="right")

        navigation = tk.Frame(hdr, bg=BG)
        navigation.pack(fill="x", pady=(14, 14))
        tk.Label(navigation, text="ANIME DOWNLOADS  /  GITRATIO EDITION",
                 font=f.label, fg=MUTED, bg=BG).pack(side="left")
        self.fs_link = Link(navigation, "Full screen", lambda: self.set_fullscreen(
            not self._fullscreen), f)
        self.fs_link.pack(side="right", padx=(18, 0))
        Link(navigation, "About", self.show_about, f).pack(side="right", padx=(18, 0))
        Link(navigation, "Open player", self.choose_videos, f).pack(side="right")
        tk.Frame(hdr, height=1, bg=LINE).pack(fill="x")

    def show_about(self) -> None:
        """Scrollable About dialog; download buttons never overflow narrow screens."""
        dlg = tk.Toplevel(self)
        dlg.title(f"About PaheBatcher v{VERSION}")
        dlg.configure(bg=BG)
        dlg.geometry("650x560")
        dlg.minsize(500, 420)
        dlg.transient(self)
        dlg.bind("<Escape>", lambda _event: dlg.destroy())

        wrapper = tk.Frame(dlg, bg=BG)
        wrapper.pack(fill="both", expand=True, padx=18, pady=(16, 0))
        canvas = tk.Canvas(wrapper, bg=BG, borderwidth=0, highlightthickness=0)
        scroll = tk.Scrollbar(wrapper, orient="vertical", command=canvas.yview,
                              bg=PANEL, troughcolor=BG, activebackground=PINK)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scroll.set)
        container = tk.Frame(canvas, bg=BG, padx=14, pady=8)
        window = canvas.create_window((0, 0), anchor="nw", window=container)
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window, width=e.width))
        container.bind("<Configure>", lambda _e: canvas.configure(
            scrollregion=canvas.bbox("all"),
        ))
        dlg.bind("<MouseWheel>", lambda e: canvas.yview_scroll(
            -1 if e.delta > 0 else 1, "units"),
        )
        dlg.bind("<Button-4>", lambda _e: canvas.yview_scroll(-1, "units"))
        dlg.bind("<Button-5>", lambda _e: canvas.yview_scroll(1, "units"))
        f = self.fonts
        tk.Label(container, text="🐰  PaheBatcher", font=f.title, bg=BG,
                 fg=TEXT, anchor="w").pack(fill="x")
        tk.Label(container, text=f"GitRatio Edition  ·  v{VERSION}",
                 font=f.small, bg=BG, fg=PINK, anchor="w").pack(
                     fill="x", pady=(5, 20),
                 )
        description = (
            "Download anime with resumable transfers and SUB/DUB selection. "
            "Watch finished episodes in the Video.js browser player, with an "
            "episode queue and source-provided series descriptions. "
            "Video controls fall back to HTML5 when offline; remote streaming "
            "is not part of the desktop player."
        )
        info = tk.Label(container, text=description, font=f.ui, bg=BG, fg=TEXT,
                        justify="left", anchor="nw")
        info.pack(fill="x", pady=(0, 22))
        info.bind("<Configure>", lambda e: info.configure(
            wraplength=max(240, e.width - 8),
        ))
        tk.Label(container, text="DOWNLOAD FOR YOUR DEVICE", font=f.label,
                 bg=BG, fg=MUTED, anchor="w").pack(fill="x", pady=(0, 10))
        choices = [
            ("Windows 11", "https://github.com/GitRatio/pahebatcher/releases/download/preview/pahebatcher-gui-windows-x64.exe"),
            ("Mac · Apple Silicon", "https://github.com/GitRatio/pahebatcher/releases/download/preview/PaheBatcher-macos-arm64.zip"),
            ("Mac · Intel", "https://github.com/GitRatio/pahebatcher/releases/download/preview/PaheBatcher-macos-x64.zip"),
            ("Linux x64", "https://github.com/GitRatio/pahebatcher/releases/download/preview/PaheBatcher-linux-x64.tar.gz"),
        ]

        def open_url(url: str) -> Callable[[], None]:
            def handler() -> None:
                webbrowser.open(url)
            return handler

        controls = tk.Frame(container, bg=BG)
        controls.pack(fill="x", pady=(0, 15))
        controls.grid_columnconfigure(0, weight=1, uniform="downloads")
        controls.grid_columnconfigure(1, weight=1, uniform="downloads")
        for index, (label, url) in enumerate(choices):
            Button(controls, label, open_url(url), f).grid(
                row=index // 2, column=index % 2, sticky="ew",
                padx=5, pady=5,
            )
        note = tk.Label(
            container,
            text=(
                "These are unsigned preview builds. macOS packages are not "
                "notarized; test your download and playback before relying on them."
            ),
            font=f.small, bg=BG, fg=MUTED, justify="left", anchor="nw",
        )
        note.pack(fill="x", pady=(0, 18))
        note.bind("<Configure>", lambda e: note.configure(
            wraplength=max(240, e.width - 8),
        ))
        links = tk.Frame(container, bg=BG)
        links.pack(fill="x", pady=(0, 10))
        Link(links, "All releases", open_url(
            "https://github.com/GitRatio/pahebatcher/releases"), f).pack(side="left")
        Link(links, "Source and license", open_url(
            "https://github.com/GitRatio/pahebatcher"), f).pack(side="left", padx=18)

        footer = tk.Frame(dlg, bg=PANEL)
        footer.pack(fill="x", side="bottom")
        Button(footer, "Close", dlg.destroy, f, primary=True).pack(
            side="right", padx=18, pady=12,
        )

    # full screen ----------------------------------------------------------
    def set_fullscreen(self, on: bool) -> None:
        self._fullscreen = on
        try:
            self.attributes("-fullscreen", on)
        except tk.TclError:
            pass  # a window manager without full-screen support: the maximize button still works
        self.fs_link.configure(text="Exit full screen" if on else "Full screen")

    def toggle_fullscreen(self, _e: tk.Event[Any] | None = None) -> str:
        self.set_fullscreen(not self._fullscreen)
        return "break"

    def _exit_fullscreen(self, _e: tk.Event[Any] | None = None) -> None:
        if self._fullscreen:
            self.set_fullscreen(False)

    def _on_resize(self, e: tk.Event[Any]) -> None:
        """Keep content centred with a sensible maximum width when the window is very wide."""
        if e.widget is not self:
            return
        pad = max(24, (e.width - MAX_CONTENT) // 2)
        if pad != self._pad:
            self._pad = pad
            for w in (self.hdr, self.notices, self.body):
                w.pack_configure(padx=pad)

    def _notice(self, text: str) -> tuple[tk.Frame, tk.Label, tk.Frame]:
        box = tk.Frame(self.notices, bg=PANEL, highlightthickness=1, highlightbackground=LINE)
        inner = tk.Frame(box, bg=PANEL)
        inner.pack(fill="x", padx=16, pady=12)
        actions = tk.Frame(inner, bg=PANEL)  # packed first so the buttons keep their full size
        actions.pack(side="right", padx=(16, 0))
        msg = tk.Label(inner, text=text, font=self.fonts.ui, fg=TEXT, bg=PANEL, anchor="w", justify="left")
        msg.pack(side="left", fill="x", expand=True)
        msg.bind("<Configure>", lambda e: msg.configure(wraplength=max(e.width - 4, 160)))  # wrap, don't clip
        return box, msg, actions

    # FFmpeg ---------------------------------------------------------------
    def _build_ffmpeg_notice(self) -> None:
        f = self.fonts
        self.ff_box, self.ff_msg, actions = self._notice(
            "FFmpeg isn't installed. It joins the downloaded pieces into a single .mp4.")
        self.ff_bar = ThinBar(self.ff_box, height=3)
        self.ff_btn = Button(actions, "Install FFmpeg", self.install_ffmpeg, f, primary=True)
        self.ff_btn.pack(side="right")
        self.ff_cancel = Link(actions, "cancel", self._cancel_ffmpeg, f, bg=PANEL)

    def refresh_ffmpeg_status(self) -> None:
        ok = ffmpeg_setup.find_ffmpeg(refresh=True) is not None
        self.dot_ffmpeg.configure(fg=OK if ok else WARN)
        if ok:
            self.ff_box.pack_forget()
        elif not self._ff_busy:
            self.ff_box.pack(fill="x", pady=(16, 0))

    def install_ffmpeg(self) -> None:
        if self._ff_busy:
            return
        self._ff_busy = True
        self._ff_cancel = threading.Event()
        cancel = self._ff_cancel
        self.ff_btn.pack_forget()
        self.ff_cancel.pack(side="right")
        self.ff_bar.pack(fill="x", side="bottom")
        self.ff_msg.configure(text="Downloading FFmpeg… this happens once", fg=TEXT)

        def progress(stage: str, frac: float | None) -> None:
            self.bridge.post(lambda: self._ff_progress(stage, frac))

        self.bridge.thread(
            lambda: ffmpeg_setup.install(progress, cancel), ok=self._ff_done, err=self._ff_failed,
        )

    def _ff_progress(self, stage: str, frac: float | None) -> None:
        if not self._ff_busy:
            return
        pct = f" {frac * 100:.0f}%" if frac is not None and stage == "Downloading" else "…"
        self.ff_msg.configure(text=f"{stage}{pct}", fg=TEXT)
        if frac is not None:
            self.ff_bar.set(frac)

    def _end_ffmpeg(self) -> None:
        self._ff_busy = False
        self.ff_cancel.pack_forget()
        self.ff_bar.pack_forget()

    def _ff_done(self, _path: str) -> None:
        self._end_ffmpeg()
        self.refresh_ffmpeg_status()
        callbacks, self._after_ff = self._after_ff, []
        for cb in callbacks:
            cb()

    def _ff_failed(self, exc: BaseException) -> None:
        self._end_ffmpeg()
        self._after_ff.clear()
        cancelled = str(exc) == "Cancelled"
        self.ff_msg.configure(text="Installation cancelled." if cancelled else f"✗ {exc}",
                              fg=MUTED if cancelled else ERR)
        self.ff_btn.configure(text="Try again")
        self.ff_btn.pack(side="right")

    def _cancel_ffmpeg(self) -> None:
        if self._ff_cancel:
            self._ff_cancel.set()

    def ensure_ffmpeg(self, then: Callable[[], None]) -> None:
        """Run ``then`` now if FFmpeg is present; otherwise install it first, then continue."""
        if ffmpeg_setup.find_ffmpeg() is not None:
            then()
            return
        self._after_ff.append(then)
        self.install_ffmpeg()

    # Cloudflare solver ----------------------------------------------------
    def _build_solver_notice(self) -> None:
        f = self.fonts
        self.fs_box, self.fs_msg, actions = self._notice(
            "The built-in browser solver isn't available. It needs Chrome or Edge installed, "
            "plus the browser add-on to get past animepahe's browser check.")
        Button(actions, "Check again", self.recheck_solver, f).pack(side="right")
        self.fs_pip = Button(actions, "Copy pip command", self._copy_pip, f, primary=True)
        self.fs_pip.pack(side="right", padx=(0, 10))

    async def _boot(self) -> bool:
        await self.backend.start()
        return await self.backend.ping()

    def recheck_solver(self) -> None:
        if self._pinging:
            return
        self._pinging = True
        self.bridge.run(self.backend.ping(), ok=self._set_solver, err=lambda _e: self._set_solver(False))

    def _set_solver(self, ok: bool) -> None:
        self._pinging = False
        self.solver_ok = bool(ok)
        self.dot_solver.configure(fg=OK if ok else ERR)
        name = getattr(self.backend.solver, "backend_name", "") if ok else ""
        self.dot_solver.configure(text=f"● {name}" if name else "● Solver")
        if ok:
            self.fs_box.pack_forget()
        else:
            self.fs_box.pack(fill="x", pady=(10, 0))
            self.after(6000, self.recheck_solver)  # keep checking quietly until it's up

    def _copy_pip(self) -> None:
        self.clipboard_clear()
        self.clipboard_append(PIP_CMD)
        self.fs_pip.configure(text="Copied ✓")
        self.after(2000, lambda: self.fs_pip.configure(text="Copy pip command"))

    # navigation -----------------------------------------------------------
    def _show(self, view: tk.Frame) -> None:
        for v in (self.v_search, self.v_eps, self.v_dl):
            v.pack_forget()
        view.pack(fill="both", expand=True)

    def show_search(self) -> None:
        self._show(self.v_search)
        self.v_search.entry.focus_set()

    def show_episodes(self, anime: AnimeInfo) -> None:
        self.v_eps.load(anime)
        self._show(self.v_eps)

    def start_download(self, anime: AnimeInfo, episodes: list[EpisodeInfo]) -> None:
        self.backend.current_dash = None
        self._show(self.v_dl)
        self.v_dl.begin(
            anime.title, len(episodes), self.backend.context(anime.title).output_dir,
            episodes, description=anime.description,
        )
        self.v_dl.future = self.bridge.run(
            self.backend.download(anime, episodes), ok=self.v_dl.finished, err=self.v_dl.failed)

    def choose_videos(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Open downloaded videos",
            filetypes=[("Videos", "*.mp4 *.webm *.m4v *.mov"), ("All files", "*.*")],
        )
        if paths:
            self.play_items([PlaybackItem.from_file(Path(path)) for path in paths])

    def play_items(self, items: list[PlaybackItem]) -> None:
        try:
            session = PlayerSession(items)
            if not session.open():
                session.close()
                raise RuntimeError("No web browser opened. Install or configure a default browser.")
            self._players.append(session)
        except (OSError, ValueError, RuntimeError) as exc:
            messagebox.showerror("PaheBatcher player", str(exc))

    # loop -----------------------------------------------------------------
    def _pump(self) -> None:
        self.bridge.drain()
        if self.v_dl.active:
            self.v_dl.refresh()
        self.after(250, self._pump)

    def on_close(self) -> None:
        if self.v_dl.active and not messagebox.askyesno("pahebatcher", "A download is running. Quit anyway?"):
            return
        if self.v_dl.future is not None:
            self.v_dl.future.cancel()
        try:
            self.bridge.run(self.backend.close()).result(timeout=6)
        except Exception:
            pass
        self.bridge.shutdown()
        for player in self._players:
            player.close()
        self.destroy()


def _win_set_icon(win: tk.Tk, ico: Path) -> None:
    """Give the title bar + taskbar the exact icon the .exe has.

    Tk's own iconbitmap can't read PNG-compressed .ico files (what our multi-size icon uses), so it
    silently falls back to the feather. Windows itself reads them fine: load the sizes directly and
    send them to the window. When frozen, the icon embedded in the .exe is used first.
    """
    try:
        import ctypes
        from ctypes import wintypes

        user32, shell32 = getattr(ctypes, "windll").user32, getattr(ctypes, "windll").shell32  # noqa: B009
        user32.LoadImageW.restype = wintypes.HANDLE
        try:  # separate taskbar identity so Windows doesn't group us under python.exe
            shell32.SetCurrentProcessExplicitAppUserModelID("pahebatcher.gui")
        except Exception:
            pass
        hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()

        def load(size: int) -> Any:
            h = None
            if getattr(sys, "frozen", False):  # icon resource embedded in our own .exe
                big, small = wintypes.HICON(), wintypes.HICON()
                if shell32.ExtractIconExW(sys.executable, 0, ctypes.byref(big), ctypes.byref(small), 1):
                    h = big if size > 20 else small
            if not h and ico.exists():
                h = user32.LoadImageW(None, str(ico), 1, size, size, 0x10)  # IMAGE_ICON, LR_LOADFROMFILE
            return h

        for which, size in ((1, user32.GetSystemMetrics(11)), (0, user32.GetSystemMetrics(49))):  # BIG, SMALL
            h = load(size)
            if h:
                user32.SendMessageW(hwnd, 0x0080, which, h)  # WM_SETICON
    except Exception:
        pass


def _prepare_process() -> None:
    """Windowed builds have no stdout/stderr; point Rich and print() somewhere harmless."""
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8", errors="replace"))  # noqa: SIM115
    from pahebatcher.ui.console import console

    console.file = open(os.devnull, "w", encoding="utf-8", errors="replace")  # noqa: SIM115
    if sys.platform == "win32":
        try:
            import ctypes

            getattr(ctypes, "windll").shcore.SetProcessDpiAwareness(1)  # noqa: B009
        except Exception:
            pass


def main() -> None:
    _prepare_process()
    App().mainloop()


if __name__ == "__main__":
    main()
