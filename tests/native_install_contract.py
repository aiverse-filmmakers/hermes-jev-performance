"""Native host tests against temporary extracted deliveries, without installation."""
import importlib
from contextlib import ExitStack
import os
from pathlib import Path
import tempfile
import sys
import unittest
from unittest import mock
import zipfile

from hermes_cli.plugins import PluginManager
from hermes_cli.plugins_manifest import parse_manifest_file
from hermes_cli import config as config_mod
from scripts.build_release import build, verify
from jevperf import __version__
from jevperf.compaction_config import read_compaction_config
from jevperf.dashboard_service import _MappingContext, health_payload, read_dashboard_config

ID = 'hermes-jev-performance'
ROOT = Path(__file__).resolve().parents[1]


class NativeDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name)
        cls.metadata = build(cls.output)
        verify(cls.metadata, cls.output)
        cls.folders = {}
        for kind in ('server', 'combined'):
            with zipfile.ZipFile(cls.output / cls.metadata['packages'][kind]['path']) as archive:
                archive.extractall(cls.output / kind)
            cls.folders[kind] = cls.output / kind / ID

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def manifest(self, folder):
        parsed = parse_manifest_file(folder / 'plugin.yaml', folder, 'user', '')
        self.assertIsNotNone(parsed)
        return parsed

    def test_actual_yaml_loader_and_settings_schema_accept_string_off(self):
        from hermes_cli.plugins_settings import _manifest_config_schema
        for folder in (ROOT, ROOT / 'agent', *self.folders.values()):
            schema = _manifest_config_schema(folder)
            defaults = {key: value.get('default') for key, value in schema.items()}
            self.assertIs(type(defaults['mode']), str)
            self.assertEqual(defaults['mode'], 'off')
            self.assertEqual(read_compaction_config(_MappingContext(defaults)).warnings, ())
            self.assertEqual(self.manifest(folder).version, __version__)

    def test_native_root_to_server_reload_retains_modes_metrics_archives_and_other_plugin(self):
        from hermes_cli.plugins_state import save_plugin_setting
        for key, value in (('mode', 'on'), ('compaction_mode', 'shadow')):
            save_plugin_setting(ID, (key,), value)
        manager = PluginManager()
        unrelated = self.output / 'unrelated'
        unrelated.mkdir(exist_ok=True)
        (unrelated / 'plugin.yaml').write_text('name: unrelated\nversion: "1.0.0"\n')
        (unrelated / '__init__.py').write_text('def register(ctx):\n    ctx.register_command("unrelated", lambda *a: "ok")\n')
        manager._load_plugin(self.manifest(unrelated))
        try:
            manager._load_plugin(self.manifest(self.folders['combined']))
            loaded = manager._plugins[ID]
            self.assertTrue(loaded.enabled, loaded.error)
            code = importlib.import_module(loaded.module.__name__ + '.agent.jevperf.store')
            drawers = importlib.import_module(loaded.module.__name__ + '.agent.jevperf.compaction_archive')
            store = code.MetricsStore()
            store.touch_turn('synthetic-migration', 'on')
            archive = drawers.OutputArchive()
            reference = archive.reference('synthetic-session')
            archive.write_batch([(reference, 'synthetic exact archived output')])
            self.assertTrue(manager.unload(ID))
            self.assertTrue(manager._plugins['unrelated'].enabled)
            manager._load_plugin(self.manifest(self.folders['server']))
            loaded = manager._plugins[ID]
            self.assertTrue(loaded.enabled, loaded.error)
            new_code = importlib.import_module(loaded.module.__name__ + '.jevperf.store')
            new_drawers = importlib.import_module(loaded.module.__name__ + '.jevperf.compaction_archive')
            self.assertEqual(new_code.MetricsStore().summary().turns, 1)
            self.assertEqual(new_drawers.OutputArchive().recover(reference)['text'], 'synthetic exact archived output')
            from hermes_cli.plugins import PluginContext
            context = PluginContext(loaded.manifest, manager)
            self.assertEqual(context.get_config('mode'), 'on')
            self.assertEqual(context.get_config('compaction_mode'), 'shadow')
            self.assertTrue(manager.unload(ID))
            self.assertTrue(store.path.is_file())
            self.assertTrue(archive.root.exists())
            manager._load_plugin(self.manifest(self.folders['server']))
            self.assertTrue(manager._plugins[ID].enabled)
        finally:
            manager.unload()

    def test_legacy_config_modes_match_runtime_and_new_settings_take_precedence(self):
        from hermes_cli.plugins_settings import plugin_settings_fields
        from hermes_cli.plugins_state import save_plugin_setting
        legacy = {'plugins': {'entries': {ID: {'config': {'mode': 'on', 'compaction_mode': 'shadow'}}}}}
        with mock.patch.object(config_mod, 'load_config_readonly', return_value=legacy):
            self.assertEqual(read_dashboard_config().mode, 'on')
            self.assertEqual(next(f for f in plugin_settings_fields(ID, ROOT) if f['key'] == 'mode')['value'], 'off')
        save_plugin_setting(ID, ('mode',), 'shadow')
        self.assertEqual(read_dashboard_config().mode, 'shadow')

    def test_host_permissions_are_reported_and_probe_does_not_write_or_call_provider(self):
        from hermes_cli import managed_scope
        with mock.patch('jevperf.dashboard_service.resolve_openrouter_credential', return_value=None), mock.patch.object(config_mod, 'is_managed', return_value=False), mock.patch.object(managed_scope, 'is_key_managed', side_effect=lambda key: key.endswith('.mode')):
            payload = health_payload()
        self.assertFalse(payload['capabilities']['routing_mode_write'])
        self.assertTrue(payload['capabilities']['compaction_mode_write'])

    def test_real_host_mount_enforces_auth_disabled_state_and_strict_bodies(self):
        from fastapi.testclient import TestClient
        from hermes_cli import web_server, web_server_dashboard, plugins_cmd
        folder = self.folders['server']
        candidate = {'name': ID, 'source': 'user', '_dir': str(folder / 'dashboard'), '_api_file': 'plugin_api.py'}
        enabled = {ID}
        initial_routes = list(web_server.app.router.routes)
        # Native startup mounts plugins before the SPA/API catch-all. Reproduce
        # that order when adding a test package to an already imported app.
        web_server.app.router.routes[:] = [route for route in initial_routes
                                           if ':path}' not in getattr(route, 'path', '')]
        with mock.patch.object(web_server, '_get_dashboard_plugins', return_value=[candidate]), mock.patch.object(plugins_cmd, '_get_enabled_set', side_effect=lambda: enabled), mock.patch.object(plugins_cmd, '_get_disabled_set', return_value=set()), mock.patch('jevperf.dashboard_service.resolve_openrouter_credential', return_value=None):
            try:
                web_server_dashboard._mount_plugin_api_routes()
                client = TestClient(web_server.app)
                self.assertTrue(any(str(folder) in str(getattr(module, '__file__', ''))
                                    for name, module in sys.modules.items()
                                    if name.startswith('hermes_jev_api_')))
                patchers = ExitStack()
                self.addCleanup(patchers.close)
                for name, module in list(sys.modules.items()):
                    if name.startswith('hermes_jev_api_') and name.endswith('.dashboard_service'):
                        patchers.enter_context(mock.patch.object(module, 'resolve_openrouter_credential', return_value=None))
                url = '/api/plugins/' + ID
                self.assertEqual(client.get(url + '/health').status_code, 401)
                headers = {'Authorization': 'Bearer ' + os.environ['HERMES_DASHBOARD_SESSION_TOKEN']}
                response = client.get(url + '/health', headers=headers)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['plugin_id'], ID)
                for endpoint in ('/mode', '/compaction'):
                    for body in ({'mode': ['on']}, {'mode': 'on', 'extra': True}):
                        self.assertEqual(client.put(url + endpoint, headers=headers, json=body).status_code, 422)
                enabled.clear()
                self.assertEqual(client.get(url + '/health', headers=headers).status_code, 404)
                self.assertEqual(client.get(url + '/health').status_code, 401)
            finally:
                web_server.app.router.routes[:] = initial_routes
