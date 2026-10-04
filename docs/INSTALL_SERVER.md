# Install the server component (VPS or local Hermes backend)

Use this when Jev should run where your Hermes agent runs. For most community members that is a VPS.

Agent 0.21.5 or newer is the declared minimum. Native loader/API tests run against the recorded [Hermes reference version](HOST_CONTRACTS.md); real VPS and Desktop installs remain pending in [verification status](STATUS.md).

## Beginner setup through Hermes Desktop

1. Open Hermes Desktop and select the gateway and profile that should run Jev. If your conversations are on a VPS, keep that VPS selected.
2. Open this server-only install link on the computer running Hermes Desktop:

   [Install Jev Performance on the selected Hermes backend](hermes://plugin/install?repo=aiverse-filmmakers/hermes-jev-performance/agent&enable=1)

3. Hermes shows what it will install and where. Confirm the target is the intended gateway/profile and the component is **Agent**. The `agent/` source contains no Desktop panel or full web dashboard bundle.
4. Approve Hermes' normal installation and security prompts. Leave its scanner enabled.
5. When installation finishes, verify that Jev Performance is enabled for the selected backend/profile.
6. In a chat on that same backend, run `/jev doctor` and `/jev status`.

New installations start with Jev routing and compaction OFF. No Jev requests are made until you choose a mode. Add the Jev/OpenRouter credential through that Hermes backend's secure credential or environment settings; never paste a key into chat. Choosing Shadow sends Jev requests and may incur provider charges, while keeping current tool behavior unchanged.

The server source folder is available in the [official GitHub repository](https://github.com/aiverse-filmmakers/hermes-jev-performance/tree/main/agent). Hermes normally downloads and installs it for you. For a repeatable evaluation, use the [alpha.10 Server ZIP](https://github.com/aiverse-filmmakers/hermes-jev-performance/releases/download/v0.1.0-alpha.10/hermes-jev-performance-server-only-0.1.0-alpha.10.zip) or the pinned installer command in the [client handoff](CLIENT_HANDOFF.md). Previous alpha.9 ZIPs predate the routing/privacy review fixes.

Keep compaction OFF during routing evaluation. It has a separate privacy boundary and external-data opt-in; see [review fixes](REVIEW_FIXES.md). Selecting its mode alone cannot authorize transmission. Evaluate only in an isolated profile after selecting the native engine, restarting it, and deliberately allowing paid history/memory/tool-preview transmission with `/jev compaction allow-external`.

## Ask Hermes in normal language

This may work if your Hermes agent has permission and a supported plugin-management tool. The Desktop link above uses Hermes' source-confirmed install flow; verify the machine/profile in its confirmation.

> Install the Server only component from `aiverse-filmmakers/hermes-jev-performance/agent` on the Hermes backend and profile serving this chat. Before installing, tell me which machine and profile you will change. Use Hermes' normal installer and security review. Do not install Desktop or browser dashboard assets. Leave routing and compaction OFF initially. Afterward, verify the installation with the plugin doctor and tell me where the Jev credential and optional context-engine setup belong without asking me to put a secret in chat.

## Optional command line

Run this on the machine/profile that runs Hermes:

```sh
hermes plugins install aiverse-filmmakers/hermes-jev-performance/agent --enable
hermes plugins doctor hermes-jev-performance --ci
hermes jev doctor
```

To remove only the server plugin later, use Hermes' Plugins screen or run `hermes plugins remove hermes-jev-performance` on the same backend/profile. Its metrics and archive files are separate user data; remove them deliberately only if you intend to delete them.

## Updates and removal in ordinary language

Ask Hermes: “Update hermes-jev-performance through your normal plugin updater on this backend/profile, keep following the Server only `/agent` source, preserve my settings and archives, and check the plugin doctor afterward.”

To stop it, disable its Agent plugin switch for that profile, or ask Hermes to disable it. To remove it, ask Hermes to use its normal plugin remover on the same backend/profile. These actions do not remove a separately installed Desktop dashboard. Read the [migration guide](INSTALL.md#existing-installation) before changing an older combined VPS installation.
