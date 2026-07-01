"""Offline tests: no-op store when MINIO_ENDPOINT is unset."""
from __future__ import annotations

from object_storage import NullStore, get_store


def test_defaults_to_nullstore(monkeypatch) -> None:
    monkeypatch.delenv("MINIO_ENDPOINT", raising=False)
    import object_storage.store as m
    m._store = None
    s = get_store()
    assert isinstance(s, NullStore)
    assert s.enabled is False


def test_nullstore_semantics() -> None:
    s = NullStore()
    assert s.put("recordings/x.ogg", b"data") is None
    s.delete("http://minio/call-recordings/recordings/x.ogg")  # no raise