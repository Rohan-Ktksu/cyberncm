"""SQLite storage for the console."""
import sqlite3, threading

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, pw_hash TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sessions (token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL, expires REAL NOT NULL);
CREATE TABLE IF NOT EXISTS sites (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, name TEXT NOT NULL, created REAL NOT NULL,
  enrol_hash TEXT, enrol_expires REAL, enrol_used INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS agents (id TEXT PRIMARY KEY, site_id INTEGER NOT NULL, pubkey TEXT NOT NULL, created REAL NOT NULL,
  last_seen REAL, last_seq INTEGER NOT NULL DEFAULT 0, state TEXT, windows_seen INTEGER NOT NULL DEFAULT 0, learn_progress REAL, info TEXT);
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, site_id INTEGER NOT NULL, received REAL NOT NULL, kind TEXT NOT NULL,
  src TEXT, window_start REAL, score REAL, expires REAL, detail TEXT, signature TEXT);
CREATE INDEX IF NOT EXISTS events_site ON events (site_id, received);
"""


class DB:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.conn.executescript(SCHEMA)

    def execute(self, sql, args=()):
        with self.lock:
            return self.conn.execute(sql, args)

    def one(self, sql, args=()):
        return self.execute(sql, args).fetchone()

    def all(self, sql, args=()):
        return self.execute(sql, args).fetchall()
