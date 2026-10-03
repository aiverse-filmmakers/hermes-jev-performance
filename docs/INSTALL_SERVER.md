# Install the server component (VPS or local Hermes backend)

Use this when Jev should run where your Hermes agent runs. For most community members that is a VPS.

## Beginner setup through Hermes Desktop

1. Open Hermes Desktop and select the gateway and profile that should run Jev. If your conversations are on a VPS, keep that VPS selected.
2. Open this server-only install link on the computer running Hermes Desktop:

   [Install Jev Performance on the selected Hermes backend](hermes://plugin/install?repo=aiverse-filmmakers/hermes-jev-performance/agent&enable=1)

3. Hermes shows what it will install and where. Confirm the target is the intended gateway/profile and the component is **Agent**. The `agent/` source contains no Desktop panel or full web dashboard bundle.
4. Approve Hermes' normal installation and security prompts. Leave its scanner enabled.
5. When installation finishes, verify that Jev Performance is enabled for the selected backend/profile.
6. In a chat on that same backend, run `/jev doctor` and `/jev status`.

New installations start with Jev routing and compaction OFF. No Jev requests are made until you choose a mode. Add the Jev/OpenRouter credential through that Hermes backend's secure credential or environment settings; never paste a key into chat. Choosing Shadow sends Jev requests and may incur provider charges, while keeping current tool behavior unchanged.

The server source folder is available in the [official GitHub repository](https://github.com/aiverse-filmmakers/hermes-jev-performance/tree/main/agent). Hermes normally downloads and installs it for you. A separately downloadable, inspected Server only ZIP will be linked from the repository's Releases page once the package build and live installer checks pass.

To enable recoverable compaction, select `hermes-jev-performance` as the Hermes profile's `context.engine`, restart the relevant agent, and verify `/jev compaction status`. Start with `/jev compaction shadow` before choosing On.

## Ask Hermes in normal language

This may work if your Hermes agent has permission and a supported plugin-management tool. The Desktop link above is the reliable click-through path.

> Install the Server only component of `aiverse-filmmakers/hermes-jev-performance` on the Hermes backend and profile serving this chat. Before installing, tell me which machine and profile you will change. Use Hermes' normal installer and security review. Do not install Desktop or browser dashboard assets. Leave routing and compaction OFF initially. Afterward, verify the installation with the plugin doctor and tell me where the Jev credential and optional context-engine setup belong without asking me to put a secret in chat.

## Optional command line

Run this on the machine/profile that runs Hermes:

```sh
hermes plugins install aiverse-filmmakers/hermes-jev-performance/agent --enable
hermes plugins doctor hermes-jev-performance --ci
hermes jev doctor
```

To remove only the server plugin later, use Hermes' Plugins screen or run `hermes plugins remove hermes-jev-performance` on the same backend/profile. Its metrics and archive files are separate user data; remove them deliberately only if you intend to delete them.
