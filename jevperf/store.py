"""Local metadata-only SQLite store for Jev performance telemetry."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
import json
import os
import sqlite3
import threading
import time
from typing import Any


SCHEMA_VERSION = 3
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


def inspect_database(path: Path | str | None = None) -> dict[str, Any]:
    """Read-only SQLite health probe. Never creates or migrates the database."""
    target = Path(path) if path is not None else default_db_path()
    if not target.exists():
        return {"state": "missing", "schema_version": None, "quick_check": None}
    try:
        uri = target.resolve().as_uri() + "?mode=ro"
        con = sqlite3.connect(uri, uri=True, timeout=2.0)
        try:
            row = con.execute("PRAGMA quick_check").fetchone()
            quick = str(row[0]) if row else "unknown"
            schema_row = con.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()
            version = int(schema_row[0]) if schema_row else 0
        finally:
            con.close()
        return {
            "state": "ready" if quick.lower() == "ok" else "corrupt",
            "schema_version": version,
            "quick_check": quick,
        }
    except Exception:
        return {"state": "corrupt", "schema_version": None, "quick_check": None}


def repair_corrupt_database(
    path: Path | str | None = None,
    *,
    now: float | None = None,
) -> dict[str, Any]:
    """Explicitly quarantine an unreadable metrics DB and create a clean schema."""
    target = Path(path) if path is not None else default_db_path()
    health = inspect_database(target)
    if health["state"] == "ready":
        return {"repaired": False, "reason": "database_is_healthy", "backups": []}
    if health["state"] == "missing":
        MetricsStore(target).initialize()
        return {"repaired": True, "reason": "created_missing_database", "backups": []}

    stamp = time.strftime(
        "%Y%m%dT%H%M%SZ",
        time.gmtime(float(now if now is not None else time.time())),
    )
    backups: list[str] = []
    target.parent.mkdir(parents=True, exist_ok=True)
    for source in (
        target,
        Path(str(target) + "-wal"),
        Path(str(target) + "-shm"),
    ):
        if not source.exists():
            continue
        destination = source.with_name(source.name + f".corrupt-{stamp}")
        source.replace(destination)
        backups.append(str(destination))

    MetricsStore(target).initialize()
    repaired_health = inspect_database(target)
    return {
        "repaired": repaired_health["state"] == "ready",
        "reason": "quarantined_corrupt_database",
        "backups": backups,
    }


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

    def _migrate_v3(self, con: sqlite3.Connection) -> None:
        columns = {
            str(row["name"])
            for row in con.execute("PRAGMA table_info(hermes_turns)").fetchall()
        }
        additions = {
            "benchmark_run_id": "TEXT",
            "benchmark_sample_id": "TEXT",
            "benchmark_fixture_id": "TEXT",
            "benchmark_warmup": "INTEGER NOT NULL DEFAULT 0",
        }
        for name, sql_type in additions.items():
            if name not in columns:
                con.execute(
                    f"ALTER TABLE hermes_turns ADD COLUMN {name} {sql_type}"
                )

        con.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_hermes_turns_benchmark_run
            ON hermes_turns(benchmark_run_id);

            CREATE UNIQUE INDEX IF NOT EXISTS idx_hermes_turns_benchmark_sample
            ON hermes_turns(benchmark_sample_id)
            WHERE benchmark_sample_id IS NOT NULL;

            CREATE TABLE IF NOT EXISTS benchmark_runs (
                run_id TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                completed_at REAL,
                status TEXT NOT NULL,
                benchmark_version INTEGER NOT NULL,
                fixture_set_hash TEXT NOT NULL,
                fixture_count INTEGER NOT NULL,
                repeats INTEGER NOT NULL,
                warmups INTEGER NOT NULL,
                environment_json TEXT NOT NULL,
                methodology_json TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_benchmark_runs_created
            ON benchmark_runs(created_at DESC);

            CREATE TABLE IF NOT EXISTS benchmark_samples (
                sample_id TEXT PRIMARY KEY,
                run_id TEXT NOT NULL,
                fixture_id TEXT NOT NULL,
                family TEXT NOT NULL,
                mode TEXT NOT NULL,
                repeat_index INTEGER NOT NULL,
                order_index INTEGER NOT NULL,
                is_warmup INTEGER NOT NULL DEFAULT 0,
                started_at REAL NOT NULL,
                completed_at REAL,
                status TEXT NOT NULL,
                runner_duration_ms REAL,
                exit_code INTEGER,
                validation_passed INTEGER,
                hermes_duration_ms REAL,
                llm_requests INTEGER,
                tool_calls INTEGER,
                input_tokens INTEGER,
                cached_input_tokens INTEGER,
                output_tokens INTEGER,
                reasoning_tokens INTEGER,
                route_family TEXT,
                route_applied INTEGER,
                jev_latency_ms REAL,
                jev_cost_usd REAL,
                jev_confidence REAL,
                error_category TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_benchmark_samples_run
            ON benchmark_samples(run_id, order_index);

            CREATE INDEX IF NOT EXISTS idx_benchmark_samples_pair
            ON benchmark_samples(run_id, fixture_id, repeat_index, mode);
            """
        )

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
                    version = 2
                if version < 3:
                    self._migrate_v3(con)
                    self._set_schema_version(con, 3)
            self._initialized = True

    def touch_turn(
        self,
        turn_key: str,
        mode: str,
        *,
        benchmark: Any = None,
        now: float | None = None,
    ) -> None:
        self.initialize()
        ts = float(now if now is not None else time.time())
        run_id = getattr(benchmark, "run_id", None)
        sample_id = getattr(benchmark, "sample_id", None)
        fixture_id = getattr(benchmark, "fixture_id", None)
        is_warmup = 1 if bool(getattr(benchmark, "is_warmup", False)) else 0
        with self._connection() as con:
            con.execute(
                """
                INSERT OR IGNORE INTO hermes_turns(
                    turn_key, started_at, mode,
                    benchmark_run_id, benchmark_sample_id,
                    benchmark_fixture_id, benchmark_warmup
                )
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    turn_key, ts, mode,
                    run_id, sample_id, fixture_id, is_warmup,
                ),
            )
            if sample_id:
                con.execute(
                    """
                    UPDATE hermes_turns
                    SET benchmark_run_id = COALESCE(benchmark_run_id, ?),
                        benchmark_sample_id = COALESCE(benchmark_sample_id, ?),
                        benchmark_fixture_id = COALESCE(benchmark_fixture_id, ?),
                        benchmark_warmup = ?
                    WHERE turn_key = ?
                    """,
                    (run_id, sample_id, fixture_id, is_warmup, turn_key),
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
            con.execute("DELETE FROM benchmark_samples WHERE started_at < ?", (cutoff,))
            con.execute("DELETE FROM benchmark_runs WHERE created_at < ?", (cutoff,))
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
                FROM jev_decisions AS jd
                LEFT JOIN hermes_turns AS ht ON ht.turn_key = jd.turn_key
                WHERE jd.created_at >= ?
                  AND ht.benchmark_run_id IS NULL
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
                  AND benchmark_run_id IS NULL
                """,
                (cutoff,),
            ).fetchone()

            routes = con.execute(
                """
                SELECT COALESCE(jd.family, 'fallback') AS family, COUNT(*) AS count
                FROM jev_decisions AS jd
                LEFT JOIN hermes_turns AS ht ON ht.turn_key = jd.turn_key
                WHERE jd.created_at >= ?
                  AND ht.benchmark_run_id IS NULL
                GROUP BY COALESCE(jd.family, 'fallback')
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


    def recent_decisions(
        self,
        *,
        since_hours: int = 24,
        limit: int = 30,
        now: float | None = None,
    ) -> list[dict[str, Any]]:
        self.initialize()
        hours = max(1, min(int(since_hours), 24 * 3650))
        row_limit = max(1, min(int(limit), 200))
        cutoff = float(now if now is not None else time.time()) - (hours * 3600)
        with self._connection() as con:
            rows = con.execute(
                """
                SELECT
                    jd.created_at AS created_at,
                    jd.mode AS mode,
                    jd.provider AS provider,
                    jd.requested_model AS requested_model,
                    jd.actual_model AS actual_model,
                    jd.family AS family,
                    jd.confidence AS confidence,
                    jd.latency_ms AS latency_ms,
                    jd.cost_usd AS cost_usd,
                    jd.input_tokens AS input_tokens,
                    jd.output_tokens AS output_tokens,
                    jd.accepted AS accepted,
                    jd.applied AS applied,
                    jd.reason AS reason,
                    jd.error_category AS error_category,
                    jd.error_status_code AS error_status_code
                FROM jev_decisions AS jd
                LEFT JOIN hermes_turns AS ht ON ht.turn_key = jd.turn_key
                WHERE jd.created_at >= ?
                  AND ht.benchmark_run_id IS NULL
                ORDER BY jd.created_at DESC
                LIMIT ?
                """,
                (cutoff, row_limit),
            ).fetchall()
        return [
            {
                "created_at": float(row["created_at"]),
                "mode": str(row["mode"]),
                "provider": row["provider"],
                "requested_model": row["requested_model"],
                "actual_model": row["actual_model"],
                "family": row["family"],
                "confidence": _number(row["confidence"]),
                "latency_ms": _number(row["latency_ms"]),
                "cost_usd": _number(row["cost_usd"]),
                "input_tokens": _integer(row["input_tokens"]),
                "output_tokens": _integer(row["output_tokens"]),
                "accepted": bool(row["accepted"]),
                "applied": bool(row["applied"]),
                "reason": str(row["reason"] or "unknown"),
                "error_category": row["error_category"],
                "error_status_code": row["error_status_code"],
            }
            for row in rows
        ]

    def reason_breakdown(
        self,
        *,
        since_hours: int = 24,
        now: float | None = None,
    ) -> list[dict[str, Any]]:
        self.initialize()
        hours = max(1, min(int(since_hours), 24 * 3650))
        cutoff = float(now if now is not None else time.time()) - (hours * 3600)
        with self._connection() as con:
            rows = con.execute(
                """
                SELECT COALESCE(route_reason, 'unknown') AS reason, COUNT(*) AS count
                FROM hermes_turns
                WHERE started_at >= ?
                  AND benchmark_run_id IS NULL
                GROUP BY COALESCE(route_reason, 'unknown')
                ORDER BY count DESC, reason ASC
                """,
                (cutoff,),
            ).fetchall()
        return [
            {"reason": str(row["reason"]), "count": int(row["count"])}
            for row in rows
        ]

    def mode_comparison(
        self,
        *,
        since_hours: int = 24,
        now: float | None = None,
    ) -> list[dict[str, Any]]:
        self.initialize()
        hours = max(1, min(int(since_hours), 24 * 3650))
        cutoff = float(now if now is not None else time.time()) - (hours * 3600)

        with self._connection() as con:
            turn_rows = con.execute(
                """
                SELECT
                    mode,
                    COUNT(*) AS turns,
                    SUM(CASE WHEN status = 'complete' THEN 1 ELSE 0 END) AS completed,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS errors,
                    AVG(duration_ms) AS avg_duration_ms,
                    AVG(tool_calls) AS avg_tool_calls,
                    AVG(llm_requests) AS avg_llm_requests,
                    AVG(input_tokens) AS avg_input_tokens,
                    AVG(cached_input_tokens) AS avg_cached_input_tokens,
                    AVG(output_tokens) AS avg_output_tokens,
                    AVG(reasoning_tokens) AS avg_reasoning_tokens
                FROM hermes_turns
                WHERE started_at >= ?
                  AND benchmark_run_id IS NULL
                GROUP BY mode
                """,
                (cutoff,),
            ).fetchall()
            decision_rows = con.execute(
                """
                SELECT
                    jd.mode AS mode,
                    COUNT(*) AS decisions,
                    COALESCE(SUM(applied), 0) AS applied,
                    AVG(latency_ms) AS avg_jev_latency_ms,
                    AVG(confidence) AS avg_jev_confidence,
                    SUM(cost_usd) AS total_jev_cost_usd
                FROM jev_decisions AS jd
                LEFT JOIN hermes_turns AS ht ON ht.turn_key = jd.turn_key
                WHERE jd.created_at >= ?
                  AND ht.benchmark_run_id IS NULL
                GROUP BY jd.mode
                """,
                (cutoff,),
            ).fetchall()

        turns_by_mode = {str(row["mode"]): row for row in turn_rows}
        decisions_by_mode = {str(row["mode"]): row for row in decision_rows}
        result: list[dict[str, Any]] = []

        for mode in ("off", "shadow", "on"):
            turns = turns_by_mode.get(mode)
            decisions = decisions_by_mode.get(mode)
            result.append(
                {
                    "mode": mode,
                    "turns": int(turns["turns"] or 0) if turns is not None else 0,
                    "completed": int(turns["completed"] or 0) if turns is not None else 0,
                    "errors": int(turns["errors"] or 0) if turns is not None else 0,
                    "avg_duration_ms": _number(turns["avg_duration_ms"]) if turns is not None else None,
                    "avg_tool_calls": _number(turns["avg_tool_calls"]) if turns is not None else None,
                    "avg_llm_requests": _number(turns["avg_llm_requests"]) if turns is not None else None,
                    "avg_input_tokens": _number(turns["avg_input_tokens"]) if turns is not None else None,
                    "avg_cached_input_tokens": _number(turns["avg_cached_input_tokens"]) if turns is not None else None,
                    "avg_output_tokens": _number(turns["avg_output_tokens"]) if turns is not None else None,
                    "avg_reasoning_tokens": _number(turns["avg_reasoning_tokens"]) if turns is not None else None,
                    "decisions": int(decisions["decisions"] or 0) if decisions is not None else 0,
                    "applied": int(decisions["applied"] or 0) if decisions is not None else 0,
                    "avg_jev_latency_ms": _number(decisions["avg_jev_latency_ms"]) if decisions is not None else None,
                    "avg_jev_confidence": _number(decisions["avg_jev_confidence"]) if decisions is not None else None,
                    "total_jev_cost_usd": _number(decisions["total_jev_cost_usd"]) if decisions is not None else None,
                }
            )
        return result

    def time_series(
        self,
        *,
        since_hours: int = 24,
        points: int = 36,
        now: float | None = None,
    ) -> list[dict[str, Any]]:
        self.initialize()
        hours = max(1, min(int(since_hours), 24 * 3650))
        point_count = max(6, min(int(points), 120))
        end = float(now if now is not None else time.time())
        cutoff = end - (hours * 3600)
        bucket_seconds = max(60, int((hours * 3600 + point_count - 1) // point_count))

        with self._connection() as con:
            rows = con.execute(
                """
                SELECT
                    CAST((started_at - ?) / ? AS INTEGER) AS bucket,
                    COUNT(*) AS turns,
                    AVG(duration_ms) AS avg_duration_ms,
                    AVG(tool_calls) AS avg_tool_calls,
                    AVG(llm_requests) AS avg_llm_requests,
                    SUM(input_tokens) AS input_tokens,
                    SUM(cached_input_tokens) AS cached_input_tokens,
                    SUM(output_tokens) AS output_tokens,
                    SUM(reasoning_tokens) AS reasoning_tokens
                FROM hermes_turns
                WHERE started_at >= ? AND started_at <= ?
                  AND benchmark_run_id IS NULL
                GROUP BY bucket
                ORDER BY bucket ASC
                """,
                (cutoff, bucket_seconds, cutoff, end),
            ).fetchall()

        return [
            {
                "started_at": cutoff + (int(row["bucket"]) * bucket_seconds),
                "bucket_seconds": bucket_seconds,
                "turns": int(row["turns"] or 0),
                "avg_duration_ms": _number(row["avg_duration_ms"]),
                "avg_tool_calls": _number(row["avg_tool_calls"]),
                "avg_llm_requests": _number(row["avg_llm_requests"]),
                "input_tokens": _integer(row["input_tokens"]),
                "cached_input_tokens": _integer(row["cached_input_tokens"]),
                "output_tokens": _integer(row["output_tokens"]),
                "reasoning_tokens": _integer(row["reasoning_tokens"]),
            }
            for row in rows
        ]


    def start_benchmark_run(
        self,
        *,
        run_id: str,
        benchmark_version: int,
        fixture_set_hash: str,
        fixture_count: int,
        repeats: int,
        warmups: int,
        environment: dict[str, Any],
        methodology: dict[str, Any],
        now: float | None = None,
    ) -> None:
        self.initialize()
        ts = float(now if now is not None else time.time())
        with self._connection() as con:
            con.execute(
                """
                INSERT INTO benchmark_runs(
                    run_id, created_at, status, benchmark_version,
                    fixture_set_hash, fixture_count, repeats, warmups,
                    environment_json, methodology_json
                ) VALUES(?, ?, 'running', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    ts,
                    int(benchmark_version),
                    str(fixture_set_hash),
                    int(fixture_count),
                    int(repeats),
                    int(warmups),
                    json.dumps(environment, sort_keys=True, separators=(",", ":")),
                    json.dumps(methodology, sort_keys=True, separators=(",", ":")),
                ),
            )

    def finish_benchmark_run(
        self,
        run_id: str,
        *,
        status: str,
        now: float | None = None,
    ) -> None:
        self.initialize()
        ts = float(now if now is not None else time.time())
        with self._connection() as con:
            con.execute(
                """
                UPDATE benchmark_runs
                SET completed_at = ?, status = ?
                WHERE run_id = ?
                """,
                (ts, str(status or "unknown"), run_id),
            )

    def plan_benchmark_sample(
        self,
        *,
        sample_id: str,
        run_id: str,
        fixture_id: str,
        family: str,
        mode: str,
        repeat_index: int,
        order_index: int,
        is_warmup: bool,
        now: float | None = None,
    ) -> None:
        self.initialize()
        ts = float(now if now is not None else time.time())
        with self._connection() as con:
            con.execute(
                """
                INSERT INTO benchmark_samples(
                    sample_id, run_id, fixture_id, family, mode,
                    repeat_index, order_index, is_warmup,
                    started_at, status
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 'running')
                """,
                (
                    sample_id,
                    run_id,
                    fixture_id,
                    family,
                    mode,
                    int(repeat_index),
                    int(order_index),
                    1 if is_warmup else 0,
                    ts,
                ),
            )

    def finalize_benchmark_sample(
        self,
        sample_id: str,
        *,
        runner_duration_ms: float | None,
        exit_code: int | None,
        validation_passed: bool | None,
        error_category: str | None = None,
        now: float | None = None,
    ) -> dict[str, Any]:
        self.initialize()
        ts = float(now if now is not None else time.time())
        with self._connection() as con:
            turn = con.execute(
                """
                SELECT *
                FROM hermes_turns
                WHERE benchmark_sample_id = ?
                ORDER BY started_at DESC
                LIMIT 1
                """,
                (sample_id,),
            ).fetchone()
            decision = None
            if turn is not None:
                decision = con.execute(
                    """
                    SELECT *
                    FROM jev_decisions
                    WHERE turn_key = ?
                    LIMIT 1
                    """,
                    (turn["turn_key"],),
                ).fetchone()

            telemetry_complete = bool(
                turn is not None and str(turn["status"]) == "complete"
            )
            process_ok = exit_code == 0
            validation_ok = validation_passed is not False

            if process_ok and telemetry_complete and validation_ok:
                status = "complete"
            elif turn is None:
                status = "missing_telemetry"
            elif not process_ok:
                status = "process_error"
            elif not validation_ok:
                status = "validation_failed"
            else:
                status = "incomplete"

            safe_error = error_category
            if safe_error is None and status != "complete":
                safe_error = status

            con.execute(
                """
                UPDATE benchmark_samples
                SET completed_at = ?,
                    status = ?,
                    runner_duration_ms = ?,
                    exit_code = ?,
                    validation_passed = ?,
                    hermes_duration_ms = ?,
                    llm_requests = ?,
                    tool_calls = ?,
                    input_tokens = ?,
                    cached_input_tokens = ?,
                    output_tokens = ?,
                    reasoning_tokens = ?,
                    route_family = ?,
                    route_applied = ?,
                    jev_latency_ms = ?,
                    jev_cost_usd = ?,
                    jev_confidence = ?,
                    error_category = ?
                WHERE sample_id = ?
                """,
                (
                    ts,
                    status,
                    _number(runner_duration_ms),
                    exit_code,
                    None if validation_passed is None else (1 if validation_passed else 0),
                    _number(turn["duration_ms"]) if turn is not None else None,
                    _integer(turn["llm_requests"]) if turn is not None else None,
                    _integer(turn["tool_calls"]) if turn is not None else None,
                    _integer(turn["input_tokens"]) if turn is not None else None,
                    _integer(turn["cached_input_tokens"]) if turn is not None else None,
                    _integer(turn["output_tokens"]) if turn is not None else None,
                    _integer(turn["reasoning_tokens"]) if turn is not None else None,
                    turn["route_family"] if turn is not None else None,
                    int(turn["route_applied"] or 0) if turn is not None else None,
                    _number(decision["latency_ms"]) if decision is not None else None,
                    _number(decision["cost_usd"]) if decision is not None else None,
                    _number(decision["confidence"]) if decision is not None else None,
                    safe_error,
                    sample_id,
                ),
            )
            row = con.execute(
                "SELECT * FROM benchmark_samples WHERE sample_id = ?",
                (sample_id,),
            ).fetchone()
        return self._benchmark_sample_payload(row)

    @staticmethod
    def _benchmark_sample_payload(row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            return {}
        return {
            "sample_id": str(row["sample_id"]),
            "fixture_id": str(row["fixture_id"]),
            "family": str(row["family"]),
            "mode": str(row["mode"]),
            "repeat_index": int(row["repeat_index"]),
            "order_index": int(row["order_index"]),
            "is_warmup": bool(row["is_warmup"]),
            "started_at": float(row["started_at"]),
            "completed_at": _number(row["completed_at"]),
            "status": str(row["status"]),
            "runner_duration_ms": _number(row["runner_duration_ms"]),
            "exit_code": row["exit_code"],
            "validation_passed": (
                None if row["validation_passed"] is None
                else bool(row["validation_passed"])
            ),
            "hermes_duration_ms": _number(row["hermes_duration_ms"]),
            "llm_requests": _integer(row["llm_requests"]),
            "tool_calls": _integer(row["tool_calls"]),
            "input_tokens": _integer(row["input_tokens"]),
            "cached_input_tokens": _integer(row["cached_input_tokens"]),
            "output_tokens": _integer(row["output_tokens"]),
            "reasoning_tokens": _integer(row["reasoning_tokens"]),
            "route_family": row["route_family"],
            "route_applied": (
                None if row["route_applied"] is None else bool(row["route_applied"])
            ),
            "jev_latency_ms": _number(row["jev_latency_ms"]),
            "jev_cost_usd": _number(row["jev_cost_usd"]),
            "jev_confidence": _number(row["jev_confidence"]),
            "error_category": row["error_category"],
        }

    def benchmark_samples(
        self,
        run_id: str,
        *,
        include_warmups: bool = True,
    ) -> list[dict[str, Any]]:
        self.initialize()
        query = """
            SELECT *
            FROM benchmark_samples
            WHERE run_id = ?
        """
        params: list[Any] = [run_id]
        if not include_warmups:
            query += " AND is_warmup = 0"
        query += " ORDER BY order_index ASC"
        with self._connection() as con:
            rows = con.execute(query, params).fetchall()
        return [self._benchmark_sample_payload(row) for row in rows]

    def benchmark_run_record(self, run_id: str) -> dict[str, Any] | None:
        self.initialize()
        with self._connection() as con:
            row = con.execute(
                "SELECT * FROM benchmark_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            environment = json.loads(str(row["environment_json"]))
        except Exception:
            environment = {}
        try:
            methodology = json.loads(str(row["methodology_json"]))
        except Exception:
            methodology = {}
        return {
            "run_id": str(row["run_id"]),
            "created_at": float(row["created_at"]),
            "completed_at": _number(row["completed_at"]),
            "status": str(row["status"]),
            "benchmark_version": int(row["benchmark_version"]),
            "fixture_set_hash": str(row["fixture_set_hash"]),
            "fixture_count": int(row["fixture_count"]),
            "repeats": int(row["repeats"]),
            "warmups": int(row["warmups"]),
            "environment": environment if isinstance(environment, dict) else {},
            "methodology": methodology if isinstance(methodology, dict) else {},
        }

    def list_benchmark_runs(self, *, limit: int = 10) -> list[dict[str, Any]]:
        self.initialize()
        row_limit = max(1, min(int(limit), 100))
        with self._connection() as con:
            rows = con.execute(
                """
                SELECT run_id
                FROM benchmark_runs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (row_limit,),
            ).fetchall()
        result = []
        for row in rows:
            record = self.benchmark_run_record(str(row["run_id"]))
            if record is not None:
                result.append(record)
        return result


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
