import tempfile

import pytest

from src import server
from src.init_db import init_db


class _MockSignalSender:
    def __init__(self):
        self.sent = []

    def send(self, recipient, text):
        self.sent.append((recipient, text))
        return True


@pytest.fixture(autouse=True)
def _db_setup(monkeypatch):
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    monkeypatch.setattr(server, "DB_PATH", db.name)
    init_db(db.name)
    yield
    import os
    os.unlink(db.name)


@pytest.fixture(autouse=True)
def _mock_signal(monkeypatch):
    monkeypatch.setattr(server, "_signal", _MockSignalSender())


@pytest.fixture
def db_conn():
    import sqlite3
    conn = sqlite3.connect(server.DB_PATH)
    yield conn
    conn.close()
