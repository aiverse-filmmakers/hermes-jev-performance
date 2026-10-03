"""Hermes API adapter for the canonical, package-isolated backend."""
from pathlib import Path
import importlib.util

runtime_root = Path(__file__).resolve().parents[1] / "jevperf"
spec = importlib.util.spec_from_file_location("jev_api_loader", runtime_root / "api_loader.py")
if spec is None or spec.loader is None:
    raise ImportError("Jev API loader is unavailable")
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)
router = loader.load_router(runtime_root)
