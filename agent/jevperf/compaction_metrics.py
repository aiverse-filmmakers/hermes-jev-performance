"""Separate metadata-only compaction metrics; drawer content never enters SQLite."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import sqlite3
import time

from .store import default_db_path


OUTCOMES = frozenset({"off", "no_candidates", "missing_credential", "archive_unavailable",
                      "keep_all", "insufficient_reduction", "still_over_budget", "shadow",
                      "applied", "deadline", "fallback_error", "recovered", "recovery_error",
                      "external_not_approved", "stale_attempt", "assessment_budget"})
NUMERIC_FIELDS = ("candidates", "selected", "requests", "estimated_tokens_before",
                  "estimated_tokens_after", "latency_ms", "cost_usd", "input_tokens", "output_tokens",
                  "known_cost_usd", "known_input_tokens", "known_output_tokens")


def metrics_path() -> Path:
    return default_db_path().with_name("compaction.sqlite3")


def record_compaction(metadata: dict, path: Path | None = None) -> None:
    target = path or metrics_path()
    clean = {"outcome": metadata.get("outcome") if metadata.get("outcome") in OUTCOMES else "fallback_error"}
    for field in NUMERIC_FIELDS:
        value = metadata.get(field)
        clean[field] = value if type(value) in (int, float) and math.isfinite(value) and value >= 0 else None
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if target.is_symlink():
        raise ValueError("unsafe_metrics_path")
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    os.close(fd)
    with sqlite3.connect(target, timeout=2) as db:
        db.execute("CREATE TABLE IF NOT EXISTS attempts (created REAL NOT NULL, metadata TEXT NOT NULL)")
        db.execute("INSERT INTO attempts VALUES (?, ?)", (time.time(), json.dumps(clean)))
        db.execute("DELETE FROM attempts WHERE created < ?", (time.time() - 30 * 86400,))


def compaction_summary(path: Path | None = None, hours: int = 24) -> dict:
    target = path or metrics_path()
    out = {"attempts": 0, "applied": 0, "shadow": 0, "fallback": 0, "retrievals": 0, "retrieval_failures": 0,
           "estimated_tokens_saved": 0, "cost_usd": None, "known_cost_usd": 0, "avg_latency_ms": None}
    if not target.exists():
        return out
    if target.is_symlink():
        raise ValueError("unsafe_metrics_path")
    with sqlite3.connect(target.absolute().as_uri() + "?mode=ro", uri=True, timeout=2) as db:
        rows = [json.loads(row[0]) for row in db.execute(
            "SELECT metadata FROM attempts WHERE created >= ?", (time.time() - max(1, min(hours, 87600)) * 3600,))]
    out["retrievals"] = sum(r["outcome"] == "recovered" for r in rows)
    out["retrieval_failures"] = sum(r["outcome"] == "recovery_error" for r in rows)
    rows = [r for r in rows if r["outcome"] not in {"recovered", "recovery_error"}]
    out["attempts"] = len(rows)
    out["applied"] = sum(r["outcome"] == "applied" for r in rows)
    out["shadow"] = sum(r["outcome"] == "shadow" for r in rows)
    out["fallback"] = len(rows) - out["applied"] - out["shadow"]
    out["estimated_tokens_saved"] = sum(max(0, (r.get("estimated_tokens_before") or 0) -
                                              (r.get("estimated_tokens_after") or 0)) for r in rows if r["outcome"] == "applied")
    costs = [r["cost_usd"] for r in rows if r.get("requests", 0)]
    out["known_cost_usd"] = sum(r.get("known_cost_usd") or 0 for r in rows)
    if costs and all(value is not None for value in costs):
        out["cost_usd"] = sum(costs)
    latencies = [r["latency_ms"] for r in rows if r.get("latency_ms") is not None]
    if latencies:
        out["avg_latency_ms"] = sum(latencies) / len(latencies)
    return out
