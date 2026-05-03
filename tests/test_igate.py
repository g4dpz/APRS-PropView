"""Tests for server.igate — bidirectional RF ↔ APRS-IS gateway."""

import pytest

from server.config import Config
from server.igate import IGate


def _make_config(
    callsign: str = "N0CALL",
    ssid: int = 0,
    rf_to_is: bool = True,
    is_to_rf: bool = True,
) -> Config:
    cfg = Config()
    cfg.station.callsign = callsign
    cfg.station.ssid = ssid
    cfg.igate.enabled = True
    cfg.igate.rf_to_is = rf_to_is
    cfg.igate.is_to_rf = is_to_rf
    return cfg


# ── RF → IS gating with q-construct ─────────────────────────────────


def test_rf_to_is_qar_when_can_tx():
    igate = IGate(_make_config())
    raw = "W3ADO>APRS,WIDE1-1:!4903.50N/07201.75W-"
    result = igate.should_gate_rf_to_is(raw, "W3ADO", can_tx_rf=True)
    assert result is not None
    assert ",qAR,N0CALL:" in result


def test_rf_to_is_qao_when_cannot_tx():
    igate = IGate(_make_config())
    raw = "W3ADO>APRS,WIDE1-1:!4903.50N/07201.75W-"
    result = igate.should_gate_rf_to_is(raw, "W3ADO", can_tx_rf=False)
    assert result is not None
    assert ",qAO,N0CALL:" in result


def test_rf_to_is_disabled():
    igate = IGate(_make_config(rf_to_is=False))
    assert igate.should_gate_rf_to_is("W3ADO>APRS:!4903.50N/07201.75W-", "W3ADO") is None


# ── IS → RF gating ──────────────────────────────────────────────────


def test_is_to_rf_gates_to_rf_heard_station():
    igate = IGate(_make_config())
    igate.note_rf_station("W3ADO")
    raw = "K3ABC>APRS,TCPIP*::W3ADO    :Hello{42}"
    assert igate.should_gate_is_to_rf(raw, "K3ABC", "APRS") is not None


def test_is_to_rf_rejects_unknown_station():
    igate = IGate(_make_config())
    raw = "K3ABC>APRS,TCPIP*::W3ADO    :Hello{42}"
    assert igate.should_gate_is_to_rf(raw, "K3ABC", "APRS") is None


def test_is_to_rf_rejects_non_message_and_disabled():
    # Non-message (position) should not be gated
    igate = IGate(_make_config())
    igate.note_rf_station("W3ADO")
    raw = "K3ABC>APRS:!4903.50N/07201.75W-"
    assert igate.should_gate_is_to_rf(raw, "K3ABC", "APRS") is None
    # Disabled IS→RF should not gate
    igate2 = IGate(_make_config(is_to_rf=False))
    igate2.note_rf_station("W3ADO")
    raw2 = "K3ABC>APRS::W3ADO    :Hello{42}"
    assert igate2.should_gate_is_to_rf(raw2, "K3ABC", "APRS") is None


# ── NOGATE / RFONLY suppression ──────────────────────────────────────


@pytest.mark.parametrize("token", ["NOGATE", "RFONLY"])
def test_nogate_rfonly_suppresses_rf_to_is(token):
    igate = IGate(_make_config())
    raw = f"W3ADO>APRS,{token}:!4903.50N/07201.75W-"
    assert igate.should_gate_rf_to_is(raw, "W3ADO") is None


@pytest.mark.parametrize("token", ["NOGATE", "RFONLY"])
def test_nogate_rfonly_suppresses_is_to_rf(token):
    igate = IGate(_make_config())
    igate.note_rf_station("W3ADO")
    raw = f"K3ABC>APRS,{token}::W3ADO    :Hello{{42}}"
    assert igate.should_gate_is_to_rf(raw, "K3ABC", "APRS") is None


# ── Third-party packet unwrapping ────────────────────────────────────


def test_third_party_unwrap_before_gating():
    igate = IGate(_make_config())
    inner = "K3ABC>APRS:!4903.50N/07201.75W-"
    raw = f"W3ADO>APRS:}}{inner}"
    result = igate.should_gate_rf_to_is(raw, "W3ADO")
    assert result is not None
    assert "K3ABC>APRS" in result


def test_third_party_suppressed_if_inner_has_tcpip():
    igate = IGate(_make_config())
    raw = "W3ADO>APRS:}}K3ABC>APRS,TCPIP:!4903.50N/07201.75W-"
    assert igate.should_gate_rf_to_is(raw, "W3ADO") is None


# ── Own-packet suppression ───────────────────────────────────────────


def test_own_rf_packet_not_gated():
    igate = IGate(_make_config())
    raw = "N0CALL>APRS:!4903.50N/07201.75W-"
    assert igate.should_gate_rf_to_is(raw, "N0CALL") is None


# ── IS → RF deduplication ────────────────────────────────────────────


def test_is_to_rf_dedup():
    igate = IGate(_make_config())
    igate.note_rf_station("W3ADO")
    raw = "K3ABC>APRS::W3ADO    :Hello{42}"
    assert igate.should_gate_is_to_rf(raw, "K3ABC", "APRS") is not None
    assert igate.should_gate_is_to_rf(raw, "K3ABC", "APRS") is None


# ── Station tracking ─────────────────────────────────────────────────


def test_note_rf_and_is_station():
    igate = IGate(_make_config())
    igate.note_rf_station("W3ADO")
    igate.note_is_station("K3ABC")
    assert "W3ADO" in igate._rf_stations
    assert "K3ABC" in igate._is_stations


def test_station_tracking_normalization_and_empty():
    igate = IGate(_make_config())
    igate.note_rf_station("  w3ado  ")
    assert "W3ADO" in igate._rf_stations
    igate2 = IGate(_make_config())
    igate2.note_rf_station("")
    assert len(igate2._rf_stations) == 0
