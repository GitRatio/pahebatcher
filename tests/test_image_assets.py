"""Image quality contracts for the GitRatio Bunny Takeover artwork.

These checks intentionally use only the Python standard library, so every
platform CI job validates the packaged images without installing Pillow.
"""

from pathlib import Path
from struct import unpack

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "src" / "pahebatcher" / "gui" / "assets"


def dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    assert data.startswith(bytes([137, 80, 78, 71, 13, 10, 26, 10]))
    return unpack(">II", data[16:24])


def test_shared_native_and_player_mascot_is_high_resolution() -> None:
    assert dimensions(ASSETS / "bunny.png") == (650, 650)
    player_html = (ASSETS / "player.html").read_text(encoding="utf-8")
    native_html = (ASSETS / "desktop.html").read_text(encoding="utf-8")
    assert "/mascot/__PLAYER_TOKEN__/bunny.png" in player_html
    assert "data:image/png;base64" not in player_html
    assert 'src="bunny.png"' in native_html
    assert "image-rendering:auto" in native_html
    assert not (ASSETS / "takeover_bunny.b64").exists()


def test_platform_icon_uses_best_available_bundled_mascot() -> None:
    # Classic/Windows icon is provided at 256px for normal taskbar dimensions.
    assert dimensions(ASSETS / "icon.png") == (256, 256)
    workflow = (ROOT / ".github" / "workflows" / "build-exe.yml").read_text(
        encoding="utf-8"
    )
    assert workflow.count("sips -z") == 2
    assert workflow.count("src/pahebatcher/gui/assets/bunny.png --out") == 2
    assert "src/pahebatcher/gui/assets/icon.png --out" not in workflow


def test_readme_shows_current_ui_without_stale_low_res_screenshots() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert 'src/pahebatcher/gui/assets/bunny.png' in readme
    assert 'width="180" height="180"' in readme
    assert "gui-search.png" not in readme
    assert "gui-downloading.png" not in readme
