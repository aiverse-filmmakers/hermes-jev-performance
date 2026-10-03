# Troubleshooting

## I cannot find the install button

Open the official install link for the component you need. If a Desktop link does nothing, follow the no-terminal [manual Desktop install steps](INSTALL_DESKTOP_WITH_VPS.md#if-the-install-link-does-not-open). They use **Settings → Plugins → Open plugins folder** and **Rescan**. Put only the Desktop `plugin.js` file in that folder; do not put the Python agent package there.

## The Desktop panel is installed but says the backend is missing

Install the Agent/Server component on the selected backend and profile. If your chats run on a VPS, the Server component goes to the VPS; the Desktop panel stays on your computer.

## It shows the wrong connection or no data

Select the intended connection and profile in Hermes Desktop. Check that the server plugin is enabled there. The panel shows the active connection/profile it is scoped to; it does not read files from another gateway.

## Jev decisions do not change

OFF makes no Jev requests. Shadow sends requests but leaves the existing tool choices unchanged. ON applies only decisions that pass the configured confidence rules; uncertain decisions fall back to Hermes. Check `/jev status` and `/jev doctor` on the backend.

## Compaction controls stay disabled

Recoverable compaction requires the server component and the Hermes setting `context.engine: hermes-jev-performance`. Select that engine in the same profile, restart the agent, then check `/jev compaction status`. Begin in Shadow mode.

## Credential warning

The credential belongs to the backend that makes Jev requests. Add it through that Hermes instance's secure credential/environment setup. Never paste the key into chat or the Desktop panel.

## Installer or compatibility errors

Read the component detection and security message in Hermes' confirmation screen. Keep the installer scanner enabled. If the plugin requires a newer Hermes version, update Hermes or use a supported release; do not use an unreviewed force option as a fix.
