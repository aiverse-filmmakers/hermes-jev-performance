# Implementation and verification status

**Package split and code checks are implemented. This is not yet a production-verified release.** Python unit tests, JavaScript syntax checks, public repository scan, and Hermes' plugin doctor have passed locally. The Hermes doctor was run against isolated temporary profiles for both the server-only folder and the combined repository package.

## What is available in this repository

- **Server only:** `agent/`, for the selected Hermes backend or VPS. It includes routing, compaction, commands, metrics API, and only a tiny hidden browser-loader shim. New installs start with routing and compaction OFF.
- **Desktop dashboard:** `desktop/`, a native Hermes Desktop panel that uses the selected authenticated connection and profile.
- **Combined local install:** the repository root, for Hermes and Hermes Desktop on the same computer.

## Verified so far

- Python tests: 228 passing on the current local runtime.
- Hermes plugin doctor: server-only and combined source packages load and register against isolated temporary profiles.
- JavaScript syntax: native Desktop source, legacy web dashboard bundle, and server shim parse successfully.
- Repository diff whitespace check passes.
- Version fields match across the combined and server manifests and dashboard manifests.
- The server dashboard shim is tested as a hidden, null-rendering registration. The Server only ZIP is 73,155 bytes; Desktop only is 4,309 bytes; combined local is 93,850 bytes. Each has a SHA-256 checksum and file inventory.

## Still needs a real app or service

- Hermes Desktop must install and visually render the panel; light/dark appearance, narrow-window layout, and keyboard interaction need an app-level check.
- A real Desktop session must verify the selected VPS connection, authenticated status reads, and scoped mode changes.
- The three Hermes install dialogs/links and component detection must be checked in the supported Desktop release.
- A real Hermes lifecycle must check upgrade, disable, re-enable, removal, and persistence. Do not run it against a member's everyday profile as a substitute for an isolated install.
- A live Jev provider request has not been run; it may incur charges and requires an intentionally configured credential.
- Release ZIPs have been built and inspected locally. A tagged downloadable GitHub release waits for the real Desktop install/render and remote-backend checks.

Until those items pass, describe the repository as an implementation/test candidate, not as production-ready or a stable release. Use the instructions in the [README](../README.md) and report any mismatch in the install dialog.
