# Implementation Status

**Current stage:** Phase 9 hardening plus the experimental recoverable-compaction extension are implemented and verified against Hermes 0.21.5 source/runtime; live lifecycle/provider/session gates remain pending.

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
| 7 | Native Hermes dashboard | Implementation complete (13/13); live dashboard gate pending | P7 |
| 8 | Controlled A/B benchmark | Implementation complete (8/8); synthetic/reproducibility gate passed | P8 |
| 9 | Hardening/packaging/migration | Implementation complete (10/10); live install/disable/remove gate pending | P9 |
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
- experimental native `ContextEngine` compaction with private archive recovery and bounded Jev previews.
- explicit `none_of_these` routing choice and decision-opportunity audit.

## Current blockers

The branch stack remains Phase 0 -> Phase 1 -> Phase 2 -> Phases 3/4 -> Phases 5/6 -> Phase 7 -> Phase 8 -> Phase 9. P1 still requires live Hermes Plugin Doctor/status validation. P2 requires one explicit live OpenRouter smoke call. P3 requires live semantic routing checks. P4 requires a live Hermes middleware pass. P5 requires a real gateway/Telegram toggle and restart-persistence check. P6 telemetry hooks will be verified during that live pass. P7 requires native dashboard discovery/API mount, authenticated UI load, and mode-toggle read-back on a real Hermes dashboard. P8 has a deterministic zero-network CI benchmark plus an explicit local read-only live harness; no real provider benchmark result is claimed or published until that harness is deliberately run. P9 now has native Hermes lifecycle documentation, compatibility checks, doctor diagnostics, migration/outage/recovery tests, an enforced public-repository scan, and a batched live release checker; clean install/disable/re-enable/remove still requires actually running that checker on a real supported Hermes environment. None of the live gates are faked by CI.

## Next implementation action

Complete the pending live P1-P9 gates on a supported Hermes/OpenRouter installation, including native install, disable/re-enable, dashboard load, optional controlled benchmark, and clean removal. After those real gates pass, proceed to **Phase 10 public beta**.

## Status update rule

Every merged implementation PR must update:

1. this file;
2. the relevant checklist in `ROADMAP.md`;
3. ADR/PRD/architecture documents if implementation changed the contract.
