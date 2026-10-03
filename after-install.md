# Hermes Jev Performance installed

The plugin installs in **SHADOW** mode by default.

Recommended checks:

```bash
hermes plugins doctor hermes-jev-performance --ci
hermes jev status
hermes jev doctor
```

For Jev routing, configure either `OPENROUTER_JEV_API_TOKEN` (preferred) or an existing `OPENROUTER_API_KEY`.

Day-to-day controls:

```text
/jev status
/jev shadow
/jev on
/jev off
/jev stats
/jev doctor
/jev compaction status
/jev compaction shadow
```

To disable the plugin itself:

```bash
hermes plugins disable hermes-jev-performance
```

Recoverable compaction is opt-in. Set `context.engine: hermes-jev-performance` in the Hermes profile, restart Hermes, and use `/jev compaction shadow` before enabling it with `/jev compaction on`.

Full install, upgrade, rollback and uninstall instructions are in `docs/INSTALL.md`.
