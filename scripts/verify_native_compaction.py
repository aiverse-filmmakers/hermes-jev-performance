#!/usr/bin/env python3
"""Offline tests against actual Hermes source/runtime in an isolated temporary profile."""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest import mock


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hermes-source", type=Path, required=True)
    args = parser.parse_args()
    source = args.hermes_source.resolve()
    if not (source / "agent" / "context_engine.py").is_file():
        parser.error("Hermes source must contain agent/context_engine.py")
    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(source))
    sys.path.append(str(repository_root))
    sys.path.append(str(repository_root / "agent"))
    sys.dont_write_bytecode = True
    # Hermes also has a tests package. Load this suite's package explicitly
    # without placing the plugin's generic agent directory ahead of Hermes.
    spec = importlib.util.spec_from_file_location("tests", repository_root / "tests/__init__.py",
                                                 submodule_search_locations=[str(repository_root / "tests")])
    package = importlib.util.module_from_spec(spec)
    sys.modules["tests"] = package
    spec.loader.exec_module(package)
    with tempfile.TemporaryDirectory() as temp, mock.patch.dict(os.environ, {
            "HERMES_HOME": str(Path(temp).resolve()), "HERMES_DISABLE_LAZY_INSTALLS": "1"}):
        # Never read the real profile or run real provider calls.
        with mock.patch.object(socket, "create_connection", side_effect=AssertionError("network forbidden")):
            suite = unittest.defaultTestLoader.loadTestsFromName("tests.native_compaction_contract")
            result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
