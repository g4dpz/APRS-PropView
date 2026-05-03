"""Tests for server.digipeater — WIDEn-N digipeater logic."""

import time
import pytest

from server.config import Config
from server.ax25 import AX25Frame, AX25Address
from server.digipeater import Digipeater, DedupeCache


def _make_config(callsign="N0CALL", ssid=0) -> Config:
    """Create a Config with digipeater enabled."""
    cfg = Config()
    cfg.station.callsign = callsign
    cfg.station.ssid = ssid
    cfg.digipeater.enabled = True
    cfg.digipeater.aliases = ["WIDE1-1", "WIDE2-1"]
    cfg.digipeater.dedupe_interval = 30
    return cfg


def _make_frame(
    src: str = "W3ADO",
    dst: str = "APRS",
    digis: list[str] | None = None,
    info: str = "!4903.50N/07201.75W-",
) -> AX25Frame:
    """Build an AX25Frame from string components."""
    frame = AX25Frame()
    frame.source = AX25Address.from_string(src)
    frame.destination = AX25Address.from_string(dst)
    frame.digipeaters = [AX25Address.from_string(d) for d in (digis or [])]
    frame.info = info.encode("latin-1")
    return frame


# ── WIDEn-N hop decrement ────────────────────────────────────────────


def test_wide1_1_last_hop():
    """WIDE1-1 → N0CALL*,WIDE1*  (last hop, mark used)."""
    digi = Digipeater(_make_config())
    frame = _make_frame(digis=["WIDE1-1"])
    result = digi.should_digipeat(frame)
    assert result is not None
    assert "N0CALL*" in result.path_str


def test_wide2_2_decrements():
    """WIDE2-2 → N0CALL*,WIDE2-1  (decrement remaining)."""
    digi = Digipeater(_make_config())
    frame = _make_frame(digis=["WIDE2-2"])
    result = digi.should_digipeat(frame)
    assert result is not None
    parts = result.path_str.split(",")
    assert parts[0] == "N0CALL*"
    assert parts[1] == "WIDE2-1"


def test_wide2_1_marks_used():
    """WIDE2-1 → N0CALL*,WIDE2*  (last hop, mark used)."""
    digi = Digipeater(_make_config())
    frame = _make_frame(digis=["WIDE2-1"])
    result = digi.should_digipeat(frame)
    assert result is not None
    assert "N0CALL*" in result.path_str
    assert "WIDE2*" in result.path_str


# ── Duplicate suppression ────────────────────────────────────────────


def test_duplicate_suppressed():
    digi = Digipeater(_make_config())
    frame = _make_frame(digis=["WIDE1-1"])
    assert digi.should_digipeat(frame) is not None
    assert digi.should_digipeat(_make_frame(digis=["WIDE1-1"])) is None


def test_different_packets_not_duplicate():
    digi = Digipeater(_make_config())
    f1 = _make_frame(src="W3ADO", digis=["WIDE1-1"], info="!4903.50N/07201.75W-")
    f2 = _make_frame(src="K3ABC", digis=["WIDE1-1"], info="!4000.00N/07500.00W-")
    assert digi.should_digipeat(f1) is not None
    assert digi.should_digipeat(f2) is not None


# ── Direct-address digipeating ───────────────────────────────────────


def test_direct_address_digipeat():
    digi = Digipeater(_make_config())
    frame = _make_frame(digis=["N0CALL"])
    result = digi.should_digipeat(frame)
    assert result is not None
    assert "N0CALL*" in result.path_str


# ── Excessive hop rejection ──────────────────────────────────────────


@pytest.mark.parametrize("path", ["WIDE7-7", "WIDE5-5", "WIDE4-4"])
def test_excessive_wide_rejected(path):
    digi = Digipeater(_make_config())
    frame = _make_frame(digis=[path])
    assert digi.should_digipeat(frame) is None


def test_wide3_3_accepted():
    """WIDE3-3 is at the limit (n <= 3) and should be accepted."""
    digi = Digipeater(_make_config())
    frame = _make_frame(digis=["WIDE3-3"])
    assert digi.should_digipeat(frame) is not None


# ── Own-packet suppression ───────────────────────────────────────────


def test_own_packet_suppressed():
    digi = Digipeater(_make_config())
    frame = _make_frame(src="N0CALL", digis=["WIDE1-1"])
    assert digi.should_digipeat(frame) is None


def test_own_packet_with_ssid_suppressed():
    digi = Digipeater(_make_config(callsign="N0CALL", ssid=5))
    frame = _make_frame(src="N0CALL-5", digis=["WIDE1-1"])
    assert digi.should_digipeat(frame) is None


# ── DedupeCache purge ────────────────────────────────────────────────


def test_dedupe_cache_expired_entry_purged():
    cache = DedupeCache(max_age=1)
    frame = _make_frame()
    cache.is_duplicate(frame)
    # Manually expire the entry
    key = list(cache._cache.keys())[0]
    cache._cache[key] = time.time() - 2
    assert cache.is_duplicate(frame) is False


# ── Disabled digipeater ──────────────────────────────────────────────


def test_disabled_digipeater_returns_none():
    cfg = _make_config()
    cfg.digipeater.enabled = False
    digi = Digipeater(cfg)
    frame = _make_frame(digis=["WIDE1-1"])
    assert digi.should_digipeat(frame) is None
