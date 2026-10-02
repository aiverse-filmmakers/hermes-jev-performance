"""Small Hermes PluginContext test double."""

from __future__ import annotations


class FakeContext:
    def __init__(self, settings=None, *, middleware=True, set_config=True, state=True):
        self.settings = dict(settings or {})
        self.commands = {}
        self.middleware = {}
        self._middleware_enabled = middleware
        self._set_config_enabled = set_config
        if state:
            self.state = {}

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def register_command(self, name, handler, description="", args_hint="", **kwargs):
        self.commands[name] = {
            "handler": handler,
            "description": description,
            "args_hint": args_hint,
        }

    def __getattribute__(self, name):
        if name == "register_middleware":
            enabled = object.__getattribute__(self, "_middleware_enabled")
            if not enabled:
                raise AttributeError(name)
        if name == "set_config":
            enabled = object.__getattribute__(self, "_set_config_enabled")
            if not enabled:
                raise AttributeError(name)
        return object.__getattribute__(self, name)

    def register_middleware(self, kind, callback):
        self.middleware.setdefault(kind, []).append(callback)

    def set_config(self, key, value):
        self.settings[key] = value

    def register_hook(self, *args, **kwargs):
        raise AssertionError("unexpected hook registration")

    def register_cli_command(self, *args, **kwargs):
        raise AssertionError("unexpected CLI subcommand registration")
