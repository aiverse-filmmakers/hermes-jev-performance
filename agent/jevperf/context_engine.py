"""Native Hermes ContextEngine adapter; imports Hermes only when requested."""
from __future__ import annotations

import inspect
import json
from typing import Any

from .compaction import JevCompactor, estimated_tokens
from .compaction_archive import OutputArchive, REFERENCE_RE
from .compaction_config import read_compaction_config
from .compaction_metrics import record_compaction
from .config import read_config


ENGINE_NAME = "hermes-jev-performance"
RECOVERY_TOOL = {
    "name": "jev_recover",
    "description": "Recover exact archived Jev tool output using a reference owned by this session. "
                   "Read pages using next_offset; do not rerun the original tool.",
    "parameters": {
        "type": "object", "properties": {
            "reference": {"type": "string", "description": "Opaque reference from an archived-output label."},
            "offset": {"type": "integer", "minimum": 0, "default": 0},
            "limit": {"type": "integer", "minimum": 1, "maximum": 20000, "default": 20000},
        }, "required": ["reference"], "additionalProperties": False,
    },
}


class RuntimeSettings:
    """Resolve current profile settings, including when loaded by engine discovery."""
    def get_config(self, key: str, default: Any = None) -> Any:
        from .dashboard_service import _settings_values
        return _settings_values().get(key, default)


def create_context_engine(ctx: Any = None, *, compactor: Any = None, archive: Any = None,
                          metrics_recorder: Any = record_compaction):
    from agent.context_compressor import ContextCompressor

    class HermesJevContextEngine(ContextCompressor):
        def __init__(self):
            # Preserve the operator's built-in compression policy for fallback.
            params: dict[str, Any] = {"model": "", "quiet_mode": True}
            try:
                from hermes_cli.config import load_config_readonly
                host = load_config_readonly()
                compression = host.get("compression", {})
                supported = inspect.signature(ContextCompressor.__init__).parameters
                aliases = {"threshold": "threshold_percent", "target_ratio": "summary_target_ratio"}
                for key, value in compression.items():
                    target = aliases.get(key, key)
                    if target in supported and target not in {"model", "api_key", "base_url", "provider", "api_mode"}:
                        params[target] = value
                output_limit = host.get("agent", {}).get("max_tokens")
                if type(output_limit) is int and output_limit > 0 and "max_tokens" in supported:
                    params["max_tokens"] = output_limit
            except Exception:
                pass
            super().__init__(**params)
            self.jev_settings = ctx if ctx is not None else RuntimeSettings()
            self.jev_compactor = compactor or JevCompactor()
            self.jev_archive = archive
            self.jev_last_result = None

        @property
        def name(self):
            return ENGINE_NAME

        def clone_for_agent(self):
            # No deep-copying PluginContext locks, provider clients or session state.
            return HermesJevContextEngine()

        def get_tool_schemas(self):
            return [*super().get_tool_schemas(), RECOVERY_TOOL]

        def _recovery_sessions(self):
            # Bind authorization to host state, never model arguments or text.
            session = getattr(self, "_session_id", "")
            sessions = []
            db = getattr(self, "_session_db", None)
            while session and session not in sessions:
                sessions.append(session)
                if db is None:
                    break
                try:
                    child = db.get_session(session) or {}
                    parent_id = child.get("parent_session_id")
                    if not parent_id:
                        break
                    parent = db.get_session(parent_id) or {}
                    model_config = child.get("model_config") or {}
                    if isinstance(model_config, str):
                        model_config = json.loads(model_config)
                    # Exclude branch/delegate edges even if an old host resolver
                    # treats a parent ended on compression as sufficient.
                    if (parent.get("end_reason") != "compression" or
                            child.get("source") != parent.get("source") or
                            any(model_config.get(k) for k in ("_delegate_from", "_branched_from")) or
                            db.get_compression_tip(parent_id) != sessions[0]):
                        break
                except Exception:
                    # An unreadable lineage fails closed for ancestors, without
                    # blocking the normal compressor or current-session recovery.
                    break
                session = parent_id
            return sessions

        def _owned_reference(self, reference):
            return any(OutputArchive.owns(reference, session) for session in self._recovery_sessions())

        def _attempt_cancelled(self):
            # Preserve the host's cooperative fence and generation ownership.
            try:
                from agent.conversation_compression import _caller_attempt_is_current
                if not _caller_attempt_is_current(self):
                    return True
            except ImportError:
                pass
            check = getattr(self, "_compression_cancelled_check", None)
            try:
                return bool(check()) if callable(check) else False
            except Exception:
                return True

        def handle_tool_call(self, name, args, **kwargs):
            if name != "jev_recover":
                return super().handle_tool_call(name, args, **kwargs)
            try:
                reference = args.get("reference")
                if not isinstance(reference, str) or REFERENCE_RE.fullmatch(reference) is None:
                    raise ValueError("invalid_reference")
                # A durable private archive index plus its session namespace is
                # authoritative even after normal summarization removes a label.
                if not self._owned_reference(reference):
                    return json.dumps({"error": "Reference does not belong to this session."})
                drawer = self.jev_archive or OutputArchive()
                payload = drawer.recover(reference, offset=args.get("offset", 0), limit=args.get("limit", 20000))
                self._recovery_metric("recovered")
                return json.dumps(payload, ensure_ascii=False)
            except Exception:
                self._recovery_metric("recovery_error")
                return json.dumps({"error": "Archived output unavailable or invalid range. Keep the reference; do not rerun an irreversible tool."})

        def _recovery_metric(self, outcome):
            try:
                if read_config(self.jev_settings).telemetry_enabled:
                    metrics_recorder({"outcome": outcome})
            except Exception:
                pass

        def compress(self, messages, current_tokens=None, focus_topic=None, force=False,
                     memory_context="", **kwargs):
            settings = read_compaction_config(self.jev_settings)
            routing = read_config(self.jev_settings)
            if self._attempt_cancelled():
                return messages
            # Global OFF and controlled OFF benchmarks make zero Jev calls.
            if routing.mode == "off" or routing.provider != "openrouter" or settings.mode == "off":
                return self._normal_compress(messages, current_tokens, focus_topic, force, memory_context, kwargs)
            try:
                estimate = estimated_tokens(messages)
                # current_tokens may include schemas/system overhead that is not compactable.
                overhead = max(0, (current_tokens or 0) - estimate)
                target = max(1, int(self.threshold_tokens * 0.9) - overhead)
                drawer = self.jev_archive or OutputArchive()
                result = self.jev_compactor.compact(
                    messages, config=settings, model=routing.model, timeout=routing.timeout_seconds,
                    archive=drawer, session_id=getattr(self, "_session_id", ""),
                    focus=focus_topic or "", target_tokens=target,
                    memory_context=memory_context, should_abort=self._attempt_cancelled,
                )
                if self._attempt_cancelled() or result.outcome == "stale_attempt":
                    # Billing belongs to the attempted provider call even when
                    # the host no longer owns the transcript generation.
                    if routing.telemetry_enabled and result.requests:
                        metadata = {**result.metadata(), "outcome": "stale_attempt",
                                    "estimated_tokens_after": result.estimated_tokens_before}
                        try:
                            metrics_recorder(metadata)
                        except Exception:
                            pass
                    if result.archive_references:
                        try:
                            drawer.discard_unpublished(result.archive_references)
                            result.archive_references.clear()
                        except (OSError, ValueError):
                            pass  # Host remains unchanged even if disk cleanup fails.
                    return messages
                self.jev_last_result = result.metadata()
                if routing.telemetry_enabled:
                    try:
                        metrics_recorder(self.jev_last_result)
                    except Exception:
                        pass
                if result.outcome == "applied":
                    # Host compression commit owns DB persistence and session rotation.
                    # Every returned row must be a copy without stale persistence marks.
                    out = [{k: v for k, v in m.items() if k not in {"_db_persisted", "_row_id"}}
                           for m in result.messages]
                    # Hermes' marker means a CONTIGUOUS carried tail. Tag only
                    # the unchanged suffix; tagging interior rows miscounts originals.
                    last_changed = max(i for i, (old, new) in enumerate(zip(messages, result.messages)) if old is not new)
                    for row in out[last_changed + 1:]:
                        row["_compaction_tail"] = True
                    self.compression_count += 1
                    self._last_compression_made_progress = True
                    self._last_compress_aborted = False
                    self._last_summary_error = None
                    self._last_summary_fallback_used = False
                    self._last_feasibility_skip = False
                    self._last_compression_savings_pct = 100 * (estimate - result.estimated_tokens_after) / max(1, estimate)
                    self.last_prompt_tokens = -1
                    return out
            except Exception:
                self.jev_last_result = {"outcome": "fallback_error"}
            return self._normal_compress(messages, current_tokens, focus_topic, force, memory_context, kwargs)

        def _normal_compress(self, messages, current_tokens, focus_topic, force, memory_context, kwargs):
            # Signature-filter once for older supported Hermes versions; never retry a paid call.
            options = {"current_tokens": current_tokens, "focus_topic": focus_topic,
                       "force": force, "memory_context": memory_context, **kwargs}
            allowed = inspect.signature(super().compress).parameters
            references = sorted({ref for m in messages if isinstance(m, dict) and isinstance(m.get("content"), str)
                                 for ref in REFERENCE_RE.findall(m["content"]) if self._owned_reference(ref)})
            out = super().compress(messages, **{k: v for k, v in options.items() if k in allowed})
            if self._attempt_cancelled() or out is messages or not references:
                return out
            # Restore discovery deterministically; authorization does not depend
            # on this footer's role or on the summarizer copying it correctly.
            missing = [ref for ref in references if not any(isinstance(m.get("content"), str) and ref in m["content"] for m in out)]
            if not missing:
                return out
            footer = "\n\n[Jev recovery references retained for this session]\n" + "\n".join(
                f"jev_recover(reference='{ref}')" for ref in missing)
            from agent.context_compressor import is_compaction_summary_message
            out = [dict(m) for m in out]
            summary = next((m for m in out if is_compaction_summary_message(m) and isinstance(m.get("content"), str)), None)
            if summary is not None:
                summary["content"] += footer
            else:
                out.append({"role": "assistant", "content": footer.strip()})
            return out

    return HermesJevContextEngine()


def register_compaction_engine(ctx: Any) -> str:
    register = getattr(ctx, "register_context_engine", None)
    if not callable(register):
        return "unavailable"
    try:
        register(create_context_engine())
        return "registered; select context.engine: hermes-jev-performance to activate"
    except Exception:
        # Routing remains available if the optional host integration is missing.
        return "unavailable"
