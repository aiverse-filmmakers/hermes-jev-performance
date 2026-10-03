# Jev Performance — Server only

This is the backend component for Hermes. Install it on the machine where the intended Hermes backend runs, including your VPS. It contains no visual dashboard bundle.

For beginner instructions, see [Install Server only](https://github.com/aiverse-filmmakers/hermes-jev-performance/blob/main/docs/INSTALL_SERVER.md). Select the right Hermes backend/profile, open this component's install link in Hermes Desktop, confirm the target shown by Hermes, and run `/jev doctor` after installation. You may also ask Hermes in plain language; the copyable request is on the [repository's main page](https://github.com/aiverse-filmmakers/hermes-jev-performance).

New installs leave routing and compaction **OFF**. Add the Jev credential through Hermes' secure settings on this backend; never paste it into chat. Shadow sends Jev requests and can incur charges.

The small hidden browser entry exists only because Hermes' backend dashboard loader expects an entry script when mounting the authenticated data API. It renders no page. The native visual dashboard is a separate install for the computer running Hermes Desktop.

See the [MIT license](https://github.com/aiverse-filmmakers/hermes-jev-performance/blob/main/LICENSE) and [third-party notices](https://github.com/aiverse-filmmakers/hermes-jev-performance/blob/main/THIRD_PARTY_NOTICES.md).
