# PaheBatcher desktop v3.12.0 — macOS and Linux

This GitRatio edition shares one Python/Tkinter desktop interface and download backend across Windows, macOS and Linux. Builds are created on the corresponding OS with PyInstaller; **do not use Windows executables on macOS/Linux**.

## Download builds by operating system

[**Windows 11**](https://github.com/GitRatio/pahebatcher/releases/download/preview/pahebatcher-gui-windows-x64.exe) · [**macOS Apple Silicon**](https://github.com/GitRatio/pahebatcher/releases/download/preview/PaheBatcher-macos-arm64.zip) · [**macOS Intel**](https://github.com/GitRatio/pahebatcher/releases/download/preview/PaheBatcher-macos-x64.zip) · [**Linux x64**](https://github.com/GitRatio/pahebatcher/releases/download/preview/PaheBatcher-linux-x64.tar.gz)

These are direct file links from the rolling **unsigned preview** release, published only after all platform builds succeed. If a preview is not available yet, use the latest successful main-branch [build artifacts](https://github.com/GitRatio/pahebatcher/actions/workflows/build-exe.yml). See README for package names.

## Prebuilt desktop packages

Open [GitRatio Releases](https://github.com/GitRatio/pahebatcher/releases) for tagged packages, or [Build executables](https://github.com/GitRatio/pahebatcher/actions/workflows/build-exe.yml) for temporary workflow artifacts (requires a successful build and sometimes a GitHub sign-in). A workflow being configured does **not** mean a published binary is already available.

| Platform | Output | Install |
| --- | --- | --- |
| macOS Apple Silicon | PaheBatcher-macos-arm64.zip | Unzip and move PaheBatcher.app into Applications |
| macOS Intel | PaheBatcher-macos-x64.zip | Unzip and move PaheBatcher.app into Applications |
| Linux x86-64 | PaheBatcher-linux-x64.tar.gz | Extract, then run bash install.sh |
| Windows 11 x64 | pahebatcher-gui-windows-x64.exe | See WINDOWS_11.md |

macOS builds are not Developer ID signed or notarized yet. Gatekeeper may warn; review the source, build yourself or wait for signed releases. Do not disable your OS security protections. macOS versions older than the CI build environments are not yet guaranteed compatible. Linux portable builds target glibc distributions such as Ubuntu 22.04+ (GUI desktop session required), not musl/Alpine. Wayland or unusual window managers may require additional desktop packages.

### Linux graphical installer

From the directory containing the extracted PaheBatcher folder and install.sh:

~~~bash
bash install.sh
~~~

This copies the GUI and bundled runtime to your user data directory and registers a desktop launcher without sudo. It respects XDG_DATA_HOME when set. You still need a Chromium-family browser installed for site connectivity and a default browser for the local Video.js 10 player.

## From source (all platforms)

Requires Python 3.11 or newer, Tkinter, and Chrome, Edge or Chromium. Source installs are easier to debug and update. Run from the checked-out repo:

~~~bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[browser]"
python -m pahebatcher.gui
~~~

On Ubuntu/Debian, install system Tk before creating the venv with sudo apt install python3-tk python3-venv. On macOS, a Python build including Tk is required. Check with python3 -m tkinter. For FFmpeg, try the GUI's Install FFmpeg button, or install it via your package manager (Homebrew: brew install ffmpeg; Debian/Ubuntu: sudo apt install ffmpeg). FFmpeg is used for merging downloaded segments.

### Mac package troubleshooting

- Open PaheBatcher.app from Finder. macOS may require an approved Apple-signed/notarized release under your security policy.
- If it cannot open, use the source method above to see Python errors.
- Keep the .app intact; it contains the application code, resources, and libraries.

### Linux troubleshooting

- Keep the entire PaheBatcher directory together; the executable alone will not run without _internal.
- If the launcher does not appear immediately, log out/in or open the executable from the shell to inspect errors.
- The GUI needs a graphical desktop session, working Tk/X11 support, and a browser. Install compatible libraries using your Linux distribution's package manager.
- Browser solving depends on installed Chromium/Chrome/Edge and live site behavior. Avoid assuming a successful build means every remote site is available.

## Local video player

Click **Open player** in the desktop header to choose one or more local MP4, M4V, MOV or WebM videos. After a successful download, click **Watch videos** to populate the playlist automatically from completed files, with series title, selected episode, and SUB/DUB information already known to the app.

The player opens in your **default web browser**. This is intentional: desktop Tkinter has no integrated modern HTML5 engine and the browser supplies cross-platform media decoding. The player uses the actual **Video.js 10.5.0 Neutral skin** loaded from a pinned jsDelivr module when online. It retains native HTML5 controls as an offline fallback, and offers a spacious layout, episode queue, source-provided anime synopsis, play/pause, fullscreen, keyboard shortcuts and seekable playback. Descriptions are shown only if supplied by the anime page; no synopsis is invented. It does **not** stream remote site links directly yet. Browser media codecs differ; MPV/VLC may be necessary for unusual codecs.

For privacy, playback uses a randomized URL served only on 127.0.0.1, has no directory listing, requires an unguessable session token, and serves only files explicitly selected by the user. The service stops when PaheBatcher closes. It never makes your video directories public.

## CI / release engineering

The repository's Build executables workflow runs the unit tests and builds platform-specific desktop packages. Mac archives contain an .app; Linux archives contain PyInstaller's portable onedir bundle, icon and install.sh. A rolling unsigned prerelease is published at the fixed `preview` tag after successful main-branch builds. Formal versioned releases are published only when a `v*` tag triggers the workflow and the required jobs pass.

The packages still need real-device QA, macOS code signing/notarization and broader Linux-distribution verification before being called production-ready.


## Native Bunny Takeover desktop window (v3.12.0)

The default application now uses **pywebview** rather than standard Tkinter controls. The HTML/CSS artwork and actions are bundled locally; no hosted UI is required. Windows 11 requires Edge WebView2 Runtime; macOS uses system WebKit. On Linux, install an appropriate Qt WebEngine runtime and `pywebview[qt]` if running from source. The Linux preview binary may require additional X11/Qt platform libraries on minimal distributions.

For development: `python -m pip install -e ".[browser,gui]"`, followed by `pahebatcher-gui`. For Linux development: also `python -m pip install "pywebview[qt]"`. The previous Tk GUI remains available as `pahebatcher-classic-gui`. The video player is still a local-only browser page.

The v3.12.0 user interface is implemented and wired to the backend, but **pixel-level/device acceptance testing is still required** across Windows scaling, macOS and Linux.
