"""Property test for message history deque maxlen.

Feature: propview-v2-upgrade
Property 15: Message history deque respects configured maxlen
Validates: Requirements 12.2
"""

from collections import deque

import pytest
from hypothesis import given, strategies as st, settings


# ── Property 15: Message history deque respects configured maxlen ───

@given(
    maxlen=st.integers(min_value=1, max_value=500),
    overflow=st.integers(min_value=1, max_value=100),
)
@settings(max_examples=200)
def test_deque_evicts_oldest_on_overflow(maxlen, overflow):
    """After inserting maxlen+overflow items, deque has exactly maxlen items
    and the oldest overflow items have been evicted."""
    d = deque(maxlen=maxlen)
    total = maxlen + overflow

    for i in range(total):
        d.appendleft({"id": i})

    assert len(d) == maxlen
    # The newest item (last inserted) should be at index 0
    assert d[0]["id"] == total - 1
    # The oldest surviving item should be at the end
    assert d[-1]["id"] == overflow


@given(maxlen=st.integers(min_value=1, max_value=500))
@settings(max_examples=100)
def test_deque_under_capacity(maxlen):
    """When fewer than maxlen items are inserted, all are retained."""
    d = deque(maxlen=maxlen)
    count = min(maxlen, 10)
    for i in range(count):
        d.appendleft({"id": i})
    assert len(d) == count


def test_packet_handler_default_maxlen():
    """PacketHandler uses default 500 when config has default value."""
    from unittest.mock import MagicMock
    from server.config import Config
    from server.packet_handler import PacketHandler

    config = Config()
    handler = PacketHandler(config, MagicMock(), None, None, MagicMock())
    assert handler._messages.maxlen == 500
