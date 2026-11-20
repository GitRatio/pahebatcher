# Windows 11 installation — GitRatio PaheBatcher

This independent GitRatio edition preserves original attribution in LICENSE and documents changes in FORK_NOTES.md.

## Option A: Standalone EXE (development build or published release)

1. For a one-click unsigned development build, [download the Windows 11 application](https://github.com/GitRatio/pahebatcher/releases/download/preview/pahebatcher-gui-windows-x64.exe). Check the [preview release](https://github.com/GitRatio/pahebatcher/releases/tag/preview) or [GitRatio Releases](https://github.com/GitRatio/pahebatcher/releases).
2. If the preview is not published yet, use the [successful build artifacts](https://github.com/GitRatio/pahebatcher/actions/workflows/build-exe.yml), download `pahebatcher-gui-windows-x64.exe`, and extract it. The preview executable is not code-signed and may trigger SmartScreen.
3. Keep Microsoft Edge or Chrome installed for the browser-based solver.
4. Install FFmpeg if it is not already available (for example, `winget install Gyan.FFmpeg`). The new webview UI reports when FFmpeg is missing.

The existing build-exe workflow produces the Windows GUI executable when a version tag triggers a release. A development branch is NOT an official downloadable executable. Do not disable Microsoft Defender or blindly bypass SmartScreen.

## Option B: Install from current source (recommended until a packaged preview is verified)

Requirements: Windows 11 x64, 64-bit Python 3.12 with the py launcher, Edge or Chrome, and network access for installing Python dependencies.

1. Visit https://github.com/GitRatio/pahebatcher
2. Choose Code > Download ZIP and extract it to a writable folder, such as Documents\PaheBatcher.
3. Double-click install-windows.bat. It creates a private .venv and installs the project with the browser extra.
4. Double-click launch-windows.bat to start the desktop app. Errors remain visible in the console.
5. Install FFmpeg separately if the application reports it missing.

The batch scripts operate in the extracted repository directory and do not need administrator privileges.

## PowerShell alternative

Open PowerShell in the extracted directory and run:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[browser,gui]"
.\.venv\Scripts\python.exe -m pahebatcher.gui
```

No virtual environment activation or PowerShell execution-policy change is necessary.

### Terminal interface

```powershell
.\.venv\Scripts\pahebatcher.exe --help
.\.venv\Scripts\pahebatcher.exe
```

## Troubleshooting

- Python launcher missing: install Python 3.12 x64 from https://www.python.org/downloads/windows/ and enable the launcher.
- No solver: ensure Edge or Chrome is installed and the browser extra finished installing.
- FFmpeg missing: install a trusted FFmpeg build (`winget install Gyan.FFmpeg`) and verify `ffmpeg -version` works.
- GUI exits immediately: run launch-windows.bat and copy the console error.
- Downloads fail: check free disk space and reduce parallel workers, then retry. Only download material you are authorized to access.

## Running tests

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev,browser,gui]"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
```

## Building a standalone EXE yourself

After tests pass, run build_exe.bat on Windows 11 to build the GUI and terminal executables in dist. The existing GitHub Actions workflow also builds release artifacts for tagged releases.
