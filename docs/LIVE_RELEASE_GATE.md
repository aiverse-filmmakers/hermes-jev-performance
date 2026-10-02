# Live P1-P9 Release Gate

This is the final real-environment gate before Phase 10 public beta.

The repository includes `scripts/live_release_gate.py` so the remaining checks can be run as one batch instead of manually one by one.

## Safety model

By default the script only performs read-only checks against the active Hermes profile.

Clean install, disable, re-enable, mode-cycle and removal checks run inside a temporary isolated `HERMES_HOME`, not the user's live Telegram profile.

Paid OpenRouter calls and real active-profile Hermes turns require explicit flags.

Raw command output is not stored in the report.

## 1. Safe read-only batch

From the repository checkout:

```bash
python3 scripts/live_release_gate.py
```

This checks:

- Hermes executable/version;
- native Hermes plugin doctor;
- `hermes jev doctor --json`;
- Jev CLI status;
- controlled benchmark preview only.

Telegram and dashboard UI remain marked MANUAL because a headless local subprocess cannot honestly prove those user-facing surfaces.

## 2. Isolated clean lifecycle batch

Use the exact full 40-character commit being evaluated:

```bash
python3 scripts/live_release_gate.py --lifecycle --ref <FULL_COMMIT_SHA>
```

This creates a temporary `HERMES_HOME` and runs:

- clean plugin install from GitHub;
- native plugin doctor;
- Jev CLI load;
- disable;
- re-enable;
- OFF / SHADOW / ON / SHADOW mode cycle;
- plugin removal;
- post-removal absence check.

The temporary profile is discarded afterward. The active Telegram profile is not changed.

## 3. Add one real Jev provider call

```bash
python3 scripts/live_release_gate.py --lifecycle --ref <FULL_COMMIT_SHA> --live-jev
```

This adds the explicit OpenRouter Jev smoke test and may incur a small provider charge.

## 4. Add real active Hermes turns

Only run this when it is acceptable to briefly cycle the active profile through OFF, SHADOW and ON:

```bash
python3 scripts/live_release_gate.py --lifecycle --ref <FULL_COMMIT_SHA> --live-jev --active-agent
```

The script records the original Jev mode first and restores it in a `finally` path even if an agent smoke turn fails.

The three active turns are deliberately simple:

- OFF: no-tool explanation;
- SHADOW: system/RAM request;
- ON: public-web request.

## 5. Machine-readable output

Add:

```bash
--json
```

The report includes only check name, PASS/FAIL/MANUAL state and safe detail text.

It excludes raw subprocess output, prompts, credentials and tool payloads.

## Two remaining manual confirmations

After the automated batch passes:

1. In the real Telegram chat, send `/jev status` and `/jev doctor`.
2. Open the Hermes dashboard and verify the Jev Performance tab loads and a mode change reads back correctly.

Those two confirmations close the gateway and dashboard portions of the live gate.

## Release rule

Do not tag the public beta merely because CI is green.

P9 is considered live-passed only after the isolated lifecycle batch, explicit provider/agent checks where applicable, Telegram confirmation and dashboard confirmation have actually been completed on a supported Hermes installation.
