# Third-party notices

This project is an independent community project. It is not affiliated with or endorsed by Nous Research, TypeSafe, OpenRouter, or the upstream projects listed below.

Substantial code copied or adapted from an upstream project must retain that project's MIT copyright notice in the relevant source file or distribution notice. Concept-only inspiration must still be documented in `docs/UPSTREAMS.md`.

## Hermes Jev Skills

- Repository: https://github.com/kerpopule/hermes-jev-skills
- License: MIT
- Copyright: Copyright (c) 2026 Steve Darlow
- Intended reuse: Hermes plugin patterns, `/jev` command UX, on/shadow/off modes, routing lifecycle patterns, dashboard concepts, and selected implementation details where appropriate.

## jev-gateway

- Repository: https://github.com/vinilana/jev-gateway
- License: MIT
- Copyright: Copyright (c) 2026 Vinicius Lana
- Intended reuse: performance telemetry concepts, request metrics, Jev latency/confidence/cost reporting, baseline mode, and dashboard comparison patterns. The proxy/gateway architecture is explicitly not adopted for v1.

## Hermes Jev

- Repository: https://github.com/ourines/hermes-jev
- License: MIT
- Copyright: Copyright (c) 2026 Ourines
- Intended reuse: Hermes-native plugin structure, OpenRouter Decisions API integration, safe provider/credential handling patterns, and fail-open decision behavior.

## Hermes Agent

- Repository: https://github.com/NousResearch/hermes-agent
- License: see upstream repository
- Intended dependency/API surface: public plugin APIs, `llm_request` middleware, slash commands, gateway compatibility, dashboard UI plugins, and dashboard backend plugin APIs.

## TypeSafe Jev

- Documentation: https://docs.typesafe.ai/
- Jev is TypeSafe's decision model. This project is a client/integration and does not claim ownership of the model or its trademarks.

## OpenRouter

- Website: https://openrouter.ai/
- The v1 provider path uses OpenRouter's Jev Decisions API. OpenRouter account terms and model availability remain external dependencies.
