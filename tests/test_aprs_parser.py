"""Tests for server.aprs_parser — APRS packet parsing, construction, and geo math."""

import pytest

from server.aprs_parser import (
    parse_packet,
    calculate_distance,
    calculate_bearing,
    make_position_packet,
    make_message_packet,
    make_ack_packet,
    make_rej_packet,
)


# ── Uncompressed position parsing ────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected_lat,expected_lon",
    [
        # North/West — W3ADO near 49.058°N, 72.029°W
        ("W3ADO-1>APRS:!4903.50N/07201.75W-PHG5360", 49 + 3.50 / 60, -(72 + 1.75 / 60)),
        # South/East — VK2RZA near 33.867°S, 151.200°E
        ("VK2RZA>APRS:!3352.00S/15112.00E#Digi", -(33 + 52.00 / 60), 151 + 12.00 / 60),
        # '=' DTI (position with messaging)
        ("N0CALL>APRS:=4903.50N/07201.75W-Test", 49 + 3.50 / 60, -(72 + 1.75 / 60)),
    ],
)
def test_uncompressed_position(raw, expected_lat, expected_lon):
    pkt = parse_packet(raw)
    assert pkt.packet_type == "position"
    assert pkt.latitude == pytest.approx(expected_lat, abs=1e-4)
    assert pkt.longitude == pytest.approx(expected_lon, abs=1e-4)


def test_uncompressed_symbol_extraction():
    raw = "N0CALL>APRS:!4903.50N/07201.75W#PHG5360"
    pkt = parse_packet(raw)
    assert pkt.symbol_table == "/"
    assert pkt.symbol_code == "#"


# ── Compressed position parsing ──────────────────────────────────────


def test_compressed_position():
    raw = "W3ADO-1>APRS:!/5L!!<*e7>7P["
    pkt = parse_packet(raw)
    assert pkt.packet_type == "position"
    assert pkt.has_position
    assert pkt.symbol_table == "/"


# ── Mic-E decoding ──────────────────────────────────────────────────


def test_mic_e_decoding():
    raw = "N0CALL>T4SQZZ:`(_fn\"Oj/]\"4T}"
    pkt = parse_packet(raw)
    assert pkt.packet_type == "mic_e"
    assert pkt.has_position
    assert isinstance(pkt.symbol_code, str)
    assert isinstance(pkt.symbol_table, str)


# ── Message parsing ──────────────────────────────────────────────────


def test_message_parsing():
    # With message ID
    pkt = parse_packet("N0CALL>APRS::W3ADO-1  :Hello World{123}")
    assert pkt.packet_type == "message"
    assert pkt.addressee == "W3ADO-1"
    assert pkt.message_text == "Hello World"
    assert pkt.message_id == "123"
    # Without message ID
    pkt2 = parse_packet("N0CALL>APRS::W3ADO-1  :Testing")
    assert pkt2.message_text == "Testing"
    assert pkt2.message_id == ""


# ── Object and item parsing ─────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,name,alive,ptype",
    [
        ("N0CALL>APRS:;LEADER   *092345z4903.50N/07201.75W-", "LEADER", True, "object"),
        ("N0CALL>APRS:;LEADER   _092345z4903.50N/07201.75W-", "LEADER", False, "object"),
        ("N0CALL>APRS:)AID #2!4903.50N/07201.75W-", "AID #2", True, "item"),
        ("N0CALL>APRS:)AID #2_4903.50N/07201.75W-", "AID #2", False, "item"),
    ],
)
def test_object_and_item(raw, name, alive, ptype):
    pkt = parse_packet(raw)
    assert pkt.packet_type == ptype
    assert pkt.object_name == name
    assert pkt.alive is alive


# ── Timestamp extraction ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "raw,expected_ts",
    [
        ("N0CALL>APRS:/092345z4903.50N/07201.75W-", "092345z"),
        ("N0CALL>APRS:@092345/4903.50N/07201.75W-", "092345/"),
    ],
)
def test_timestamp_extraction(raw, expected_ts):
    pkt = parse_packet(raw)
    assert pkt.timestamp == expected_ts


# ── Altitude extraction ──────────────────────────────────────────────


def test_altitude_extraction():
    pkt = parse_packet("N0CALL>APRS:!4903.50N/07201.75W-/A=001234")
    assert pkt.altitude == pytest.approx(1234 * 0.3048, abs=0.1)
    pkt2 = parse_packet("N0CALL>APRS:!4903.50N/07201.75W-PHG5360")
    assert pkt2.altitude is None


# ── Distance and bearing calculations ────────────────────────────────


@pytest.mark.parametrize(
    "lat1,lon1,lat2,lon2,expected_km",
    [
        (40.0, -74.0, 40.0, -74.0, 0.0),          # same point
        (40.7128, -74.0060, 51.5074, -0.1278, 5570),  # NY→London
        (0.0, 0.0, 0.0, 1.0, 111.32),              # 1° longitude at equator
    ],
)
def test_calculate_distance(lat1, lon1, lat2, lon2, expected_km):
    dist = calculate_distance(lat1, lon1, lat2, lon2)
    assert dist == pytest.approx(expected_km, rel=0.02)


@pytest.mark.parametrize(
    "lat1,lon1,lat2,lon2,expected_bearing",
    [
        (40.0, -74.0, 41.0, -74.0, 0.0),   # due north
        (0.0, 0.0, 0.0, 1.0, 90.0),        # due east
        (40.0, -74.0, 39.0, -74.0, 180.0),  # due south
    ],
)
def test_calculate_bearing(lat1, lon1, lat2, lon2, expected_bearing):
    bearing = calculate_bearing(lat1, lon1, lat2, lon2)
    assert bearing == pytest.approx(expected_bearing, abs=1.0)
    assert 0 <= bearing < 360


# ── Packet construction ──────────────────────────────────────────────


def test_make_position_packet_roundtrip():
    info = make_position_packet("N0CALL", 49.0583, -72.0292, comment="Test")
    raw = f"N0CALL>APRS:{info}"
    pkt = parse_packet(raw)
    assert pkt.latitude == pytest.approx(49.0583, abs=0.01)
    assert pkt.longitude == pytest.approx(-72.0292, abs=0.01)


def test_make_message_and_ack_packets():
    assert make_message_packet("W3ADO-1", "Hello", "42") == ":W3ADO-1  :Hello{42}"
    assert make_message_packet("W3ADO-1", "Hello") == ":W3ADO-1  :Hello"
    assert make_ack_packet("W3ADO-1", "42") == ":W3ADO-1  :ack42"
    assert make_rej_packet("W3ADO-1", "42") == ":W3ADO-1  :rej42"


def test_addressee_padding():
    info = make_message_packet("AB", "Hi")
    assert info.startswith(":AB       :")


# ── Edge cases ───────────────────────────────────────────────────────


def test_status_and_path_parsing():
    pkt = parse_packet("N0CALL>APRS:>Running PropView v2")
    assert pkt.packet_type == "status"
    assert pkt.comment == "Running PropView v2"
    pkt2 = parse_packet("N0CALL>APRS,WIDE1-1,WIDE2-1:!4903.50N/07201.75W-")
    assert pkt2.path == "WIDE1-1,WIDE2-1"
