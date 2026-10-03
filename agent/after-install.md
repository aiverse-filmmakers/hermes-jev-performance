# Server component installed

New installations start with routing and compaction **OFF**. This server package includes no visual dashboard bundle. A tiny hidden browser-loader shim exists only so Hermes can mount the authenticated plugin API used by the native Desktop panel.

Check the selected Hermes backend/profile:

```text
/jev status
/jev doctor
```

Add the Jev/OpenRouter credential through that backend's secure secret settings. Never paste it into chat. Choose `/jev shadow` only when you are ready for provider requests and possible charges. Shadow leaves routing unchanged while observing decisions.

Compaction remains off until the Hermes profile selects `context.engine: hermes-jev-performance` and the agent restarts. Then inspect `/jev compaction status`, use `/jev compaction shadow`, and enable On only after reviewing its behavior.

The visual Jev Performance panel is installed separately on the computer running Hermes Desktop. When Hermes runs on a VPS, install this component on that VPS and the Desktop component locally.
