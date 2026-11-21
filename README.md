# PaheBatcher — GitRatio Bunny Takeover

<img src="src/pahebatcher/gui/assets/bunny.png" alt="GitRatio Bunny Takeover mascot" width="180" height="180">

**Independent, open-source desktop edition** of [abdullahkhfb/pahebatcher](https://github.com/abdullahkhfb/pahebatcher), with the GitRatio Bunny Takeover interface. Download anime episodes in batches, resume interrupted transfers, and play downloaded files locally.

**Current application version:** 3.13.0 · **Platforms:** Windows 11 x64, macOS Intel, macOS Apple Silicon and Linux x64 · **License:** MIT

The default desktop interface is built with **pywebview + local HTML/CSS**; the Python download engine and terminal interface remain available. Windows uses WebView2, macOS uses WebKit and Linux uses Qt WebEngine. The classic Tkinter UI remains available separately.

### v3.13.0 preview — published

The changes in [PR #9](https://github.com/GitRatio/pahebatcher/pull/9) add a bounded multi-series queue, Unicode-safe Windows GUI output, more accurate partial-download status, and a compact in-app GitHub update notice. The About page displays the installed version and release status; it never downloads or installs an update automatically. Release checks use one small, bounded GitHub API request per app launch, and transfer status refreshes every two seconds instead of 800 milliseconds to lower idle CPU use. These features are included in the published v3.13.0 preview.

**Low-resource approach:** no added update-check dependencies or resident update service, no automatic installer cache, and one active series at a time with bounded episode concurrency. The queue is currently in-memory and will not survive an app restart; restart persistence is a separate future milestone. The app's About page and GitHub release notes describe the current functionality.


> **Bunny Takeover** is the theme of this fork, not a transfer of ownership. The original authors retain attribution and license rights. GitRatio is not affiliated with or endorsed by the upstream maintainer. See [fork notes](FORK_NOTES.md) and [LICENSE](LICENSE).

**Size and artwork:** The mascot is retained at full resolution and compressed losslessly during packaging. Decorative artwork no longer intercepts navigation clicks. Linux builds are testing removal of non-runtime debug symbols; this saves space without dropping Qt libraries. Compare the downloaded package size with the latest [rolling release](https://github.com/GitRatio/pahebatcher/releases/tag/preview). Runtime acceptance on real devices remains necessary.

## Downloads — v3.13.0 preview

| Operating system | Preview package |
| --- | --- |
| **Windows 11 x64** | [Download Windows EXE](https://github.com/GitRatio/pahebatcher/releases/download/preview/pahebatcher-gui-windows-x64.exe) |
| **macOS Apple Silicon** | [Download ARM64 ZIP](https://github.com/GitRatio/pahebatcher/releases/download/preview/PaheBatcher-macos-arm64.zip) |
| **macOS Intel** | [Download x64 ZIP](https://github.com/GitRatio/pahebatcher/releases/download/preview/PaheBatcher-macos-x64.zip) |
| **Linux x64** | [Download TAR.GZ](https://github.com/GitRatio/pahebatcher/releases/download/preview/PaheBatcher-linux-x64.tar.gz) |

These are **unsigned, development-preview** builds. macOS builds are not notarized. Check the [rolling preview release](https://github.com/GitRatio/pahebatcher/releases/tag/preview) for the version of the published assets before installing. For build logs and test screenshots, see [Build executables](https://github.com/GitRatio/pahebatcher/actions/workflows/build-exe.yml) and [visual QA](https://github.com/GitRatio/pahebatcher/actions/workflows/ui-visual.yml). Browser screenshots verify layout, but real-device scaling and playback tests are still necessary.

**Install guides:** [Windows 11](WINDOWS_11.md) · [macOS & Linux](MACOS_LINUX.md)

## Desktop interface

The default interface includes a graffiti-themed header, a full-resolution bunny mascot, search and episode selection, responsive download controls, progress, settings, a local video library and an About screen. The player uses the **same bundled high-resolution mascot**, not the old thumbnail. Artwork is decorative; search results and episodes come from the source rather than fabricated posters.

The downloaded-file player supports MP4, WebM, M4V and MOV where the browser's codecs permit. Playback runs on a private loopback server with a session token and only serves explicitly selected local files. The pinned online Video.js skin has a native HTML5 fallback. This is **not a remote-streaming player**.

## Highlights

- **Redesigned desktop app and terminal UI**, both with live per-episode download
  dashboard.
- **Fast and safe:** parallel episodes, parallel HLS segments, and downloads
  resume exactly where they stopped.
- **Stream in MPV** from the terminal, and switch between SUB and DUB between
  episodes.
- **Watchlist:** follow airing shows and fetch only the new episodes.
- **No Docker, no extra services.** A built-in browser solver gets past
  Cloudflare using the Chrome or Edge you already have.
- **FFmpeg:** required to combine downloaded segments. Install it with your package manager before downloading with the new desktop UI.
- **Local episode player:** redesigned graffiti-themed layout, 'Download video' save-copy action, episode playlist and responsive 16:9 Video.js 10.5.0 Neutral controls (with native offline fallback), episode queue, series/movie details, source-provided synopsis, audio language, seeking and fullscreen. No remote-stream playback in this GUI feature yet.
- **Desktop packaging:** macOS .app archives for Apple Silicon/Intel and a portable Linux x64 app with an app-menu installer.

## Install

### Windows (easiest)

1.  Download the [Windows 11 desktop EXE](https://github.com/GitRatio/pahebatcher/releases/download/preview/pahebatcher-gui-windows-x64.exe), or consult the [Windows 11 guide](WINDOWS_11.md).
2.  Make sure **Microsoft Edge** (included with Windows) or **Google Chrome**
    is installed.
3.  Install FFmpeg if necessary (for example, `winget install Gyan.FFmpeg`), then run the application.

Tagged GitRatio releases may offer standalone CLI binaries. Preview builds are test artifacts, not signed production installers.

### macOS and Linux desktop packages

Use the platform links above for preview packages and see [MACOS_LINUX.md](MACOS_LINUX.md) for macOS `.app`, Linux portable desktop installation, FFmpeg and system requirements. These preview packages are unsigned and not notarized.

### From source (Windows, macOS, Linux)

```bash
git clone https://github.com/GitRatio/pahebatcher.git
cd pahebatcher
pip install -e ".[browser,gui]"

pahebatcher-gui      # desktop app
pahebatcher          # terminal
```

### Requirements

| Needs          | For                                       | How                                                                                                           |
| -------------- | ----------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Python 3.11+   | running from source                       | [python.org](https://www.python.org/downloads/)                                                               |
| pywebview      | default desktop UI                         | installed by the `gui` extra; on Linux also install `pywebview[qt]`  |
| Chrome or Edge | the built-in Cloudflare solver            | usually already installed                                                                                     |
| FFmpeg         | joining downloaded pieces into `.mp4`     | `winget install Gyan.FFmpeg` / `brew install ffmpeg` / `apt install ffmpeg` |
| MPV            | streaming only                            | `winget install mpv.net` / `brew install mpv` / `apt install mpv`                                             |

## Desktop app

1.  **Search** for an anime and select a result.
2.  **Pick episodes** by clicking them, or use **All**, **None**, or a range
    like `1-12`, `1,4,7`, `5-`.
3.  Press **Download**. Watch progress in **Downloads**, then find files under **Library**.

Quality, audio language and parallel-download preferences are in the episode
download panel and **Settings**; the save folder can be changed using
**Choose folder**. Settings are stored in the application data folder. See
[Where files live](#where-files-live).

**FFmpeg:** the current webview UI requires FFmpeg to be installed before
starting downloads. If it is missing, the app displays a message instead of
starting the download. Use your platform package manager to install it.

**Window sizing:** resize or maximize the desktop window normally. Download
controls rearrange on narrow windows and high-DPI displays. The local
video player offers its own fullscreen control.

Select a video from **Library** and press **Play**. In the native desktop UI, the local HTML5 player is loaded into the application's webview where supported; a browser fallback remains available. Local file metadata is inferred from filenames. See [MACOS_LINUX.md](MACOS_LINUX.md).

The desktop app still does not do **remote site streaming** or the watchlist yet. Use the terminal for those.

## Terminal

Run `pahebatcher` for the interactive wizard (search, pick episodes, download),
or pass a series URL.

```bash
pahebatcher "https://animepahe.pw/anime/<uuid>" --all -q 720        # whole series
pahebatcher "<url>" --range 1-12 --audio eng -q 1080 -o ~/anime     # dub, 1080p, custom folder
pahebatcher "<url>" --latest 3                                      # newest 3 episodes
pahebatcher "<url>" --list                                          # list episodes and exit
pahebatcher "<url>" --stream                                        # play in MPV
```

Files are saved as `Ep 001 - Title.mp4` in `<output>/<Series>/` (default
`./downloads`).

### Terminal options

| Flag                 | Meaning                                    | Default       |
| -------------------- | ------------------------------------------ | ------------- |
| `-a`, `--all`        | every episode                              |               |
| `-r`, `--range R`    | `1-12`, `1,4,7`, `13-`, `1-6,10`           |               |
| `-n`, `--latest N`   | newest N episodes                          |               |
| `-s`, `--stream`     | stream in MPV                              |               |
| `-l`, `--list`       | list episodes and exit                     |               |
| `-o`, `--output DIR` | output folder                              | `./downloads` |
| `-q`, `--quality`    | `360`, `720`, `1080`                       | `1080`        |
| `--audio`            | `jpn` (sub) or `eng` (dub)                 | `jpn`         |
| `-j`, `--parallel N` | episodes at once (1-6)                     | `2`           |
| `-w`, `--workers N`  | segment fetchers per episode (8-32)        | `24`          |
| `--retry N`          | automatic retries per failed episode (0-2) | `2`           |
| `--keep-temp`        | keep raw `.ts` segments                    | off           |
| `-v`, `--verbose`    | debug logging                              | off           |

`--all`, `--range`, `--latest` and `--stream` are mutually exclusive. Without
one of them, the wizard asks which episodes you want.

Total simultaneous connections are `parallel x workers`. If you see segment
failures, lower `-w` (to 8-12) before lowering `-j`.

### Streaming

MPV opens with a live "Now playing" panel. After an episode: `N` next, `P`
previous, `A` toggle SUB/DUB, `R` replay, `S` jump to an episode, `Q` quit.

### Sessions

Interrupted downloads are cached segment by segment. Pick **Sessions** in the
main menu to resume, delete one, or clear the whole cache (`pahe_cache/`).
Cache folders older than 24 hours are cleaned up automatically.

### Linux, macOS and WSL helper

`make run` sets up a virtual environment (including the browser solver) and
starts the app. `make help` lists the rest (`run`, `watchlist-check`, `test`,
`lint`, ...).

## Watchlist

Follow a show once, then run one command whenever you like (for example from
cron). It downloads only the episodes you don't have yet and is safe to run
repeatedly.

```bash
pahebatcher wl add "https://animepahe.pw/anime/<uuid>" -q 1080 --audio jpn -o ~/anime
pahebatcher wl add Frieren          # search by name
pahebatcher check                   # download anything new
pahebatcher wl list                 # see what's tracked
```

| Command                                       | What it does                                                                                                                         |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `wl add [URL or name]`                        | track a series (uses your saved settings unless you pass flags; accepts `-q`, `--audio`, `-o`, `-j`, `-w`, `--retry`, `--keep-temp`) |
| `check [N]` (or `wl check`, `sync`, `update`) | download new episodes for every tracked series, or only for entry `N`                                                                |
| `wl list` / `wl show N`                       | list entries / show one                                                                                                              |
| `wl remove N`                                 | stop tracking (`-y` skips the confirmation)                                                                                          |
| `wl relink [N] [URL]`                         | repair an entry whose animepahe link died; without `URL` it finds the new one by title, and without `N` it repairs every dead entry  |
| `wl reset N` (or `wl reset --all`)            | forget which episodes you deleted so they download again                                                                             |

`wl` is short for `watchlist` (`w` and `watch` also work). `N` can be the list
number, the URL, or part of the title.

- **Deleted a single episode?** It stays skipped while the series folder
  exists. Delete the whole folder, or run `wl reset N`, to download it again.
- **State** lives in `watchlist.json` in the folder you run from (override
  with `WATCHLIST_PATH`).
- **Cron example** (hourly). On Windows, use Task Scheduler with
  `python -m pahebatcher check` instead.

  ```cron
  0 * * * * cd /path/to/pahebatcher && venv/bin/python -m pahebatcher check >> watchlist.log 2>&1
  ```

## Configuration

Defaults are saved to `pahebatcher.toml` in the folder you run the terminal app
from. The desktop app keeps its own settings in `gui.toml` (see
[Where files live](#where-files-live)). Command-line flags override saved
settings.

```bash
pahebatcher config show
pahebatcher config set quality 720
pahebatcher config set audio_lang eng
pahebatcher config reset
```

| Key             | Default       | Values                                                           |
| --------------- | ------------- | ---------------------------------------------------------------- |
| `quality`       | `1080`        | `360`, `720`, `1080`                                             |
| `audio_lang`    | `jpn`         | `jpn`, `eng`                                                     |
| `max_parallel`  | `2`           | `1`-`6`                                                          |
| `hls_workers`   | `24`          | `8`-`32`                                                         |
| `output_dir`    | `./downloads` | any path                                                         |
| `keep_temp`     | `false`       | `true`, `false`                                                  |
| `auto_retry`    | `2`           | `0`-`2`                                                          |
| `cache_ttl`     | `60`          | minutes to cache scan results; `0` disables                      |
| `resolve_ahead` | `999`         | how many episodes to resolve ahead; `1` is gentler on Cloudflare |
| `browser_mode`  | `auto`        | `auto`, `headless`, `headed`                                     |
| `cookie_string` | empty         | your browser's `cf_clearance=...` cookie                         |
| `clearance_ttl` | `20`          | minutes a solved clearance is reused; `0` disables               |

Not every setting applies everywhere:

- `output_dir` and `keep_temp` are used by the desktop app, and `output_dir`
  is also the default for `wl add`. One-off terminal downloads ignore them:
  use `-o` and `--keep-temp`.
- The other keys apply to both apps and to the watchlist.

See `pahebatcher.toml.example` for a ready-to-copy file. It sets
`resolve_ahead = 1` (the gentler serial setting), while the built-in default is
`999`.

### Where files live

| What                                     | Location                                                                                                                                                                                         |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Terminal settings                        | `pahebatcher.toml` in the folder you run from                                                                                                                                                    |
| Watchlist                                | `watchlist.json` in the folder you run from (or `WATCHLIST_PATH`)                                                                                                                                |
| Download cache                           | `pahe_cache/` in the folder you run from                                                                                                                                                         |
| Desktop settings (`gui.toml`) and FFmpeg | the app data folder: `%LOCALAPPDATA%\pahebatcher` on Windows, `~/Library/Application Support/pahebatcher` on macOS, `$XDG_DATA_HOME/pahebatcher` (default `~/.local/share/pahebatcher`) on Linux |

Set `PAHEBATCHER_HOME` to move the app data folder.

## Cloudflare solver

animepahe sits behind Cloudflare, so pahebatcher needs a solver to get past its
browser check. The built-in browser solver drives your installed Chrome or Edge
with its own profile. Nothing is downloaded or bundled, and the `.exe` builds
include it. From source, install it with `pip install "pahebatcher[browser]"`
(`make run` does this for you).

With `browser_mode = auto` it solves in the background first and opens a
visible window only if Cloudflare needs a human click. To use a specific
browser, set `PAHEBATCHER_BROWSER` to its executable path. To route through a
proxy or VPN, set `PAHEBATCHER_PROXY` (for example
`http://user:pass@host:port`).

> **Upgrading?** FlareSolverr support has been removed, so `FLARESOLVERR_URL`
> and `FLARESOLVERR_PROXY` are no longer read (use `PAHEBATCHER_PROXY`
> instead), and an old `solver_backend` line in your config is ignored.

**Android/Termux:** automatic solving doesn't work there. Solve once in a real
browser on the same network and run
`pahebatcher config set cookie_string "cf_clearance=..."`. Repeat when it
expires.

## Build the executables

On Windows, double-click **`build_exe.bat`** (Python 3.11+ required). It cleans
old output, installs everything and writes:

- `dist\pahebatcher-gui.exe`: the desktop app, no console window
- `dist\pahebatcher.exe`: the terminal app

Both use the app icon from `src/pahebatcher/gui/assets/` (`icon.ico` for the
file, `icon.png` for the window; the bundled 650px bunny image is the macOS icon artwork source).

Pushing a version tag like `v3.12.0` makes the **Build executables** GitHub workflow run
the tests, build the binaries and attach them to a Release (the Windows desktop
app, plus Windows, Linux and macOS terminal apps). You can also run it by hand
from the Actions tab, which builds the binaries without publishing a Release.

FFmpeg, MPV and Chrome/Edge are not bundled.

## Troubleshooting

| Problem                                                    | Fix                                                                                                                                                |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| "No Cloudflare solver"                                     | Install Chrome or Edge and `pip install "pahebatcher[browser]"`. In WSL, install a Linux Chrome or set `PAHEBATCHER_BROWSER`.                      |
| Solver never gets through                                  | `pahebatcher config set browser_mode headed`, then tick the checkbox in the window. Or try another network, or a proxy via `PAHEBATCHER_PROXY`.    |
| FFmpeg not found                                           | Install FFmpeg using your OS package manager and verify `ffmpeg -version` works. |
| `MPV not found`                                            | Install MPV, or use download mode.                                                                                                                 |
| Many segment failures or slow downloads                    | Lower `-w` to 8-12 and `-j` to 1 if the CDN is rate limiting; raise `-w` to 24-32 if you are just slow.                                            |
| `Resolution timed out`                                     | Try `-j 1`. It already retries each episode automatically (see `--retry`).                                                                         |
| `No Kwik link found`                                       | Try another `--quality`, or set `cookie_string` from your browser.                                                                                 |
| Cache folder keeps growing                                 | Clear it from **Sessions** in the terminal menu. Stale sessions older than 24 hours are cleaned automatically.                                     |
| `watchlist check` says up to date but a new episode is out | Check `wl show N` for the right audio and output folder. If you moved or renamed files, `check` can't match them (names must start with `Ep 001`). |
| Windows shows a SmartScreen warning                        | The `.exe` is unsigned. Choose **More info**, then **Run anyway**.                                                                                 |
| Windows still shows the old icon after a rebuild           | Windows caches icons. Move the `.exe` to a new folder or restart Explorer.                                                                         |
| Browser did not open its debugging port                    | A leftover pahebatcher browser window holds the browser profile. Close it and try again.                                                           |

## Development

```bash
pip install -e ".[dev,browser,gui]"
pytest                # tests
ruff check src        # lint
mypy src              # strict type check
```

`make test`, `make lint`, `make typecheck` and `make benchmark` do the same on
Linux, macOS and WSL.

| Path                             | Purpose                                                                  |
| -------------------------------- | ------------------------------------------------------------------------ |
| `main.py`                        | command-line parsing and the main flow                                   |
| `gui/`                           | native webview UI (`webui.py`), classic Tk GUI (`app.py`), player, bridge and bundled assets |
| `ui/`                            | terminal UI: dashboard, prompts, tables, theme, console                  |
| `downloader.py`                  | two-stage pipeline: resolve stream URLs ahead, then download in parallel |
| `store.py`                       | segment cache with atomic writes, resume, and FFmpeg assembly            |
| `http.py`, `tls.py`, `cache.py`  | HTTP client with retries, TLS context, TTL cache                         |
| `solver.py`, `browser_solver.py` | Cloudflare solving (built-in browser)                                    |
| `ffmpeg_setup.py`                | finds FFmpeg or installs it                                              |
| `extract/`                       | animepahe scanner, Kwik link extraction, M3U8 parsing                    |
| `stream.py`                      | MPV streaming                                                            |
| `watchlist.py`, `sessions.py`    | watchlist and session manager                                            |
| `config.py`, `config_manager.py` | constants and saved settings                                             |
| `models.py`, `utils.py`          | shared data classes and helpers                                          |

All paths are under `src/pahebatcher/`. The code is Python 3.11+, strictly
typed, and linted with ruff.

### Contributing

Fork, branch, and open a pull request. Keep `pytest`, `ruff check src` and
`mypy src` green, add tests for what you change, and use a conventional commit
prefix (`fix:`, `feat:`, `docs:`, `refactor:`, `chore:`).

Ideas welcome: PyPI publishing, finishing active downloads on Ctrl+C, streaming
and watchlist in the desktop app, other audio languages.

## Credits

- **Original pahebatcher:** [abdullahkhfb](https://github.com/abdullahkhfb/pahebatcher); this is an independent MIT-licensed derivative, not a transfer of upstream ownership.
- **GitRatio edition:** Windows fixes, fork maintenance, and the tongue-in-cheek bunny-takeover theme.

- **Original logo** by [/u/HellHarbinger][hellharbinger]; retained in `assets/logo/` with upstream attribution.
- **GitRatio Bunny Takeover mascot:** supplied for this fork and bundled for the native UI, local player and desktop icons.
- **WSL setup** (`setup-wsl.sh` and the Makefile): idea and first version by
  [/u/HellHarbinger][hellharbinger].

## License

MIT. See [LICENSE](LICENSE). For personal and educational use. You are
responsible for following the terms of the sites you access. Support the
official creators.

## See also

- `pahebatcher.toml.example`: a ready-to-copy configuration file.

[hellharbinger]: https://www.reddit.com/user/HellHarbinger/
