import sqlite3

from src.server import _queue_message

TEST_DB = ":memory:"


def test_queue_message_inserts_row(db_conn):
    _queue_message("+32456789012", "Ik heb rugpijn.")
    row = db_conn.execute(
        "SELECT sender, message, status, channel FROM message_queue WHERE id=1"
    ).fetchone()
    assert row[0] == "+32456789012"
    assert row[1] == "Ik heb rugpijn."
    assert row[2] == "pending"
    assert row[3] == "signal"


def test_multiple_messages_in_order(db_conn):
    _queue_message("+32456111111", "Bericht A")
    _queue_message("+32456222222", "Bericht B")
    rows = db_conn.execute(
        "SELECT sender, message FROM message_queue ORDER BY id"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0][1] == "Bericht A"
    assert rows[1][1] == "Bericht B"
