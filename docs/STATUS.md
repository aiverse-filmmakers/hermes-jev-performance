# Implementation and verification status

**The corrected packages are an alpha test candidate. Production verification still requires the real Desktop/VPS checks below.** Official source: `aiverse-filmmakers/hermes-jev-performance`, branch `main`.

## Available components

- **Server only:** `agent/`, for the Hermes backend/VPS. Routing, compaction, commands, metrics API, and a 73-byte hidden browser-loader shim. No visual UI bundles, tests, or benchmark fixtures. New routing and compaction modes are the string `off`.
- **Desktop dashboard:** `desktop/`, a native panel using the active authenticated gateway/profile. No local model is required to view a VPS backend.
- **Combined local:** repository root, for a local Hermes backend and Desktop on the same computer. The legacy browser dashboard remains available in this combined distribution.

## Repository checks

- Python behavioral/package tests pass, including extracted package loading and deterministic ZIP checks.
- Desktop behavior tests exercise the delivered ESM file with an isolated SDK/hook harness. They cover REST/display scope, stale reads/read-back, write guards, overlapping refreshes, unload cleanup, empty states, and benchmark labels. These are not visual app tests.
- Native Hermes contracts verify YAML defaults, actual plugin loader migration/unload/reload with modes/metrics/archives/unrelated-plugin preservation, legacy settings, managed permissions, and real FastAPI authenticated API mounting/body validation.
- Native compaction contracts exercise the actual Hermes engine, resume/recovery, normal fallback, and session-store behavior with synthetic data and no network.
- Version/schema inputs, Python compilation, JavaScript syntax, public repository scan, document-link validation, and diff checks pass.
- Builds contain one installable `hermes-jev-performance` folder. Check each release's `release-manifest.json`, inventory, and SHA-256 files for exact sizes and checksums. Source timestamps and permissions do not alter the ZIP bytes.

For exact commands and test counts from the correction run, see [TESTING.md](TESTING.md#installation-split-correction-checks).

## Still needs a real app or service

- Branded Hermes Desktop install dialogs and actual panel discovery/rendering, including light/dark appearance, narrow layout, keyboard navigation, and unload behavior.
- Actual selected VPS connection/authentication and scoped read/write on a remote gateway.
- Native installer admission, source/provenance migration, Desktop reconciliation, update/remove, and real process restart. Offline module loading proves a narrower contract.
- A deliberately configured live Jev provider request, which may incur charges. No such request was run during the repository correction.
- A stable release remains gated on those checks. Any published alpha assets are test candidates and must say so.

Repository corrections and offline tests have not installed or enabled the plugin in the user's Hermes environments.
