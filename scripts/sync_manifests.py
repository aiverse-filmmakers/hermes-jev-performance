#!/usr/bin/env python3
"""Render both plugin manifests from one dependency-free packaging specification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def manifest_text(root: Path = ROOT, *, server: bool = False) -> str:
    spec = json.loads((root / "packaging/plugin-manifest.json").read_text())
    if server:
        spec["description"] = "Jev routing, recoverable compaction, and performance data API for Hermes."
    for key in ("mode", "compaction_mode"):
        if spec["config_schema"][key]["default"] != "off":
            raise ValueError(f"{key} must have the string default off")

    def render(mapping: dict, indent: int = 0) -> list[str]:
        rows = []
        for key, value in mapping.items():
            prefix = " " * indent + key + ":"
            if isinstance(value, dict):
                rows.append(prefix)
                rows.extend(render(value, indent + 2))
            else:
                # JSON scalars/arrays are valid YAML; quoted strings avoid YAML 1.1 booleans.
                rows.append(prefix + " " + json.dumps(value, ensure_ascii=False))
        return rows

    return "\n".join(render(spec)) + "\n"


def sync(root: Path = ROOT, *, check: bool = False) -> None:
    for target, server in (("plugin.yaml", False), ("agent/plugin.yaml", True)):
        path = root / target
        expected = manifest_text(root, server=server)
        if check:
            if path.read_text() != expected:
                raise ValueError(f"{target} has drifted; run scripts/sync_manifests.py")
        else:
            path.write_text(expected, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    sync(check=parser.parse_args().check)
