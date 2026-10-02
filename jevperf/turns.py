"""Fresh-turn state extraction, redaction and bounded decision cache."""

from __future__ import annotations

from collections import OrderedDict
import hashlib
import re
import threading
from typing import Any, Callable


MAX_ROUTING_STATE_CHARS = 12000
MAX_CACHED_TURNS = 1024

_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|auth[_-]?token|password|secret)\b"
    r"(\s*[:=]\s*)([^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")
_COMMON_TOKEN = re.compile(r"\bsk-[A-Za-z0-9._-]{12,}\b")


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for item in content:
        if isinstance(item, str):
            parts.append(item)
            continue
        if not isinstance(item, dict):
            continue
        for key in ("text", "input_text", "content"):
            value = item.get(key)
            if isinstance(value, str) and value:
                parts.append(value)
                break
    return "\n".join(parts)


def _last_user_text(items: Any) -> str:
    if isinstance(items, str):
        return items
    if not isinstance(items, list):
        return ""

    for item in reversed(items):
        if not isinstance(item, dict) or item.get("role") != "user":
            continue
        text = _content_text(item.get("content"))
        if text.strip():
            return text
    return ""


def redact_routing_state(text: str) -> str:
    text = _BEARER.sub("Bearer <REDACTED>", text)
    text = _COMMON_TOKEN.sub("<REDACTED_TOKEN>", text)
    text = _SECRET_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}{match.group(2)}<REDACTED>",
        text,
    )
    return text


def extract_routing_state(request: Any) -> str | None:
    """Extract only the latest user content, never the whole conversation."""
    if not isinstance(request, dict):
        return None

    text = _last_user_text(request.get("messages"))
    if not text:
        text = _last_user_text(request.get("input"))
    if not text:
        return None

    text = redact_routing_state(text.strip())
    if len(text) > MAX_ROUTING_STATE_CHARS:
        text = text[:MAX_ROUTING_STATE_CHARS]
    return text or None


def turn_key(session_id: Any, turn_id: Any) -> str | None:
    """Return an opaque correlation key without persisting raw Hermes IDs."""
    turn = str(turn_id or "").strip()
    if not turn:
        return None
    session = str(session_id or "").strip()
    raw = f"{session}\0{turn}".encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()[:32]


class TurnDecisionCache:
    """Bounded process-local LRU cache storing decisions, never prompt text."""

    def __init__(self, max_entries: int = MAX_CACHED_TURNS) -> None:
        self.max_entries = max(1, int(max_entries))
        self._items: OrderedDict[str, Any] = OrderedDict()
        self._inflight: dict[str, threading.Lock] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any:
        with self._lock:
            value = self._items.get(key)
            if value is not None:
                self._items.move_to_end(key)
            return value

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            while len(self._items) > self.max_entries:
                self._items.popitem(last=False)

    def get_or_compute(self, key: str, factory: Callable[[], Any]) -> Any:
        """Return cached value or compute it once for this key under concurrency."""
        existing = self.get(key)
        if existing is not None:
            return existing

        with self._lock:
            key_lock = self._inflight.get(key)
            if key_lock is None:
                key_lock = threading.Lock()
                self._inflight[key] = key_lock

        try:
            with key_lock:
                existing = self.get(key)
                if existing is not None:
                    return existing
                value = factory()
                if value is not None:
                    self.put(key, value)
                return value
        finally:
            with self._lock:
                if self._inflight.get(key) is key_lock and not key_lock.locked():
                    self._inflight.pop(key, None)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
