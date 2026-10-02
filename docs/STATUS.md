# Implementation Status

**Current stage:** Phase 0 - Foundation / source-of-truth documentation.

## Phase status

| Phase | Name | Status | Gate |
|---|---|---|---|
| 0 | Foundation and provenance | In review | P0 |
| 1 | Hermes plugin skeleton | Not started | P1 |
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

None for Phase 1 after Phase 0 documentation is merged.

## Next implementation action

Start **Phase 1.1**: create the plugin manifest and minimal importable plugin skeleton on a dedicated feature branch.

## Status update rule

Every merged implementation PR must update:

1. this file;
2. the relevant checklist in `ROADMAP.md`;
3. ADR/PRD/architecture documents if implementation changed the contract.
