# Install both components when Hermes runs on this computer

Use this when the Hermes backend and Hermes Desktop are both on the same computer.

You need a working local Hermes backend (Agent 0.21.5 or newer) and a Desktop build with native plugin install links. Desktop 0.17 source contracts have been checked; actual app installation and appearance are still pending. See [verification status](STATUS.md).

1. In Hermes Desktop, select the **Local** connection and the profile you intend to use.
2. Open the [Install Jev Performance for local Hermes](hermes://plugin/install?repo=aiverse-filmmakers/hermes-jev-performance&enable=1) link.
3. Check that the dialog detects both **Agent** and **Desktop**. Confirm those two components and the local profile.
4. Approve Hermes' normal installer/security and dependency prompts.
5. Enable the components if Hermes asks, then open **Jev Performance** and confirm it says Local and the chosen profile.

The first installation leaves routing and compaction OFF. Use the setup checklist to configure the Jev credential securely on this computer. Shadow makes Jev provider requests and may incur charges. Compaction additionally requires selecting the plugin as the Hermes `context.engine` and restarting the agent.

If Hermes cannot open the combined install link, you can paste this into a chat served by your local Hermes:

> Install and enable the combined Hermes Jev Performance package from `aiverse-filmmakers/hermes-jev-performance` on this computer. First confirm this chat uses a local backend and tell me the profile. Use the normal Hermes installer and security checks, leave routing and compaction Off, and check `/jev doctor` afterward. If you cannot add the Desktop component locally, explain that step and link the official Desktop guide. Never ask me to put a secret into chat.

For manual Desktop setup, use the [Desktop guide](INSTALL_DESKTOP_WITH_VPS.md#if-the-install-link-does-not-open) with your Local connection selected. The optional [command-line instructions](INSTALL.md#optional-command-line-controls) cover installing and updating the backend; a CLI-only backend install does not prove the Desktop panel was enabled.

## Updates and removal

Ask Hermes: “Update hermes-jev-performance through your normal plugin updater on this local profile, preserve my settings and archives, and run the plugin doctor afterward.” For a manually added Desktop file, follow its [update steps](INSTALL_DESKTOP_WITH_VPS.md#updates-and-removal).

To disable the backend, use its Agent plugin switch for this profile. To disable the panel, use its Desktop plugin switch. Ask Hermes to remove the backend plugin through its normal remover if desired, and follow the Desktop guide to remove a manual panel. Settings, metrics, and recoverable archives are separate data; deleting them is a separate deliberate choice.

To switch to a VPS later, install the Server only component on that VPS and keep the Desktop component on this computer. The dashboard follows the connection selected in Hermes Desktop.

If the app does not detect both components, stop and check that the official repository contains `agent/plugin.yaml` and `desktop/plugin.js`. Do not put the combined repository folder into the Desktop-only plugins directory by hand.
