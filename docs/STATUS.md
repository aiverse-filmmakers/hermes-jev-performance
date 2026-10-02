# Implementation Status

**Current stage:** Phases 5 and 6 - gateway controls and local telemetry implemented; live Hermes/OpenRouter integration gates pending.

## Phase status

| Phase | Name | Status | Gate |
|---|---|---|---|
| 0 | Foundation and provenance | In review | P0 |
| 1 | Hermes plugin skeleton | Implementation complete (8/8); live gate pending | P1 |
| 2 | OpenRouter Jev client | Implementation complete (10/10); live gate pending | P2 |
| 3 | Tool-family router | Implementation complete (10/10); live semantic gate pending | P3 |
| 4 | Off/Shadow/On middleware | Implementation complete (10/10); live Hermes gate pending | P4 |
| 5 | Telegram/gateway and CLI controls | Implementation complete (10/10); live gateway gate pending | P5 |
| 6 | Telemetry and metrics store | Implementation complete (11/11); code gate passed | P6 |
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

The branch stack remains Phase 0 -> Phase 1 -> Phase 2 -> Phases 3/4 -> Phases 5/6. P1 still requires live Hermes Plugin Doctor/status validation. P2 requires one explicit live OpenRouter smoke call. P3 requires live semantic routing checks. P4 requires a live Hermes middleware pass. P5 requires a real gateway/Telegram toggle and restart-persistence check. Phase 6's metadata/privacy/migration code gate is green in CI, but its hooks will still be verified during the same live integration pass. None of these live gates are faked by CI.

## Next implementation action

Complete the pending live P1-P5 integration gates on a supported Hermes/OpenRouter installation. In parallel, the next implementation phase is **Phase 7**: build the native Hermes performance dashboard against the versioned local telemetry API/store.

## Status update rule

Every merged implementation PR must update:

1. this file;
2. the relevant checklist in `ROADMAP.md`;
3. ADR/PRD/architecture documents if implementation changed the contract.
