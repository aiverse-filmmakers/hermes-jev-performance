# Compatibility Matrix

Hermes Jev Performance is designed against Hermes' public plugin APIs and feature-detects those surfaces at runtime.

## Declared floor

```yaml
requires_hermes: ">=0.21.5"
```

Hermes 0.21.5 is the declared minimum because the required v1 plugin surfaces are documented and available on that release line.

## Python

| Python | Status |
|---|---|
| 3.11 | Tested in CI |
| 3.12 | Tested in CI |
| 3.13 | Tested in CI |
| 3.14 | Tested in CI |

Python versions outside 3.11-3.14 are not currently claimed as tested.

## Hermes feature matrix

| Surface | Required for | Missing behavior |
|---|---|---|
| `ctx.register_command` | `/jev` controls | Plugin is unsupported and will not register |
| `ctx.get_config` | validated settings | Plugin is unsupported and will not register |
| `ctx.register_middleware` | Jev routing | Degraded: no routing modification |
| `ctx.set_config` | persistent mode/notice changes | Degraded: settings cannot be changed through plugin controls |
| `ctx.register_hook` | Hermes performance telemetry + reply notice | Degraded: affected telemetry/notices unavailable |
| `ctx.register_cli_command` | `hermes jev ...` | Optional: agent runtime can still work without CLI extension |
| Hermes dashboard plugin discovery | Jev Performance web tab | Dashboard unavailable; routing/commands remain independent |
| Hermes plugin install/update/remove | lifecycle/packaging | Use a supported Hermes release or manual dev install only |

Feature detection is authoritative. Version metadata is supporting evidence, not a substitute for checking the actual public surfaces.

## Dashboard profile isolation

The dashboard carries the selected Hermes profile in every plugin API request.

Newer Hermes hosts scope plugin API requests to that profile before the plugin handler runs. Hermes 0.21.5 has profile identity helpers but does not automatically apply the selected management profile to third-party plugin API routers.

To keep the declared 0.21.5 floor safe, every Jev dashboard backend route verifies that a named selected profile matches Hermes' effective `HERMES_HOME` for that request. Therefore:

- correctly profile-scoped hosts work normally;
- a dashboard directly serving the selected profile works normally on 0.21.5;
- an unsafe cross-profile request on a host that did not scope the plugin route fails closed with HTTP 409 before telemetry is read or settings are written;
- an unknown profile fails with a safe HTTP 404;
- the plugin does not import Hermes private profile-scope internals.

This makes wrong-profile access a hard failure rather than silently falling back to whichever profile the dashboard process launched with.

## Compatibility states

### Supported

Base plugin APIs plus routing, persistence and telemetry-hook surfaces are present. The CLI extension may be absent without disabling the core runtime.

### Degraded

The plugin can load safely but one or more optimization/observability surfaces are missing. Examples: middleware unavailable means no Jev routing; hooks unavailable means reduced telemetry; settings writer unavailable means status works but mode changes cannot persist. Normal Hermes remains available.

### Unsupported

The required base plugin context cannot provide both `register_command` and `get_config`. The plugin refuses registration rather than guessing or patching Hermes internals.

## Runtime version checks

`hermes jev doctor` reports the detected Hermes version when available, declared Hermes floor, public surface availability, Python version, config validity, credential presence without printing secrets, telemetry DB health/schema, dashboard assets, and benchmark fixtures.

The doctor performs no network calls.

## Live validation status

Automated CI validates synthetic Hermes plugin contexts across Python 3.11-3.14.

Before public beta, the release gate still requires live smoke validation on:

1. Hermes 0.21.5 release line.
2. The current supported Hermes stable release at beta time.

For each live row: plugin install, plugin doctor/import, SHADOW request, ON clear-family request, OFF zero-Jev request, Telegram/gateway control, dashboard discovery/API, selected-profile isolation behavior, controlled benchmark preview, disable, re-enable, remove/uninstall, and a normal Hermes request after removal.

Until those live rows are actually run, this document does not claim they passed.
