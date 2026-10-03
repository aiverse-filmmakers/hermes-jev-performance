"""Load the delivered API without global import-path changes or agent collisions."""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
from pathlib import Path
import sys


def load_router(runtime_root: Path):
    root = runtime_root.resolve()
    name = 'hermes_jev_api_' + hashlib.sha256(str(root).encode()).hexdigest()[:16]
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, root / '__init__.py',
                                                     submodule_search_locations=[str(root)])
        if spec is None or spec.loader is None:
            raise ImportError('Jev backend package is unavailable')
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    return importlib.import_module(name + '.plugin_api').router
