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

3. Hermes should show a Desktop component install. Confirm that the agent component is not selected and the install target is the local Desktop app.
4. Approve the normal install prompt and enable Jev Performance in **Plugins** if it is not already enabled.
5. Open **Jev Performance** in the app. Check that it displays the VPS connection/profile and reports the server plugin version.

Use the [official source folder](https://github.com/aiverse-filmmakers/hermes-jev-performance/tree/main/desktop) if Hermes asks for a Git source. The Desktop install dialog and link behavior should be checked against the installed Hermes Desktop version before relying on them for a community rollout.

The panel uses Hermes Desktop's authenticated connection. Do not copy a gateway token into the plugin. Jev credentials stay in the backend's secure credential settings.

## If the panel says the backend is missing

Install the [Server only component](hermes://plugin/install?repo=aiverse-filmmakers/hermes-jev-performance/agent&enable=1) with the correct VPS selected, then return to the panel and refresh.

If it reports a connection or profile error, confirm the VPS is reachable and the correct profile is selected. A dashboard installed on this computer does not install its Python agent code on the VPS.

If the link does not open an install dialog, use **Plugins → Install from Git** in a Hermes Desktop version that supports plugin installation links and enter `aiverse-filmmakers/hermes-jev-performance/desktop`. Exact menu names and Desktop compatibility must be verified against the release being used.
