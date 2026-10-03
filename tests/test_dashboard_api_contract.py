import asyncio
import importlib.util
import pathlib
import sys
import types
import unittest
from unittest import mock


ROOT = pathlib.Path(__file__).resolve().parents[1]
PLUGIN_API = ROOT / "dashboard" / "plugin_api.py"


class FakeHTTPException(Exception):
    def __init__(self, status_code, detail):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class FakeAPIRouter:
    def __init__(self):
        self.routes = []

    def _register(self, method, path):
        def decorator(fn):
            self.routes.append((method, path, fn))
            return fn
        return decorator

    def get(self, path):
        return self._register("GET", path)

    def put(self, path):
        return self._register("PUT", path)


def fake_query(default=None, **kwargs):
    return default


def load_api_module():
    fake = types.ModuleType("fastapi")
    fake.APIRouter = FakeAPIRouter
    fake.HTTPException = FakeHTTPException
    fake.Query = fake_query

    previous_fastapi = sys.modules.get("fastapi")
    sys.modules["fastapi"] = fake
    name = "hermes_jev_dashboard_api_test"
    spec = importlib.util.spec_from_file_location(name, PLUGIN_API)
    module = importlib.util.module_from_spec(spec)
    previous_module = sys.modules.get(name)
    sys.modules[name] = module
    try:
        assert spec.loader is not None
        spec.loader.exec_module(module)
    finally:
        if previous_fastapi is None:
            sys.modules.pop("fastapi", None)
        else:
            sys.modules["fastapi"] = previous_fastapi
        if previous_module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous_module
    return module


def fake_hermes_profile_modules(*, exists=True, matches=True):
    profiles = types.ModuleType("hermes_cli.profiles")
    profiles.profile_exists = lambda name: exists
    profiles.profile_matches_home = lambda name: matches
    hermes_cli = types.ModuleType("hermes_cli")
    hermes_cli.profiles = profiles
    return {
        "hermes_cli": hermes_cli,
        "hermes_cli.profiles": profiles,
    }


class DashboardApiContractTests(unittest.TestCase):
    def test_expected_routes_only(self):
        module = load_api_module()
        routes = {(method, path) for method, path, _ in module.router.routes}
        self.assertEqual(
            routes,
            {
                ("GET", "/status"),
                ("GET", "/summary"),
                ("GET", "/analytics"),
                ("GET", "/benchmarks"),
                ("GET", "/benchmarks/{run_id}/export"),
                ("PUT", "/mode"),
                ("PUT", "/compaction"),
            },
        )

    def test_every_backend_route_enforces_selected_profile_scope(self):
        source = PLUGIN_API.read_text(encoding="utf-8")
        self.assertEqual(source.count("_ensure_profile_scope(profile)"), 7)

    def test_named_profile_is_allowed_when_host_scope_matches(self):
        module = load_api_module()
        with mock.patch.dict(
            sys.modules,
            fake_hermes_profile_modules(exists=True, matches=True),
        ):
            module._ensure_profile_scope("work")

    def test_named_profile_mismatch_fails_closed(self):
        module = load_api_module()
        with mock.patch.dict(
            sys.modules,
            fake_hermes_profile_modules(exists=True, matches=False),
        ):
            with self.assertRaises(FakeHTTPException) as caught:
                module._ensure_profile_scope("work")
        self.assertEqual(caught.exception.status_code, 409)
        self.assertNotIn("/", caught.exception.detail)

    def test_unknown_named_profile_is_safe_404(self):
        module = load_api_module()
        with mock.patch.dict(
            sys.modules,
            fake_hermes_profile_modules(exists=False, matches=False),
        ):
            with self.assertRaises(FakeHTTPException) as caught:
                module._ensure_profile_scope("missing")
        self.assertEqual(caught.exception.status_code, 404)
        self.assertNotIn("missing", caught.exception.detail)

    def test_mode_body_rejects_extra_fields(self):
        module = load_api_module()
        with self.assertRaises(FakeHTTPException) as caught:
            asyncio.run(module.update_mode({"mode": "on", "extra": True}))
        self.assertEqual(caught.exception.status_code, 422)

    def test_mode_body_requires_string(self):
        module = load_api_module()
        with self.assertRaises(FakeHTTPException) as caught:
            asyncio.run(module.update_mode({"mode": 1}))
        self.assertEqual(caught.exception.status_code, 422)

    def test_mode_permission_error_is_safe_403(self):
        module = load_api_module()

        def denied(mode):
            raise PermissionError("PRIVATE_INTERNAL_DETAIL")

        module.set_dashboard_mode = denied
        with self.assertRaises(FakeHTTPException) as caught:
            asyncio.run(module.update_mode({"mode": "on"}))
        self.assertEqual(caught.exception.status_code, 403)
        self.assertNotIn("PRIVATE_INTERNAL_DETAIL", caught.exception.detail)

    def test_mode_readback_failure_is_safe_409(self):
        module = load_api_module()

        def failed(mode):
            raise RuntimeError("PRIVATE_INTERNAL_DETAIL")

        module.set_dashboard_mode = failed
        with self.assertRaises(FakeHTTPException) as caught:
            asyncio.run(module.update_mode({"mode": "on"}))
        self.assertEqual(caught.exception.status_code, 409)
        self.assertNotIn("PRIVATE_INTERNAL_DETAIL", caught.exception.detail)

    def test_status_failure_does_not_leak_exception_text(self):
        module = load_api_module()

        def failed():
            raise RuntimeError("PRIVATE_INTERNAL_DETAIL")

        module.status_payload = failed
        with self.assertRaises(FakeHTTPException) as caught:
            asyncio.run(module.get_status())
        self.assertEqual(caught.exception.status_code, 503)
        self.assertNotIn("PRIVATE_INTERNAL_DETAIL", caught.exception.detail)

    def test_bundle_uses_host_authenticated_profile_scoped_transport_for_mode_write(self):
        source = (ROOT / "dashboard" / "dist" / "index.js").read_text(encoding="utf-8")
        self.assertIn('new URLSearchParams(window.location.search).get("profile")', source)
        self.assertIn('SDK.fetchJSON(apiUrl("/mode"), {', source)
        self.assertIn('profile=" + encodeURIComponent(profile)', source)
        self.assertIn('method: "PUT"', source)
        self.assertNotIn("window.__HERMES_SESSION_TOKEN__", source)
        self.assertNotIn("document.cookie", source)

    def test_benchmark_export_not_found_is_safe_404(self):
        module = load_api_module()

        def missing(run_id):
            raise KeyError("PRIVATE_INTERNAL_DETAIL")

        module.benchmark_export_payload = missing
        with self.assertRaises(FakeHTTPException) as caught:
            asyncio.run(module.get_benchmark_export("bench-missing"))
        self.assertEqual(caught.exception.status_code, 404)
        self.assertNotIn("PRIVATE_INTERNAL_DETAIL", caught.exception.detail)

    def test_benchmark_list_failure_is_safe_503(self):
        module = load_api_module()

        def failed(limit=10):
            raise RuntimeError("PRIVATE_INTERNAL_DETAIL")

        module.benchmark_runs_payload = failed
        with self.assertRaises(FakeHTTPException) as caught:
            asyncio.run(module.get_benchmarks(limit=10))
        self.assertEqual(caught.exception.status_code, 503)
        self.assertNotIn("PRIVATE_INTERNAL_DETAIL", caught.exception.detail)


if __name__ == "__main__":
    unittest.main()
