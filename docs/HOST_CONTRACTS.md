# Hermes host contracts

This records source evidence used during the installation split. Source inspection is not a substitute for running the release through the branded Desktop installer or a real remote gateway.

## Inspected runtime

- Hermes Agent source: `v0.21.5+5279.g4e74031` (2026.9.24). The correction's offline host contracts use the available Hermes Python 3.11 runtime; this is separate from the previously observed runtime version.
- Hermes source revision: `4e7403130ee278bd99c450fcd9f73c6b32135c95` in the local development checkout. This is evidence only; community installs do not need that checkout.
- Hermes Desktop source package version `0.17.0` supports the APIs used here. A running Desktop app reported client `0.17.0` and backend `0.21.5`; this was a version observation only, not a plugin installation test.
- Starting Jev plugin revision: `47b61fa6592b4657858f4d3807e14f21d6b78174`.
- Sources reviewed: `hermes_cli/plugins_cmd.py`, `plugins_cmd_install.py`, `plugins_loader.py`, `web_server_dashboard.py`, `apps/desktop/electron/desktop-plugin-install.ts`, `desktop-plugins-root.ts`, `apps/desktop/src/contrib/plugin.ts`, `apps/desktop/src/sdk/index.ts`, and `web/src/plugins/usePlugins.ts`.
- Official references: [Desktop Plugin SDK](https://hermes-agent.nousresearch.com/docs/developer-guide/desktop-plugin-sdk), [plugin install links and subdirectory installs](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins), [multiple Hermes connections in Desktop](https://hermes-agent.nousresearch.com/docs/user-guide/multi-connection-desktop).

## Source-confirmed behavior

| Behavior | Source evidence | Status |
|---|---|---|
| Hermes install link | Desktop deep-link handler accepts `hermes://plugin/install?repo=...` and routes it to the plugin install confirmation. | Source-confirmed; click/install flow not run. |
| Agent install from a Git subdirectory | `plugins_cmd.py` accepts `owner/repo/path`; installer reads that subdirectory's manifest and uses its `name`. | Source-confirmed; live receipt pending. |
| Desktop-only install link | Desktop resolves `owner/repo/desktop` to that Git subdirectory, detects its root `plugin.js`, then copies only that folder into the app's local Desktop plugin directory. The generic `desktop` subdirectory is excluded when deriving the stable folder, leaving `hermes-jev-performance`. | Source-confirmed for Desktop `0.17.0`; branded install not run. |
| Manual Desktop install fallback | The Desktop Plugins settings page exposes **Open plugins folder** and **Rescan**; each plugin is loaded from `<desktop-plugins>/<plugin-id>/plugin.js`. | Source-confirmed; this is the documented fallback when the install link cannot be opened. |
| Server-only install link | The `/agent` subdirectory contains `plugin.yaml` and `__init__.py`, and no sibling Desktop entry inside that selected source. | Source-confirmed against plugin-detection contract; actual selected install not run. |
| Combined package | Hermes detects the root Agent manifest and nested `desktop/plugin.js`; the install dialog can install the agent to the selected gateway and the Desktop files to this computer. | Source-confirmed; lifecycle test pending. |
| Remote Desktop connection | Desktop SDK `ctx.rest` calls the plugin namespace using the active gateway connection. The Desktop app handles gateway auth. | Documented/source-confirmed; live remote integration pending. |
| Agent API mount | Hermes finds the manifest/API and mounts the delivered router under `/api/plugins/<name>`. Actual host tests verify authenticated health, unauthenticated 401, disabled-plugin 404, and strict mode bodies. | Passed in an isolated offline host app; real remote transport remains pending. |
| Missing browser entry behavior | Hermes defaults a missing manifest `entry` to `dist/index.js`; its web loader injects a script for every manifest. | Source-confirmed: manifest omission alone is not API-only safe. |
| Hidden browser tab | Manifest `tab.hidden` prevents a visible browser dashboard tab; the browser loader still needs a registration for the manifest. | Source-confirmed; server shim smoke test pending. |
| Profile switches | `ctx.rest` uses the active gateway profile. The panel uses `host.state.profile` with `connectionId`, rather than the focused chat's profile. | Delivered-file behavior tests pass for delayed reads/read-back, write races, and cleanup; real app switches remain pending. |

## Deliberately unverified

- The actual install-link click, confirmation choices, and resulting folder contents on the user's Desktop version. The UI was not used to install or enable this plugin.
- Manual file placement, rescan, and plugin enablement through the actual Hermes Desktop app.
- Install, update, disable, and remove through the actual Hermes Desktop app.
- Remote VPS authentication/read/write against a live gateway.
- Browser server-only shim appearance and network request in a running Hermes web dashboard.
- Real OpenRouter credentials or Jev response.
- Automatic context-engine settings write; use documented settings/manual setup unless a supported public writer is proven.

No minimum Desktop version should be advertised until the supported Desktop release is tested. Server compatibility and Desktop compatibility are separate claims.

## Review-correction verification

The alpha.10 corrections run the offline loader/API suite (5 tests) and expanded native compaction suite (11 tests) against reference source `7533bd2756b9526b52f527f737420a19e57331d7`, using Python 3.11.16. The latter includes real normal compression assembly with only the provider mocked, summarize-then-recover, fresh engine/session ownership, compression rotation, real agent commit and carried-tail recall behavior. These runs use temporary profiles and forbid provider network access.

An additional older development checkout (`29d4c0ebfde82ad8ae3d411f1ad2c401199d37a7`) passes the compaction suite, but its loader/API checks do not run successfully with this runtime because required YAML/host modules are missing. It is not evidence of installer/API compatibility. No claim is made about the user's actual VPS serving runtime/profile. See [TESTING.md](TESTING.md#routing-and-compaction-review-corrections) and [REVIEW_FIXES.md](REVIEW_FIXES.md).
