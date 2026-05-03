"""Property test for ducting cache threshold decision.

Feature: propview-v2-upgrade
Property 11: Ducting cache threshold decision is correct
Validates: Requirements 9.1, 9.2, 9.3

The threshold logic: skip API fetch if |pressure_diff| < 2.0 mb AND
|temp_diff| < 3.0°F. Fetch if either threshold is met or exceeded.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume


# ── Pure threshold decision function (extracted for testing) ────────

def should_refetch(
    prev_pressure: float,
    curr_pressure: float,
    prev_temp: float,
    curr_temp: float,
) -> bool:
    """Return True if a fresh ducting fetch should be triggered.

    Thresholds: pressure >= 2.0 mb OR temperature >= 3.0°F.
    """
    pressure_diff = abs(curr_pressure - prev_pressure)
    temp_diff = abs(curr_temp - prev_temp)
    return pressure_diff >= 2.0 or temp_diff >= 3.0


# ── Strategies ──────────────────────────────────────────────────────

pressure_st = st.floats(min_value=950, max_value=1060, allow_nan=False)
temp_st = st.floats(min_value=-40, max_value=130, allow_nan=False)
small_delta_st = st.floats(min_value=0, max_value=1.99, allow_nan=False)
large_pressure_delta_st = st.floats(min_value=2.0, max_value=20, allow_nan=False)
large_temp_delta_st = st.floats(min_value=3.0, max_value=30, allow_nan=False)


# ── Property 11: Ducting cache threshold decision ───────────────────

@given(
    p1=pressure_st,
    p_delta=small_delta_st,
    t1=temp_st,
    t_delta=st.floats(min_value=0, max_value=2.99, allow_nan=False),
)
@settings(max_examples=300)
def test_below_both_thresholds_returns_cached(p1, p_delta, t1, t_delta):
    """When both pressure < 2mb AND temp < 3°F, should NOT refetch."""
    assume(p_delta < 2.0 and t_delta < 3.0)
    assert not should_refetch(p1, p1 + p_delta, t1, t1 + t_delta)
    assert not should_refetch(p1, p1 - p_delta, t1, t1 - t_delta)


@given(
    p1=pressure_st,
    p_delta=large_pressure_delta_st,
    t1=temp_st,
    t_delta=st.floats(min_value=0, max_value=50, allow_nan=False),
)
@settings(max_examples=200)
def test_pressure_threshold_met_triggers_refetch(p1, p_delta, t1, t_delta):
    """When pressure diff >= 2mb, should refetch regardless of temp."""
    p2 = p1 + p_delta
    actual_diff = abs(p2 - p1)
    assume(actual_diff >= 2.0)
    assert should_refetch(p1, p2, t1, t1 + t_delta)


@given(
    p1=pressure_st,
    p_delta=st.floats(min_value=0, max_value=50, allow_nan=False),
    t1=temp_st,
    t_delta=large_temp_delta_st,
)
@settings(max_examples=200)
def test_temp_threshold_met_triggers_refetch(p1, p_delta, t1, t_delta):
    """When temp diff >= 3°F, should refetch regardless of pressure."""
    t2 = t1 + t_delta
    actual_diff = abs(t2 - t1)
    # Only assert if the actual float difference is >= 3.0
    assume(actual_diff >= 3.0)
    assert should_refetch(p1, p1 + p_delta, t1, t2)


# ── Boundary tests ──────────────────────────────────────────────────

def test_exact_pressure_threshold():
    """Exactly 2.0 mb pressure diff triggers refetch."""
    assert should_refetch(1013.0, 1015.0, 70.0, 70.0)
    assert should_refetch(1013.0, 1011.0, 70.0, 70.0)


def test_just_below_pressure_threshold():
    """1.99 mb pressure diff does NOT trigger refetch (if temp also below)."""
    assert not should_refetch(1013.0, 1014.99, 70.0, 70.0)


def test_exact_temp_threshold():
    """Exactly 3.0°F temp diff triggers refetch."""
    assert should_refetch(1013.0, 1013.0, 70.0, 73.0)
    assert should_refetch(1013.0, 1013.0, 70.0, 67.0)


def test_just_below_temp_threshold():
    """2.99°F temp diff does NOT trigger refetch (if pressure also below)."""
    assert not should_refetch(1013.0, 1013.0, 70.0, 72.99)


def test_both_thresholds_met():
    """Both thresholds met still triggers refetch."""
    assert should_refetch(1013.0, 1016.0, 70.0, 75.0)


def test_zero_change():
    """No change at all — should NOT refetch."""
    assert not should_refetch(1013.0, 1013.0, 70.0, 70.0)
