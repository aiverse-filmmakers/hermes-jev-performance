# Architecture Decision Records

This file is the compact ADR index. Decisions may later be split into individual `docs/adr/NNNN-*.md` files when they need longer rationale.

## ADR-001 - Hermes-native plugin, not provider proxy

**Status:** Accepted

Use Hermes public plugin/middleware/dashboard APIs. Do not route Hermes' provider traffic through the `jev-gateway` proxy architecture in v1.

**Why:** preserves existing provider auth, reduces moving parts, aligns with Hermes extension model, and isolates failure.

## ADR-002 - Tool routing only in v1

**Status:** Accepted

Jev chooses tool families in v1. It does not change the primary model/provider.

**Why:** the primary product question is whether narrower tool exposure improves Hermes performance. Mixing model switching into the experiment would confound measurement and alter user expectations.

## ADR-003 - OpenRouter first

**Status:** Accepted

OpenRouter Decisions API is the v1 Jev provider. Provider abstraction remains narrow enough to permit future adapters.

**Why:** existing upstream implementation exists, the endpoint exposes the required Jev contract, and it keeps the first implementation focused.

## ADR-004 - Off / Shadow / On

**Status:** Accepted

Three persistent modes are mandatory.

**Why:** OFF creates a real baseline, SHADOW validates Jev decisions without behavioral risk, ON applies accepted routes.

## ADR-005 - Fail open for routing

**Status:** Accepted

Any Jev/routing failure returns the original Hermes request unchanged.

**Why:** Jev is an optimization, not a dependency required for Hermes correctness.

## ADR-006 - `multi` is first-class

**Status:** Accepted

Mixed-tool requests are explicitly classifiable as `multi` and remain unrestricted.

**Why:** a single-family router can otherwise break valid multi-step workflows.

## ADR-007 - SQLite local telemetry

**Status:** Accepted

Use local SQLite for v1 metrics.

**Why:** standard library, transactional, queryable, compact, no hosted dependency.

## ADR-008 - No content telemetry

**Status:** Accepted

Do not persist prompt/tool/file/memory content.

**Why:** performance questions can be answered from metadata and content storage creates unnecessary privacy/security risk.

## ADR-009 - Native Hermes dashboard extension

**Status:** Accepted

Ship dashboard assets inside the same Hermes plugin directory using Hermes' supported dashboard plugin structure and backend API namespace.

**Why:** one installation, one auth model, no extra public server.

## ADR-010 - Telegram uses standard Hermes slash command

**Status:** Accepted

`/jev` is implemented through Hermes command registration rather than a Telegram-specific bot fork.

**Why:** gateway portability and less maintenance.

## ADR-011 - First install defaults to Shadow

**Status:** Proposed

Recommended first-run mode is `shadow`, not `on`.

**Why:** lets users observe decisions before enabling behavioral changes. Final default should be confirmed in Phase 1.

## ADR-012 - Controlled benchmark separated from organic analytics

**Status:** Accepted

Controlled A/B runs are stored/tagged separately from ordinary usage.

**Why:** unmatched organic requests cannot support a causal speed claim.
