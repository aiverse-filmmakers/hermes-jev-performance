# Jev Performance for Hermes

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
5. To use recoverable compaction, select `hermes-jev-performance` as the Hermes context engine in the same profile and restart its agent. Start compaction in Shadow.

## Downloadable packages

Separate Server only, Desktop dashboard, and combined ZIPs with file lists and checksums are built and verified during development. They are not published as a GitHub release yet. For now, use the official install links above; Hermes will show the source and its normal security prompt before installing.

## Help and compatibility

- [Server only setup](docs/INSTALL_SERVER.md)
- [Desktop dashboard for a VPS](docs/INSTALL_DESKTOP_WITH_VPS.md)
- [Both components on a local computer](docs/INSTALL_LOCAL.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [Compatibility](docs/COMPATIBILITY.md)
- [Current verification status](docs/STATUS.md)
- [Security and privacy](docs/SECURITY.md)

This is an independent community project, not an official Hermes or OpenRouter product. See [LICENSE](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md).
