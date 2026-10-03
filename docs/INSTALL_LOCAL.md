# Install both components when Hermes runs on this computer

Use this when the Hermes backend and Hermes Desktop are both on the same computer.

1. In Hermes Desktop, select the **Local** connection and the profile you intend to use.
2. Open the [Install Jev Performance for local Hermes](hermes://plugin/install?repo=aiverse-filmmakers/hermes-jev-performance&enable=1) link.
3. Check that the dialog detects both **Agent** and **Desktop**. Confirm those two components and the local profile.
4. Approve Hermes' normal installer/security and dependency prompts.
5. Enable the components if Hermes asks, then open **Jev Performance** and confirm it says Local and the chosen profile.

The first installation leaves routing and compaction OFF. Use the setup checklist to configure the Jev credential securely on this computer. Shadow makes Jev provider requests and may incur charges. Compaction additionally requires selecting the plugin as the Hermes `context.engine` and restarting the agent.

If Hermes cannot open the combined install link, go to the [official repository](https://github.com/aiverse-filmmakers/hermes-jev-performance) and follow its Install both on this computer guide. Use a Hermes Desktop version that supports plugin installation from Git.

To switch to a VPS later, install the Server only component on that VPS and keep the Desktop component on this computer. The dashboard follows the connection selected in Hermes Desktop.

If the app does not detect both components, stop and check that the repository's `main` release contains `plugin.yaml`, `__init__.py`, and `desktop/plugin.js`; do not install the repository folder into the Desktop-only plugins directory by hand.
