# Install, Upgrade, Disable, Uninstall

Hermes Jev Performance uses Hermes' native plugin lifecycle. It does not require a custom installer and does not patch Hermes core files.

## Requirements

- Hermes Agent **0.21.5 or newer**.
- Python in the plugin's tested range: **3.11 through 3.14**.
- OpenRouter access for SHADOW/ON routing.
- Either:
  - `OPENROUTER_JEV_API_TOKEN` (preferred dedicated Jev credential), or
  - `OPENROUTER_API_KEY` (compatibility fallback).

OFF mode works without an OpenRouter credential.

## Recommended install

From the public GitHub repository:

```bash
hermes plugins install aiverse-filmmakers/hermes-jev-performance --enable
```

Hermes owns the clone, install metadata, activation and dependency admission.

For reproducible production installs, pin a full 40-character commit:

```bash
hermes plugins install aiverse-filmmakers/hermes-jev-performance --enable --ref <FULL_COMMIT_SHA>
```

A pinned plugin does not move during normal `hermes plugins update`. To move a pin, explicitly reinstall with `--force --ref <NEW_FULL_COMMIT_SHA>`.

## First checks

```bash
hermes plugins doctor hermes-jev-performance --ci
hermes jev status
hermes jev doctor
```

The plugin defaults to SHADOW on first install.

SHADOW calls Jev and records routing telemetry but does not change Hermes' eager tool list.

## Enable / disable

Enable:

```bash
hermes plugins enable hermes-jev-performance
```

Disable without deleting:

```bash
hermes plugins disable hermes-jev-performance
```

Disabling the plugin is the cleanest rollback. Hermes removes the plugin's runtime registrations through its own plugin lifecycle. No Hermes core rollback is required.

## Routing mode vs plugin disable

These are different controls:

```text
/jev off
```

keeps the plugin loaded but makes zero Jev routing calls. Local baseline telemetry may continue.

```bash
hermes plugins disable hermes-jev-performance
```

unloads/disables the plugin itself through Hermes.

## Upgrade

For an unpinned git install:

```bash
hermes plugins check-updates
hermes plugins update hermes-jev-performance
```

Then validate:

```bash
hermes plugins doctor hermes-jev-performance --ci
hermes jev doctor
```

Telemetry schema upgrades are forward migrations. Current schema is v4.

## Roll back

Preferred rollback:

1. Disable the plugin.
2. Install or re-pin the previously known-good full commit.
3. Run Hermes plugin doctor.
4. Re-enable only after validation.

Example:

```bash
hermes plugins disable hermes-jev-performance
hermes plugins install aiverse-filmmakers/hermes-jev-performance --force --ref <PREVIOUS_FULL_COMMIT_SHA>
hermes plugins doctor hermes-jev-performance --ci
hermes plugins enable hermes-jev-performance
```

Do not edit Hermes core files to roll this plugin back.

## Telemetry database recovery

If diagnostics report a corrupt local metrics database, routing still fails open independently of telemetry.

Inspect first:

```bash
hermes jev doctor
```

Before repairing, stop any other Hermes gateway, dashboard, agent, or automation process that uses the same profile. Repair renames the SQLite database and its WAL/SHM companions, so it must not race another writer.

Then run a one-off CLI repair:

```bash
hermes jev doctor --repair-db
hermes jev doctor
```

After doctor reports a healthy schema, restart the normal Hermes services for that profile.

Repair affects only this plugin's local telemetry database. It does not touch Hermes conversations, configuration, credentials or other plugin data. Repair is never automatic.

## Uninstall

Remove the plugin through Hermes:

```bash
heres plugins remove hermes-jev-performance
```

Hermes removes the installed plugin directory and its install metadata.

Local metrics under the profile's plugin-data directory may be retained independently for safety/history depending on Hermes/profile lifecycle behavior. If a user wants those metrics removed too, they should inspect the profile-local plugin-data location first and delete it deliberately rather than using a repository-provided destructive script.

## Verify normal Hermes operation after disable/uninstall

Run a normal Hermes request and:

```bash
hermes plugins list
```

The plugin must not be enabled after disable, and must not be present after remove.

No Hermes provider/model/auth rollback is needed because this project never replaces those paths.

## Live release gate

Before public beta, run the batched real-environment gate instead of testing lifecycle steps one-by-one:

```bash
python3 scripts/live_release_gate.py --lifecycle --ref <FULL_COMMIT_SHA>
```

Add `--live-jev` for one explicit OpenRouter Jev call and `--active-agent` only when real active-profile Hermes turns are acceptable.

The lifecycle portion uses a temporary isolated `HERMES_HOME`, so clean install, disable, re-enable and removal do not touch the live Telegram profile.

See [`LIVE_RELEASE_GATE.md`](LIVE_RELEASE_GATE.md) for the full procedure.
