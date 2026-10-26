"""Masked callback caller correlation never stores or crosses raw identifiers."""

from omnivoice.vobiz_callers import PendingVobizCallers


def test_masked_caller_is_one_use_and_line_scoped():
    pending = PendingVobizCallers()
    pending.remember("line-a", "carrier-call", "+919876543210")
    assert "9876543210" not in repr(pending._entries)
    assert "carrier-call" not in repr(pending._entries)
    assert pending.take("line-b", "carrier-call") is None
    assert pending.take("line-a", "carrier-call") == "••••3210"
    assert pending.take("line-a", "carrier-call") is None


def test_masked_caller_rejects_bad_input_and_is_bounded(monkeypatch):
    now = [100.0]
    monkeypatch.setattr("omnivoice.vobiz_callers.time.monotonic", lambda: now[0])
    pending = PendingVobizCallers(limit=1, ttl_seconds=5)
    pending.remember("line", "bad", "anonymous")
    assert pending.take("line", "bad") is None
    pending.remember("line", "one", "+919876543210")
    pending.remember("line", "two", "+919876543211")
    assert pending.take("line", "one") is None
    now[0] = 106.0
    assert pending.take("line", "two") is None
