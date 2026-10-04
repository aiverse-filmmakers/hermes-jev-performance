"""Fresh-turn state extraction, redaction and bounded decision cache."""

from __future__ import annotations

from collections import OrderedDict
import hashlib
import json
import re
import threading
from typing import Any, Callable


MAX_ROUTING_STATE_CHARS = 12000
MAX_CACHED_TURNS = 1024

_CREDENTIAL_LABEL = r"[\w-]*(?:api[_-]?key|access[_-]?key|private[_-]?key|token|password|passwd|pwd|secret|credential|authorization)[\w-]*"
_SECRET_ASSIGNMENT = re.compile(
    rf'''(?ix)(?<![\w-])(["']?{_CREDENTIAL_LABEL}["']?)(\s*[:=]\s*)'''
    r'''("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|[^\s,;\}\]"']+)'''
)
_SENSITIVE_MARKER = re.compile(rf"(?i)\b{_CREDENTIAL_LABEL}\b|-----BEGIN [\w ]*PRIVATE KEY-----")
_BEARER = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")
_COMMON_TOKEN = re.compile(
    r"\b(?:sk-[A-Za-z0-9._-]{12,}|gh[pousr]_[A-Za-z0-9]{16,}|"
    r"github_pat_[A-Za-z0-9_]{16,}|xox[baprs]-[A-Za-z0-9-]{10,}|AKIA[A-Z0-9]{16})\b"
)
_URL_CREDENTIALS = re.compile(r"(?i)(https?://)[^\s/@]+:[^\s/@]+@")
_FOLLOWUP = re.compile(r"(?i)^(?:(?:k|ok|okay|yes|sure|please)[,!. ]*)*(?:continue|proceed|finish|do it|do the same|go ahead|same|keep going)\b")
_CONTEXT_REFERENCE = re.compile(r"(?i)\b(?:last time|(?:discussed|agreed|mentioned) earlier|as before|previous (?:task|request|instructions))\b")


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
            return ""
        if item.get("type") not in {None, "text", "input_text"}:
            # A text caption alone cannot describe an attached image/file/audio.
            return ""
        for key in ("text", "input_text", "content"):
            value = item.get(key)
            if isinstance(value, str) and value:
                parts.append(value)
                break
        else:
            return ""
    return "\n".join(parts)


def _last_user_text(items: Any) -> str:
    if isinstance(items, str):
        return items
    if not isinstance(items, list):
        return ""

    for item in reversed(items):
        if not isinstance(item, dict) or item.get("role") != "user":
            continue
        # Stop at the latest user, including an empty or image-only message.
        return _content_text(item.get("content"))
    return ""


def redact_routing_state(text: str) -> str:
    # Whole JSON objects need structural handling (including nested/array values).
    try:
        value = json.loads(text)
        def clean(item: Any) -> Any:
            if isinstance(item, dict):
                return {k: "<REDACTED>" if re.fullmatch(_CREDENTIAL_LABEL, k, re.I) else clean(v)
                        for k, v in item.items()}
            if isinstance(item, list):
                return [clean(v) for v in item]
            return item
        if isinstance(value, (dict, list)):
            text = json.dumps(clean(value), ensure_ascii=False)
    except (ValueError, RecursionError):
        pass
    text = _URL_CREDENTIALS.sub(r"\1<REDACTED>@", text)
    text = _BEARER.sub("Bearer <REDACTED>", text)
    text = _COMMON_TOKEN.sub("<REDACTED_TOKEN>", text)
    text = _SECRET_ASSIGNMENT.sub(
        lambda match: match.group(0) if match.group(3).startswith(("{", "[")) else
        f"{match.group(1)}{match.group(2)}<REDACTED>",
        text,
    )
    return text


def safe_external_text(text: str) -> str | None:
    """Reject sensitive formats we cannot confidently redact; never a DLP guarantee."""
    for match in _SECRET_ASSIGNMENT.finditer(text):
        value, suffix = match.group(3), text[match.end():]
        # Shell concatenation does not end at a closing quote. A scalar regex
        # cannot safely parse expansions/adjacent quoted or unquoted fragments.
        if value.startswith(('"', "'")):
            if suffix and not re.match(r"[\s,;}\]]", suffix):
                return None
        elif not value.startswith(("{", "[")) and (
                suffix.startswith(('"', "'")) or re.match(r"[ \t]+[^\s,;}\]]", suffix)):
            # This applies to every credential label, including client_secret
            # and environment API keys. Require a quoted or explicit boundary.
            return None
    redacted = redact_routing_state(text)
    # Embedded structured assignments and malformed quotes cannot be safely
    # understood by the scalar regex. Do not transmit their remaining payload.
    for match in _SECRET_ASSIGNMENT.finditer(redacted):
        if match.group(3).startswith(("{", "[")):
            return None
    remainder = _SECRET_ASSIGNMENT.sub("", redacted)
    if _SENSITIVE_MARKER.search(remainder):
        return None
    return redacted


def extract_routing_state(request: Any) -> str | None:
    """Extract only the latest user content, never the whole conversation."""
    if not isinstance(request, dict):
        return None

    # The serving API's selected transcript is authoritative. Never fall back
    # to another field after finding an unusable latest message.
    items = request.get("messages") if "messages" in request else request.get("input")
    text = _last_user_text(items).strip()
    if not text or len(text) > MAX_ROUTING_STATE_CHARS:
        return None
    user_count = sum(isinstance(m, dict) and m.get("role") == "user" for m in items) if isinstance(items, list) else 1
    if _FOLLOWUP.search(text) or _CONTEXT_REFERENCE.search(text) or (user_count > 1 and len(text.split()) <= 6):
        # Do not transmit history to guess what a short continuation means.
        return None
    text = safe_external_text(text)
    return text if text and len(text) <= MAX_ROUTING_STATE_CHARS else None


def decision_key(key: str, state: str, config: Any) -> str:
    """Invalidate by semantic state and decision settings without retaining text."""
    values = [key, state, config.mode, config.provider, config.model,
              config.min_confidence, config.timeout_seconds]
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()


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
        self._revoked: set[str] = set()
        self._lock = threading.Lock()

    def get(self, key: str) -> Any:
        with self._lock:
            value = self._items.get(key)
            if value is not None:
                self._items.move_to_end(key)
            return value

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            if value == (None, None) and key in self._inflight:
                # Revocation must outlive LRU eviction until the worker returns.
                self._revoked.add(key)
            self._put_locked(key, value)

    def _put_locked(self, key: str, value: Any) -> None:
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
                with self._lock:
                    # A concurrent invalidation is authoritative over a slow
                    # classifier's response. Never revive the old restriction.
                    if key in self._revoked:
                        self._put_locked(key, (None, None))
                        return (None, None)
                    existing = self._items.get(key)
                    if existing is not None:
                        self._items.move_to_end(key)
                        return existing
                    if value is not None:
                        self._put_locked(key, value)
                    return value
        finally:
            with self._lock:
                if self._inflight.get(key) is key_lock and not key_lock.locked():
                    self._inflight.pop(key, None)
                    self._revoked.discard(key)

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)
