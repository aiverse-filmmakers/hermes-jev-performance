# Add the Desktop dashboard while Hermes stays on your VPS

This installs the visual Jev panel on your computer and keeps Jev's work and data on the Hermes backend you select. It does not start a local Hermes model or move chats off your VPS.

## What you need

- Hermes Desktop on your computer.
- A working connection to the Hermes VPS.
- The Jev Performance **Server only** component installed and enabled on the VPS/profile you want to manage.

## Install

1. In Hermes Desktop, keep or select your existing VPS connection.
2. Open this link on the computer running Hermes Desktop:

   [Install the Jev Performance Desktop dashboard on this computer](hermes://plugin/install?repo=aiverse-filmmakers/hermes-jev-performance/desktop)

3. Hermes should show a Desktop component install. Confirm that the Agent component is not selected and the install target is this computer's Hermes Desktop app.
4. Approve the normal install prompt and enable Jev Performance in **Plugins** if it is not already enabled.
5. Open **Jev Performance** in the app. Check that it displays the VPS connection/profile and reports the server plugin version.

The dashboard is a small file that runs inside Hermes Desktop. It uses the connection you already selected, including a VPS connection; there is no local model to install. The panel uses Hermes Desktop's authenticated connection. Do not copy a gateway token into the plugin. Jev credentials stay in the backend's secure credential settings.

## If the panel says the backend is missing

Install the [Server only component](hermes://plugin/install?repo=aiverse-filmmakers/hermes-jev-performance/agent&enable=1) with the correct VPS selected, then return to the panel and refresh.

If it reports a connection or profile error, confirm the VPS is reachable and the correct profile is selected. A dashboard installed on this computer does not install its Python agent code on the VPS.

### If the install link does not open

You can add the dashboard file using Finder; no terminal is needed:

1. Download the [official `plugin.js` file](https://raw.githubusercontent.com/aiverse-filmmakers/hermes-jev-performance/main/desktop/plugin.js).
2. In Hermes Desktop, open **Settings → Plugins**, then click **Open plugins folder**.
3. In the folder that opens, make a folder named `hermes-jev-performance`.
4. Move the downloaded `plugin.js` into that new folder. It should be directly inside it, like `hermes-jev-performance/plugin.js`.
5. Return to **Settings → Plugins**, click **Rescan**, and turn on **Jev Performance**.

To update this manual installation later, replace the `plugin.js` file with the latest one from the same official link and click **Rescan**. If the buttons in your Hermes Desktop look different, check the official [Hermes plugin instructions](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins) before proceeding.
