"""Local metadata-only SQLite store for Jev performance telemetry."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import os
import sqlite3
import threading
import time
from typing import Any


SCHEMA_VERSION = 2
PLUGIN_DATA_DIR = "hermes-jev-performance"
DB_FILENAME = "metrics.sqlite3"


class StoreSchemaError(RuntimeError):
    """The local metrics DB schema is newer than this plugin understands."""


def _fallback_hermes_home() -> Path:
    configured = os.environ.get("HERMES_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".hermes"


def current_hermes_home() -> Path:
    try:
        from hermes_constants import get_hermes_home
    except ImportError:
        return _fallback_hermes_home()
    try:
        return Path(get_hermes_home())
    except Exception:
        return _fallback_hermes_home()


def default_db_path() -> Path:
    return current_hermes_home() / "plugin-data" / PLUGIN_DATA_DIR / DB_FILENAME


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _integer(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return max(0, value)


@dataclass(frozen=True)
class StatsSummary:
    since_hours: int
    decisions: int
    turns: int
    applied: int
    fallback: int
    avg_confidence: float | None
    avg_jev_latency_ms: float | None
    total_jev_cost_usd: float | None
    avg_turn_duration_ms: float | None
    avg_tool_calls: float | None
    avg_llm_requests: float | None
    input_tokens: int | None
    output_tokens: int | None
    routes: tuple[tuple[str, int], ...]


class MetricsStore:
    """Small SQLite store. Opens short-lived connections for thread/process safety."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else default_db_path()
        self._init_lock = threading.Lock()
        self._initialized = False

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.path), timeout=3.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout = 3000")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _schema_version(self, con: sqlite3.Connection) -> int:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        row = con.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        if row is None:
            return 0
        try:
            return int(row["value"])
        except (TypeError, ValueError):
            return 0

    def _set_schema_version(self, con: sqlite3.Connection, version: int) -> None:
        con.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES('schema_version', ?)",
            (str(version),),
        )

    def _migrate_v1(self, con: sqlite3.Connection) -> None:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS jev_decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turn_key TEXT NOT NULL UNIQUE,
                created_at REAL NOT NULL,
                mode TEXT NOT NULL,
                provider TEXT,
                requested_model TEXT,
                actual_model TEXT,
                family TEXT,
                confidence REAL,
                latency_ms REAL,
                cost_usd REAL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                accepted INTEGER NOT NULL DEFAULT 0,
                applied INTEGER NOT NULL DEFAULT 0,
                reason TEXT NOT NULL,
                error_category TEXT,
                error_status_code INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_jev_decisions_created
            ON jev_decisions(created_at);

            CREATE INDEX IF NOT EXISTS idx_jev_decisions_family
            ON jev_decisions(family);

            CREATE TABLE IF NOT EXISTS hermes_turns (
                turn_key TEXT PRIMARY KEY,
                started_at REAL NOT NULL,
                completed_at REAL,
                mode TEXT NOT NULL,
                route_family TEXT,
                route_applied INTEGER NOT NULL DEFAULT 0,
                duration_ms REAL,
                llm_requests INTEGER NOT NULL DEFAULT 0,
                tool_calls INTEGER NOT NULL DEFAULT 0,
                input_tokens INTEGER,
                cached_input_tokens INTEGER,
                output_tokens INTEGER,
                reasoning_tokens INTEGER,
                status TEXT NOT NULL DEFAULT 'running'
            );

            CREATE INDEX IF NOT EXISTS idx_hermes_turns_started
            ON hermes_turns(started_at);

            CREATE INDEX IF NOT EXISTS idx_hermes_turns_mode
            ON hermes_turns(mode);

            CREATE TABLE IF NOT EXISTS mode_changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at REAL NOT NULL,
                old_mode TEXT NOT NULL,
                new_mode TEXT NOT NULL,
                source TEXT NOT NULL
            );
            """
        )

    def _migrate_v2(self, con: sqlite3.Connection) -> None:
        columns = {
            str(row["name"])
            for row in con.execute("PRAGMA table_info(hermes_turns)").fetchall()
        }
        if "route_reason" not in columns:
            con.execute("ALTER TABLE hermes_turns ADD COLUMN route_reason TEXT")

    def initialize(self) -> None:
        if self._initialized:
            return
        with self._init_lock:
            if self._initialized:
                return
            with self._connection() as con:
                version = self._schema_version(con)
                if version > SCHEMA_VERSION:
                    raise StoreSchemaError(
                        f"metrics schema {version} is newer than supported {SCHEMA_VERSION}"
                    )
                if version < 1:
                    self._migrate_v1(con)
                    self._set_schema_version(con, 1)
                    version = 1
                if version < 2:
                    self._migrate_v2(con)
                    self._set_schema_version(con, 2)
            self._initialized = True

    def touch_turn(self, turn_key: str, mode: str, *, now: float | None = None) -> None:
        self.initialize()
        ts = float(now if now is not None else time.time())
        with self._connection() as con:
            con.execute(
                """
                INSERT OR IGNORE INTO hermes_turns(turn_key, started_at, mode)
                VALUES(?, ?, ?)
                """,
                (turn_key, ts, mode),
            )

    def record_decision(
        self,
        *,
        turn_key: str,
        mode: str,
        decision: Any,
        applied: bool,
        reason: str,
        now: float | None = None,
    ) -> None:
        self.initialize()
        ts = float(now if now is not None else time.time())
        with self._connection() as con:
            con.execute(
                """
                INSERT OR IGNORE INTO jev_decisions(
                    turn_key, created_at, mode, provider, requested_model, actual_model,
                    family, confidence, latency_ms, cost_usd, input_tokens, output_tokens,
                    accepted, applied, reason, error_category, error_status_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn_key,
                    ts,
                    mode,
                    getattr(decision, "provider", None),
                    getattr(decision, "requested_model", None),
                    getattr(decision, "actual_model", None),
                    getattr(decision, "family", None),
                    _number(getattr(decision, "confidence", None)),
                    _number(getattr(decision, "latency_ms", None)),
                    _number(getattr(decision, "cost_usd", None)),
                    _integer(getattr(decision, "input_tokens", None)),
                    _integer(getattr(decision, "output_tokens", None)),
                    1 if bool(getattr(decision, "accepted", False)) else 0,
                    1 if applied else 0,
                    str(reason or "unknown"),
                    getattr(decision, "error_category", None),
                    getattr(decision, "error_status_code", None),
                ),
            )
            con.execute(
                """
                UPDATE hermes_turns
                SET route_family = ?, route_applied = ?, route_reason = ?
                WHERE turn_key = ?
                """,
                (
                    getattr(decision, "family", None),
                    1 if applied else 0,
                    str(reason or "unknown"),
                    turn_key,
                ),
            )

    def record_turn_reason(self, turn_key: str, reason: str) -> None:
        self.initialize()
        with self._connection() as con:
            con.execute(
                "UPDATE hermes_turns SET route_reason = ? WHERE turn_key = ?",
                (str(reason or "unknown"), turn_key),
            )

    def increment_llm_request(self, turn_key: str) -> None:
        self.initialize()
        with self._connection() as con:
            con.execute(
                "UPDATE hermes_turns SET llm_requests = llm_requests + 1 WHERE turn_key = ?",
                (turn_key,),
            )

    def add_usage(self, turn_key: str, usage: dict[str, Any] | None) -> None:
        if not isinstance(usage, dict):
            return

        input_tokens = _integer(
            usage.get("input_tokens")
            if "input_tokens" in usage
            else usage.get("prompt_tokens")
        )
        output_tokens = _integer(
            usage.get("output_tokens")
            if "output_tokens" in usage
            else usage.get("completion_tokens")
        )

        cached_input = _integer(usage.get("cached_input_tokens"))
        if cached_input is None:
            details = usage.get("input_tokens_details")
            if isinstance(details, dict):
                cached_input = _integer(details.get("cached_tokens"))
        if cached_input is None:
            details = usage.get("prompt_tokens_details")
            if isinstance(details, dict):
                cached_input = _integer(details.get("cached_tokens"))

        reasoning = _integer(usage.get("reasoning_tokens"))
        if reasoning is None:
            details = usage.get("output_tokens_details")
            if isinstance(details, dict):
                reasoning = _integer(details.get("reasoning_tokens"))
        if reasoning is None:
            details = usage.get("completion_tokens_details")
            if isinstance(details, dict):
                reasoning = _integer(details.get("reasoning_tokens"))

        if all(value is None for value in (input_tokens, output_tokens, cached_input, reasoning)):
            return

        self.initialize()
        with self._connection() as con:
            con.execute(
                """
                UPDATE hermes_turns
                SET input_tokens = COALESCE(input_tokens, 0) + COALESCE(?, 0),
                    cached_input_tokens = COALESCE(cached_input_tokens, 0) + COALESCE(?, 0),
                    output_tokens = COALESCE(output_tokens, 0) + COALESCE(?, 0),
                    reasoning_tokens = COALESCE(reasoning_tokens, 0) + COALESCE(?, 0)
                WHERE turn_key = ?
                """,
                (input_tokens, cached_input, output_tokens, reasoning, turn_key),
            )

    def increment_tool_call(self, turn_key: str) -> None:
        self.initialize()
        with self._connection() as con:
            con.execute(
                "UPDATE hermes_turns SET tool_calls = tool_calls + 1 WHERE turn_key = ?",
                (turn_key,),
            )

    def finish_turn(
        self,
        turn_key: str,
        *,
        status: str,
        now: float | None = None,
    ) -> None:
        self.initialize()
        ts = float(now if now is not None else time.time())
        with self._connection() as con:
            row = con.execute(
                "SELECT started_at FROM hermes_turns WHERE turn_key = ?",
                (turn_key,),
            ).fetchone()
            if row is None:
                return
            duration_ms = max(0.0, (ts - float(row["started_at"])) * 1000.0)
            con.execute(
                """
                UPDATE hermes_turns
                SET completed_at = ?, duration_ms = ?, status = ?
                WHERE turn_key = ?
                """,
                (ts, duration_ms, status, turn_key),
            )

    def record_mode_change(
        self,
        old_mode: str,
        new_mode: str,
        *,
        source: str,
        now: float | None = None,
    ) -> None:
        self.initialize()
        ts = float(now if now is not None else time.time())
        with self._connection() as con:
            con.execute(
                """
                INSERT INTO mode_changes(created_at, old_mode, new_mode, source)
                VALUES(?, ?, ?, ?)
                """,
                (ts, old_mode, new_mode, source),
            )

    def cleanup(self, retention_days: int, *, now: float | None = None) -> None:
        self.initialize()
        days = max(1, int(retention_days))
        cutoff = float(now if now is not None else time.time()) - (days * 86400)
        with self._connection() as con:
            con.execute("DELETE FROM jev_decisions WHERE created_at < ?", (cutoff,))
            con.execute("DELETE FROM hermes_turns WHERE started_at < ?", (cutoff,))
            con.execute("DELETE FROM mode_changes WHERE created_at < ?", (cutoff,))

    def summary(self, *, since_hours: int = 24, now: float | None = None) -> StatsSummary:
        self.initialize()
        hours = max(1, min(int(since_hours), 24 * 3650))
        cutoff = float(now if now is not None else time.time()) - (hours * 3600)

        with self._connection() as con:
            decisions = con.execute(
                """
                SELECT
                    COUNT(*) AS count,
                    COALESCE(SUM(applied), 0) AS applied,
                    AVG(confidence) AS avg_confidence,
                    AVG(latency_ms) AS avg_latency,
                    SUM(cost_usd) AS total_cost
                FROM jev_decisions
                WHERE created_at >= ?
                """,
                (cutoff,),
            ).fetchone()

            turns = con.execute(
                """
                SELECT
                    COUNT(*) AS count,
                    AVG(duration_ms) AS avg_duration,
                    AVG(tool_calls) AS avg_tools,
                    AVG(llm_requests) AS avg_llm,
                    SUM(input_tokens) AS input_tokens,
                    SUM(output_tokens) AS output_tokens
                FROM hermes_turns
                WHERE started_at >= ?
                """,
                (cutoff,),
            ).fetchone()

            routes = con.execute(
                """
                SELECT COALESCE(family, 'fallback') AS family, COUNT(*) AS count
                FROM jev_decisions
                WHERE created_at >= ?
                GROUP BY COALESCE(family, 'fallback')
                ORDER BY count DESC, family ASC
                """,
                (cutoff,),
            ).fetchall()

        decision_count = int(decisions["count"] or 0)
        applied = int(decisions["applied"] or 0)
        return StatsSummary(
            since_hours=hours,
            decisions=decision_count,
            turns=int(turns["count"] or 0),
            applied=applied,
            fallback=max(0, decision_count - applied),
            avg_confidence=_number(decisions["avg_confidence"]),
            avg_jev_latency_ms=_number(decisions["avg_latency"]),
            total_jev_cost_usd=_number(decisions["total_cost"]),
            avg_turn_duration_ms=_number(turns["avg_duration"]),
            avg_tool_calls=_number(turns["avg_tools"]),
            avg_llm_requests=_number(turns["avg_llm"]),
            input_tokens=_integer(turns["input_tokens"]),
            output_tokens=_integer(turns["output_tokens"]),
            routes=tuple((str(row["family"]), int(row["count"])) for row in routes),
        )


class StoreProvider:
    """Resolve the current profile's store lazily and cache stores by path."""

    def __init__(self, path_resolver=default_db_path) -> None:
        self._path_resolver = path_resolver
        self._stores: dict[str, MetricsStore] = {}
        self._lock = threading.Lock()

    def get(self) -> MetricsStore:
        path = Path(self._path_resolver())
        key = str(path)
        with self._lock:
            store = self._stores.get(key)
            if store is None:
                store = MetricsStore(path)
                self._stores[key] = store
            return store
