# Install, update, and remove Jev Performance

Pick the install that matches where Hermes runs. The backend component belongs on the machine running Hermes. The optional native dashboard belongs on the computer running Hermes Desktop.

- [Server only (VPS or local backend)](INSTALL_SERVER.md)
- [Desktop dashboard connected to a VPS](INSTALL_DESKTOP_WITH_VPS.md)
- [Both components on one local computer](INSTALL_LOCAL.md)

## First setup

New installs start with routing and recoverable compaction **OFF**. Confirm the target machine/profile in Hermes' installer. Run `/jev doctor` on that backend when installation finishes. Add the Jev/OpenRouter credential through Hermes' secure settings on the backend that will call Jev; do not put secrets into chat or the dashboard. Shadow sends requests and may incur provider charges, even though it leaves the tool choices unchanged.

Compaction needs a separate Hermes profile setting: select `hermes-jev-performance` as `context.engine`, restart the agent, and check `/jev compaction status`. Begin in Shadow.

## Optional command-line controls

These are for people comfortable with a terminal. Beginners can use Hermes Desktop or ask Hermes to install the server component in normal language.

```sh
hermes plugins install aiverse-filmmakers/hermes-jev-performance/agent --enable
hermes plugins doctor hermes-jev-performance --ci
hermes jev doctor
```

For a local backend and its Desktop app, install the root combined package instead:

```sh
hermes plugins install aiverse-filmmakers/hermes-jev-performance --enable
```

To update or remove the backend component, use Hermes' Plugins screen or run:

```sh
hermes plugins update hermes-jev-performance
hermes plugins disable hermes-jev-performance
hermes plugins remove hermes-jev-performance
```

The Desktop dashboard is updated or removed through its own Hermes Desktop plugin controls. Removing that local dashboard does not remove the server plugin from a VPS. Removing the server plugin may leave its metrics and recoverable archive data in Hermes profile storage; delete that data separately only if you intentionally want to discard it.

## Existing installation

If you installed the earlier combined package on a VPS, install the Server only source at `aiverse-filmmakers/hermes-jev-performance/agent` through Hermes' plugin installer. Keep the same plugin name and profile. Check `/jev status` and `/jev doctor` afterward. The plugin stores metrics and archives in profile data, separate from the source folder; the upgrade should retain those files. If Hermes reports a source conflict, follow its displayed update/reinstall steps and verify data remains before removing any old directory manually.

See [Troubleshooting](TROUBLESHOOTING.md) for connection, install, and setup issues.
