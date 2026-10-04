"""Labelled synthetic recall/calibration probe, with explicit optional live Jev calls."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import tempfile
import time
from typing import Callable

from .compaction import JevCompactor, RULEBOOK_VERSION, STUB_PREFIX, estimated_tokens
from .compaction_archive import OutputArchive
from .compaction_config import CompactionConfig


def fixture() -> tuple[list[dict], list[str], dict[str, bool]]:
    rows = [{"role": "system", "content": "Preserve exact facts; never invent missing evidence."},
            {"role": "user", "content": "Retain APP_SHARD_COUNT and the unresolved exact trace ID. "
             "The repetitive INFO log is obsolete and may be archived."},
            {"role": "assistant", "content": "Inspecting the configuration and traces."}]
    critical = ["APP_SHARD_COUNT=13", "TRACE_ID=trace-synthetic-42"]
    outputs = ["INFO stable synthetic event\n" * 3000,
               "APP_SHARD_COUNT=13\n", "unresolved synthetic trace\n" * 500 + "TRACE_ID=trace-synthetic-42"]
    labels = {}
    for i, content in enumerate(outputs):
        cid = f"synthetic-{i}"
        rows.append({"role": "assistant", "content": "", "tool_calls": [{"id": cid, "type": "function",
                     "function": {"name": "read_file", "arguments": "{}"}}]})
        rows.append({"role": "tool", "tool_call_id": cid, "content": content})
        labels[f"archive_{len(rows)-1}"] = i == 0
    # Unique old outputs stay outside the complete protected recent exchange.
    for i in range(18):
        rows += [{"role": "user", "content": f"Continue the synthetic audit step {i}."},
                 {"role": "assistant", "content": "The unresolved trace and config remain needed."}]
    return rows, critical, labels


def run_compaction_probe(*, live: bool = False, model: str = "typesafe/jev-1.13", timeout: float = 2.5,
                         compactor: JevCompactor | None = None, normal_compress: Callable | None = None) -> dict:
    rows, critical, labels = fixture()
    def labelled_response(**kwargs):
        return {"model": "synthetic-labelled", "usage": {}, "answers": {
            name: {"type": "noul", "noul": 0.99 if labels[name.split("_part_")[0]] else 0.01} for name in kwargs["questions"]}}
    class SyntheticCredential:
        token = "synthetic-not-a-provider-key"
    engine = compactor or (JevCompactor() if live else JevCompactor(
        evaluator=labelled_response, credential_resolver=lambda: SyntheticCredential()))
    def score(messages):
        text = "\n".join(m.get("content", "") for m in messages if isinstance(m.get("content"), str))
        return sum(value in text for value in critical)
    before = estimated_tokens(rows)
    report = {"kind": "synthetic_fixture_live_jev" if live else "synthetic_contract_probe",
              "rulebook": RULEBOOK_VERSION, "critical_facts": len(critical), "arms": [],
              "claims": "Synthetic replay; not a real-task benchmark or calibrated accuracy guarantee."}
    report["arms"].append({"policy": "retain_all", "critical_recall": score(rows),
                           "estimated_context_tokens": before, "provider_cost_usd": None})
    # A deterministic control reveals whether Jev adds value beyond size/recency.
    recency = [dict(row) for row in rows]
    for i in (4, 8):
        recency[i]["content"] = "[older large result removed by recency control]"
    report["arms"].append({"policy": "recency_size_control", "critical_recall": score(recency),
                           "estimated_context_tokens": estimated_tokens(recency), "provider_cost_usd": 0})
    with tempfile.TemporaryDirectory() as temp:
        archive = OutputArchive(Path(temp).resolve() / "drawer")
        started = time.monotonic()
        result = engine.compact(rows, config=replace(CompactionConfig(), mode="on", allow_external=True), model=model,
                                timeout=timeout, archive=archive, session_id="synthetic-probe")
        recovery_ok = 0
        recovery_total = 0
        for old, new in zip(rows, result.messages):
            content = new.get("content", "")
            if not isinstance(content, str) or not content.startswith(STUB_PREFIX):
                continue
            recovery_total += 1
            reference = content[len(STUB_PREFIX):].split(";", 1)[0]
            recovered, offset = "", 0
            while offset is not None:
                page = archive.recover(reference, offset=offset)
                recovered += page["text"]
                offset = page["next_offset"]
            recovery_ok += recovered == old["content"]
        report["arms"].append({"policy": "jev_live" if live else "labelled_contract_control",
            "critical_recall": score(result.messages), "estimated_context_tokens": estimated_tokens(result.messages),
            "outcome": result.outcome, "duration_ms": (time.monotonic() - started) * 1000,
            "provider_cost_usd": result.cost_usd, "provider_input_tokens": result.input_tokens,
            "provider_output_tokens": result.output_tokens,
            "assessment_requests": result.requests, "selected_outputs": result.selected,
            "exact_recovery_passed": recovery_ok, "exact_recovery_total": recovery_total})
    if normal_compress is not None:
        started = time.monotonic()
        compressed = normal_compress(rows)
        report["arms"].append({"policy": "normal_hermes_compression", "critical_recall": score(compressed),
            "estimated_context_tokens": estimated_tokens(compressed), "duration_ms": (time.monotonic() - started) * 1000,
            "provider_cost_usd": None})
    return report


def render_probe(report: dict) -> str:
    return json.dumps(report, indent=2, sort_keys=True)
