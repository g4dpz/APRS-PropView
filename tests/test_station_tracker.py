"""Tests for server.station_tracker — static helper methods (no async/DB needed)."""

import pytest

from server.station_tracker import StationTracker


# ── _is_direct_path ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path,expected",
    [
        ("", True),                        # empty path = direct
        ("WIDE1-1", True),                 # unused hop = still direct
        ("WIDE1-1*", True),                # WIDE alias used = direct
        ("WIDE2-1*", True),                # WIDE alias used = direct
        ("RELAY*", True),                  # RELAY alias = direct
        ("TRACE*", True),                  # TRACE alias = direct
        ("N0CALL*", False),                # real callsign = not direct
        ("K3ABC*,WIDE2-1", False),         # relayed through real digi
        ("WIDE1-1*,WIDE2-1", True),        # only WIDE aliases used
        ("N0CALL*,WIDE2-1*", False),       # real callsign in path
    ],
)
def test_is_direct_path(path, expected):
    assert StationTracker._is_direct_path(path) is expected


# ── _count_hops ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path,expected",
    [
        ("", 0),
        ("WIDE1-1", 0),                   # unused = 0 hops
        ("WIDE1-1*", 1),                  # one used hop
        ("N0CALL*,WIDE2-1", 1),           # one used, one unused
        ("N0CALL*,K3ABC*", 2),            # two used hops
        ("N0CALL*,K3ABC*,WIDE2-1", 2),   # two used, one unused
        ("A*,B*,C*", 3),                  # three used hops
    ],
)
def test_count_hops(path, expected):
    assert StationTracker._count_hops(path) == expected


# ── _score_to_level ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "score,expected",
    [
        (0.0, "none"),
        (0.5, "poor"),
        (24.9, "poor"),
        (25.0, "fair"),
        (49.9, "fair"),
        (50.0, "good"),
        (74.9, "good"),
        (75.0, "excellent"),
        (100.0, "excellent"),
    ],
)
def test_score_to_level(score, expected):
    assert StationTracker._score_to_level(score) == expected


# ── Boundary checks ─────────────────────────────────────────────────


def test_zero_score_is_none():
    assert StationTracker._score_to_level(0) == "none"


def test_max_score_is_excellent():
    assert StationTracker._score_to_level(100) == "excellent"


def test_empty_path_zero_hops():
    assert StationTracker._count_hops("") == 0


def test_empty_path_is_direct():
    assert StationTracker._is_direct_path("") is True


def test_mycall_star_not_direct():
    """A real callsign with * means another digi relayed it."""
    assert StationTracker._is_direct_path("MYCALL*") is False


def test_wide_star_is_direct():
    """WIDE alias with * doesn't count as relayed through another digi."""
    assert StationTracker._is_direct_path("WIDE1*") is True
