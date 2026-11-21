"""Release checks must be small, offline-safe, and install nothing."""
from __future__ import annotations

import json

from pahebatcher import update_check


def test_versions_are_compared_numerically() -> None:
    assert update_check.version_tuple("PaheBatcher v3.13.0 Preview") == (3, 13, 0)
    assert update_check.version_tuple("3.9.10") < update_check.version_tuple("3.12.0")
    assert update_check.version_tuple("rolling-preview") is None


class FakeResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, count: int) -> bytes:
        assert count == 32769
        return self.payload


def test_newer_release_notifies_without_downloading(monkeypatch) -> None:
    fetched = []

    def fetch(request, timeout):
        fetched.append((request.full_url, timeout))
        return FakeResponse(json.dumps({
            "name": "GitRatio Edition v3.13.0 Preview",
            "tag_name": "preview",
            "draft": False,
        }).encode())

    monkeypatch.setattr(update_check, "urlopen", fetch)
    assert update_check.lookup_update("3.12.0") == {
        "checked": True,
        "available": True,
        "version": "3.13.0",
        "url": update_check.RELEASE_PAGE,
    }
    assert fetched == [(update_check.RELEASE_API, 3)]


def test_same_version_and_offline_fail_closed(monkeypatch) -> None:
    monkeypatch.setattr(update_check, "urlopen", lambda *_args, **_kwargs:
                        FakeResponse(b'{"name":"v3.12.0 Preview"}'))
    assert update_check.lookup_update("3.12.0") == {"checked": True, "available": False}

    def offline(*_args, **_kwargs):
        raise OSError("offline")

    monkeypatch.setattr(update_check, "urlopen", offline)
    assert update_check.lookup_update("3.12.0") == {"checked": True, "available": False}


def test_oversized_response_is_ignored(monkeypatch) -> None:
    monkeypatch.setattr(update_check, "urlopen", lambda *_args, **_kwargs:
                        FakeResponse(b"x" * 32769))
    assert update_check.lookup_update("3.12.0") == {"checked": True, "available": False}
