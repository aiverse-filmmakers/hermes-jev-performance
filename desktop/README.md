# Jev Performance for Hermes Desktop

This is the local visual panel. Install it on the computer running Hermes Desktop. It reads data from the active Hermes connection, which may be your VPS; it does not need a local Hermes model.

Use the Hermes Desktop **Install from Git** flow with the official repository's `desktop/` component, then enable **Jev Performance** under Plugins. If you opened a VPS chat, the confirmation dialog installs this Desktop component on this computer; it does not copy it to the VPS.

The matching **Server only** component must be installed and enabled on the backend/profile you want to manage. The panel displays the selected connection/profile. Use the official repository installation guide for the exact tested app version and troubleshooting steps.

The entry file uses Hermes' documented `@hermes/plugin-sdk` and React runtime exports. It is plain ESM and needs no build command.
