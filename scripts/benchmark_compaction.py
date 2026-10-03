#!/usr/bin/env python3
"""Offline-by-default probe; optional actual Jev and normal Hermes compression arms."""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from jevperf.compaction_benchmark import render_probe, run_compaction_probe  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Explicit paid Jev call with synthetic data only.")
    parser.add_argument("--normal-hermes", action="store_true", help="Also call the actual configured Hermes summarizer (paid). Requires --live and --baseline-model.")
    parser.add_argument("--baseline-model", help="Your existing Hermes model identifier; never changes Hermes config.")
    parser.add_argument("--model", default="typesafe/jev-1.13")
    args = parser.parse_args()
    baseline = None
    if args.normal_hermes:
        if not args.live or not args.baseline_model:
            parser.error("--normal-hermes requires --live and --baseline-model")
        from jevperf.context_engine import create_context_engine
        engine = create_context_engine()
        engine.update_model(model=args.baseline_model, context_length=1000000)
        def baseline(rows):
            return engine._normal_compress(rows, None, "Preserve exact configuration and unresolved trace ID", True, "", {})
    report = run_compaction_probe(live=args.live, model=args.model, normal_compress=baseline)
    print(render_probe(report))
    arm = report["arms"][2]
    return 0 if arm["outcome"] == "applied" and arm["critical_recall"] == report["critical_facts"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
