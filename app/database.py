from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .clock import isoformat, utc_now

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    nickname TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS subscriptions (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    topics_json TEXT NOT NULL,
    keywords_json TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS briefs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    brief_date TEXT NOT NULL,
    run_id TEXT,
    kind TEXT NOT NULL DEFAULT 'news',
    status TEXT NOT NULL,
    content_json TEXT,
    content_markdown TEXT,
    email_subject TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    delivered_at TEXT,
    UNIQUE(user_id, brief_date)
);
CREATE TABLE IF NOT EXISTS agent_runs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    brief_id TEXT NOT NULL REFERENCES briefs(id) ON DELETE CASCADE,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    rounds INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS tool_calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
    sequence INTEGER NOT NULL,
    tool_name TEXT NOT NULL,
    arguments_json TEXT NOT NULL,
    result_summary TEXT NOT NULL,
    ok INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(run_id, sequence)
);
CREATE TABLE IF NOT EXISTS email_settings (
    id INTEGER PRIMARY KEY CHECK(id=1),
    host TEXT NOT NULL DEFAULT '',
    port INTEGER NOT NULL DEFAULT 587,
    username TEXT NOT NULL DEFAULT '',
    password TEXT NOT NULL DEFAULT '',
    sender TEXT NOT NULL DEFAULT '',
    use_tls INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_briefs_user_date ON briefs(user_id, brief_date DESC);
CREATE INDEX IF NOT EXISTS idx_tool_calls_run ON tool_calls(run_id, sequence);
"""


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=15000")
        try:
            yield conn
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def get_email_settings(self) -> dict | None:
        with self.connect() as conn:
            return self._dict(conn.execute("SELECT * FROM email_settings WHERE id=1").fetchone())

    def save_email_settings(self, host: str, port: int, username: str, password: str, sender: str, use_tls: bool, now: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO email_settings(id,host,port,username,password,sender,use_tls,updated_at)
                   VALUES(1,?,?,?,?,?,?,?)
                   ON CONFLICT(id) DO UPDATE SET host=excluded.host,port=excluded.port,username=excluded.username,
                   password=excluded.password,sender=excluded.sender,use_tls=excluded.use_tls,updated_at=excluded.updated_at""",
                (host, port, username, password, sender, int(use_tls), now),
            )

    @staticmethod
    def _dict(row: sqlite3.Row | None) -> dict | None:
        return dict(row) if row is not None else None

    def create_user(self, nickname: str, email: str, now: str) -> dict:
        user_id = uuid.uuid4().hex
        with self.connect() as conn:
            conn.execute(
                "INSERT INTO users(id,nickname,email,created_at) VALUES(?,?,?,?)",
                (user_id, nickname.strip(), email.strip(), now),
            )
        return self.get_user(user_id)

    def update_user(self, user_id: str, nickname: str, email: str, now: str) -> None:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("UPDATE users SET nickname=?,email=? WHERE id=?", (nickname.strip(), email.strip(), user_id))
            conn.execute("UPDATE subscriptions SET updated_at=? WHERE user_id=?", (now, user_id))
            conn.execute("COMMIT")

    def get_user(self, user_id: str) -> dict | None:
        with self.connect() as conn:
            return self._dict(conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone())

    def list_users(self, query: str = "") -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
        needle = query.strip().casefold()
        users = []
        for row in rows:
            user = dict(row)
            if needle and needle not in user["nickname"].casefold() and needle not in user["email"].casefold():
                continue
            user["subscription"] = self.get_subscription(user["id"])
            users.append(user)
        return users

    def delete_user(self, user_id: str) -> bool:
        with self.connect() as conn:
            cursor = conn.execute("DELETE FROM users WHERE id=?", (user_id,))
            return cursor.rowcount == 1

    def save_subscription(self, user_id: str, topics: list[str], keywords: list[str], now: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO subscriptions(user_id,topics_json,keywords_json,enabled,updated_at)
                   VALUES(?,?,?,1,?)
                   ON CONFLICT(user_id) DO UPDATE SET topics_json=excluded.topics_json,
                   keywords_json=excluded.keywords_json,enabled=1,updated_at=excluded.updated_at""",
                (user_id, json.dumps(topics, ensure_ascii=False), json.dumps(keywords, ensure_ascii=False), now),
            )

    def get_subscription(self, user_id: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM subscriptions WHERE user_id=?", (user_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["topics"] = json.loads(result.pop("topics_json"))
        result["keywords"] = json.loads(result.pop("keywords_json"))
        return result

    def enabled_subscriptions(self) -> list[dict]:
        return [user for user in self.list_users() if user["subscription"] and user["subscription"]["enabled"]]

    def find_brief(self, user_id: str, brief_date: str) -> dict | None:
        with self.connect() as conn:
            return self._dict(conn.execute("SELECT * FROM briefs WHERE user_id=? AND brief_date=?", (user_id, brief_date)).fetchone())

    def get_brief(self, brief_id: str, user_id: str | None = None) -> dict | None:
        query = "SELECT * FROM briefs WHERE id=?"
        params: tuple = (brief_id,)
        if user_id:
            query += " AND user_id=?"
            params = (brief_id, user_id)
        with self.connect() as conn:
            return self._dict(conn.execute(query, params).fetchone())

    def list_briefs(self, user_id: str, limit: int = 20) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM briefs WHERE user_id=? ORDER BY brief_date DESC,created_at DESC LIMIT ?", (user_id, limit)).fetchall()
        return [dict(row) for row in rows]

    def reserve_brief(self, user_id: str, brief_date: str, now: str) -> tuple[str, bool]:
        brief_id = uuid.uuid4().hex
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute("SELECT id,status FROM briefs WHERE user_id=? AND brief_date=?", (user_id, brief_date)).fetchone()
            if existing is None:
                conn.execute(
                    "INSERT INTO briefs(id,user_id,brief_date,status,created_at,updated_at) VALUES(?,?,?,'generating',?,?)",
                    (brief_id, user_id, brief_date, now, now),
                )
                conn.execute("COMMIT")
                return brief_id, True
            if existing["status"] in {"failed", "source_failed"}:
                conn.execute(
                    "UPDATE briefs SET status='generating',error=NULL,run_id=NULL,content_json=NULL,content_markdown=NULL,updated_at=? WHERE id=?",
                    (now, existing["id"]),
                )
                conn.execute("COMMIT")
                return existing["id"], True
            conn.execute("COMMIT")
            return existing["id"], False

    def create_run(self, user_id: str, brief_id: str, mode: str, now: str) -> str:
        run_id = uuid.uuid4().hex
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "INSERT INTO agent_runs(id,user_id,brief_id,mode,status,started_at) VALUES(?,?,?,?,'running',?)",
                (run_id, user_id, brief_id, mode, now),
            )
            conn.execute("UPDATE briefs SET run_id=?,updated_at=? WHERE id=?", (run_id, now, brief_id))
            conn.execute("COMMIT")
        return run_id

    def finish_run(self, run_id: str, status: str, rounds: int, now: str, error: str | None = None) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE agent_runs SET status=?,rounds=?,error=?,finished_at=? WHERE id=?",
                (status, rounds, error, now, run_id),
            )

    def add_tool_call(self, run_id: str, sequence: int, name: str, arguments: dict, summary: str, ok: bool, duration_ms: int, now: str) -> None:
        encoded = json.dumps(arguments, ensure_ascii=False)
        if len(encoded) > 4000:
            encoded = encoded[:4000] + "…"
        with self.connect() as conn:
            conn.execute(
                """INSERT INTO tool_calls(run_id,sequence,tool_name,arguments_json,result_summary,ok,duration_ms,created_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (run_id, sequence, name, encoded, summary[:4000], int(ok), duration_ms, now),
            )

    def get_run(self, run_id: str) -> dict | None:
        with self.connect() as conn:
            return self._dict(conn.execute("SELECT * FROM agent_runs WHERE id=?", (run_id,)).fetchone())

    def list_tool_calls(self, run_id: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM tool_calls WHERE run_id=? ORDER BY sequence", (run_id,)).fetchall()
        return [dict(row) for row in rows]

    def save_generated_brief(self, brief_id: str, kind: str, content: dict, markdown: str, subject: str, status: str, now: str) -> None:
        with self.connect() as conn:
            conn.execute(
                """UPDATE briefs SET kind=?,content_json=?,content_markdown=?,email_subject=?,status=?,error=NULL,updated_at=?
                   WHERE id=? AND status='generating'""",
                (kind, json.dumps(content, ensure_ascii=False), markdown, subject, status, now, brief_id),
            )

    def mark_brief_failed(self, brief_id: str, status: str, error: str, now: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE briefs SET status=?,error=?,updated_at=? WHERE id=?", (status, error[:4000], now, brief_id))

    def claim_delivery(self, brief_id: str, now: str) -> bool:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                "UPDATE briefs SET status='sending',updated_at=? WHERE id=? AND status IN ('pending_delivery','delivery_failed','preview')",
                (now, brief_id),
            )
            conn.execute("COMMIT")
            return cursor.rowcount == 1

    def mark_delivered(self, brief_id: str, now: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE briefs SET status='delivered',delivered_at=?,updated_at=?,error=NULL WHERE id=?", (now, now, brief_id))

    def mark_delivery_failed(self, brief_id: str, error: str, now: str) -> None:
        with self.connect() as conn:
            conn.execute("UPDATE briefs SET status='delivery_failed',error=?,updated_at=? WHERE id=?", (error[:4000], now, brief_id))
