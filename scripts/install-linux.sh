#!/usr/bin/env bash
# User-local installer for the portable PaheBatcher Linux desktop build.
set -euo pipefail

here="$(cd -- "$(dirname -- "$0")" && pwd)"
source_app="$here/PaheBatcher"
if [[ ! -x "$source_app/PaheBatcher" ]]; then
  echo "Missing portable PaheBatcher application. Extract the entire .tar.gz first." >&2
  exit 1
fi

data_dir="$(printenv XDG_DATA_HOME || true)"
if [[ -z "$data_dir" ]]; then
  data_dir="$HOME/.local/share"
fi
app_dir="$data_dir/pahebatcher-app"
desktop_dir="$data_dir/applications"
mkdir -p "$app_dir" "$desktop_dir"

# Preserve the executable and PyInstaller's _internal folder.
cp -a "$source_app/." "$app_dir/"
install -m 644 "$here/icon.png" "$app_dir/icon.png"
chmod 755 "$app_dir/PaheBatcher"

# Quote the Exec path in the XDG desktop entry to support spaces in home paths.
app_exec="$app_dir/PaheBatcher"
cat > "$desktop_dir/pahebatcher-gitratio.desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=PaheBatcher (GitRatio)
GenericName=Episode Downloader and Player
Comment=Download and watch permitted anime episodes
Exec="$app_exec"
Icon=$app_dir/icon.png
Terminal=false
Categories=AudioVideo;Video;Network;
StartupNotify=true
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$desktop_dir" >/dev/null 2>&1 || true
fi
echo "PaheBatcher installed for this user."
echo "Open PaheBatcher (GitRatio) from your app menu, or run:"
echo "  $app_dir/PaheBatcher"
