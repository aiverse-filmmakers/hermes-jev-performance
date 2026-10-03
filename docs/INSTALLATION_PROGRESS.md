# Installation split implementation progress

This file records implementation evidence and verification gaps for the three Hermes installation choices.

## T0 — Hermes host contracts

- Hermes reference source: a local Hermes Agent checkout at revision `4e7403130ee278bd99c450fcd9f73c6b32135c95` (local development source; do not encode local paths in public instructions).
- Installed runtime reports Hermes Agent `v0.21.5+5279.g4e74031`, dated `2026.9.24`; Python `3.14.7`.
- Current plugin repository starts at commit `47b61fa6592b4657858f4d3807e14f21d6b78174`.
- Agent installer resolves a Git source subdirectory, reads that subdirectory's `plugin.yaml`, and names the installed package from its manifest. `agent/` can therefore be a server-only install root while retaining plugin ID `hermes-jev-performance`.
- Desktop installer finds `desktop/plugin.js`; for a `desktop` source subdirectory it derives the stable plugin folder from the repository name. `hermes-jev-performance` is the expected ID/folder.
- Combined-package reconciliation copies `<agent package>/desktop/plugin.js` to the app-level Desktop plugin root. Remote installs cannot use that filesystem copy; Hermes' Desktop install dialog clones the Desktop subdirectory locally.
- The Desktop SDK provides `ctx.rest` to the active gateway's authenticated `/api/plugins/<id>` namespace. It can work with a remote backend; plugin code does not need gateway token access.
- The browser dashboard API discovery reads `dashboard/manifest.json` from the enabled agent package and mounts its `plugin_api.py`. Its manifest builder defaults `entry` to `dist/index.js`, and the browser loader injects that script unconditionally. A missing entry would create a broken browser plugin load.
- The web registry permits a hidden tab and provides `window.__HERMES_PLUGINS__.register(name, Component)`. A tiny null-rendering registration shim is the current candidate for agent-only server packaging, pending package/browser tests. It must create no visible tab/slot and is not the native Desktop UI.
- Hermes plugin loading namespaces package code under `hermes_plugins`; package-internal imports must be relative. Moving code beneath `agent/` must never introduce absolute `import agent`.
- Official contracts consulted: [Desktop Plugin SDK](https://hermes-agent.nousresearch.com/docs/developer-guide/desktop-plugin-sdk), [Plugin installation and subdirectory installs](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins).
- Not verified yet: actual branded Hermes Desktop install dialog, exact remote API auth behavior in a running Desktop session, subdirectory installer live receipt, API-only browser shim execution, or a real OpenRouter request.

## Checkpoints

| Task | Status | Evidence / next action |
|---|---|---|
| T0 host contracts | Source-verified; live app pending | Hermes source inspection confirms subdirectory and API contracts. The hidden entry is covered by package/visibility tests. Desktop UI and real install dialog remain unverified. |
| T1 Python package split | Implemented; passing | Canonical Python package is under `agent/jevperf`; root combined package delegates to it. Package paths resolve in independent and combined installs. |
| T2 API contract | Implemented; passing | Health endpoint reports version/schema, modes, setup state, and credential presence only; profile-scope and service tests pass. |
| T3 native Desktop panel | Implemented; static checks pass | Native plugin uses authenticated `ctx.rest`, displays selected connection/profile, scopes requests on changes, and polls with cleanup. Real app rendering/accessibility remain pending. |
| T4 release artifacts | Implemented; package checks pass | `scripts/build_release.py` creates three allowlisted ZIPs, file inventories, SHA-256 checksums, and a versioned release manifest. ZIPs: Server only 73,155 bytes; Desktop 4,309 bytes; combined local 93,850 bytes. Hermes doctor passes on extracted Server only and combined ZIPs in isolated temp profiles. |
| T5 lifecycle and migration | Implemented; automated coverage | Existing mode state is preserved; new installs default OFF. Isolated live upgrade/disable/re-enable/remove has not been run. |
| T6 beginner guides | Implemented | README leads with three choices, a plain-language install request, setup, and troubleshooting. Install dialogs still need live verification. |
| T7 CI and full checks | Local checks pass; CI pending | 228 unit tests, Python compile, three JavaScript parse checks, repository scan, diff check, release ZIP build/inventory checks pass locally. CI now builds packages too. Extracted server and combined ZIPs pass Hermes plugin doctor. |
| T8 publish | Source pushed to official `main`; downloadable release pending | Commit `7498c68` was pushed to `aiverse-filmmakers/hermes-jev-performance` on 2026-10-03. No stable tag was created. The Hermes Desktop visual/remote checks are still open; GitHub API/host lookup was also unavailable from this session when checking release state. |
