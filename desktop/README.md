# Jev Performance — Desktop dashboard

**Alpha test candidate.** The dashboard runs on the computer running Hermes Desktop. It reads the selected backend/profile, including an existing VPS connection. No local model is required. The matching Server component must be enabled on that backend.

Open the [Desktop install guide](https://github.com/aiverse-filmmakers/hermes-jev-performance/blob/main/docs/INSTALL_DESKTOP_WITH_VPS.md) for the official install link and setup checklist.

For a Desktop ZIP from the [alpha release](https://github.com/aiverse-filmmakers/hermes-jev-performance/releases/tag/v0.1.0-alpha.9): extract it, open Hermes Desktop **Settings → Plugins → Open plugins folder**, and move the extracted `hermes-jev-performance` folder there. `plugin.js` must sit directly inside it. Click **Rescan**, enable **Jev Performance**, then open its sidebar entry. Check the displayed connection/profile and Server version.

To update manually, replace `plugin.js` from the official source and click **Rescan**. To disable, turn off its Desktop switch. To remove, disable first, then delete only its `hermes-jev-performance` folder from the opened Desktop plugins folder and click **Rescan**. The Server component and its data have their own lifecycle.

Routing and compaction begin Off on new Server installs. Configure Jev credentials securely on the backend. Shadow and On send provider requests and can incur charges. Compaction requires selecting the Jev context engine and restarting the backend agent.

This plain ESM entry uses Hermes' public SDK; there is no user build step. See [compatibility and verification status](https://github.com/aiverse-filmmakers/hermes-jev-performance/blob/main/docs/STATUS.md) before treating it as a production release.
