# Implementation Status

**Current stage:** Phase 2 - OpenRouter Jev client implemented; live provider smoke gate pending.

## Phase status

| Phase | Name | Status | Gate |
|---|---|---|---|
| 0 | Foundation and provenance | In review | P0 |
| 1 | Hermes plugin skeleton | Implementation complete (8/8); live gate pending | P1 |
| 2 | OpenRouter Jev client | Implementation complete (10/10); live gate pending | P2 |
| 3 | Tool-family router | Not started | P3 |
| 4 | Off/Shadow/On middleware | Not started | P4 |
| 5 | Telegram/gateway and CLI controls | Not started | P5 |
| 6 | Telemetry and metrics store | Not started | P6 |
| 7 | Native Hermes dashboard | Not started | P7 |
| 8 | Controlled A/B benchmark | Not started | P8 |
| 9 | Hardening/packaging/migration | Not started | P9 |
| 10 | Public beta | Not started | P10 |

## Current accepted architecture

- Hermes-native plugin.
- OpenRouter Jev backend.
- Tool-family routing only for v1.
- Existing Hermes model/provider/auth untouched.
- off/shadow/on modes.
- one routing decision per fresh user turn.
- conservative `multi` and fail-open fallback.
- Telegram/gateway `/jev` controls.
- local SQLite performance metadata.
- native Hermes dashboard extension.
- controlled benchmark separated from observational data.

## Current blockers

The branch stack remains Phase 0 -> Phase 1 -> Phase 2. P1 still requires live Hermes Plugin Doctor/status validation. P2 still requires one explicit live `python -m jevperf.smoke` call against OpenRouter. Neither live gate is faked by CI.

## Next implementation action

Complete the pending live P1/P2 gates on a supported Hermes/OpenRouter installation. After those gates pass, start **Phase 3.1**: define the 10-family routing criteria and deterministic routing fixtures.

## Status update rule

Every merged implementation PR must update:

1. this file;
2. the relevant checklist in `ROADMAP.md`;
3. ADR/PRD/architecture documents if implementation changed the contract.
