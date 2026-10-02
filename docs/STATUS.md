# Implementation Status

**Current stage:** Phase 1 - Hermes plugin skeleton (stacked behind Phase 0 documentation PR).

## Phase status

| Phase | Name | Status | Gate |
|---|---|---|---|
| 0 | Foundation and provenance | In review | P0 |
| 1 | Hermes plugin skeleton | In progress (1/8) | P1 |
| 2 | OpenRouter Jev client | Not started | P2 |
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

Phase 0 documentation PR must merge before the Phase 1 implementation branch is merged. Phase 1 work may be prepared as a stacked branch in the meantime.

## Next implementation action

Start **Phase 1.2**: create the minimal no-op `register(ctx)` entry point. It must import/register cleanly and make no network calls.

## Status update rule

Every merged implementation PR must update:

1. this file;
2. the relevant checklist in `ROADMAP.md`;
3. ADR/PRD/architecture documents if implementation changed the contract.
