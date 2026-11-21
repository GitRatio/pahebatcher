"""Minimal, opt-in-to-install GitHub release metadata check.

One bounded HTTPS request; no timer, download, cache, or added dependency.
Only the release's version is displayed. Never executes remote code.
"""
from __future__ import annotations

import json
import re
from urllib.request import Request, urlopen

from pahebatcher.config import VERSION

RELEASE_API = "https://api.github.com/repos/GitRatio/pahebatcher/releases/tags/preview"
RELEASE_PAGE = "https://github.com/GitRatio/pahebatcher/releases/tag/preview"
_VERSION = re.compile(r"(?<![0-9])v?(\\d+)\\.(\\d+)\\.(\\d+)(?![0-9])")


def version_tuple(value: str) -> tuple[int, int, int] | None:
    match = _VERSION.search(value)
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def lookup_update(current_version: str = VERSION) -> dict[str, object]:
    """Return safe release metadata; fail quietly when offline."""
    result: dict[str, object] = {"checked": True, "available": False}
    try:
        request = Request(RELEASE_API, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "GitRatio-PaheBatcher-update-check",
        })
        with urlopen(request, timeout=3) as response:
            raw = response.read(32769)
        if len(raw) > 32768:
            return result
        release = json.loads(raw)
        if not isinstance(release, dict) or release.get("draft") is True:
            return result
        # Preview is a rolling tag, so compare its human-facing version name
        # rather than the invariant "preview" tag name.
        name = release.get("name")
        version = version_tuple(name) if isinstance(name, str) else None
        current = version_tuple(current_version)
        if version is not None and current is not None and version > current:
            result.update({
                "available": True,
                "version": ".".join(map(str, version)),
                "url": RELEASE_PAGE,
            })
    except (OSError, TimeoutError, ValueError, TypeError, json.JSONDecodeError):
        pass
    return result
