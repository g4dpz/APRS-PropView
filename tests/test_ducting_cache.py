"""Property test for ducting cache threshold decision.

Feature: uk-eu-internationalization
Property 14: Below-threshold atmospheric changes do not trigger ducting refetch
Property 15: Pressure threshold met triggers ducting refetch
Property 16: Temperature threshold met triggers ducting refetch
Validates: Requirements 14.1, 14.2, 14.3

The threshold logic: skip API fetch if |pressure_diff| < 2.0 mb AND
|temp_diff| < 3.0°F. Fetch if either threshold is met or exceeded.
"""

import pytest
from hypothesis import given, strategies as st, settings, assume

from server.weather import _should_refetch_ducting


# ── Strategies ──────────────────────────────────────────────────────

pressure_st = st.floats(min_value=950, max_value=1060, allow_nan=False)
temp_st = st.floats(min_value=-40, max_value=130, allow_nan=False)
small_delta_st = st.floats(min_value=0, max_value=1.99, allow_nan=False)
large_pressure_delta_st = st.floats(min_value=2.0, max_value=20, allow_nan=False)
large_temp_delta_st = st.floats(min_value=3.0, max_value=30, allow_nan=False)


# ── Property 14: Below-threshold → no refetch ──────────────────────

@given(
    p1=pressure_st,
    p_delta=small_delta_st,
    t1=temp_st,
    t_delta=st.floats(min_value=0, max_value=2.99, allow_nan=False),
)
@settings(max_examples=300)
def test_below_both_thresholds_returns_cached(p1, p_delta, t1, t_delta):
    """**Validates: Requirements 14.1**
    When both pressure < 2mb AND temp < 3°F, should NOT refetch."""
    assume(p_delta < 2.0 and t_delta < 3.0)
    assert not _should_refetch_ducting(p1, p1 + p_delta, t1, t1 + t_delta)
    assert not _should_refetch_ducting(p1, p1 - p_delta, t1, t1 - t_delta)


# ── Property 15: Pressure threshold met → refetch ──────────────────

@given(
    p1=pressure_st,
    p_delta=large_pressure_delta_st,
    t1=temp_st,
    t_delta=st.floats(min_value=0, max_value=50, allow_nan=False),
)
@settings(max_examples=200)
def test_pressure_threshold_met_triggers_refetch(p1, p_delta, t1, t_delta):
    """**Validates: Requirements 14.2**
    When pressure diff >= 2mb, should refetch regardless of temp."""
    p2 = p1 + p_delta
    actual_diff = abs(p2 - p1)
    assume(actual_diff >= 2.0)
    assert _should_refetch_ducting(p1, p2, t1, t1 + t_delta)


# ── Property 16: Temperature threshold met → refetch ───────────────

@given(
    p1=pressure_st,
    p_delta=st.floats(min_value=0, max_value=50, allow_nan=False),
    t1=temp_st,
    t_delta=large_temp_delta_st,
)
@settings(max_examples=200)
def test_temp_threshold_met_triggers_refetch(p1, p_delta, t1, t_delta):
    """**Validates: Requirements 14.3**
    When temp diff >= 3°F, should refetch regardless of pressure."""
    t2 = t1 + t_delta
    actual_diff = abs(t2 - t1)
    assume(actual_diff >= 3.0)
    assert _should_refetch_ducting(p1, p1 + p_delta, t1, t2)


# ── Boundary tests ──────────────────────────────────────────────────

def test_exact_pressure_threshold():
    """Exactly 2.0 mb pressure diff triggers refetch."""
    assert _should_refetch_ducting(1013.0, 1015.0, 70.0, 70.0)
    assert _should_refetch_ducting(1013.0, 1011.0, 70.0, 70.0)


def test_just_below_pressure_threshold():
    """1.99 mb pressure diff does NOT trigger refetch (if temp also below)."""
    assert not _should_refetch_ducting(1013.0, 1014.99, 70.0, 70.0)


def test_exact_temp_threshold():
    """Exactly 3.0°F temp diff triggers refetch."""
    assert _should_refetch_ducting(1013.0, 1013.0, 70.0, 73.0)
    assert _should_refetch_ducting(1013.0, 1013.0, 70.0, 67.0)


def test_just_below_temp_threshold():
    """2.99°F temp diff does NOT trigger refetch (if pressure also below)."""
    assert not _should_refetch_ducting(1013.0, 1013.0, 70.0, 72.99)


def test_both_thresholds_met():
    """Both thresholds met still triggers refetch."""
    assert _should_refetch_ducting(1013.0, 1016.0, 70.0, 75.0)


def test_zero_change():
    """No change at all — should NOT refetch."""
    assert not _should_refetch_ducting(1013.0, 1013.0, 70.0, 70.0)


def test_none_previous_pressure_triggers_refetch():
    """None previous pressure triggers refetch."""
    assert _should_refetch_ducting(None, 1013.0, 70.0, 70.0)


def test_none_previous_temp_triggers_refetch():
    """None previous temperature triggers refetch."""
    assert _should_refetch_ducting(1013.0, 1013.0, None, 70.0)


def test_none_both_previous_triggers_refetch():
    """None for both previous values triggers refetch."""
    assert _should_refetch_ducting(None, 1013.0, None, 70.0)
