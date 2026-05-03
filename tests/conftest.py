"""Shared test fixtures for APRS PropView tests."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest


@pytest.fixture
def mock_config():
    """Create a mock Config object with sensible defaults."""
    from server.config import Config
    return Config()


@pytest.fixture
def temp_db_path():
    """Provide a temporary database file path, cleaned up after test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    Path(path).unlink(missing_ok=True)
    for ext in ["-wal", "-shm"]:
        Path(path + ext).unlink(missing_ok=True)


@pytest.fixture
def mock_websocket_manager():
    """Create a mock WebSocketManager."""
    ws = MagicMock()
    ws.broadcast = AsyncMock()
    ws.send_to = AsyncMock()
    ws.connect = AsyncMock(return_value=True)
    ws.disconnect = MagicMock()
    ws.client_count = 0
    return ws
