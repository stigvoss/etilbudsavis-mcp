import importlib
import sys

import pytest

API_KEY = "test-key-0123456789abcdefghijklmnop"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def load_server(monkeypatch):
    """Import a fresh copy of server.py under the given environment."""

    def load(**env):
        monkeypatch.delenv("MCP_API_KEY_FILE", raising=False)
        monkeypatch.setenv("MCP_API_KEY", API_KEY)
        for name, value in env.items():
            monkeypatch.setenv(name, value)
        sys.modules.pop("server", None)
        return importlib.import_module("server")

    yield load
    sys.modules.pop("server", None)
