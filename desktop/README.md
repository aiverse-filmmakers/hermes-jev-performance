# Jev Performance for Hermes Desktop

This is the local visual panel. Install it on the computer running Hermes Desktop. It reads data from the active Hermes connection, which may be your VPS; it does not need a local Hermes model.

Start with the [easy Desktop install guide](../docs/INSTALL_DESKTOP_WITH_VPS.md). It opens the official Desktop-only install link. If that link does not open, the guide shows how to add the single `plugin.js` file through Hermes Desktop's **Open plugins folder** and **Rescan** buttons.

If your chats use a VPS, keep that VPS connection selected. The panel runs on this computer and reads from the selected Hermes connection; it does not install files or a model on the VPS.

The matching **Server only** component must be installed and enabled on the backend/profile you want to manage. The panel displays the selected connection/profile. Use the official repository installation guide for the exact tested app version and troubleshooting steps.

The entry file uses Hermes' documented `@hermes/plugin-sdk` and React runtime exports. It is plain ESM and needs no build command.
