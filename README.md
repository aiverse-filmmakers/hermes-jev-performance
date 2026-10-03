# Hermes Jev Performance

A Hermes-native Jev routing and observability plugin focused on one question:

> Does Jev make Hermes faster, cheaper, and more efficient without reducing capability?

This project combines proven ideas from several MIT-licensed Jev/Hermes projects into one Hermes-native plugin:

- [kerpopule/hermes-jev-skills](https://github.com/kerpopule/hermes-jev-skills) for Hermes plugin patterns, `/jev` controls, shadow mode, routing UX, and dashboard ideas.
- [vinilana/jev-gateway](https://github.com/vinilana/jev-gateway) for observability, latency/cost/token metrics, and Jev ON vs OFF baseline comparison concepts.
- [ourines/hermes-jev](https://github.com/ourines/hermes-jev) for Hermes-native Jev integration and OpenRouter Decisions API support.
- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) for the public Hermes plugin, middleware, slash-command, and dashboard extension APIs.

## Project status

**Active implementation. Routing and experimental recoverable compaction are implemented and tested against Hermes 0.21.5 source/runtime. Live OpenRouter and real-session gates remain pending. No stable release yet.**

The canonical implementation plan is in [`docs/SOURCE_OF_TRUTH.md`](docs/SOURCE_OF_TRUTH.md).

## v1 goals

- Hermes-native plugin. No proxy/gateway replacement.
- Preserve the user's existing Hermes model/provider authentication.
- Jev tool-family routing through OpenRouter.
- Conservative routing with fail-open behavior.
- `off`, `shadow`, and `on` modes.
- Telegram/gateway-compatible `/jev` controls.
- Local performance telemetry: Jev latency, confidence, cost, Hermes duration, tool calls, LLM calls, and token usage when exposed by Hermes.
- Native Hermes dashboard tab.
- Honest Jev ON vs OFF comparison and a controlled benchmark mode.
- No prompt, tool argument, secret, or credential logging by default.
- Experimental Jev-guided recoverable tool-output compaction through Hermes' native ContextEngine API.

## Non-goals for v1

- Replacing Hermes' primary model.
- Replacing Hermes' provider connection.
- Acting as a generic OpenAI/Anthropic proxy.
- Automatically changing model/provider routing.
- Sending private telemetry to a hosted service.
- Claiming a performance improvement without measured evidence.

## Planned commands

```text
/jev
/jev status
/jev on
/jev off
/jev shadow
/jev notice on
/jev notice off
/jev stats
/jev doctor
/jev compaction status
/jev compaction shadow
/jev compaction on
/jev compaction off
```

Equivalent CLI controls are provided where Hermes' public plugin APIs support them.

Controlled benchmark CLI:

```text
hermes jev benchmark
hermes jev benchmark --live
hermes jev benchmark --live --export ./benchmark.json
```

The first command is preview-only. `--live` is explicitly required before any matched Hermes/OpenRouter benchmark turns run. The default workload fixtures are read-only and exclude public-web research. A live run still uses the configured Hermes model/provider, and ON samples also call OpenRouter Jev.

Diagnostics:

```text
hermes jev doctor
hermes jev doctor --json
```

Compaction is OFF by default. To activate it, set `context.engine: hermes-jev-performance` in the Hermes profile, restart Hermes, then use `/jev compaction shadow` first. The compactor archives exact old tool outputs in private profile storage and exposes `jev_recover` for paged recovery. Run the offline probe with `python3 scripts/benchmark_compaction.py`; add `--live` only when you intentionally want a paid synthetic Jev request.

## Routing families

The initial routing taxonomy is:

```text
github
apps
web
terminal
files
memory
skills
media
none
multi
none_of_these
```

`multi`, low-confidence decisions, unsupported conditions, and Jev failures must fall back to normal unrestricted Hermes behavior.

## Documentation

- [Source of truth](docs/SOURCE_OF_TRUTH.md)
- [Install, upgrade and uninstall](docs/INSTALL.md)
- [Compatibility matrix](docs/COMPATIBILITY.md)
- [Product requirements](docs/PRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Implementation roadmap](docs/ROADMAP.md)
- [Telemetry and benchmarking](docs/TELEMETRY.md)
- [Controlled benchmark](docs/BENCHMARK.md)
- [Testing strategy](docs/TESTING.md)
- [Jev decision audit](docs/JEV_DECISION_AUDIT.md)
- [Security and privacy](docs/SECURITY.md)
- [Upstream projects and provenance](docs/UPSTREAMS.md)
- [Architecture decisions](docs/DECISIONS.md)
- [Current implementation status](docs/STATUS.md)

## License

MIT. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

This is an independent community project and is not affiliated with or endorsed by Nous Research, TypeSafe, OpenRouter, or the upstream projects.
