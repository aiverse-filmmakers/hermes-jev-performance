# Client handoff — 0.1.0-alpha.12

Jev Performance is an independent MIT-licensed Hermes plugin delivered as an alpha for evaluation. It adds optional tool-family routing and performance telemetry, plus experimental recoverable compaction. It uses `typesafe/jev-1.13` through OpenRouter by default. Routing accuracy and net time/token savings have not yet been demonstrated in live client workflows.

## Delivery

Use the [versioned alpha.12 release](https://github.com/aiverse-filmmakers/hermes-jev-performance/releases/tag/v0.1.0-alpha.12). It contains three component ZIPs, `release-manifest.json`, per-package SHA-256 checksums and file inventories. Verify the downloaded ZIP against its checksum before installation. The tag identifies the exact delivered source; native one-click links instead follow the repository's current source.

| Client setup | Package and instructions |
|---|---|
| Hermes backend on a VPS | Server only; [server guide](INSTALL_SERVER.md) |
| VPS backend with Hermes Desktop on a computer | Server only on the VPS and Desktop dashboard on the computer; [Desktop guide](INSTALL_DESKTOP_WITH_VPS.md) |
| Local Hermes backend and Desktop together | Combined local; [local guide](INSTALL_LOCAL.md) |

Hermes Agent `>=0.21.5` is the declared minimum. Python 3.11–3.14 are tested in CI. The optional panel requires a Hermes Desktop build with the public Plugin SDK. Read [compatibility](COMPATIBILITY.md): offline contracts do not establish compatibility with every client deployment.

For an installer-managed Server evaluation pinned to this release, run on the intended backend in an isolated Hermes profile:

```sh
hermes plugins install aiverse-filmmakers/hermes-jev-performance/agent --enable --ref v0.1.0-alpha.12
hermes plugins doctor hermes-jev-performance --ci
hermes jev doctor
hermes jev status
```

Use the repository root instead of `/agent` when installing the combined backend package. Verify the Desktop component separately through Hermes Desktop. Check that doctor reports version `0.1.0-alpha.12` and the intended profile before continuing.

## Evaluation

1. Start in an isolated profile with the old Jev router absent. Avoid running both routing middlewares together.
2. Verify the installed version, profile, doctor result and OFF status. Upgrades retain existing routing settings: explicitly choose OFF when preparing an evaluation profile.
3. Configure the OpenRouter credential through the backend's secure settings. Never paste a key into a chat or dashboard. Routing sends redacted latest-user text externally; redaction is a heuristic and does not identify all private information.
4. Deliberately choose routing Shadow when external requests and provider charges are acceptable. Shadow leaves tool choices unchanged. Exercise research, file, skill, memory, media and mixed workflows before considering On.
5. Enable optional Jev compaction using the [compaction guide](COMPACTION.md): select the native engine, restart, allow external data and choose Shadow or On. It can archive unique older outputs after complete redacted chunk assessment. Hermes' normal compression remains available as fallback. Both features start OFF to prevent automatic transmission/charges.
6. Verify the actual Desktop panel, remote connection/profile, process restart and install/update/remove behavior on the client's Hermes version before production adoption. Record the release tag and host version with the results.

## Evidence and limits

279 Python unit/package tests, 11 Desktop behavior tests, 5 native loader/API/migration tests and 14 native compaction tests passed with synthetic data and mocked provider responses. The native reference and commands are recorded in [TESTING.md](TESTING.md#second-hermes-audit-corrections).

No paid provider trial or production installation was performed for this release. Rendered Desktop QA and live VPS workflows remain outstanding. Compaction archives and the host database are separate commits; a crash can leave unpublished archives. Arbitrary noncontiguous carried rows also retain a host recall integration limitation. These are documented alpha limits, not completed production checks.

## Stop or remove

Run `/jev off` on the affected backend/profile to suspend Jev calls and routing restrictions. Run `/jev compaction deny-external` to revoke compaction transmission consent. To stop the plugin entirely, disable it through Hermes' plugin controls. If the Jev context engine was selected, restore the client's previous engine setting and restart the agent before removing the Server plugin.

Disable/remove the Desktop dashboard separately. Preserve metrics and archives when disabling or updating; deleting archive data discards exact recovery. Use the [install/update/remove guide](INSTALL.md) and [troubleshooting](TROUBLESHOOTING.md) for lifecycle steps.

When reporting an issue through the [repository issue tracker](https://github.com/aiverse-filmmakers/hermes-jev-performance/issues), include plugin/host versions, component, mode and a synthetic reproduction. Exclude credentials, private conversation text, tool outputs and archive contents.
