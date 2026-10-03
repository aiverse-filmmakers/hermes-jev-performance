# Hermes host contracts

This records source evidence used during the installation split. Source inspection is not a substitute for running the release through the branded Desktop installer or a real remote gateway.

## Inspected runtime

- Hermes Agent: `v0.21.5+5279.g4e74031` (2026.9.24), Python 3.14.7.
- Hermes source revision: `4e7403130ee278bd99c450fcd9f73c6b32135c95` in the local development checkout. This is evidence only; community installs do not need that checkout.
- Starting Jev plugin revision: `47b61fa6592b4657858f4d3807e14f21d6b78174`.
- Sources reviewed: `hermes_cli/plugins_cmd.py`, `plugins_cmd_install.py`, `plugins_loader.py`, `web_server_dashboard.py`, `apps/desktop/electron/desktop-plugin-install.ts`, `desktop-plugins-root.ts`, `apps/desktop/src/contrib/plugin.ts`, `apps/desktop/src/sdk/index.ts`, and `web/src/plugins/usePlugins.ts`.
- Official references: [Desktop Plugin SDK](https://hermes-agent.nousresearch.com/docs/developer-guide/desktop-plugin-sdk), [plugin install links and subdirectory installs](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins), [multiple Hermes connections in Desktop](https://hermes-agent.nousresearch.com/docs/user-guide/multi-connection-desktop).

## Source-confirmed behavior

| Behavior | Source evidence | Status |
|---|---|---|
| Agent install from a Git subdirectory | `plugins_cmd.py` accepts `owner/repo/path`; installer reads that subdirectory's manifest and uses its `name`. | Source-confirmed; live receipt pending. |
| Desktop install from a Git subdirectory | Desktop installer detects `desktop/plugin.js`; a subdirectory named `desktop` is excluded when deriving the stable folder, so the repository name is used. | Source-confirmed; branded Desktop test pending. |
| Combined package | Hermes looks for `<agent package>/desktop/plugin.js` and reconciles it into the local app-level Desktop plugin folder. | Source-confirmed; lifecycle test pending. |
| Remote Desktop connection | Desktop SDK `ctx.rest` calls the plugin namespace using the active gateway connection. The Desktop app handles gateway auth. | Documented/source-confirmed; live remote integration pending. |
| Agent API mount | Hermes finds `dashboard/manifest.json` under enabled agent plugins, validates the relative `api` path, imports `plugin_api.py`, and mounts the router under `/api/plugins/<name>`. | Source-confirmed; package integration test pending. |
| Missing browser entry behavior | Hermes defaults a missing manifest `entry` to `dist/index.js`; its web loader injects a script for every manifest. | Source-confirmed: manifest omission alone is not API-only safe. |
| Hidden browser tab | Manifest `tab.hidden` prevents a visible browser dashboard tab; the browser loader still needs a registration for the manifest. | Source-confirmed; server shim smoke test pending. |
| Profile switches | The Desktop SDK request is associated with active plugin scope; host state exposes connection/profile. | Source-confirmed; stale response/write integration tests pending. |

## Deliberately unverified

- Hermes Desktop's exact menu text, current GUI install dialog, and actual install-link handling on the user's version.
- Install, update, disable, and remove through the actual Hermes Desktop app.
- Remote VPS authentication/read/write against a live gateway.
- Browser server-only shim appearance and network request in a running Hermes web dashboard.
- Real OpenRouter credentials or Jev response.
- Automatic context-engine settings write; use documented settings/manual setup unless a supported public writer is proven.

No minimum Desktop version should be advertised until the supported Desktop release is tested. Server compatibility and Desktop compatibility are separate claims.
