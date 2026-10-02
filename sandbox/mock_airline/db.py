"""SQLite storage and synthetic seed data for the mock airline."""

import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS flights (
    id TEXT PRIMARY KEY,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    departs_at TEXT NOT NULL,
    seats_available INTEGER NOT NULL CHECK (seats_available >= 0)
);
CREATE TABLE IF NOT EXISTS bookings (
    confirmation_code TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    flight_id TEXT NOT NULL REFERENCES flights(id)
);
CREATE TABLE IF NOT EXISTS idempotency_keys (
    key TEXT PRIMARY KEY,
    confirmation_code TEXT NOT NULL,
    flight_id TEXT NOT NULL,
    response TEXT NOT NULL
);
"""

# Synthetic data only: no real people or bookings.
FLIGHTS = [
    ("WS100", "SFO", "JFK", "2026-11-02T08:00", 3),
    ("WS102", "SFO", "JFK", "2026-11-02T13:00", 0),
    ("WS104", "SFO", "JFK", "2026-11-02T18:00", 5),
    ("WS106", "SFO", "JFK", "2026-11-03T08:00", 2),
    ("WS200", "JFK", "SFO", "2026-11-05T09:30", 4),
]

BOOKINGS = [
    ("ABC123", "Avery", "Sample", "WS100"),
    ("XYZ789", "Jordan", "Placeholder", "WS200"),
]


def connect(path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection, seed: bool = True) -> None:
    conn.executescript(SCHEMA)
    if seed and conn.execute("SELECT COUNT(*) FROM flights").fetchone()[0] == 0:
        with conn:
            conn.executemany("INSERT INTO flights VALUES (?, ?, ?, ?, ?)", FLIGHTS)
            conn.executemany("INSERT INTO bookings VALUES (?, ?, ?, ?)", BOOKINGS)
