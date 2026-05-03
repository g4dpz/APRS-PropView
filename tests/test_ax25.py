"""Tests for server.ax25 — AX.25 frame encoding, decoding, and address handling."""

import pytest

from server.ax25 import AX25Frame, AX25Address, AX25_UI_CONTROL, AX25_PID_NO_LAYER3


# ── AX25Address from_string parsing ──────────────────────────────────


@pytest.mark.parametrize(
    "input_str,call,ssid,hbit",
    [
        ("N0CALL", "N0CALL", 0, False),
        ("N0CALL-15", "N0CALL", 15, False),
        ("N0CALL-3*", "N0CALL", 3, True),
        ("n0call", "N0CALL", 0, False),
    ],
)
def test_address_from_string(input_str, call, ssid, hbit):
    addr = AX25Address.from_string(input_str)
    assert addr.callsign == call
    assert addr.ssid == ssid
    assert addr.h_bit is hbit


# ── SSID handling (0-15) ─────────────────────────────────────────────


@pytest.mark.parametrize("ssid", range(0, 16))
def test_ssid_range(ssid):
    addr = AX25Address.from_string(f"N0CALL-{ssid}")
    assert addr.ssid == ssid


def test_ssid_zero_no_suffix():
    assert AX25Address(callsign="N0CALL", ssid=0).full_call == "N0CALL"


def test_ssid_nonzero_has_suffix():
    assert AX25Address(callsign="N0CALL", ssid=7).full_call == "N0CALL-7"


# ── H-bit flag manipulation ─────────────────────────────────────────


def test_hbit_survives_encode_decode():
    for hbit_val in (True, False):
        addr = AX25Address(callsign="N0CALL", ssid=3, h_bit=hbit_val)
        decoded = AX25Address.decode(addr.encode(is_last=False))
        assert decoded.h_bit is hbit_val
        assert decoded.ssid == 3


# ── AX25Frame encode/decode round-trip ───────────────────────────────


def test_simple_frame_roundtrip():
    frame = AX25Frame()
    frame.source = AX25Address.from_string("N0CALL")
    frame.destination = AX25Address.from_string("APRS")
    frame.info = b"!4903.50N/07201.75W-"

    decoded = AX25Frame.decode(frame.encode())
    assert decoded is not None
    assert decoded.source.callsign == "N0CALL"
    assert decoded.destination.callsign == "APRS"
    assert decoded.info == b"!4903.50N/07201.75W-"


def test_frame_with_digipeaters_roundtrip():
    frame = AX25Frame()
    frame.source = AX25Address.from_string("W3ADO")
    frame.destination = AX25Address.from_string("APRS")
    frame.digipeaters = [
        AX25Address.from_string("WIDE1-1"),
        AX25Address(callsign="N0CALL", ssid=0, h_bit=True),
    ]
    frame.info = b"Test"

    decoded = AX25Frame.decode(frame.encode())
    assert decoded is not None
    assert len(decoded.digipeaters) == 2
    assert decoded.digipeaters[0].callsign == "WIDE1"
    assert decoded.digipeaters[0].ssid == 1
    assert decoded.digipeaters[1].h_bit is True


def test_control_and_pid_preserved():
    frame = AX25Frame()
    frame.source = AX25Address.from_string("N0CALL")
    frame.destination = AX25Address.from_string("APRS")
    frame.control = AX25_UI_CONTROL
    frame.pid = AX25_PID_NO_LAYER3
    frame.info = b"Hello"

    decoded = AX25Frame.decode(frame.encode())
    assert decoded.control == AX25_UI_CONTROL
    assert decoded.pid == AX25_PID_NO_LAYER3


# ── to_aprs_string output ───────────────────────────────────────────


def test_to_aprs_string_simple():
    frame = AX25Frame()
    frame.source = AX25Address.from_string("N0CALL")
    frame.destination = AX25Address.from_string("APRS")
    frame.info = b"!4903.50N/07201.75W-"
    assert frame.to_aprs_string() == "N0CALL>APRS:!4903.50N/07201.75W-"


def test_to_aprs_string_with_path():
    frame = AX25Frame()
    frame.source = AX25Address.from_string("W3ADO")
    frame.destination = AX25Address.from_string("APRS")
    frame.digipeaters = [
        AX25Address(callsign="N0CALL", ssid=0, h_bit=True),
        AX25Address.from_string("WIDE2-1"),
    ]
    frame.info = b"Test"
    assert frame.to_aprs_string() == "W3ADO>APRS,N0CALL*,WIDE2-1:Test"


def test_from_aprs_string_roundtrip():
    original = "W3ADO>APRS,WIDE1-1,WIDE2-1:!4903.50N/07201.75W-"
    frame = AX25Frame.from_aprs_string(original)
    assert frame is not None
    assert frame.to_aprs_string() == original


# ── Edge cases ───────────────────────────────────────────────────────


def test_decode_too_short():
    assert AX25Frame.decode(b"\x00" * 10) is None


def test_from_aprs_string_invalid():
    assert AX25Frame.from_aprs_string("garbage") is None
    assert AX25Frame.from_aprs_string("N0CALL:info") is None


def test_short_callsign_pads_to_7_bytes():
    addr = AX25Address(callsign="AB", ssid=0)
    assert len(addr.encode(is_last=True)) == 7
