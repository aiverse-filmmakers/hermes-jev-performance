#!/usr/bin/env python3
"""Offline native loader/API checks. No Hermes installer or real profile is used."""
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hermes-source', type=Path, required=True)
    args = parser.parse_args()
    source = args.hermes_source.resolve()
    if not (source / 'hermes_cli/plugins.py').is_file():
        parser.error('Hermes source must contain hermes_cli/plugins.py')
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(source))
    sys.path.append(str(root))
    sys.path.append(str(root / 'agent'))
    sys.dont_write_bytecode = True
    with tempfile.TemporaryDirectory() as temp, mock.patch.dict(os.environ, {
            'HERMES_HOME': str(Path(temp).resolve()), 'HERMES_DISABLE_LAZY_INSTALLS': '1',
            'HERMES_DASHBOARD_SESSION_TOKEN': 'synthetic-contract-token'}):
        with mock.patch.object(socket, 'create_connection', side_effect=AssertionError('network forbidden')):
            spec = importlib.util.spec_from_file_location('jevperf_native_install_contract', root / 'tests/native_install_contract.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            suite = unittest.defaultTestLoader.loadTestsFromModule(module)
            result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
