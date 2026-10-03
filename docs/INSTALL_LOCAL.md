# Install both components when Hermes runs on this computer

Use this when the Hermes backend and Hermes Desktop are both on the same computer.

1. In Hermes Desktop, select the **Local** connection and the profile you intend to use.
2. Open the [Install Jev Performance for local Hermes](hermes://plugin/install?repo=aiverse-filmmakers/hermes-jev-performance&enable=1) link.
3. Check that the dialog detects both **Agent** and **Desktop**. Confirm those two components and the local profile.
4. Approve Hermes' normal installer/security and dependency prompts.
5. Enable the components if Hermes asks, then open **Jev Performance** and confirm it says Local and the chosen profile.

The first installation leaves routing and compaction OFF. Use the setup checklist to configure the Jev credential securely on this computer. Shadow makes Jev provider requests and may incur charges. Compaction additionally requires selecting the plugin as the Hermes `context.engine` and restarting the agent.

If Hermes cannot open the combined install link, use Hermes' normal plugin installation instructions or ask Hermes to install the combined plugin from the official repository. This guide's terminal option is for people comfortable with command-line setup.

To switch to a VPS later, install the Server only component on that VPS and keep the Desktop component on this computer. The dashboard follows the connection selected in Hermes Desktop.

If the app does not detect both components, stop and check that the official repository contains `agent/plugin.yaml` and `desktop/plugin.js`. Do not put the combined repository folder into the Desktop-only plugins directory by hand.
