"""Small Hermes PluginContext test double."""

from __future__ import annotations


class FakeContext:
    def __init__(
        self,
        settings=None,
        *,
        middleware=True,
        set_config=True,
        hooks=True,
        cli=True,
        state=True,
    ):
        self.settings = dict(settings or {})
        self.commands = {}
        self.middleware = {}
        self.hooks = {}
        self.cli_commands = {}
        self._middleware_enabled = middleware
        self._set_config_enabled = set_config
        self._hooks_enabled = hooks
        self._cli_enabled = cli
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
            if not object.__getattribute__(self, "_middleware_enabled"):
                raise AttributeError(name)
        if name == "set_config":
            if not object.__getattribute__(self, "_set_config_enabled"):
                raise AttributeError(name)
        if name == "register_hook":
            if not object.__getattribute__(self, "_hooks_enabled"):
                raise AttributeError(name)
        if name == "register_cli_command":
            if not object.__getattribute__(self, "_cli_enabled"):
                raise AttributeError(name)
        return object.__getattribute__(self, name)

    def register_middleware(self, kind, callback):
        self.middleware.setdefault(kind, []).append(callback)

    def set_config(self, key, value):
        self.settings[key] = value

    def register_hook(self, name, callback):
        self.hooks.setdefault(name, []).append(callback)

    def register_cli_command(
        self,
        name,
        help,
        setup_fn,
        handler_fn=None,
        description="",
    ):
        self.cli_commands[name] = {
            "help": help,
            "setup_fn": setup_fn,
            "handler_fn": handler_fn,
            "description": description,
        }
