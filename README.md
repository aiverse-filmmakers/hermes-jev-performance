# Jev Performance for Hermes

**Version 0.1.0-alpha.10 — for client evaluation.** Routing review fixes and offline Hermes contracts are checked. Live Desktop/VPS installation, appearance and routing quality still need verification before production adoption. Start with the [client handoff](docs/CLIENT_HANDOFF.md) and [current status](docs/STATUS.md).

**Install Jev where Hermes runs. Add the visual dashboard only on the computer where you use Hermes Desktop.** The same official GitHub repository provides three setups:

| Your setup | What to install |
|---|---|
| Hermes runs on a VPS | [Install Server only](docs/INSTALL_SERVER.md) on the VPS. It contains the routing and compaction features, commands, and a small data API. It does not include the visual dashboard files. |
| Hermes runs on a VPS and you want a dashboard | Install [Server only on the VPS](docs/INSTALL_SERVER.md), then [Desktop dashboard on your computer](docs/INSTALL_DESKTOP_WITH_VPS.md). Hermes Desktop uses the VPS connection you already have. |
| Hermes and Hermes Desktop run on your computer | [Install both together](docs/INSTALL_LOCAL.md). |

You can ask Hermes to do the server setup in ordinary language. For example, paste this into a chat connected to the VPS you intend to change:

> Install and enable the Server only component of Hermes Jev Performance from `aiverse-filmmakers/hermes-jev-performance/agent` on the backend and profile serving this chat. Tell me which machine and profile you will change, use Hermes' normal installer and security checks, and leave routing and compaction OFF. When finished, check that it installed correctly and explain any remaining setup in beginner-friendly language. Never ask me to paste a secret into chat.

Or use the one-click [Server only install link](hermes://plugin/install?repo=aiverse-filmmakers/hermes-jev-performance/agent&enable=1) from Hermes Desktop, then confirm the target backend and profile in Hermes' dialog.

## What Jev does

Jev can help Hermes choose relevant tool families and can optionally compact older tool outputs while keeping exact copies recoverable. Hermes continues to use your existing model, conversations, and gateway. New installations start with routing **OFF** and compaction **OFF**. **Shadow** sends Jev requests without changing tool choices and may incur provider charges.

## Getting started safely

1. Install the component for your setup using one of the guides above.
2. Run `/jev doctor` in a chat connected to the backend where the Server component was installed.
3. Add the Jev/OpenRouter credential using that backend's secure credential settings. Never paste it into chat or the dashboard.
4. Choose Shadow only when you are ready for provider requests and possible charges. Review the results before choosing On.
5. Keep compaction OFF during routing evaluation. Experimental compaction requires native engine selection and a separate external-data opt-in; see [review fixes and remaining gates](docs/REVIEW_FIXES.md). Compaction Shadow can send redacted history, memory excerpts and tool previews to OpenRouter, unlike routing's latest-user-only state.

## Downloadable packages

Use the [0.1.0-alpha.10 release](https://github.com/aiverse-filmmakers/hermes-jev-performance/releases/tag/v0.1.0-alpha.10), which includes the [routing/privacy corrections](docs/REVIEW_FIXES.md):

- [Server only for your VPS/backend](https://github.com/aiverse-filmmakers/hermes-jev-performance/releases/download/v0.1.0-alpha.10/hermes-jev-performance-server-only-0.1.0-alpha.10.zip)
- [Desktop dashboard for your computer](https://github.com/aiverse-filmmakers/hermes-jev-performance/releases/download/v0.1.0-alpha.10/hermes-jev-performance-desktop-dashboard-0.1.0-alpha.10.zip)
- [Both components for a local computer](https://github.com/aiverse-filmmakers/hermes-jev-performance/releases/download/v0.1.0-alpha.10/hermes-jev-performance-combined-local-0.1.0-alpha.10.zip)

Each ZIP contains one `hermes-jev-performance` folder, its instructions, and license. The release includes file inventories and SHA-256 checksums. Start with the guide for your setup; the native install links above let Hermes download the correct component directly.

Native install links follow the repository's current source. For a repeatable client evaluation, use the versioned packages or the pinned CLI command in the [client handoff](docs/CLIENT_HANDOFF.md). Previous alpha.9 packages predate these fixes; use alpha.10 for new evaluations. See the [changelog](CHANGELOG.md).

## Help and compatibility

- [Server only setup](docs/INSTALL_SERVER.md)
- [Desktop dashboard for a VPS](docs/INSTALL_DESKTOP_WITH_VPS.md)
- [Both components on a local computer](docs/INSTALL_LOCAL.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Compatibility](docs/COMPATIBILITY.md)
- [Current verification status](docs/STATUS.md)
- [Security and privacy](docs/SECURITY.md)

This is an independent community project, not an official Hermes or OpenRouter product. See [LICENSE](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md).
