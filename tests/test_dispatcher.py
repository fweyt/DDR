import sqlite3

from src.server import _queue_message, _process_one

TEST_DB = ":memory:"


def test_process_one_processes_pending(db_conn):
    _queue_message("+32456789012", "Ik heb rugpijn.")
    result = _process_one()
    assert result is True
    row = db_conn.execute(
        "SELECT sender, message, status, reply FROM message_queue WHERE id=1"
    ).fetchone()
    assert row[0] == "+32456789012"
    assert row[1] == "Ik heb rugpijn."
    assert row[2] == "completed"
    assert row[3] is not None


def test_process_one_returns_false_when_empty():
    result = _process_one()
    assert result is False


def test_multiple_messages_processed_in_order(db_conn):
    _queue_message("+32456111111", "Bericht A")
    _queue_message("+32456222222", "Bericht B")
    _process_one()
    _process_one()
    rows = db_conn.execute(
        "SELECT status FROM message_queue ORDER BY id"
    ).fetchall()
    assert all(r[0] == "completed" for r in rows)
