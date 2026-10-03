"""Exercise extracted code without installing it or importing the source checkout."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import types

root = Path(sys.argv[1]).resolve()
home = Path(os.environ['HERMES_HOME']).resolve()
os.environ['HERMES_HOME'] = str(home)
home.mkdir(parents=True)
namespace = types.ModuleType('hermes_plugins')
namespace.__path__ = []
sys.modules['hermes_plugins'] = namespace
name = 'hermes_plugins.hermes_jev_performance'
spec = importlib.util.spec_from_file_location(name, root / '__init__.py', submodule_search_locations=[str(root)])
plugin = importlib.util.module_from_spec(spec)
sys.modules[name] = plugin
spec.loader.exec_module(plugin)


class Context:
    def __init__(self):
        self.settings = {'mode': 'on', 'compaction_mode': 'shadow'}
        self.commands = {}
        self.state = {}

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def set_config(self, key, value):
        self.settings[key] = value

    def register_command(self, name, handler, **kwargs):
        self.commands[name] = handler

    def register_middleware(self, *args):
        pass

    def register_hook(self, *args):
        pass

    def register_cli_command(self, **kwargs):
        pass


ctx = Context()
plugin.register(ctx)
assert 'jev' in ctx.commands
canonical = name + ('.agent.jevperf' if (root / 'agent').exists() else '.jevperf')
paths = sys.modules[canonical + '.package_paths']
assert paths.PLUGIN_ROOT == root
config = sys.modules[canonical + '.config']
assert config.read_config(ctx).mode == 'on'
from importlib import import_module
archive_module = import_module(canonical + '.compaction_archive')
store_module = import_module(canonical + '.store')
archive = archive_module.OutputArchive()
reference = archive.reference('synthetic-session')
archive.write_batch([(reference, 'synthetic archived output')])
store = store_module.MetricsStore()
store.touch_turn('synthetic-turn', 'on')
assert archive.recover(reference)['text'] == 'synthetic archived output'
assert store.summary().turns == 1
# Profile data remains recoverable independently of plugin layout.
assert home in archive.root.parents
(home / 'unrelated-plugin.json').write_text(json.dumps({'enabled': True}))
assert 'agent' not in sys.modules  # no collision with Hermes' generic agent package
print('isolated package PASS')
